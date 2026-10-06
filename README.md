# FaceGuard Evidence

FaceGuard Evidence is a personal, evidence-grounded multimodal
retrieval-augmented generation (RAG) project by Tan Yan Yi.

The planned system will upgrade the complete original FaceGuard website with
an evidence-grounded RAG workflow. It will retain the website's image
analysis, authentication, profile and history capabilities while adding file
metadata, versioned model documentation, measured evaluation evidence,
authoritative research and media-verification guidance.

> **Project status:** Phase 0 provenance and reproducibility audit. The RAG
> implementation has not started.

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

## Planned Response Structure

Responses will distinguish:

1. **Observed facts** - directly measurable file or image properties.
2. **Detector output** - model version, probability, threshold and latency.
3. **Retrieved evidence** - cited passages relevant to the result.
4. **Supported conclusions** - claims justified by the available evidence.
5. **Unsupported conclusions** - identity, authorship, intent or certainty
   claims that the system cannot establish.
6. **Verification steps** - practical actions for further investigation.

## First-Release Scope

The initial release is limited to:

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
history will be preserved when its website is integrated into this private
repository, retaining the original authors and commits rather than copying the
files into a fresh commit.

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
