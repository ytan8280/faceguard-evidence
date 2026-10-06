from __future__ import annotations

import json
from pathlib import Path

from tools.capture_sources import normalize_html, normalize_whitespace, sha256_bytes


REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_IDS = ("EXT-GUIDE-001", "EXT-REPORT-001", "EXT-STD-001")


def test_normalize_html_preserves_structure_and_removes_navigation() -> None:
    raw_html = b"""
    <html>
      <body>
        <article class="doc">
          <h1>Example Source</h1>
          <div id="toc"><a href="#section">Duplicate section link</a></div>
          <h2 id="section">Section</h2>
          <p>Evidence with <a href="/terms">terms</a>.</p>
          <img alt="Architecture diagram" src="diagram.png">
          <script>ignored()</script>
        </article>
      </body>
    </html>
    """

    normalized = normalize_html(raw_html, "https://example.test/source/page.html")

    assert normalized.startswith("# Example Source\n")
    assert "## Section" in normalized
    assert "Duplicate section link" not in normalized
    assert "ignored()" not in normalized
    assert "[terms](https://example.test/terms)" in normalized
    assert "[Image: Architecture diagram]" in normalized


def test_normalization_and_hashing_are_deterministic() -> None:
    normalized = normalize_whitespace("Heading\u00a0\n\n\nBody\u00ad text  \n")

    assert normalized == "Heading\n\nBody text\n"
    assert sha256_bytes(normalized.encode("utf-8")) == (
        "71E390FCD82C170AF30C56511901E401C9C842AB7DD873C6CDF6D63102F5B8DD"
    )


def test_committed_snapshot_metadata_matches_normalized_content() -> None:
    for source_id in SNAPSHOT_IDS:
        source_dir = REPO_ROOT / "data" / "sources" / source_id
        metadata = json.loads((source_dir / "metadata.json").read_text(encoding="utf-8"))
        content_bytes = (source_dir / "content.md").read_bytes()

        assert metadata["source_id"] == source_id
        assert metadata["normalized"]["bytes"] == len(content_bytes)
        assert metadata["normalized"]["sha256"] == sha256_bytes(content_bytes)
        assert metadata["normalized"]["lines"] == len(
            content_bytes.decode("utf-8").splitlines()
        )
        assert content_bytes.startswith(b"# ")
        assert {path.name for path in source_dir.iterdir()} == {
            "content.md",
            "metadata.json",
        }
