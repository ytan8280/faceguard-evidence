from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.reranker import (  # noqa: E402
    RerankerError,
    load_reranker,
    load_reranker_config,
    score_passages,
)


def main() -> None:
    config = load_reranker_config(REPO_ROOT)
    reranker = load_reranker(config)
    scores, latency_ms = score_passages(
        reranker,
        query="How many people live in Berlin?",
        passages=[
            (
                "Berlin had a population of 3,520,031 registered inhabitants "
                "in an area of 891.82 square kilometers."
            ),
            "Berlin is well known for its museums.",
        ],
    )
    if scores[0].score <= scores[1].score:
        raise RerankerError(
            "Reranker smoke test did not rank the relevant passage first."
        )

    print(f"Model: {config.model_id}")
    print(f"Revision: {config.model_revision}")
    print(f"Model SHA-256: {reranker.model_sha256}")
    print(f"Max length: {config.max_length}")
    print(f"Batch size: {config.batch_size}")
    print(f"Load latency: {reranker.load_latency_ms:.3f} ms")
    print(f"Inference latency: {latency_ms:.3f} ms")
    print(f"Relevant score: {scores[0].score:.6f}")
    print(f"Unrelated score: {scores[1].score:.6f}")


if __name__ == "__main__":
    try:
        main()
    except RerankerError as exc:
        raise SystemExit(f"Reranker verification failed: {exc}") from exc
