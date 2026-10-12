# FaceGuard Evidence

FaceGuard Evidence is a personal, evidence-grounded multimodal
retrieval-augmented generation (RAG) project by Tan Yan Yi.

The system upgrades the complete original FaceGuard website with an
evidence-grounded RAG workflow. It retains the website's image
analysis, authentication, profile and history capabilities while adding file
metadata, versioned model documentation, measured evaluation evidence,
authoritative research and media-verification guidance.

> **Project status:** FaceGuard Evidence v0.1.0 MVP. The still-image
> upload-to-report workflow, versioned detector adapter, metadata extraction,
> PostgreSQL lexical and vector retrieval, local reranking, structured cited
> generation, held-out evaluation, frontend report and measured cost tracking
> are complete. See the
> [complete walkthrough](docs/FACEGUARD_EVIDENCE_WALKTHROUGH.md) and
> [v0.1.0 release notes](CHANGELOG.md).

## Why This Project Exists

A detector probability is not proof that an image is real or AI-generated. It
also cannot establish who created an image, which tool created it or whether
there was deceptive intent.

FaceGuard Evidence is intended to place detector output inside a traceable
evidence workflow:

```text
Uploaded still image
        |
        +--> Observable file and image metadata
        |
        +--> Versioned FaceGuard detector adapter
        |
        +--> Retrieval from an approved evidence collection
        |
        +--> Cited response with explicit claim boundaries
```

The user may provide a focused question about the uploaded image. When no
question is supplied, the system will generate a default evidence report.

## Report Structure

Responses will distinguish:

1. **Observed facts** - directly measurable file or image properties.
2. **Detector output** - model version, probability, threshold and latency.
3. **Retrieved evidence** - cited passages relevant to the result.
4. **Supported conclusions** - claims justified by the available evidence.
5. **Unsupported conclusions** - identity, authorship, intent or certainty
   claims that the system cannot establish.
6. **Verification steps** - practical actions for further investigation.

## First-Release Scope

Version 0.1.0 is limited to:

- one unified FaceGuard website;
- the existing authentication, profile and analysis-history capabilities;
- still-image uploads;
- one existing FaceGuard ViT-B/16 detector checkpoint;
- relevant image and file metadata;
- structure-aware evidence ingestion and chunking;
- PostgreSQL full-text retrieval;
- pgvector semantic retrieval;
- hybrid retrieval fusion;
- a reranking experiment;
- cited, evidence-bounded generation;
- separate retrieval and generation evaluation; and
- latency, token-usage and Azure-cost measurement.

## Non-Goals

The initial release will not include:

- video or audio analysis;
- facial recognition or identity inference;
- attribution to a specific generator or person;
- intent or criminality inference;
- automatic moderation, enforcement or publication decisions;
- multiple cooperating agents;
- Kubernetes or blockchain; or
- unsupported or estimated model-performance claims.

## Relationship to the Original FaceGuard Project

The original detector was developed collectively by the MCS24 Team at Monash
University Malaysia:

<https://github.com/MCS24-Team/FaceGuard-AI-Detector-MVP>

It remains separately attributed team work. The original repository's full Git
history is preserved in this private repository, retaining the original
authors and commits rather than copying the files into a fresh commit.

Tan's new RAG work will be added after that preserved history. Detector access
will still use a small, versioned adapter so the model remains replaceable and
auditable. The selected checkpoint is stored outside Git and identified by its
SHA-256 checksum.

See:

- [`ATTRIBUTION.md`](ATTRIBUTION.md)
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md)

## Evidence and Reproducibility

Evidence sources are not accepted merely because they are publicly accessible.
Each source must have a recorded identity, version, owner, permitted-use basis
and retrieval status.

Historical metrics from the original training notebook are documented as
historical evidence. They are not presented as independently reproduced
FaceGuard Evidence results.

See:

- [`docs/DATA_SOURCE_REGISTER.md`](docs/DATA_SOURCE_REGISTER.md)
- [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md)
- [`docs/LEARNING_LOG.md`](docs/LEARNING_LOG.md)

## Data and Artifact Policy

This repository must not contain:

- restricted datasets or annotations;
- uploaded user images;
- secrets or private environment files;
- model checkpoints without verified redistribution permission; or
- copied third-party training code with unresolved licensing.

The repository will commit an `.env.example` when runtime configuration is
introduced, while real secrets remain in local `.env` files.

## Current Work

Phase 0 establishes:

- collective and individual attribution;
- third-party provenance;
- exact detector artifact identity;
- known reproducibility gaps;
- source-acceptance rules; and
- experiment-recording standards.

Implementation will begin only after this foundation is reviewed.

---

## Original FaceGuard Website Baseline

The following baseline documentation is preserved from the imported MCS24 Team
repository. It describes the original website before the FaceGuard Evidence
RAG extension.

Claims in this baseline section are part of the original project description.
They are not independently verified FaceGuard Evidence measurements.

<p align="center">
  <img src="dev/frontend/src/assets/logo.png" alt="FaceGuard logo" width="250" />
</p>

MCS24 Team is dedicated to develop **FaceGuard: a Privacy-Preserving AI for Detecting Deepfake Profile Photos**, a user-friendly web-based system to accurately identify and classify AI-generated human face images on social media and dating platforms. **FaceGuard** is anticipated to deliver a fully functional web-based system with visual explainability via Grad-CAM heatmaps that can accurately classify profile photos as real or AI-generated.

> **INTELLECTUAL PROPERTY NOTICE:**
>
> **FaceGuard** and all original materials in this repository (including source code, UI design, documentation, model integration logic and project artifacts) are intellectual property of the **MCS24 Team** unless otherwise stated.
>
> **Copyright © 2025/26 MCS24 Team. All rights reserved.**
>
> Third-party components, datasets and model weights remain the property of their respective owners and are subject to their original licenses and terms. Refer to [THIRD_PARTY_NOTICES.md](models/THIRD_PARTY_NOTICES.md) for attribution details.
> 
> If you reference this project in reports, demos or derivative works, please credit it as:
> ```
> FaceGuard: a Privacy-Preserving AI for Detecting Deepfake Profile Photos, MCS24 Team, 2026.
> ```
>
> **DISCLAIMER:** This project is for educational and research purposes only. It is not intended for commercial use and is not endorsed by any organization or entity. Use at your own risk.

## Project Overview

The FaceGuard MVP provides:

- Web-based image upload and preview workflow
- Backend inference API for binary REAL/FAKE classification
- Confidence score and model metadata in responses
- In-memory processing with no database persistence
- Account authentication and authorisation
- Explainability overlays (Grad-CAM heatmaps)

![FaceGuard result panel sample](result_panel.png)

## Repository Structure

```text
FaceGuard-AI-Detector/
├── config/
│   └── settings.py
│
├── dev/
│   ├── backend/
│   └── frontend/
│
├── docs/
│   ├── design/
│   ├── diagrams/
│   └── documents/
│
└── models/
  ├── pretrained/
  │   ├── vit.pth
  │   ├── xception.pth
  │   └── pg_fdd.pth
  │
  ├── README.md
  └── THIRD_PARTY_NOTICES.md
```

## Prerequisites

- Python 3.9+
- Node.js 18+
- npm 9+
- Docker Desktop with Docker Compose
- A compatible model checkpoint file (eg. `models/pretrained/vit.pth`)

## Quick Start

### 1. Install Python dependencies

From the repository root:

```bash
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

For local development and backend regression tests, install the separate test
dependencies instead:

```bash
pip install -r requirements-dev.txt
```

### 2. Install frontend dependencies

```bash
cd dev/frontend
npm install
```

### 3. Configure and start the RAG database

Copy the PostgreSQL entries from `.env.example` into the ignored `.env` and
replace `RAG_POSTGRES_PASSWORD` with a local password. Keep
`RAG_DATABASE_URL` consistent with the same database, user, password and port.

Start the pgvector-enabled PostgreSQL service:

```bash
docker compose up -d rag-postgres
```

Apply all pending schema migrations:

```bash
python tools/migrate_rag_database.py
```

Validate migration files and history without changing the database:

```bash
python tools/migrate_rag_database.py --check
```

Load the verified sources, build the deterministic corpus manifest and ingest
the current chunks:

```bash
python tools/ingest_rag_corpus.py
```

Running the ingestion command again verifies and reuses the same corpus
revision. It does not duplicate source versions or chunks.

Evaluate the versioned PostgreSQL lexical-retrieval baseline separately from
answer generation:

```bash
python tools/evaluate_lexical_retrieval.py \
  --output data/evaluation/results/lexical_baseline_v1.json
```

The question set, relevance judgments and complete per-question rankings are
versioned under `data/evaluation/`.

After corpus revision `2` has complete embeddings, evaluate the exact semantic
baseline against the unchanged questions:

```bash
docker compose --profile tools run --rm rag-tools \
  tools/evaluate_semantic_retrieval.py \
  --output data/evaluation/results/semantic_baseline_v1.json \
  --application-revision <git-revision-or-revision-dirty>
```

Use `--dry-run` first to verify question identities and complete vector
coverage without calling Azure. The measured baseline disables PostgreSQL
index and bitmap scans so the initial quality comparison uses exact cosine
ranking rather than approximate HNSW candidates.

Evaluate the frozen equal-weight Reciprocal Rank Fusion baseline:

```bash
docker compose --profile tools run --rm rag-tools \
  tools/evaluate_hybrid_retrieval.py \
  --output data/evaluation/results/hybrid_rrf_baseline_v1.json \
  --application-revision <git-revision-or-revision-dirty>
```

This combines top-20 lexical and top-20 exact-semantic candidates with the
preselected RRF constant `60`, then evaluates the fused top five. Do not tune
the constant or weights merely to improve the same 12-question test set.

Verify and evaluate the pinned local cross-encoder:

```bash
docker compose --profile tools run --rm rag-tools \
  tools/verify_reranker.py

docker compose --profile tools run --rm rag-tools \
  tools/evaluate_reranker.py \
  --output data/evaluation/results/reranker_baseline_v1.json \
  --application-revision <git-revision-or-revision-dirty>
```

The model weights are pinned by Hugging Face revision and stored only in the
Docker-managed cache volume. The evaluator compares reranking semantic top-20
candidates with reranking the lexical/semantic top-20 union from the frozen
hybrid artifact.

The retrieval evaluation split is recorded in:

```text
data/evaluation/retrieval_split_v1.json
```

The original 12 questions are development data because their results were
inspected during retriever design. The separate held-out file contains 12 new
questions, two per source, frozen before its first measurement:

```text
data/evaluation/retrieval_questions_heldout_v1.json
```

After the recorded held-out comparison, do not tune retrieval configuration
against those questions without creating another independent test set.

Verify the configured Azure structured-generation deployment before building
evidence prompts:

```bash
docker compose --profile tools run --rm rag-tools \
  tools/verify_azure_generation.py
```

The smoke test uses the Responses API with `store: false`, a strict
Pydantic-generated JSON Schema, local schema validation, explicit token
accounting and verified input/output pricing.

Validate or run the versioned generation-only evaluation:

```bash
docker compose --profile tools run --rm rag-tools \
  tools/evaluate_generation.py --dry-run

docker compose --profile tools run --rm rag-tools \
  tools/evaluate_generation.py \
  --output data/evaluation/results/generation_baseline_v1.json \
  --application-revision <git-revision-or-revision-dirty>
```

The six synthetic cases use curated corpus evidence so generation behavior is
measured independently from retrieval failures.

The generation development/held-out split is recorded in:

```text
data/evaluation/generation_split_v1.json
```

After the held-out run, neither prompt wording nor automatic scoring rules
should be tuned against those six cases without creating another independent
test set.

Report prompt/schema v2 has a separate consumed held-out set:

```text
data/evaluation/generation_cases_report_v2_heldout_v1.json
```

Its measured artifacts are:

```text
data/evaluation/results/generation_report_v2_heldout_v1.json
data/evaluation/results/generation_report_v2_heldout_manual_review_v1.json
```

The eight cases safely refused all requested overclaims. Five passed strict
manual report-quality review; the frozen automatic rubric passed one and
produced four clear false negatives. Do not tune report v2 against this set
and present a rerun as independent held-out evidence.

Before adding vector storage, configure the Azure embedding variables from
`.env.example` in the ignored `.env`. Keep the real API key only in `.env`.
Verify the exact deployment, returned vector dimensions, token usage and
request latency with one non-sensitive probe:

```bash
python tools/verify_azure_embedding.py
```

The command prints hashes and summary measurements, not the API key or the
embedding vector. The current probe targets the Microsoft Foundry
OpenAI-compatible `v1` embeddings endpoint.

Windows Application Control can block psycopg's native DLL on the host. The
profile-gated `rag-tools` service provides a pinned Linux Python environment
for database-backed RAG commands without changing that security policy:

```bash
docker compose --profile tools build rag-tools
docker compose --profile tools run --rm rag-tools \
  tools/embed_rag_corpus.py --limit 3 --dry-run
```

The embedding command defaults to the corpus revision used by the lexical
baseline. It requires either `--limit N` for a deliberate pilot or `--all` for
an explicit full run. Container runs also require the current application
revision because worktree Git metadata is outside the mounted directory:

```bash
docker compose --profile tools run --rm rag-tools \
  tools/embed_rag_corpus.py \
  --limit 3 \
  --application-revision <git-revision-or-revision-dirty>
```

The document embedding format is versioned as
`source-heading-content-v1`; query input remains `raw-question-v1`. Repeating
the same command verifies and reuses matching vectors rather than calling
Azure again.

After verifying the official Azure input-token price, configure the three
pricing fields in `.env` and apply that basis to completed unpriced rows:

```bash
docker compose --profile tools run --rm rag-tools \
  tools/apply_embedding_pricing.py --yes
```

The command uses exact decimal arithmetic and is idempotent. It does not call
Azure.

Start the localhost-only evidence and detector services:

```bash
docker compose --profile evidence up -d rag-api detector-api
```

Verify readiness:

```text
GET http://127.0.0.1:8002/health
GET http://127.0.0.1:8001/api/health
```

The inherited backend uses `RAG_API_URL=http://127.0.0.1:8002` and exposes an
additive evidence endpoint:

```text
POST /api/evidence/analyze
multipart fields:
  file: still image
  question: optional evidence question
```

The original `/api/analyze` response contract is unchanged. The new endpoint
returns privacy-limited metadata, versioned detector output, top-five cited
evidence, the structured evidence report, and measured pipeline cost/latency.

The detector checkpoint is bind-mounted read-only from
`FACEGUARD_MODEL_PATH`; it is not copied into the Docker image.

Run a synthetic full-pipeline verification without a user image:

```bash
python tools/verify_evidence_report.py
```

The default host binding is `127.0.0.1:55432`, avoiding the separate PDPA
project's PostgreSQL service on `127.0.0.1:5432`.

### 4. Start backend

In a terminal from the repository root:

```bash
cd dev/backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### 5. Start frontend

In a second terminal:

```bash
cd dev/frontend
npm run dev
```

Open the application at:

- `http://localhost:5173`

The Detector page now defaults to **Evidence Report** mode. It calls
`/api/evidence/analyze` and presents:

- the bounded overall assessment before the raw REAL/FAKE detector label;
- direct metadata observations;
- detector output and caveats;
- top-five cited evidence sources;
- supported conclusions with `OBS-*`, `DET-*`, and `E-*` bases;
- unsupported conclusions;
- verification steps; and
- expandable cost and latency diagnostics.

Switch to **Detector Only** to preserve the inherited `/api/analyze`
experience.

## Health Endpoint

Verify backend readiness:

- `GET http://127.0.0.1:8001/api/health`

Example response:

```json
{
  "status": "ok",
  "model_ready": true,
  "model_name": "vit"
}
```

If `model_ready` is `false`, the backend is reachable but the configured
checkpoint file is missing or failed to load.

## Backend Tests

Run the backend and source-snapshot regression tests from the repository root:

```bash
python -m pytest dev/backend/tests tests
```

The tests generate their own in-memory images and do not require a checkpoint,
database connection or user image.

## Evidence Source Snapshots

Approved external sources are captured as normalized Markdown plus JSON
metadata:

```bash
python tools/capture_sources.py
```

Capture one source by ID:

```bash
python tools/capture_sources.py EXT-GUIDE-001
```

The utility verifies the official downloaded content against its pinned
SHA-256 before writing. It commits neither raw HTML nor PDFs. Existing
snapshots are not replaced unless `--force` is supplied.

## API Contract

### GET /api/health

Returns service and model availability status.

### POST /api/analyze

Accepts `multipart/form-data` with field:

- `file` (JPEG, PNG, or WebP)

Example response:

```json
{
  "label": "FAKE",
  "confidence": 0.9123,
  "fake_probability": 0.9123,
  "threshold": 0.5,
  "explanation": "Prediction is based on a ViT deepfake classifier...",
  "model_name": "vit",
  "heatmap_overlay": "data:image/png;base64,...",
  "explainability_method": "grad_cam"
}
```

## Model Checkpoints

The backend loads model checkpoints from a local path or from Hugging Face Hub
based on environment variables and `config/settings.py`.

Common checkpoint names:

- `vit.pth`
- `vit3.pth`
- `xception.pth`
- `pg_fdd.pth`

Large model binaries are excluded from source control. Keep checkpoints in local
or approved storage and distribute them according to license terms.

### Hugging Face Hub on Render

For deployment, upload the checkpoint to a Hugging Face model repository and set
these Render backend environment variables:

```text
HF_MODEL_REPO=your-username/faceguard-vit3
HF_MODEL_FILE=vit3.pth
HF_TOKEN=your_hugging_face_read_token
MODEL_CACHE_DIR=/tmp/faceguard_models
FACEGUARD_MODEL_NAME=vit
FACEGUARD_FRONTEND_ORIGINS=https://your-vercel-app.vercel.app
```

If you want to keep local development using a file on disk, set:

```text
FACEGUARD_MODEL_PATH=models/baseline/vit3.pth
```

## Design and Project Artifacts

Supporting design and project materials are available in:

- `docs/design/`
- `docs/diagrams/`
- `docs/documents/`

## Additional Documentation

For a simple end-to-end explanation of the complete system, read
[**FaceGuard Evidence: Complete Project Walkthrough**](docs/FACEGUARD_EVIDENCE_WALKTHROUGH.md).

For development operations and troubleshooting guidance, refer to [**Developer Guide**](DEVELOPER_GUIDE.md).
