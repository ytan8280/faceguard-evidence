# Changelog

## v0.1.1 - 2026-10-12

### Fixed

- allow the detector API container to honor `FACEGUARD_ENABLE_DATABASE` from
  the ignored `.env` instead of always forcing database mode off;
- include the MongoDB and bcrypt dependencies required by email and Google
  authentication when database mode is enabled;
- document the optional MongoDB, collection and Google client environment
  variables in `.env.example`.

## v0.1.0 - 2026-10-12

FaceGuard Evidence v0.1.0 is the first complete still-image MVP.

### Added

- versioned adapter for the inherited FaceGuard `vit3` detector;
- privacy-limited image and file metadata extraction;
- verified six-source evidence corpus with structure-aware chunking;
- immutable PostgreSQL source, corpus, chunk and embedding provenance;
- PostgreSQL lexical retrieval and exact pgvector semantic retrieval;
- lexical/semantic candidate union with a pinned local cross-encoder reranker;
- strict Azure structured generation with validated `OBS-*`, `DET-*` and
  `E-*` claim references;
- additive `POST /api/evidence/analyze` endpoint;
- Dockerized PostgreSQL, RAG API and detector API services;
- frontend Evidence Report mode while preserving Detector Only mode;
- separate retrieval and generation evaluations with frozen development and
  held-out sets;
- measured latency, token usage and Azure cost;
- complete architecture, experiment, learning and walkthrough documentation.

### Measured results

- held-out reranked retrieval:
  - Recall@1: `0.791667`;
  - Recall@3: `1.000000`;
  - Recall@5: `1.000000`;
  - MRR: `0.902778`;
- report-v2 held-out generation:
  - safe refusal: `8/8`;
  - strict manual report-quality pass: `5/8`;
  - frozen automatic complete pass: `1/8`;
- one accepted real-route analysis:
  - total measured Azure cost: `$0.002506775 USD`.

The retrieval figures come from a small developer-authored 12-question
held-out set. They are project measurements, not a general performance claim.

### Known limitations

- the inherited `0.25` detector threshold has not been independently
  validated and conflicts with historical `0.5` material;
- historical detector accuracy has not been independently reproduced;
- Content Credentials are reported as `not_inspected`;
- report-v2 held-out review found three claim-precision defects;
- CPU reranking and Azure generation dominate latency;
- evidence reports are not persisted in user history;
- the Azure generation deployment is Legacy and retires on 2027-04-14;
- the evaluation sets are small and developer-authored;
- only still images and one detector version are supported.

### Release boundaries

The release does not include model checkpoints, secrets, user images,
restricted datasets, database volumes or runtime artifacts.
