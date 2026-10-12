from __future__ import annotations

from dev.backend.app.rag.evidence_generation import (
    DetectorAssessment,
    FaceGuardEvidenceAnswer,
    FaceGuardEvidenceReportAnswer,
    ObservedFactStatement,
    ReportSupportedConclusion,
    SupportedConclusion,
    UnsupportedConclusion,
    VerificationStep,
)
from dev.backend.app.rag.generation_evaluation import (
    GenerationExpectations,
    SupportedBasisExpectation,
    UnsupportedTopicExpectation,
    score_generated_answer,
)
from dev.backend.tests.rag.test_evidence_generation import _request
from dev.backend.app.rag.generation_evaluation import GenerationCase


def test_generation_rule_score_accepts_expected_refusal_and_citations() -> None:
    case = GenerationCase(
        case_id="CASE",
        title="Case",
        request=_request(),
        expectations=GenerationExpectations(
            allowed_overall_assessments=("requires_verification",),
            required_citation_groups=(("E-1",),),
            required_unsupported_topics=(
                UnsupportedTopicExpectation(
                    topic="certainty",
                    terms=("definitely", "prove"),
                ),
            ),
            forbidden_supported_patterns=("definitely fake",),
            minimum_verification_steps=1,
        ),
    )
    answer = FaceGuardEvidenceAnswer(
        schema_version="faceguard-evidence-answer-v1",
        overall_assessment="requires_verification",
        observed_facts=[
            ObservedFactStatement(
                statement="The file is a JPEG.",
                observation_ids=["OBS-1"],
            )
        ],
        detector_output=DetectorAssessment(
            statement="The detector returned FAKE.",
            detector_ids=["DET-1"],
            caveats=[],
        ),
        retrieved_evidence=[],
        supported_conclusions=[
            SupportedConclusion(
                statement="Further verification is warranted.",
                citations=["E-1"],
                qualification="The result is not proof.",
            )
        ],
        unsupported_conclusions=[
            UnsupportedConclusion(
                claim="The image is definitely fake.",
                reason="The evidence does not prove that claim.",
            )
        ],
        recommended_verification_steps=[
            VerificationStep(
                step="Find the earliest copy.",
                rationale="Earlier context can provide provenance.",
            )
        ],
    )

    score = score_generated_answer(answer, case)

    assert score.passed is True


def test_report_generation_score_checks_claim_basis_and_separation() -> None:
    case = GenerationCase(
        case_id="REPORT-CASE",
        title="Report case",
        request=_request(),
        expectations=GenerationExpectations(
            allowed_overall_assessments=("requires_verification",),
            required_citation_groups=(("E-1",),),
            required_unsupported_topics=(),
            forbidden_supported_patterns=(),
            minimum_verification_steps=1,
            required_observed_fact_groups=(("OBS-1",),),
            required_supported_basis_groups=(
                SupportedBasisExpectation(
                    observation_ids=(),
                    detector_ids=("DET-1",),
                    citation_ids=("E-1",),
                ),
            ),
            forbidden_supported_observation_ids=("OBS-1",),
        ),
    )
    answer = FaceGuardEvidenceReportAnswer(
        schema_version="faceguard-evidence-report-answer-v2",
        overall_assessment="requires_verification",
        observed_facts=[
            ObservedFactStatement(
                statement="The file is a JPEG.",
                observation_ids=["OBS-1"],
            )
        ],
        detector_output=DetectorAssessment(
            statement="The detector returned FAKE.",
            detector_ids=["DET-1"],
            caveats=[],
        ),
        retrieved_evidence=[],
        supported_conclusions=[
            ReportSupportedConclusion(
                statement="The detector result requires verification.",
                observation_ids=[],
                detector_ids=["DET-1"],
                citations=["E-1"],
                qualification="The result is not proof.",
            )
        ],
        unsupported_conclusions=[],
        recommended_verification_steps=[
            VerificationStep(
                step="Find the earliest copy.",
                rationale="Earlier context can provide provenance.",
            )
        ],
    )

    score = score_generated_answer(answer, case)

    assert score.passed is True
    assert score.observed_fact_references_present is True
    assert score.supported_basis_present is True
    assert score.supported_observations_separated is True
