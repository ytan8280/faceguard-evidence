from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .evidence_generation import FaceGuardEvidenceReportAnswer


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceObservationRequest(_StrictModel):
    observation_id: str = Field(pattern=r"^OBS-[1-9][0-9]*$")
    statement: str = Field(min_length=1)


class EvidenceDetectorRequest(_StrictModel):
    detector_id: str = Field(pattern=r"^DET-[1-9][0-9]*$")
    model_name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    fake_probability: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    limitations: list[str]
    adapter_version: str = Field(min_length=1)
    preprocessing_version: str = Field(min_length=1)


class EvidenceReportRequest(_StrictModel):
    question: str = Field(min_length=1, max_length=1000)
    observations: list[EvidenceObservationRequest] = Field(min_length=1)
    detector_output: EvidenceDetectorRequest


class EvidenceCitationResponse(_StrictModel):
    citation_id: str
    chunk_id: str
    source_id: str
    source_title: str
    heading: str
    page_number: int | None
    canonical_url: str
    reranker_score: float
    lexical_rank: int | None
    semantic_rank: int | None


class EvidencePipelineMetrics(_StrictModel):
    query_embedding_tokens: int
    query_embedding_cost: str
    query_embedding_latency_ms: float
    lexical_latency_ms: float
    semantic_latency_ms: float
    reranker_latency_ms: float
    generation_input_tokens: int
    generation_cached_input_tokens: int
    generation_output_tokens: int
    generation_cost: str
    generation_latency_ms: float
    total_measured_cost: str


class EvidencePipelineConfiguration(_StrictModel):
    pipeline_version: str
    corpus_sha256: str
    lexical_retriever_version: str
    semantic_retriever_version: str
    candidate_limit_per_retriever: int
    reranker_version: str
    prompt_version: str
    answer_schema_version: str
    embedding_model: str
    generation_model: str


class EvidenceReportResponse(_StrictModel):
    question: str
    report: FaceGuardEvidenceReportAnswer
    evidence: list[EvidenceCitationResponse]
    metrics: EvidencePipelineMetrics
    configuration: EvidencePipelineConfiguration
