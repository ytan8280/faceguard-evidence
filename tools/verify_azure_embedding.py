from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dev.backend.app.rag.azure_embeddings import (  # noqa: E402
    AzureEmbeddingError,
    load_azure_embedding_config,
    request_embedding_probe,
)


PROBE_TEXT = (
    "FaceGuard Evidence retrieves cited documentation to help users "
    "interpret detector output without treating it as proof."
)


def main() -> None:
    config = load_azure_embedding_config(REPO_ROOT)
    result = request_embedding_probe(config, PROBE_TEXT)

    print("Azure embedding smoke test succeeded.")
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except AzureEmbeddingError as exc:
        raise SystemExit(f"Azure embedding smoke test failed: {exc}") from exc
