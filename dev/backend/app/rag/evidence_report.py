from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any

from psycopg import Connection

from .azure_embeddings import (
    AzureEmbeddingConfig,
    request_embedding_with_retry,
)
from .azure_generation import (
    AzureGenerationConfig,
    GenerationPricing,
    request_structured_generation,
)
from .embedding_ingestion import EmbeddingPricing
from .embedding_input import (
    prepare_document_embedding_input,
    prepare_query_embedding_input,
)
from .evidence_generation import (
    REPORT_ANSWER_SCHEMA_VERSION,
    REPORT_PROMPT_VERSION,
    DetectorOutputInput,
    EvidenceChunkInput,
    EvidenceGenerationRequest,
    FaceGuardEvidenceReportAnswer,
    ObservedFactInput,
    prepare_generation_prompt,
    validate_generated_report_answer,
)
from .evidence_report_models import (
    EvidenceCitationResponse,
    EvidencePipelineConfiguration,
    EvidencePipelineMetrics,
    EvidenceReportRequest,
    EvidenceReportResponse,
)
from .hybrid_retrieval import HYBRID_CANDIDATE_LIMIT
from .reranker import LoadedReranker, RERANKER_VERSION, score_passages
from .retrieval import (
    LEXICAL_RETRIEVER_VERSION,
    RetrievedChunk,
    lexical_retrieve,
    resolve_corpus_revision_id,
)
from .semantic_retrieval import (
    SEMANTIC_RETRIEVER_VERSION,
    SemanticRetrievedChunk,
    resolve_embedding_model_id,
    semantic_retrieve_exact,
    verify_embedding_coverage,
)


REPORT_PIPELINE_VERSION = "faceguard-evidence-report-v1"
REPORT_CORPUS_SHA256 = (
    "842CBBEFA28D2B8389FF2694420F771A12DFAEBF9F9DDFA5A214BF258F596CEB"
)
REPORT_EVIDENCE_LIMIT = 5
REPORT_MAX_OUTPUT_TOKENS = 1600


class EvidenceReportError(RuntimeError):
    """Raised when an end-to-end evidence report cannot be built safely."""


@dataclass(frozen=True, slots=True)
class _UnionCandidate:
    chunk_id: str
    source_id: str
    source_title: str
    heading_path: tuple[str, ...]
    page_number: int | None
    content: str
    lexical_rank: int | None
    semantic_rank: int | None


def _candidate_union(
    lexical: list[RetrievedChunk],
    semantic: list[SemanticRetrievedChunk],
) -> list[_UnionCandidate]:
    candidates: dict[str, _UnionCandidate] = {}
    order: list[str] = []
    for chunk in lexical:
        candidates[chunk.chunk_id] = _UnionCandidate(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            source_title=chunk.source_title,
            heading_path=chunk.heading_path,
            page_number=chunk.page_number,
            content=chunk.content,
            lexical_rank=chunk.rank,
            semantic_rank=None,
        )
        order.append(chunk.chunk_id)
    for chunk in semantic:
        existing = candidates.get(chunk.chunk_id)
        if existing is None:
            candidates[chunk.chunk_id] = _UnionCandidate(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                source_title=chunk.source_title,
                heading_path=chunk.heading_path,
                page_number=chunk.page_number,
                content=chunk.content,
                lexical_rank=None,
                semantic_rank=chunk.rank,
            )
            order.append(chunk.chunk_id)
        else:
            candidates[chunk.chunk_id] = _UnionCandidate(
                chunk_id=existing.chunk_id,
                source_id=existing.source_id,
                source_title=existing.source_title,
                heading_path=existing.heading_path,
                page_number=existing.page_number,
                content=existing.content,
                lexical_rank=existing.lexical_rank,
                semantic_rank=chunk.rank,
            )
    return [candidates[chunk_id] for chunk_id in order]


def _source_details(
    connection: Connection,
    *,
    corpus_revision_id: int,
    chunk_ids: list[str],
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            chunks.chunk_id,
            documents.canonical_url
        FROM rag.evidence_chunks AS chunks
        JOIN rag.source_documents AS documents
          ON documents.source_document_id = chunks.source_document_id
        WHERE chunks.corpus_revision_id = %s
          AND chunks.chunk_id = ANY(%s)
        """,
        (corpus_revision_id, chunk_ids),
    ).fetchall()
    details = {str(row["chunk_id"]): dict(row) for row in rows}
    missing = sorted(set(chunk_ids).difference(details))
    if missing:
        raise EvidenceReportError(
            "Reranked evidence chunks are missing from the corpus: "
            + ", ".join(missing)
        )
    return details


def build_evidence_report(
    connection: Connection,
    *,
    request: EvidenceReportRequest,
    embedding_config: AzureEmbeddingConfig,
    embedding_pricing: EmbeddingPricing,
    reranker: LoadedReranker,
    generation_config: AzureGenerationConfig,
    generation_pricing: GenerationPricing,
) -> EvidenceReportResponse:
    if not connection.autocommit:
        raise EvidenceReportError(
            "Evidence reporting requires an autocommit database connection."
        )

    corpus_revision_id = resolve_corpus_revision_id(
        connection,
        corpus_sha256=REPORT_CORPUS_SHA256,
    )
    embedding_model_id = resolve_embedding_model_id(
        connection,
        config=embedding_config,
    )
    verify_embedding_coverage(
        connection,
        corpus_revision_id=corpus_revision_id,
        embedding_model_id=embedding_model_id,
    )

    query_input = prepare_query_embedding_input(request.question)
    query_embedding = request_embedding_with_retry(
        embedding_config,
        query_input.text,
    )
    query_embedding_cost = embedding_pricing.cost_for_tokens(
        query_embedding.prompt_tokens
    )

    started_at = perf_counter()
    lexical = lexical_retrieve(
        connection,
        corpus_revision_id=corpus_revision_id,
        query=request.question,
        limit=HYBRID_CANDIDATE_LIMIT,
    )
    lexical_latency_ms = (perf_counter() - started_at) * 1_000

    started_at = perf_counter()
    semantic = semantic_retrieve_exact(
        connection,
        corpus_revision_id=corpus_revision_id,
        embedding_model_id=embedding_model_id,
        query_vector=query_embedding.vector,
        expected_dimensions=embedding_config.dimensions,
        limit=HYBRID_CANDIDATE_LIMIT,
    )
    semantic_latency_ms = (perf_counter() - started_at) * 1_000

    candidates = _candidate_union(lexical, semantic)
    passages = [
        prepare_document_embedding_input(
            source_title=candidate.source_title,
            heading_text=" > ".join(candidate.heading_path),
            content=candidate.content,
        ).text
        for candidate in candidates
    ]
    reranker_scores, reranker_latency_ms = score_passages(
        reranker,
        query=request.question,
        passages=passages,
    )
    ranked = sorted(
        zip(candidates, reranker_scores, strict=True),
        key=lambda item: (
            -item[1].score,
            item[0].chunk_id,
        ),
    )[:REPORT_EVIDENCE_LIMIT]

    top_chunk_ids = [candidate.chunk_id for candidate, _ in ranked]
    source_details = _source_details(
        connection,
        corpus_revision_id=corpus_revision_id,
        chunk_ids=top_chunk_ids,
    )

    evidence_inputs: list[EvidenceChunkInput] = []
    evidence_responses: list[EvidenceCitationResponse] = []
    for index, (candidate, score) in enumerate(ranked, start=1):
        citation_id = f"E-{index}"
        heading = " > ".join(candidate.heading_path)
        evidence_inputs.append(
            EvidenceChunkInput(
                citation_id=citation_id,
                chunk_id=candidate.chunk_id,
                source_id=candidate.source_id,
                source_title=candidate.source_title,
                heading_text=heading,
                page_number=candidate.page_number,
                content=candidate.content,
            )
        )
        evidence_responses.append(
            EvidenceCitationResponse(
                citation_id=citation_id,
                chunk_id=candidate.chunk_id,
                source_id=candidate.source_id,
                source_title=candidate.source_title,
                heading=heading,
                page_number=candidate.page_number,
                canonical_url=str(
                    source_details[candidate.chunk_id]["canonical_url"]
                ),
                reranker_score=score.score,
                lexical_rank=candidate.lexical_rank,
                semantic_rank=candidate.semantic_rank,
            )
        )

    generation_request = EvidenceGenerationRequest(
        question=request.question,
        observed_facts=tuple(
            ObservedFactInput(
                observation_id=item.observation_id,
                statement=item.statement,
            )
            for item in request.observations
        ),
        detector_output=DetectorOutputInput(
            detector_id=request.detector_output.detector_id,
            model_name=request.detector_output.model_name,
            label=request.detector_output.label,
            fake_probability=request.detector_output.fake_probability,
            threshold=request.detector_output.threshold,
            limitations=tuple(request.detector_output.limitations),
        ),
        evidence_chunks=tuple(evidence_inputs),
    )
    prompt = prepare_generation_prompt(
        generation_request,
        prompt_version=REPORT_PROMPT_VERSION,
    )
    generated = request_structured_generation(
        generation_config,
        generation_pricing,
        system_prompt=prompt.system_prompt,
        user_prompt=prompt.user_prompt,
        response_model=FaceGuardEvidenceReportAnswer,
        schema_name="faceguard_evidence_answer",
        max_output_tokens=REPORT_MAX_OUTPUT_TOKENS,
    )
    report = generated.parsed
    if not isinstance(report, FaceGuardEvidenceReportAnswer):
        raise EvidenceReportError(
            "Structured generation returned an unexpected response type."
        )
    validate_generated_report_answer(report, generation_request)

    total_cost = query_embedding_cost + generated.calculated_cost
    return EvidenceReportResponse(
        question=request.question,
        report=report,
        evidence=evidence_responses,
        metrics=EvidencePipelineMetrics(
            query_embedding_tokens=query_embedding.prompt_tokens,
            query_embedding_cost=str(query_embedding_cost),
            query_embedding_latency_ms=query_embedding.latency_ms,
            lexical_latency_ms=lexical_latency_ms,
            semantic_latency_ms=semantic_latency_ms,
            reranker_latency_ms=reranker_latency_ms,
            generation_input_tokens=generated.input_tokens,
            generation_cached_input_tokens=generated.cached_input_tokens,
            generation_output_tokens=generated.output_tokens,
            generation_cost=str(generated.calculated_cost),
            generation_latency_ms=generated.latency_ms,
            total_measured_cost=str(total_cost),
        ),
        configuration=EvidencePipelineConfiguration(
            pipeline_version=REPORT_PIPELINE_VERSION,
            corpus_sha256=REPORT_CORPUS_SHA256,
            lexical_retriever_version=LEXICAL_RETRIEVER_VERSION,
            semantic_retriever_version=SEMANTIC_RETRIEVER_VERSION,
            candidate_limit_per_retriever=HYBRID_CANDIDATE_LIMIT,
            reranker_version=RERANKER_VERSION,
            prompt_version=REPORT_PROMPT_VERSION,
            answer_schema_version=REPORT_ANSWER_SCHEMA_VERSION,
            embedding_model=embedding_config.model_name,
            generation_model=generation_config.model_name,
        ),
    )
