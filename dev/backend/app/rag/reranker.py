from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from huggingface_hub import snapshot_download
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


RERANKER_VERSION = "msmarco-minilm-l6-v2-cross-encoder-v1"


class RerankerError(RuntimeError):
    """Raised when the local cross-encoder cannot be configured or executed."""


@dataclass(frozen=True, slots=True)
class RerankerConfig:
    model_id: str
    model_revision: str
    max_length: int
    batch_size: int


@dataclass(frozen=True, slots=True)
class LoadedReranker:
    config: RerankerConfig
    tokenizer: object
    model: object
    snapshot_path: Path
    model_sha256: str
    load_latency_ms: float


@dataclass(frozen=True, slots=True)
class RerankerScore:
    score: float
    original_token_count: int
    truncated: bool


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RerankerError(f"{name} is not configured.")
    return value


def load_reranker_config(repository_root: Path) -> RerankerConfig:
    load_dotenv(repository_root / ".env", override=False)
    try:
        max_length = int(_required_environment("RERANKER_MAX_LENGTH"))
        batch_size = int(_required_environment("RERANKER_BATCH_SIZE"))
    except ValueError as exc:
        raise RerankerError(
            "Reranker max length and batch size must be integers."
        ) from exc
    if max_length <= 0:
        raise RerankerError("Reranker max length must be positive.")
    if batch_size <= 0:
        raise RerankerError("Reranker batch size must be positive.")

    return RerankerConfig(
        model_id=_required_environment("RERANKER_MODEL_ID"),
        model_revision=_required_environment("RERANKER_MODEL_REVISION"),
        max_length=max_length,
        batch_size=batch_size,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_reranker(config: RerankerConfig) -> LoadedReranker:
    started_at = perf_counter()
    snapshot_path = Path(
        snapshot_download(
            repo_id=config.model_id,
            revision=config.model_revision,
            allow_patterns=[
                "config.json",
                "model.safetensors",
                "special_tokens_map.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.txt",
            ],
        )
    )
    model_path = snapshot_path / "model.safetensors"
    if not model_path.is_file():
        raise RerankerError(
            "Pinned reranker snapshot does not contain model.safetensors."
        )

    tokenizer = AutoTokenizer.from_pretrained(
        snapshot_path,
        local_files_only=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        snapshot_path,
        local_files_only=True,
        use_safetensors=True,
    )
    model.to("cpu")
    model.eval()
    torch.set_num_threads(1)

    return LoadedReranker(
        config=config,
        tokenizer=tokenizer,
        model=model,
        snapshot_path=snapshot_path,
        model_sha256=_sha256(model_path),
        load_latency_ms=(perf_counter() - started_at) * 1_000,
    )


def score_passages(
    reranker: LoadedReranker,
    *,
    query: str,
    passages: list[str],
) -> tuple[list[RerankerScore], float]:
    normalized_query = query.strip()
    if not normalized_query:
        raise RerankerError("Reranker query must not be blank.")
    if not passages:
        raise RerankerError("Reranker requires at least one passage.")
    if any(not passage.strip() for passage in passages):
        raise RerankerError("Reranker passages must not be blank.")

    token_counts = [
        len(
            reranker.tokenizer(
                normalized_query,
                passage,
                add_special_tokens=True,
                truncation=False,
                verbose=False,
            )["input_ids"]
        )
        for passage in passages
    ]

    started_at = perf_counter()
    scores: list[float] = []
    for start in range(0, len(passages), reranker.config.batch_size):
        batch = passages[start : start + reranker.config.batch_size]
        features = reranker.tokenizer(
            [normalized_query] * len(batch),
            batch,
            padding=True,
            truncation="only_second",
            max_length=reranker.config.max_length,
            return_tensors="pt",
        )
        with torch.inference_mode():
            logits = reranker.model(**features).logits
        scores.extend(float(value) for value in logits.squeeze(-1).tolist())
    latency_ms = (perf_counter() - started_at) * 1_000

    return (
        [
            RerankerScore(
                score=score,
                original_token_count=token_count,
                truncated=token_count > reranker.config.max_length,
            )
            for score, token_count in zip(scores, token_counts, strict=True)
        ],
        latency_ms,
    )
