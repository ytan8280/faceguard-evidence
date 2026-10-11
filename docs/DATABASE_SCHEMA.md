# FaceGuard Evidence Database Schema

## Purpose

FaceGuard Evidence uses two databases with separate responsibilities:

- MongoDB continues to support the inherited FaceGuard authentication,
  profile and analysis-history features.
- PostgreSQL stores the versioned RAG evidence corpus and supports retrieval.

Keeping these responsibilities separate avoids an unrelated authentication
migration while the RAG pipeline is being built and evaluated.

## Migration Strategy

PostgreSQL changes use ordered, versioned SQL files under
`database/migrations/`.

The initial migration is:

```text
database/migrations/001_create_rag_core.sql
```

Plain SQL is used first so PostgreSQL types, constraints, generated columns
and indexes remain visible and explainable. A Python database access layer can
be added after the schema is validated.

## Schema Boundary

All RAG tables live in the PostgreSQL `rag` schema:

```text
rag.source_documents
rag.corpus_revisions
rag.corpus_sources
rag.evidence_chunks
rag.ingestion_runs
```

This avoids mixing RAG tables with unrelated application tables.

## Data Relationships

```text
source_documents
       ^
       | many document versions belong to many corpus revisions
       |
corpus_sources >---- corpus_revisions
       |
       | one approved source version produces many chunks
       v
evidence_chunks

ingestion_runs ----> corpus_revisions
```

## `rag.source_documents`

This table stores immutable, verified versions of approved source documents.

| Column | Meaning |
|---|---|
| `source_document_id` | Internal PostgreSQL identity |
| `source_id` | Stable project identifier such as `FG-DOC-001` |
| `content_sha256` | Exact identity of this content version |
| `title` | Human-readable source title |
| `source_category` | Model documentation, technical report, provenance guidance, and similar categories |
| `publisher` | Issuing project or organization |
| `authors` | PostgreSQL text array of credited authors |
| `source_version` | Source-supplied version, release or content-hash identity |
| `published_at` | Source publication date |
| `canonical_url` | Citation URL or repository URI |
| `license_name` / `license_url` | Permitted-use record |
| `content_path` | Auditable repository source or snapshot path |
| `content` | Verified normalized source text |
| `content_bytes` / `content_lines` | Integrity diagnostics |
| `metadata` | Complete source metadata snapshot as JSONB |
| `created_at` | Database insertion time |

The unique pair `(source_id, content_sha256)` allows a living internal document
to have multiple immutable versions without overwriting history.

## `rag.corpus_revisions`

A corpus revision identifies one exact retrieval collection.

It includes:

- the ordered source-content hashes;
- chunker version;
- maximum chunk size;
- overlap configuration;
- source and chunk counts; and
- a JSON manifest used to calculate and audit `corpus_sha256`.

The corpus hash makes ingestion idempotent. Attempting to ingest the same
sources with the same chunking configuration finds the existing revision
instead of creating a logically duplicate corpus.

## `rag.corpus_sources`

This join table records which immutable source versions belong to one corpus
revision.

`source_order` is stored because deterministic source ordering contributes to
reproducible manifests, diagnostics and evaluation outputs.

The table also prevents a source document from being deleted while a corpus
revision still references it.

## `rag.evidence_chunks`

This is the primary retrieval table.

| Column | Meaning |
|---|---|
| `corpus_revision_id` | Exact corpus to which the chunk belongs |
| `chunk_id` | Deterministic ID produced by the chunker |
| `source_document_id` | Immutable source version that produced the chunk |
| `source_title` | Denormalized title used in weighted full-text search |
| `ordinal` | Stable one-based position within the source |
| `heading_path` | Markdown section ancestry as a text array |
| `heading_text` | Deterministic ` > `-joined heading path used by full-text search |
| `page_number` | Original PDF page when available |
| `content` | Citation-ready chunk text |
| `content_sha256` | Exact chunk-content identity |
| `char_count` | Verified character count |
| `oversized` | Whether an atomic technical block exceeded the soft limit |
| `chunker_version` | Transformation version |
| `search_vector` | Generated PostgreSQL full-text-search representation |
| `created_at` | Database insertion time |

The primary key is `(corpus_revision_id, chunk_id)`. The same deterministic
chunk may appear in different corpus revisions without losing its corpus
context.

### Full-Text Weighting

`search_vector` is generated automatically:

- source title and `heading_text` receive weight `A`;
- chunk content receives weight `B`.

This means a query matching a section heading such as `Decision Threshold`
normally ranks above the same terms appearing incidentally in body text.

A GIN index makes PostgreSQL full-text queries efficient.

`heading_path` remains structured for citations and display. `heading_text` is
stored separately because PostgreSQL generated columns permit only immutable
functions, while `ARRAY_TO_STRING` is not classified immutable. The ingestion
layer produces both values and a database check requires them to agree.

## `rag.ingestion_runs`

This table records operational attempts rather than evidence content.

It distinguishes:

- `running`;
- `completed`; and
- `failed` ingestion attempts.

Failed runs require an error message. Completed and failed runs require a
completion timestamp. This makes failures explicit instead of returning a
success-shaped fallback.

## Why Embeddings Are Not in Migration 001

pgvector requires a known embedding dimension for the clearest type and index,
for example:

```sql
embedding VECTOR(1536)
```

The project has not yet selected and measured an Azure embedding deployment.
Adding an arbitrary dimension would falsely lock the schema to an unapproved
model.

A later migration will add:

- an embedding-model registry;
- chunk embeddings tied to the exact chunk content hash;
- the selected vector dimension;
- cosine-distance indexing; and
- model/deployment version metadata.

This separates the PostgreSQL full-text baseline from the semantic-retrieval
experiment.

## Runtime Validation

Migration `001` was validated on:

- PostgreSQL `16.15`;
- pgvector-enabled image `pgvector/pgvector:pg16`; and
- available pgvector extension version `0.8.7`.

The first draft attempted to derive searchable heading text directly from the
`heading_path` array inside the generated column. PostgreSQL rejected that
design because generated expressions must be immutable and
`ARRAY_TO_STRING` is not classified immutable.

The validated design stores both:

- `heading_path`, for structured citations and display; and
- `heading_text`, for immutable generated full-text-search construction.

A check constraint requires `heading_text` to match the structured path.
Validation details are recorded as `FG-EXP-007` in
[`EXPERIMENTS.md`](EXPERIMENTS.md).

## Idempotent Ingestion Concept

The future ingestion command will:

1. load and verify approved sources;
2. produce deterministic chunks;
3. create a canonical manifest from source hashes and chunker settings;
4. calculate `corpus_sha256`;
5. reuse an existing corpus revision when that hash already exists;
6. insert missing immutable source versions;
7. link them through `corpus_sources`;
8. insert chunks inside one transaction; and
9. mark the ingestion run completed only after the transaction succeeds.

This prevents partial or duplicate corpus states.
