from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
import psycopg
from psycopg.rows import dict_row

from .rag.azure_embeddings import (
    load_azure_embedding_config,
)
from .rag.azure_generation import (
    load_azure_generation_config,
    load_generation_pricing,
)
from .rag.embedding_ingestion import load_embedding_pricing
from .rag.evidence_report import (
    REPORT_PIPELINE_VERSION,
    build_evidence_report,
)
from .rag.evidence_report_models import (
    EvidenceReportRequest,
    EvidenceReportResponse,
)
from .rag.reranker import load_reranker, load_reranker_config
from tools.project_runtime import database_url


REPO_ROOT = Path(__file__).resolve().parents[3]
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database_url = database_url(REPO_ROOT)
    app.state.embedding_config = load_azure_embedding_config(REPO_ROOT)
    embedding_pricing = load_embedding_pricing(REPO_ROOT)
    if embedding_pricing is None:
        raise RuntimeError("Verified embedding pricing is not configured.")
    app.state.embedding_pricing = embedding_pricing
    app.state.generation_config = load_azure_generation_config(REPO_ROOT)
    app.state.generation_pricing = load_generation_pricing(REPO_ROOT)
    app.state.reranker = load_reranker(load_reranker_config(REPO_ROOT))
    yield


app = FastAPI(
    title="FaceGuard Evidence RAG API",
    version=REPORT_PIPELINE_VERSION,
    description=(
        "Local-only retrieval, reranking and structured-generation sidecar."
    ),
    lifespan=lifespan,
)


@app.get("/health")
def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "pipeline_version": REPORT_PIPELINE_VERSION,
        "reranker_ready": getattr(request.app.state, "reranker", None)
        is not None,
    }


@app.post("/build-report", response_model=EvidenceReportResponse)
def build_report(
    payload: EvidenceReportRequest,
    request: Request,
) -> EvidenceReportResponse:
    try:
        with psycopg.connect(
            request.app.state.database_url,
            autocommit=True,
            row_factory=dict_row,
        ) as connection:
            return build_evidence_report(
                connection,
                request=payload,
                embedding_config=request.app.state.embedding_config,
                embedding_pricing=request.app.state.embedding_pricing,
                reranker=request.app.state.reranker,
                generation_config=request.app.state.generation_config,
                generation_pricing=request.app.state.generation_pricing,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Evidence report sidecar request failed.")
        raise HTTPException(
            status_code=502,
            detail=(
                "Evidence report generation failed: "
                f"{exc.__class__.__name__}"
            ),
        ) from exc
