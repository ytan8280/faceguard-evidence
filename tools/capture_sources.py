from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify
from pypdf import PdfReader
import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "data" / "sources"
CAPTURE_TOOL_VERSION = "1"
USER_AGENT = "FaceGuard-Evidence-Source-Capture/1.0"


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    title: str
    source_category: str
    publisher: str
    authors: tuple[str, ...]
    version: str
    published_at: str
    canonical_url: str
    media_type: str
    extractor: Literal["html_article", "pdf_pages"]
    expected_original_sha256: str
    license_name: str
    license_url: str
    rights_basis: str


SOURCES = {
    "EXT-STD-001": SourceDefinition(
        source_id="EXT-STD-001",
        title="Content Credentials: C2PA Technical Specification",
        source_category="media_provenance_standard",
        publisher="Coalition for Content Provenance and Authenticity",
        authors=("Coalition for Content Provenance and Authenticity",),
        version="2.3 (tag commit 6998a277b4519fc652550686861f0b97a64e5c19)",
        published_at="2026-01-11",
        canonical_url=(
            "https://spec.c2pa.org/specifications/specifications/2.3/"
            "specs/C2PA_Specification.html"
        ),
        media_type="text/html",
        extractor="html_article",
        expected_original_sha256=(
            "C8C3DD79C68DF36042D1DA1719BBF7662493D53C7410D5F50C32010131D2ECA0"
        ),
        license_name="Creative Commons Attribution 4.0 International",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        rights_basis="CC BY 4.0 with attribution retained.",
    ),
    "EXT-GUIDE-001": SourceDefinition(
        source_id="EXT-GUIDE-001",
        title="C2PA and Content Credentials Explainer",
        source_category="media_provenance_guidance",
        publisher="Coalition for Content Provenance and Authenticity",
        authors=("Coalition for Content Provenance and Authenticity",),
        version="2.3 (tag commit 6998a277b4519fc652550686861f0b97a64e5c19)",
        published_at="2026-01-11",
        canonical_url=(
            "https://spec.c2pa.org/specifications/specifications/2.3/"
            "explainer/Explainer.html"
        ),
        media_type="text/html",
        extractor="html_article",
        expected_original_sha256=(
            "C40695D9091A21853D32BDA7AF05317CB1B5447D6C2498CDB6F27D7449A68775"
        ),
        license_name="Creative Commons Attribution 4.0 International",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        rights_basis="CC BY 4.0 with attribution retained.",
    ),
    "EXT-REPORT-001": SourceDefinition(
        source_id="EXT-REPORT-001",
        title=(
            "Reducing Risks Posed by Synthetic Content: An Overview of "
            "Technical Approaches to Digital Content Transparency"
        ),
        source_category="government_technical_report",
        publisher="National Institute of Standards and Technology",
        authors=(
            "Bilva Chandra",
            "Jesse Dunietz",
            "Kamie Roberts",
            "Yooyoung Lee",
            "Peter Fontana",
            "George Awad",
        ),
        version="NIST AI 100-4",
        published_at="2024-11-20",
        canonical_url="https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-4.pdf",
        media_type="application/pdf",
        extractor="pdf_pages",
        expected_original_sha256=(
            "A387A4977DB70D65CDBC178C8B0CB8AA5DEDB85FA80D6F473C244E2767A4FD54"
        ),
        license_name="NIST Technical Series reuse terms",
        license_url=(
            "https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-"
            "srd-data-software-and-technical-series-publications"
        ),
        rights_basis=(
            "NIST grants worldwide royalty-free reuse rights for employee-authored "
            "technical publications with acknowledgment."
        ),
    ),
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest().upper()


def normalize_whitespace(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00a0", " ").replace("\u00ad", "")
    lines = [line.rstrip() for line in text.splitlines()]
    normalized_lines: list[str] = []
    previous_blank = False

    for line in lines:
        is_blank = not line.strip()
        if is_blank:
            if normalized_lines and not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue

        normalized_lines.append(line)
        previous_blank = False

    return "\n".join(normalized_lines).strip() + "\n"


def normalize_html(raw_content: bytes, source_url: str) -> str:
    soup = BeautifulSoup(raw_content.decode("utf-8"), "html.parser")
    article = soup.select_one("article.doc")
    if article is None:
        raise ValueError("Expected one C2PA article.doc element.")

    for selector in (
        "script",
        "style",
        "button",
        "svg",
        "nav",
        "#toc",
        ".toc",
        ".toolbar",
        ".pagination",
        ".breadcrumbs",
    ):
        for node in article.select(selector):
            node.decompose()

    for image in article.select("img"):
        alt_text = image.get("alt", "").strip()
        if alt_text:
            image.replace_with(f"[Image: {alt_text}]")
        else:
            image.decompose()

    for link in article.select("[href]"):
        link["href"] = urljoin(source_url, link["href"])

    markdown = markdownify(
        str(article),
        heading_style="ATX",
        bullets="-",
    )
    return normalize_whitespace(markdown)


def normalize_pdf(raw_content: bytes, title: str) -> str:
    reader = PdfReader(io.BytesIO(raw_content))
    sections = [f"# {title}"]

    for page_number, page in enumerate(reader.pages, start=1):
        extracted = normalize_whitespace(page.extract_text() or "")
        sections.append(f"<!-- source-page: {page_number} -->\n\n{extracted.rstrip()}")

    return normalize_whitespace("\n\n".join(sections))


def capture_source(source: SourceDefinition, *, force: bool = False) -> Path:
    output_dir = OUTPUT_ROOT / source.source_id
    content_path = output_dir / "content.md"
    metadata_path = output_dir / "metadata.json"

    if not force and (content_path.exists() or metadata_path.exists()):
        raise FileExistsError(
            f"Snapshot already exists for {source.source_id}. Use --force to replace it."
        )

    response = requests.get(
        source.canonical_url,
        headers={"User-Agent": USER_AGENT},
        timeout=120,
    )
    response.raise_for_status()
    raw_content = response.content
    original_sha256 = sha256_bytes(raw_content)
    if original_sha256 != source.expected_original_sha256:
        raise RuntimeError(
            f"Original content hash changed for {source.source_id}: "
            f"expected {source.expected_original_sha256}, received {original_sha256}."
        )

    if source.extractor == "html_article":
        normalized_content = normalize_html(raw_content, source.canonical_url)
        normalization_steps = [
            "Decoded official HTML as UTF-8.",
            "Selected the article.doc content node.",
            "Removed scripts, styles, navigation, generated table of contents, and controls.",
            "Replaced images with available alt text and resolved links to absolute URLs.",
            "Converted structural HTML to ATX-heading Markdown.",
            "Applied Unicode NFC and deterministic blank-line normalization.",
        ]
    else:
        normalized_content = normalize_pdf(raw_content, source.title)
        normalization_steps = [
            "Extracted text from each PDF page in order with pypdf.",
            "Inserted HTML comments recording one-based source page numbers.",
            "Added a Markdown document title from verified source metadata.",
            "Applied Unicode NFC and deterministic blank-line normalization.",
        ]

    normalized_bytes = normalized_content.encode("utf-8")
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    metadata = {
        "schema_version": 1,
        "source_id": source.source_id,
        "title": source.title,
        "source_category": source.source_category,
        "publisher": source.publisher,
        "authors": list(source.authors),
        "version": source.version,
        "published_at": source.published_at,
        "canonical_url": source.canonical_url,
        "retrieved_at": retrieved_at,
        "license": {
            "name": source.license_name,
            "url": source.license_url,
            "rights_basis": source.rights_basis,
        },
        "original": {
            "media_type": source.media_type,
            "bytes": len(raw_content),
            "sha256": original_sha256,
        },
        "normalized": {
            "format": "markdown",
            "bytes": len(normalized_bytes),
            "lines": len(normalized_content.splitlines()),
            "sha256": sha256_bytes(normalized_bytes),
        },
        "normalization": {
            "tool": "tools/capture_sources.py",
            "tool_version": CAPTURE_TOOL_VERSION,
            "dependencies": {
                "beautifulsoup4": version("beautifulsoup4"),
                "markdownify": version("markdownify"),
                "pypdf": version("pypdf"),
            },
            "steps": normalization_steps,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    content_path.write_bytes(normalized_bytes)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture approved external evidence sources as normalized snapshots."
    )
    parser.add_argument(
        "source_ids",
        nargs="*",
        metavar="SOURCE_ID",
        help=(
            "Source IDs to capture. Omit to capture every approved external source. "
            f"Available: {', '.join(sorted(SOURCES))}."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing snapshot.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    unknown_source_ids = sorted(set(args.source_ids) - set(SOURCES))
    if unknown_source_ids:
        raise SystemExit(f"Unknown source ID(s): {', '.join(unknown_source_ids)}")
    source_ids = args.source_ids or sorted(SOURCES)
    for source_id in source_ids:
        output_dir = capture_source(SOURCES[source_id], force=args.force)
        print(f"Captured {source_id} -> {output_dir.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
