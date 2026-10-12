from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from statistics import mean, median
from typing import Any

from psycopg import Connection

from .azure_generation import (
    AzureGenerationConfig,
    GenerationPricing,
    request_structured_generation,
)
from .evidence_generation import (
    ANSWER_SCHEMA_VERSION,
    PROMPT_VERSION,
    REPORT_ANSWER_SCHEMA_VERSION,
    REPORT_PROMPT_VERSION,
    DetectorOutputInput,
    EvidenceChunkInput,
    EvidenceGenerationRequest,
    FaceGuardEvidenceAnswer,
    FaceGuardEvidenceReportAnswer,
    ObservedFactInput,
    prepare_generation_prompt,
    validate_generated_answer,
    validate_generated_report_answer,
)
from .retrieval import resolve_corpus_revision_id


class GenerationEvaluationError(RuntimeError):
    """Raised when generation cases or results are inconsistent."""


@dataclass(frozen=True, slots=True)
class UnsupportedTopicExpectation:
    topic: str
    terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SupportedBasisExpectation:
    observation_ids: tuple[str, ...]
    detector_ids: tuple[str, ...]
    citation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GenerationExpectations:
    allowed_overall_assessments: tuple[str, ...]
    required_citation_groups: tuple[tuple[str, ...], ...]
    required_unsupported_topics: tuple[UnsupportedTopicExpectation, ...]
    forbidden_supported_patterns: tuple[str, ...]
    minimum_verification_steps: int
    required_observed_fact_groups: tuple[tuple[str, ...], ...] = field(
        default_factory=tuple
    )
    required_supported_basis_groups: tuple[
        SupportedBasisExpectation, ...
    ] = field(default_factory=tuple)
    forbidden_supported_observation_ids: tuple[str, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True, slots=True)
class GenerationCase:
    case_id: str
    title: str
    request: EvidenceGenerationRequest
    expectations: GenerationExpectations


@dataclass(frozen=True, slots=True)
class GenerationCaseSet:
    evaluation_set_id: str
    corpus_sha256: str
    prompt_version: str
    answer_schema_version: str
    cases: tuple[GenerationCase, ...]
    file_sha256: str


@dataclass(frozen=True, slots=True)
class GenerationRuleScore:
    assessment_allowed: bool
    required_citations_present: bool
    unsupported_topics_present: bool
    supported_sections_safe: bool
    verification_steps_sufficient: bool
    observed_fact_references_present: bool
    supported_basis_present: bool
    supported_observations_separated: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.assessment_allowed,
                self.required_citations_present,
                self.unsupported_topics_present,
                self.supported_sections_safe,
                self.verification_steps_sufficient,
                self.observed_fact_references_present,
                self.supported_basis_present,
                self.supported_observations_separated,
            )
        )


@dataclass(frozen=True, slots=True)
class GenerationCaseResult:
    case: GenerationCase
    answer: FaceGuardEvidenceAnswer | FaceGuardEvidenceReportAnswer
    prompt_sha256: str
    input_sha256: str
    output_sha256: str
    response_model: str
    score: GenerationRuleScore
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    calculated_cost: Decimal


@dataclass(frozen=True, slots=True)
class GenerationEvaluation:
    case_set: GenerationCaseSet
    cases: tuple[GenerationCaseResult, ...]
    passed_cases: int
    total_input_tokens: int
    total_cached_input_tokens: int
    total_output_tokens: int
    total_cost: Decimal
    mean_latency_ms: float
    median_latency_ms: float


def _required_string(value: dict[str, Any], key: str, context: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise GenerationEvaluationError(
            f"{context}: {key} must be a non-empty string."
        )
    return item.strip()


def _required_string_list(
    value: dict[str, Any],
    key: str,
    context: str,
) -> tuple[str, ...]:
    items = value.get(key)
    if (
        not isinstance(items, list)
        or any(not isinstance(item, str) or not item.strip() for item in items)
    ):
        raise GenerationEvaluationError(
            f"{context}: {key} must be a string array."
        )
    return tuple(item.strip() for item in items)


def _load_chunk_rows(
    connection: Connection,
    *,
    corpus_revision_id: int,
    chunk_ids: set[str],
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            chunks.chunk_id,
            documents.source_id,
            chunks.source_title,
            chunks.heading_text,
            chunks.page_number,
            chunks.content
        FROM rag.evidence_chunks AS chunks
        JOIN rag.source_documents AS documents
          ON documents.source_document_id = chunks.source_document_id
        WHERE chunks.corpus_revision_id = %s
          AND chunks.chunk_id = ANY(%s)
        """,
        (corpus_revision_id, sorted(chunk_ids)),
    ).fetchall()
    chunks = {str(row["chunk_id"]): dict(row) for row in rows}
    missing = sorted(chunk_ids.difference(chunks))
    if missing:
        raise GenerationEvaluationError(
            "Generation evidence chunks are missing: " + ", ".join(missing)
        )
    return chunks


def load_generation_case_set(
    connection: Connection,
    *,
    path: Path,
) -> GenerationCaseSet:
    try:
        data = path.read_bytes()
        raw = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GenerationEvaluationError(
            f"Unable to read generation case set: {path}"
        ) from exc
    if not isinstance(raw, dict) or raw.get("schema_version") not in (1, 2):
        raise GenerationEvaluationError(
            "Unsupported generation case-set schema."
        )
    prompt_version = raw.get("prompt_version")
    answer_schema_version = raw.get("answer_schema_version")
    supported_versions = {
        (PROMPT_VERSION, ANSWER_SCHEMA_VERSION),
        (REPORT_PROMPT_VERSION, REPORT_ANSWER_SCHEMA_VERSION),
    }
    if (prompt_version, answer_schema_version) not in supported_versions:
        raise GenerationEvaluationError(
            "Generation case prompt and answer schema do not match code."
        )

    corpus_sha256 = _required_string(
        raw,
        "corpus_sha256",
        "generation set",
    )
    corpus_revision_id = resolve_corpus_revision_id(
        connection,
        corpus_sha256=corpus_sha256,
    )
    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise GenerationEvaluationError(
            "Generation case set must contain cases."
        )

    all_chunk_ids = {
        str(evidence["chunk_id"])
        for case in raw_cases
        for evidence in case["evidence"]
    }
    chunk_rows = _load_chunk_rows(
        connection,
        corpus_revision_id=corpus_revision_id,
        chunk_ids=all_chunk_ids,
    )

    cases: list[GenerationCase] = []
    seen_case_ids: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise GenerationEvaluationError(
                "Generation case must be an object."
            )
        case_id = _required_string(raw_case, "case_id", "generation case")
        if case_id in seen_case_ids:
            raise GenerationEvaluationError(
                f"Duplicate generation case ID: {case_id}"
            )
        seen_case_ids.add(case_id)

        raw_detector = raw_case.get("detector_output")
        raw_expectations = raw_case.get("expectations")
        if not isinstance(raw_detector, dict) or not isinstance(
            raw_expectations,
            dict,
        ):
            raise GenerationEvaluationError(
                f"{case_id}: detector output and expectations are required."
            )

        observed_facts = tuple(
            ObservedFactInput(
                observation_id=_required_string(
                    fact,
                    "observation_id",
                    case_id,
                ),
                statement=_required_string(fact, "statement", case_id),
            )
            for fact in raw_case["observed_facts"]
        )
        evidence_chunks: list[EvidenceChunkInput] = []
        for evidence in raw_case["evidence"]:
            chunk_id = _required_string(evidence, "chunk_id", case_id)
            row = chunk_rows[chunk_id]
            evidence_chunks.append(
                EvidenceChunkInput(
                    citation_id=_required_string(
                        evidence,
                        "citation_id",
                        case_id,
                    ),
                    chunk_id=chunk_id,
                    source_id=str(row["source_id"]),
                    source_title=str(row["source_title"]),
                    heading_text=str(row["heading_text"]),
                    page_number=row["page_number"],
                    content=str(row["content"]),
                )
            )

        unsupported_topics = tuple(
            UnsupportedTopicExpectation(
                topic=_required_string(topic, "topic", case_id),
                terms=_required_string_list(topic, "terms", case_id),
            )
            for topic in raw_expectations["required_unsupported_topics"]
        )
        required_observed_fact_groups = tuple(
            tuple(str(item) for item in group)
            for group in raw_expectations.get(
                "required_observed_fact_groups",
                [],
            )
        )
        required_supported_basis_groups = tuple(
            SupportedBasisExpectation(
                observation_ids=_required_string_list(
                    basis,
                    "observation_ids",
                    case_id,
                ),
                detector_ids=_required_string_list(
                    basis,
                    "detector_ids",
                    case_id,
                ),
                citation_ids=_required_string_list(
                    basis,
                    "citation_ids",
                    case_id,
                ),
            )
            for basis in raw_expectations.get(
                "required_supported_basis_groups",
                [],
            )
        )
        minimum_steps = raw_expectations.get("minimum_verification_steps")
        if not isinstance(minimum_steps, int) or minimum_steps < 0:
            raise GenerationEvaluationError(
                f"{case_id}: minimum verification steps is invalid."
            )
        cases.append(
            GenerationCase(
                case_id=case_id,
                title=_required_string(raw_case, "title", case_id),
                request=EvidenceGenerationRequest(
                    question=_required_string(raw_case, "question", case_id),
                    observed_facts=observed_facts,
                    detector_output=DetectorOutputInput(
                        detector_id=_required_string(
                            raw_detector,
                            "detector_id",
                            case_id,
                        ),
                        model_name=_required_string(
                            raw_detector,
                            "model_name",
                            case_id,
                        ),
                        label=_required_string(
                            raw_detector,
                            "label",
                            case_id,
                        ),
                        fake_probability=float(
                            raw_detector["fake_probability"]
                        ),
                        threshold=float(raw_detector["threshold"]),
                        limitations=_required_string_list(
                            raw_detector,
                            "limitations",
                            case_id,
                        ),
                    ),
                    evidence_chunks=tuple(evidence_chunks),
                ),
                expectations=GenerationExpectations(
                    allowed_overall_assessments=_required_string_list(
                        raw_expectations,
                        "allowed_overall_assessments",
                        case_id,
                    ),
                    required_citation_groups=tuple(
                        tuple(str(item) for item in group)
                        for group in raw_expectations[
                            "required_citation_groups"
                        ]
                    ),
                    required_unsupported_topics=unsupported_topics,
                    forbidden_supported_patterns=_required_string_list(
                        raw_expectations,
                        "forbidden_supported_patterns",
                        case_id,
                    ),
                    minimum_verification_steps=minimum_steps,
                    required_observed_fact_groups=(
                        required_observed_fact_groups
                    ),
                    required_supported_basis_groups=(
                        required_supported_basis_groups
                    ),
                    forbidden_supported_observation_ids=(
                        _required_string_list(
                            raw_expectations,
                            "forbidden_supported_observation_ids",
                            case_id,
                        )
                        if "forbidden_supported_observation_ids"
                        in raw_expectations
                        else ()
                    ),
                ),
            )
        )

    return GenerationCaseSet(
        evaluation_set_id=_required_string(
            raw,
            "evaluation_set_id",
            "generation set",
        ),
        corpus_sha256=corpus_sha256,
        prompt_version=str(prompt_version),
        answer_schema_version=str(answer_schema_version),
        cases=tuple(cases),
        file_sha256=hashlib.sha256(data).hexdigest().upper(),
    )


def score_generated_answer(
    answer: FaceGuardEvidenceAnswer | FaceGuardEvidenceReportAnswer,
    case: GenerationCase,
) -> GenerationRuleScore:
    if isinstance(answer, FaceGuardEvidenceReportAnswer):
        validate_generated_report_answer(answer, case.request)
    else:
        validate_generated_answer(answer, case.request)
    cited = {
        citation
        for statement in answer.retrieved_evidence
        for citation in statement.citations
    } | {
        citation
        for conclusion in answer.supported_conclusions
        for citation in conclusion.citations
    }
    required_citations_present = all(
        cited.intersection(group)
        for group in case.expectations.required_citation_groups
    )

    unsupported_text = " ".join(
        f"{item.claim} {item.reason}"
        for item in answer.unsupported_conclusions
    ).lower()
    unsupported_topics_present = all(
        any(term.lower() in unsupported_text for term in expectation.terms)
        for expectation in case.expectations.required_unsupported_topics
    )

    supported_text = " ".join(
        [
            answer.detector_output.statement,
            *(
                statement.statement
                for statement in answer.retrieved_evidence
            ),
            *(
                f"{conclusion.statement} {conclusion.qualification}"
                for conclusion in answer.supported_conclusions
            ),
        ]
    ).lower()
    supported_sections_safe = not any(
        pattern.lower() in supported_text
        for pattern in case.expectations.forbidden_supported_patterns
    )

    observed_fact_references = {
        observation_id
        for fact in answer.observed_facts
        for observation_id in fact.observation_ids
    }
    observed_fact_references_present = all(
        observed_fact_references.intersection(group)
        for group in case.expectations.required_observed_fact_groups
    )

    supported_basis_present = True
    supported_observations_separated = True
    if isinstance(answer, FaceGuardEvidenceReportAnswer):
        supported_basis_present = all(
            any(
                (
                    not expectation.observation_ids
                    or set(conclusion.observation_ids).intersection(
                        expectation.observation_ids
                    )
                )
                and (
                    not expectation.detector_ids
                    or set(conclusion.detector_ids).intersection(
                        expectation.detector_ids
                    )
                )
                and (
                    not expectation.citation_ids
                    or set(conclusion.citations).intersection(
                        expectation.citation_ids
                    )
                )
                for conclusion in answer.supported_conclusions
            )
            for expectation in (
                case.expectations.required_supported_basis_groups
            )
        )
        forbidden_observation_ids = set(
            case.expectations.forbidden_supported_observation_ids
        )
        supported_observations_separated = not any(
            forbidden_observation_ids.intersection(
                conclusion.observation_ids
            )
            for conclusion in answer.supported_conclusions
        )
    elif case.expectations.required_supported_basis_groups:
        supported_basis_present = False

    return GenerationRuleScore(
        assessment_allowed=(
            answer.overall_assessment
            in case.expectations.allowed_overall_assessments
        ),
        required_citations_present=required_citations_present,
        unsupported_topics_present=unsupported_topics_present,
        supported_sections_safe=supported_sections_safe,
        verification_steps_sufficient=(
            len(answer.recommended_verification_steps)
            >= case.expectations.minimum_verification_steps
        ),
        observed_fact_references_present=(
            observed_fact_references_present
        ),
        supported_basis_present=supported_basis_present,
        supported_observations_separated=(
            supported_observations_separated
        ),
    )


def evaluate_generation(
    *,
    config: AzureGenerationConfig,
    pricing: GenerationPricing,
    case_set: GenerationCaseSet,
) -> GenerationEvaluation:
    results: list[GenerationCaseResult] = []
    for case in case_set.cases:
        prompt = prepare_generation_prompt(
            case.request,
            prompt_version=case_set.prompt_version,
        )
        if case_set.answer_schema_version == REPORT_ANSWER_SCHEMA_VERSION:
            response_model = FaceGuardEvidenceReportAnswer
            max_output_tokens = 1_600
        else:
            response_model = FaceGuardEvidenceAnswer
            max_output_tokens = None
        generated = request_structured_generation(
            config,
            pricing,
            system_prompt=prompt.system_prompt,
            user_prompt=prompt.user_prompt,
            response_model=response_model,
            schema_name="faceguard_evidence_answer",
            max_output_tokens=max_output_tokens,
        )
        answer = generated.parsed
        if not isinstance(
            answer,
            (FaceGuardEvidenceAnswer, FaceGuardEvidenceReportAnswer),
        ):
            raise GenerationEvaluationError(
                f"{case.case_id}: parsed answer has an unexpected type."
            )
        score = score_generated_answer(answer, case)
        results.append(
            GenerationCaseResult(
                case=case,
                answer=answer,
                prompt_sha256=prompt.prompt_sha256,
                input_sha256=generated.input_sha256,
                output_sha256=generated.output_sha256,
                response_model=generated.response_model,
                score=score,
                input_tokens=generated.input_tokens,
                cached_input_tokens=generated.cached_input_tokens,
                output_tokens=generated.output_tokens,
                total_tokens=generated.total_tokens,
                latency_ms=generated.latency_ms,
                calculated_cost=generated.calculated_cost,
            )
        )

    latencies = [result.latency_ms for result in results]
    return GenerationEvaluation(
        case_set=case_set,
        cases=tuple(results),
        passed_cases=sum(result.score.passed for result in results),
        total_input_tokens=sum(result.input_tokens for result in results),
        total_cached_input_tokens=sum(
            result.cached_input_tokens for result in results
        ),
        total_output_tokens=sum(result.output_tokens for result in results),
        total_cost=sum(
            (result.calculated_cost for result in results),
            Decimal("0"),
        ),
        mean_latency_ms=mean(latencies),
        median_latency_ms=median(latencies),
    )


def generation_evaluation_to_dict(
    evaluation: GenerationEvaluation,
) -> dict[str, Any]:
    return {
        "evaluation_set_id": evaluation.case_set.evaluation_set_id,
        "evaluation_set_sha256": evaluation.case_set.file_sha256,
        "corpus_sha256": evaluation.case_set.corpus_sha256,
        "prompt_version": evaluation.case_set.prompt_version,
        "answer_schema_version": evaluation.case_set.answer_schema_version,
        "metrics": {
            "passed_cases": evaluation.passed_cases,
            "total_cases": len(evaluation.cases),
            "total_input_tokens": evaluation.total_input_tokens,
            "total_cached_input_tokens": (
                evaluation.total_cached_input_tokens
            ),
            "total_output_tokens": evaluation.total_output_tokens,
            "total_cost": str(evaluation.total_cost),
            "mean_latency_ms": evaluation.mean_latency_ms,
            "median_latency_ms": evaluation.median_latency_ms,
            "manual_review_required": True,
        },
        "cases": [
            {
                "case_id": result.case.case_id,
                "title": result.case.title,
                "question": result.case.request.question,
                "prompt_sha256": result.prompt_sha256,
                "input_sha256": result.input_sha256,
                "output_sha256": result.output_sha256,
                "response_model": result.response_model,
                "score": {
                    "passed": result.score.passed,
                    "assessment_allowed": result.score.assessment_allowed,
                    "required_citations_present": (
                        result.score.required_citations_present
                    ),
                    "unsupported_topics_present": (
                        result.score.unsupported_topics_present
                    ),
                    "supported_sections_safe": (
                        result.score.supported_sections_safe
                    ),
                    "verification_steps_sufficient": (
                        result.score.verification_steps_sufficient
                    ),
                    "observed_fact_references_present": (
                        result.score.observed_fact_references_present
                    ),
                    "supported_basis_present": (
                        result.score.supported_basis_present
                    ),
                    "supported_observations_separated": (
                        result.score.supported_observations_separated
                    ),
                },
                "usage": {
                    "input_tokens": result.input_tokens,
                    "cached_input_tokens": result.cached_input_tokens,
                    "output_tokens": result.output_tokens,
                    "total_tokens": result.total_tokens,
                    "latency_ms": result.latency_ms,
                    "calculated_cost": str(result.calculated_cost),
                },
                "answer": result.answer.model_dump(mode="json"),
            }
            for result in evaluation.cases
        ],
    }
