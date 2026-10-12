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

The migrations are:

```text
database/migrations/001_create_rag_core.sql
database/migrations/002_add_chunk_embeddings.sql
```

Plain SQL is used first so PostgreSQL types, constraints, generated columns
and indexes remain visible and explainable.

`tools/migrate_rag_database.py` applies these files through psycopg 3. The
runner:

- discovers files named `NNN_description.sql` in lexical order;
- records each original file's SHA-256 in `rag.schema_migrations`;
- rejects a changed checksum for an already-applied migration;
- uses a PostgreSQL advisory lock to prevent concurrent migration runs;
- applies each pending migration and its history record atomically; and
- supports `--check` for non-mutating file and history validation.

Migration `001` predates the Python runner and contains one outer
`BEGIN`/`COMMIT` wrapper. The runner removes only that wrapper in memory so it
can own the transaction while retaining the committed migration bytes and
checksum. Nested or incomplete transaction control is rejected.

`.gitattributes` enforces LF line endings for migration files. Without that
rule, Windows and Linux checkouts could hash equivalent SQL differently.

## Schema Boundary

All RAG tables live in the PostgreSQL `rag` schema:

```text
rag.source_documents
rag.corpus_revisions
rag.corpus_sources
rag.evidence_chunks
rag.ingestion_runs
rag.embedding_models
rag.embedding_runs
rag.chunk_embeddings
rag.schema_migrations
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

embedding_models <---- embedding_runs ----> corpus_revisions
       ^                       |
       |                       |
       +------ chunk_embeddings ------> evidence_chunks
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

## Embedding Schema

Migration `001` intentionally deferred embeddings until a live Azure request
verified the model output. `FG-EXP-011` confirmed that
`text-embedding-3-small` version `1` returned exactly `1,536` values.

Migration `002` therefore enables pgvector and adds:

```text
rag.embedding_models
rag.embedding_runs
rag.chunk_embeddings
```

### `rag.embedding_models`

This registry separates the Azure deployment name used by API requests from
the model family and effective model version required for provenance.

It records:

- provider, deployment, model and model version;
- API version and Azure region;
- fixed output dimension and distance metric;
- document and query input-format versions;
- Azure version-upgrade policy; and
- additional non-secret metadata.

The current schema accepts only `1,536` dimensions and cosine distance. A
different model dimension requires a deliberate migration rather than an
unreviewed runtime value.

### `rag.embedding_runs`

This operational table records attempts to embed one exact corpus revision
with one registered model configuration.

It tracks:

- running, completed or failed state;
- application revision;
- target, embedded, reused and failed chunk counts;
- Azure input-token usage and API latency; and
- optional verified price, currency, price-check date and calculated cost.

Pricing fields are nullable as one consistent group. This allows embedding
work to proceed without inventing a cost when an official price has not yet
been verified.

### `rag.chunk_embeddings`

Each row stores one vector for:

```text
corpus revision + chunk ID + embedding model identity
```

The foreign key also includes the exact chunk `content_sha256`. An embedding
therefore cannot be attached to a different version of the chunk text.

The table records:

- the embedding-input SHA-256 and character count;
- measured prompt tokens and API latency;
- optional calculated cost;
- Azure's response-model identity;
- a vector SHA-256; and
- the `VECTOR(1536)` value.

The primary key prevents duplicate vectors for the same chunk and model
identity. Repeated generation must verify and reuse an existing row or surface
a conflict.

### Cosine Search

The vector column is declared explicitly:

```sql
embedding VECTOR(1536)
```

An HNSW index uses `vector_cosine_ops`. A separate B-tree index narrows
retrieval by corpus revision and embedding-model identity.

The first release intentionally has one approved embedding model. If future
experiments store vectors from multiple model spaces, indexing must be
revisited so approximate candidates are not mixed across incompatible models.

## Persistent Local Development

`compose.yaml` defines a dedicated pgvector-enabled PostgreSQL service:

| Setting | Value |
|---|---|
| Compose service | `rag-postgres` |
| Container database | `faceguard_evidence` by default |
| Host binding | `127.0.0.1:55432` by default |
| Container port | `5432` |
| Persistent volume | `faceguard-evidence_faceguard_rag_pgdata` |
| Health check | `pg_isready` |

The image is pinned by digest rather than relying only on a moving tag.
Migration files are not mounted into `docker-entrypoint-initdb.d`; schema
changes are always explicit and checksum-tracked.

The optional `tools` Compose profile also defines `rag-tools`, a pinned
Python 3.12 environment containing only the database-backed RAG CLI
dependencies. It exists because Windows Application Control blocks the host
psycopg native DLL. Running the tool in Linux preserves the security policy
and avoids adding a second database driver.

The tools container:

- mounts the repository at `/workspace`;
- connects to `rag-postgres` through the internal Compose network;
- receives secrets from the ignored `.env`;
- overrides the host PostgreSQL URL with the internal service address; and
- starts only when the `tools` profile is explicitly selected.

The `evidence` Compose profile adds a persistent localhost-only `rag-api`
service on `127.0.0.1:8002`. It uses the same pinned tools image and cache,
loads the reranker at startup and creates a fresh PostgreSQL connection for
each report request.

The detector backend sends only:

- privacy-limited observation statements;
- versioned detector output and caveats; and
- the user's evidence question.

The image bytes and heatmap are not sent to the RAG sidecar or Azure
generation model.

For reproducible CPU validation, the `evidence` profile also defines a
`detector-api` service on `127.0.0.1:8001`. It bind-mounts the verified
checkpoint read-only and communicates with `rag-api` over the private Compose
network.

Its build context excludes the ignored `.env` and all repository content
except the Dockerfile and minimal requirements file.

Configure the `RAG_POSTGRES_*` values and `RAG_DATABASE_URL` in the ignored
root `.env`. Never commit the real password or database URL.

Start the service and apply migrations from the repository root:

```bash
docker compose up -d rag-postgres
python tools/migrate_rag_database.py
python tools/migrate_rag_database.py --check
```

Running the apply command again is safe: migrations whose names and checksums
already match are skipped.

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

The persistent Compose service and Python migration runner were subsequently
validated in `FG-EXP-008`. The first run applied migration `001`, the second
run skipped it, and check mode reported zero pending migrations. The service
was healthy on `127.0.0.1:55432`, and the recorded migration remained after a
container restart. The separate PDPA database remained healthy and unchanged
on `127.0.0.1:5432`.

Migration `002` was validated first in a temporary PostgreSQL database, where
a `1,536`-dimensional vector was inserted and queried with cosine distance and
an unsupported `3,072`-dimension model registration was rejected.

Windows Application Control subsequently blocked the pinned psycopg binary's
native DLL. The persistent migration was therefore executed through the
trusted `psql` client inside the existing PostgreSQL container. It used one
transaction, the same advisory-lock key and the original migration-file
SHA-256, then inserted the normal `rag.schema_migrations` history row.
Migration history now contains:

```text
002_add_chunk_embeddings.sql
784AACF3608D702167F7947E6B9315912DCD9E817C224C89F40D329B0549FB37
```

This fallback did not bypass or weaken the operating-system security policy.
The separate PDPA database remained healthy and unchanged.

## Idempotent Corpus Ingestion

`tools/ingest_rag_corpus.py`:

1. load and verify approved sources;
2. produce deterministic chunks;
3. create a canonical manifest from source hashes, chunker settings and every
   ordered chunk identity;
4. calculate `corpus_sha256`;
5. acquire a PostgreSQL advisory lock for corpus ingestion;
6. insert missing immutable source versions;
7. create and populate a new corpus revision inside one transaction, or verify
   every source and chunk before reusing an existing revision; and
8. mark the ingestion run completed only after the transaction succeeds.

The operational `running` record is created separately. If corpus insertion or
verification fails, the content transaction rolls back and the run is updated
to `failed` in a new transaction. This preserves failure evidence without
leaving a partially populated corpus.

Source conflicts are not silently ignored. When a `(source_id,
content_sha256)` already exists, its stored content, provenance metadata and
document fields must match the verified snapshot exactly.

Run ingestion from the repository root:

```bash
python tools/ingest_rag_corpus.py
```

The first measured ingestion and controlled rollback test are recorded as
`FG-EXP-009` in [`EXPERIMENTS.md`](EXPERIMENTS.md).

## Idempotent Chunk Embedding

`tools/embed_rag_corpus.py`:

1. resolves one exact corpus SHA-256;
2. orders chunks by corpus source order and source ordinal;
3. builds `source-heading-content-v1` input;
4. hashes the exact UTF-8 input;
5. registers or verifies the Azure model identity;
6. records a running embedding attempt;
7. verifies and reuses matching stored vectors;
8. requests only missing vectors from Azure;
9. inserts all newly generated vectors and completes the run in one final
   transaction; and
10. records a failed run without inserting partial vectors if preparation,
   Azure validation or final storage fails.

The command requires `--limit N` or explicit `--all`, preventing an accidental
full-corpus Azure run. `--dry-run` prepares and reports input hashes without
calling Azure or writing embedding rows.

The first three-chunk pilot and reuse run are recorded as `FG-EXP-013`.
