# Learning Log

This log records what was learned, why project decisions were made and which
questions remain open. It is not an experiment-results log.

## 2026-10-06 - Phase 0: Provenance and Reproducibility

### What I learned

#### RAG is a technique, not a user-interface format

Retrieval-augmented generation means retrieving relevant evidence before a
language model generates a response. The output may be a question answer,
report, summary or recommendation.

For FaceGuard Evidence:

1. the detector produces a model score;
2. metadata extraction records observable image and file facts;
3. retrieval finds relevant model documentation, evaluation evidence,
   research and verification guidance; and
4. generation produces a cited response with explicit claim boundaries.

The detector performs image classification. RAG does not replace the detector;
it supplies context for interpreting the detector output responsibly.

#### A detector score is evidence, not proof

A high fake probability does not establish:

- who created an image;
- which exact tool created it;
- whether there was deceptive intent;
- the identity or trustworthiness of a depicted person; or
- certainty that the image is AI-generated.

The system must separate observed facts, detector output, retrieved evidence,
supported conclusions, unsupported conclusions and verification steps.

#### Filenames do not uniquely identify model artifacts

`vit3.pth` is only a filename. The selected artifact is identified by:

- size: `343,248,309` bytes; and
- SHA-256:
  `6FAE9B18A7A7BAFED65FE5A944FC1B66A8CE070896A8531C6C5857477806C25B`.

The checksum allows future runs to state exactly which checkpoint produced a
result.

#### Historical metrics are not the same as reproduced measurements

The original notebook records historical metrics for a checkpoint named
`vit3.pth`, but:

- the notebook did not hash the checkpoint;
- the generated evaluation CSV is no longer available;
- raw prediction and label arrays were deleted;
- train/evaluation overlap was not checked; and
- the exact training source revision was not recorded.

The values may be documented as historical notebook output, but they must not
be presented as independently reproduced FaceGuard Evidence results.

#### Public availability is not a software license

The original FaceGuard repository is public but has no software license and
states that its original materials are MCS24 Team intellectual property. Tan
reports explicit team permission to reuse the code and weights.

That permission does not override third-party terms for AI-Face,
DeepfakeBench, ImageNet-derived pretrained weights or other dependencies.

### Decisions made

#### Initial repository-boundary decision

The initial plan was to keep the complete original application outside this
repository and connect only the detector through an adapter.

This decision was revised after clarifying that the intended final product is
the complete FaceGuard website upgraded with RAG, including authentication,
profiles and analysis history.

#### Preserve the original website history in FaceGuard Evidence

The original detector remains team work. The new RAG implementation remains
Tan's personal post-graduation work.

The original repository's full Git history will be imported into this private
repository before RAG implementation begins. This preserves the original
authors and commits rather than copying team files into a fresh commit.

Reasons:

- preserve collective attribution and original Git history;
- make Tan's new contribution easy to identify;
- provide one unified website containing the original user features and the
  new RAG workflow;
- keep detector access behind a versioned adapter;
- allow the detector to be versioned independently; and
- avoid treating imported team code as newly authored personal work.

#### Start with a single-question workflow

The intended first release will:

1. accept one still image;
2. accept an optional focused question;
3. produce a default evidence report when no question is supplied; and
4. avoid multi-turn conversation state initially.

This keeps retrieval and evaluation attributable to one image and one query.

#### Treat the detector as one bounded evidence source

The detector adapter should return structured data such as:

- model identifier and artifact hash;
- probability and configured threshold;
- resulting label;
- preprocessing version;
- inference latency; and
- explainability artifact status.

The RAG layer should not reinterpret the probability as certainty.

### Questions still open

- Which decision threshold should FaceGuard Evidence adopt?
- Which embedding and reranking models meet the project's Azure cost and
  reproducibility requirements?
- What evaluation set can be legally retained for independent detector
  validation?

### Current boundary

Phase 0 is complete, and the original website history is preserved in this
repository. The imported application baseline, checkpoint loading, Atlas
connection and one controlled still-image inference have been verified. No RAG
ingestion, chunking, retrieval, prompting or evaluation implementation has
started. Phase 1 source acceptance and corpus snapshot preparation are now in
progress.

## 2026-10-06 - Versioned Detector Boundary

### What I learned

The original `/api/analyze` endpoint directly coordinated preprocessing,
checkpoint inference and Grad-CAM generation. If future RAG code called that
model service directly, detector implementation details would spread into the
new personal code and make the original team component harder to identify or
replace.

A detector adapter creates a narrow boundary:

1. the API supplies a cleaned image;
2. the adapter applies the inherited crop and normalization configuration;
3. the imported inference service runs the checkpoint and Grad-CAM; and
4. the adapter maps the result into a stable detector-output structure.

The adapter does not decide whether the prediction is correct. It reports the
model output and identifies the adapter and preprocessing versions so later
evidence-generation code can preserve provenance.

### Decision made

The first release will load the checkpoint locally behind
`faceguard-detector-adapter-v1`. Keeping the current local execution path
minimizes behavior changes while the application baseline is being preserved.
An external detector service can be evaluated later if deployment constraints
justify the additional network and versioning boundary.

The endpoint response remains unchanged. Adapter-specific provenance fields are
available internally for future evidence records rather than being added to the
historical frontend contract immediately.

## 2026-10-06 - First Evidence Corpus

### What I learned

Choosing a corpus is not the same as downloading documents. Every source needs
an acceptance decision covering authority, version identity, permitted use,
storage treatment and the claims it is suitable to support.

Search summaries are discovery aids, not evidence. During source review, one
search result incorrectly described the DeepfakeBench code license as Apache
2.0, while the repository's actual license file specifies CC BY-NC 4.0.
Another result described C2PA `2.4` as the stable release, while the official
C2PA release record identifies `2.3` as the latest final release. Primary
sources corrected both claims.

The first corpus should be small enough to inspect manually. A six-document
mixed corpus can still demonstrate meaningful retrieval:

- FaceGuard model, experiment and attribution evidence answer project-specific
  questions;
- the C2PA specification and explainer answer media-provenance questions; and
- NIST AI 100-4 supplies broader synthetic-content transparency and risk
  guidance.

DeepfakeBench remains relevant, but public availability and a repository code
license do not automatically establish rights for committing the paper's full
text.

### Decisions made

Approved external documents will be stored as normalized UTF-8 snapshots with
source metadata. Raw PDFs and HTML will not be committed. Each snapshot will
retain both original-download and normalized-text hashes plus transformation
notes.

These snapshots are source inputs, not chunks. The source loading and chunking
logic is implemented in small reviewed stages with a detailed walkthrough so
the transformation from source document to retrievable chunk remains
explainable and testable.

## 2026-10-07 - Verified Loading and Structure-Aware Chunking

### What I learned

RAG ingestion should not begin by splitting arbitrary files. The source loader
first verifies that content matches approved metadata, remains inside the
repository boundary and has the expected byte count, line count and SHA-256.
Only then does it create an immutable `SourceDocument`.

Chunking needs to preserve the document's meaning and citation location:

- Markdown headings become a hierarchical heading path;
- NIST PDF page markers become page metadata;
- ordinary prose may be divided at sentence boundaries;
- tables, fenced code and lists remain atomic; and
- chunk IDs include a content-hash prefix so changed content produces a changed
  identity.

A maximum chunk size is not an absolute rule when respecting source structure.
The first baseline uses a `2,000`-character soft limit. Twenty-three C2PA
technical blocks exceed it because splitting them would risk separating table
headers from values or damaging code examples. They are marked explicitly for
later embedding-model handling.

No overlap was selected for the baseline. Heading metadata already provides
context, while overlap would introduce duplicate retrieval results and make
the first retrieval evaluation harder to interpret.

### Measured baseline

The six approved documents produced `847` deterministic chunks:

- `36` from the C2PA explainer;
- `141` from NIST AI 100-4;
- `609` from the C2PA technical specification;
- `14` from the FaceGuard model card;
- `42` from the experiment log; and
- `5` from the attribution record.

These measurements describe chunk construction only. They do not establish
that retrieval quality is good; that must be evaluated with versioned
questions and relevance judgments after indexing.

### Corpus revision lesson

The experiment log is itself an approved corpus document. Recording a new
experiment therefore changes that source's content hash and creates a new
corpus revision.

The `847`-chunk baseline remains reproducible because `FG-EXP-006` records the
six exact input hashes used for the measurement. Future ingestion runs may
produce a different chunk count after the living internal documentation
changes; that is versioned corpus evolution, not an unexplained inconsistency.

## 2026-10-11 - PostgreSQL Retrieval Schema

### What I learned

PostgreSQL and MongoDB have different responsibilities in FaceGuard Evidence.
The inherited website continues to use MongoDB for authentication, profiles
and analysis history. PostgreSQL is introduced specifically for versioned
evidence and retrieval.

The database must distinguish:

- a stable source identity such as `FG-DOC-002`;
- an immutable version of that source identified by its content hash;
- a corpus revision containing an exact ordered set of source versions;
- chunks produced by one chunker configuration; and
- an operational attempt to ingest that corpus.

Storing only a flat `chunks` table would lose these relationships and make it
hard to explain which document version or corpus produced a retrieved result.

### Decisions made

The first schema uses versioned plain SQL migrations so PostgreSQL behavior is
visible before adding a Python abstraction.

Migration `001` creates the core relational and full-text-search schema but
does not add pgvector embeddings. Vector dimensions depend on the selected
embedding model. The embedding registry, vector column and vector index will
be introduced only after an Azure embedding deployment is selected and its
input limits and dimensions are verified.

Full-text retrieval weights source titles and heading paths above ordinary
body content. This makes document structure useful during lexical retrieval
instead of storing headings only for display.

### Runtime validation lesson

The first migration draft failed on a real PostgreSQL server because generated
columns allow only immutable expressions. PostgreSQL does not classify
`ARRAY_TO_STRING` as immutable, so a generated `tsvector` could not derive
searchable text directly from the heading array.

The corrected schema stores:

- `heading_path` as a structured text array for citation and display; and
- `heading_text` as a deterministic ` > `-joined value for full-text search.

A check constraint requires the two forms to agree. This is intentional
denormalization: a small amount of duplicate data makes the full-text column
valid and indexable while preserving structured provenance.

This reinforced the difference between a plausible SQL design and a verified
schema. The migration was not considered complete until it applied on
PostgreSQL 16 and its retrieval and rejection behavior were measured.

## 2026-10-11 - Persistent PostgreSQL and Migration History

### What I learned

A Docker image, a database schema and a migration runner solve different
problems:

- Compose makes the local database reproducible and keeps its data in a named
  volume.
- SQL migrations describe each schema change in reviewable database language.
- The Python runner decides which migrations are pending, applies them safely
  and records exactly which file bytes were used.

The database URL is configuration, not source code. Its password belongs only
in the ignored `.env`; `.env.example` documents the required variable names
with a non-secret placeholder.

### Decisions made

FaceGuard PostgreSQL binds to `127.0.0.1:55432`. Port `5432` was already owned
by the separate Malaysian PDPA project, so reusing or stopping that database
would have violated the project boundary.

The Compose service uses a pgvector-enabled PostgreSQL 16 image pinned by
digest and a named FaceGuard-specific volume. pgvector is available but is not
enabled or used by migration `001`; the embedding model and vector dimension
must be selected first.

The migration runner uses psycopg 3, an advisory lock and SHA-256 migration
history. A second run skips a migration only when both its filename and
checksum match. A changed applied file is an error rather than an implicit
rewrite of database history.

### Migration immutability lesson

Migration `001` was committed before the Python runner existed and already had
an outer `BEGIN`/`COMMIT` wrapper. Removing those lines would have changed a
versioned migration merely to fit new tooling.

The runner instead preserves and hashes the original file, strips only that
single outer wrapper in memory and executes the body inside its own
transaction. This keeps schema changes and their history record atomic without
rewriting the committed migration. Nested or incomplete transaction control
is rejected.

Migration and internal evidence-document hashes must also be independent of
the developer's operating system. Git normally stores LF but may check files
out as CRLF on Windows. Explicit LF rules were therefore added for the SQL
migrations and the three canonical internal corpus documents before their
hashes were recorded.

### What the validation proves

The persistent service became healthy, migration `001` applied once, a second
run skipped it and check mode reported zero pending files. The stored checksum
matched the migration on disk, and the history remained after a container
restart. This proves local deployment, volume persistence and migration
idempotency; it does not prove retrieval quality because no corpus content has
been ingested yet.

## 2026-10-11 - Idempotent Corpus Ingestion

### What I learned

Deterministic chunking is not sufficient by itself. The database also needs a
deterministic identity for the exact retrieval collection.

The corpus manifest therefore includes:

- the ordered source IDs, versions and content hashes;
- the chunker version, maximum size and overlap configuration; and
- every ordered chunk ID, source, content hash, heading path, page number,
  character count and oversized flag.

Canonical JSON serialization produces one `corpus_sha256`. A change to a
source, chunk or chunking configuration therefore produces a different corpus
revision instead of overwriting the previous one.

### Preparation and persistence are separate

`prepare_corpus()` performs deterministic validation without touching the
database. It checks document identities, chunk ownership, contiguous
ordinals, content hashes, character counts and chunk IDs.

`ingest_prepared_corpus()` owns the database boundary. It uses an advisory lock
and an autocommit connection, then opens an explicit content transaction.
Source versions, corpus membership, chunks and the completed run state succeed
or roll back together.

### Idempotency means verified reuse

`ON CONFLICT DO NOTHING` alone would be too weak. It could hide a conflict
whose stored metadata or content differs from the current verified source.

When a source or corpus already exists, the ingestion code reads it back and
compares the stored values with the prepared corpus. Reuse occurs only after
the source membership and all chunk records match. Otherwise ingestion fails
explicitly.

### Failure records use a separate transaction

If the `running` record were created inside the same transaction as all
evidence content, a rollback would also erase the evidence that ingestion
failed.

The run record is therefore created first. The corpus transaction either marks
it completed or rolls back. A separate transaction then marks a failure with
its error message. A controlled inconsistency confirmed that no source,
corpus or chunk was added while the failed run remained auditable.

### What the first measurement proves

The first approved corpus revision stored six source versions and `871`
chunks, including `23` explicitly oversized technical blocks. A repeated
command reused the same corpus revision without duplicating content.

A PostgreSQL full-text query for `decision threshold` ranked the model card's
matching section first. This confirms that ingestion populated the generated
search vectors, but it is not a retrieval-quality evaluation. Relevance still
requires a versioned question set and judgments.

### Version evolution observed

Revision `1` contains the six source versions used by `FG-EXP-009` and `871`
chunks. Recording that experiment changed only the living experiment-log
source, so the next ingestion created revision `2` with `879` chunks while
preserving revision `1`.

The current revision is:

```text
842CBBEFA28D2B8389FF2694420F771A12DFAEBF9F9DDFA5A214BF258F596CEB
```

This is the intended behavior: historical retrieval experiments keep their
original corpus, while new work uses a new immutable revision.

## 2026-10-11 - Lexical Retrieval Evaluation

### What I learned

Showing that PostgreSQL returns search results is not the same as showing that
it retrieves relevant evidence. Retrieval requires a question set with
relevance judgments fixed before measuring the system.

The first set contains `12` questions spanning all six sources. Each question
points to exact relevant chunk IDs and includes a written rationale. The set is
pinned to corpus revision `2`, so future corpus changes cannot silently alter
the evaluation target.

### Metrics are complementary

Recall@K measures how much of the judged evidence appears in the first K
results. A question with two relevant chunks receives Recall@1 of `0.5` when
one is ranked first.

Mean Reciprocal Rank measures how early the first relevant chunk appears. It
does not require every relevant chunk to be returned.

Using both metrics avoids describing a result with one relevant chunk at rank
one and a missing second chunk as perfect retrieval.

### Lexical baseline design

The first retriever converts the normalized question terms into an OR query to
generate candidates. This avoids making every question term mandatory.

PostgreSQL also produces a stricter web-search query. A strict match receives
an additional score contribution, but strictness is not an absolute sorting
tier. The weighted chunk vector already gives source titles and headings more
importance than body text.

This design is intentionally simple and explainable. It is the baseline that
semantic, hybrid and reranked retrieval must beat.

### Measured weaknesses

The baseline returned candidates for all questions but achieved:

- mean Recall@1 of `0.291667`;
- mean Recall@3 of `0.625000`;
- mean Recall@5 of `0.750000`; and
- MRR of `0.548611`.

The preprocessing question and two C2PA definition questions had no relevant
chunk in the first five results. General detector language in the NIST report
overwhelmed the short FaceGuard preprocessing section. Repeated technical
terms in long C2PA chunks overwhelmed concise glossary and overview chunks.

These are useful failures. The question wording and judgments remain fixed so
later retrieval methods can be compared against the same target.

Recording `FG-EXP-010` and its final canonical artifact hashes evolved the
living experiment-log source again. The current development corpus is revision
`4` with `889` chunks:

```text
44F1574EB9B174571D9A751FD127CBB2A10CE1FBEFB4ED3739CCF8E1BE421AD0
```

The lexical result remains pinned to revision `2`; retaining that older corpus
is what makes the measurement reproducible after documentation changes.

## 2026-10-11 - Verifying the Azure Embedding Deployment

### What I learned

An embedding model deployment must be verified before designing the vector
database schema. The model family alone is insufficient: the project also
needs the deployment name, model version, output dimension, endpoint
interface and upgrade policy.

FaceGuard Evidence now has a deployment isolated from the separate PDPA
project. This keeps endpoint ownership, quota and future cost records
separate. The code sends the deployment name to Azure but records
`text-embedding-3-small` version `1` as model provenance.

### Why dimensions come before the migration

pgvector columns have a declared dimension. The live smoke test returned
exactly `1,536` values, so the next migration can deliberately use:

```text
vector(1536)
```

Creating that column before verifying the service would risk a schema that
cannot store the actual response.

### What the smoke test checked

The probe sent one fixed, non-sensitive sentence and required:

- one embedding result;
- exactly `1,536` finite numeric values;
- Azure prompt-token and total-token usage;
- a successful HTTP response; and
- no API key or full vector in logs.

The request used `18` tokens and took `1,214.843 ms`. These are measured values
for one request, not a latency benchmark. The input and vector were identified
with SHA-256 so the measurement can be compared without committing the full
vector.

### What this does not prove

Generating a vector does not prove that semantic search is useful. Retrieval
quality will only be established after corpus revision `2` is embedded and
the semantic retriever is evaluated against the same `12` questions and fixed
relevance judgments as the lexical baseline.

Cost also remains unknown until the official Azure input-token price is
recorded. The project will not infer a price from quota or estimate a cost.

## 2026-10-11 - Adding the pgvector Embedding Schema

### What I learned

Storing vectors requires more than adding one `VECTOR` column. A reproducible
system must answer:

- which model and deployment produced the vector;
- which effective model version was active;
- which corpus and exact chunk content were embedded;
- how the embedding input was constructed;
- how many tokens and how much API time were used; and
- which verified price basis was used for cost.

Migration `002` therefore adds a model registry, operational embedding runs
and immutable chunk embeddings rather than attaching an unexplained vector
directly to `evidence_chunks`.

### Why the chunk hash is repeated

`chunk_embeddings` references the chunk using:

```text
corpus revision + chunk ID + content SHA-256
```

The hash looks redundant because the chunk ID already belongs to a corpus.
Including it in the foreign key makes the content dependency explicit and
allows PostgreSQL to reject an embedding that claims to belong to different
text.

### Why runs and vectors are separate

An embedding run describes an operational attempt. It can fail or reuse
existing vectors. A chunk embedding is durable evidence tied to exact content
and a model identity.

Separating them means a failed run remains auditable without creating partial
or success-shaped vector records.

### Why the dimension is fixed

The live Azure probe returned `1,536` values, so the schema uses:

```text
VECTOR(1536)
```

It also rejects model registrations with other dimensions. Supporting a new
dimension later should be an explicit schema and evaluation decision.

### How the migration was validated

The migration was first applied to a temporary PostgreSQL database. It
successfully:

- enabled pgvector `0.8.7`;
- created the three embedding tables;
- inserted and queried a `1,536`-dimensional vector;
- returned cosine distance `0` for a vector compared with itself; and
- rejected an attempted `3,072`-dimension model registration.

The temporary database was then removed.

The persistent migration runner could not load psycopg because Windows
Application Control blocked its native DLL. The security policy was not
disabled or bypassed. The migration was instead applied through `psql` inside
the existing database container using one transaction, the migration advisory
lock and the exact file checksum.

The FaceGuard database remained healthy on port `55432`, and the separate PDPA
database remained healthy on port `5432`.

## 2026-10-11 - Running the First Idempotent Embedding Pilot

### Why a pilot came before the full corpus

The lexical evaluation corpus contains `879` chunks. Calling Azure for every
chunk before testing identities, transactions and reuse would risk paying for
vectors that could not be stored or reproduced.

The first live run was therefore limited to the first three deterministically
ordered chunks from corpus revision `2`.

### Deterministic document input

Each document embedding uses:

```text
Source: <source title>
Section: <heading path, when available>

<chunk content>
```

This is versioned as `source-heading-content-v1`. Source IDs, page numbers and
hashes are excluded because they aid provenance but do not add natural
language meaning. Query input remains the unmodified normalized question under
`raw-question-v1`.

Line endings are normalized to LF, surrounding whitespace is removed and the
complete UTF-8 input receives a SHA-256. The vector can therefore be reused
only when the exact chunk content, context format and model identity still
match.

### Why the tools container was added

Windows Application Control blocked the host psycopg native DLL. Disabling the
policy would be the wrong solution.

The `rag-tools` Compose profile runs the approved Python and psycopg versions
inside a pinned Linux image. It connects to the same isolated PostgreSQL
service and reads secrets from `.env`, while `.dockerignore` prevents secrets
from entering the build context.

### What the pilot measured

The first run embedded three chunks:

- `698` Azure input tokens;
- `2,388.769 ms` accumulated API latency;
- three different `1,536`-dimensional vectors; and
- no partial or failed rows.

The second identical run embedded zero chunks and reused all three:

- `0` Azure tokens;
- `0 ms` Azure API latency; and
- no duplicate vector rows.

This is verified idempotency, not merely an `ON CONFLICT DO NOTHING` shortcut.
The existing rows were read back and their chunk-content hash, embedding-input
hash, character count and dimension were compared before reuse.

### What remains unproven

Three stored vectors do not establish retrieval quality. The full corpus has
not been embedded, query embeddings have not been implemented and no semantic
Recall@K or MRR values exist yet.

Official Azure pricing also remains unverified, so the pilot records tokens
and latency but leaves calculated cost empty.

## 2026-10-11 - Verifying and Applying Azure Embedding Pricing

### What I learned

Deployment quota is not a price. The `120,000` tokens-per-minute value controls
throughput and cannot be used to calculate cost.

The authenticated Microsoft Azure pricing page for Japan East and USD listed:

```text
text-embedding-3-small
$0.000025 per 1,000 tokens
```

The project stores prices per one million tokens, so the equivalent value is:

```text
$0.025 USD per 1,000,000 input tokens
```

### Exact pilot cost

Azure measured `698` input tokens for the first pilot:

```text
698 × 0.025 / 1,000,000
= 0.00001745 USD
```

The three per-chunk costs sum to the same value:

```text
71 tokens  = 0.000001775 USD
224 tokens = 0.000005600 USD
403 tokens = 0.000010075 USD
```

The reuse run used zero Azure tokens and therefore cost zero.

### Why the price was backfilled

The original API response gave token usage before the official price was
verified. Rather than invent a cost at request time, the database stored null
pricing fields.

After verification, a dedicated command applied the dated price basis to
completed unpriced runs and chunk rows using exact PostgreSQL numeric
arithmetic. Running the command again updated zero rows, confirming that the
pricing backfill is idempotent.

### Cost authorization boundaries

The model page records an `8,191`-token input limit. If every one of the `879`
chunks used that full limit, the theoretical corpus ceiling would be:

```text
7,199,889 tokens
$0.179997225 USD
```

This is a conservative authorization ceiling, not an estimate of actual
usage. The next bounded batch can use the same method before Azure calls are
authorized.

## 2026-10-11 - Expanding the Embedding Boundary to 25 Chunks

### Why the boundary increased gradually

The first three-chunk pilot proved storage and reuse, but it did not exercise a
longer sequence of Azure requests. The next run selected the first `25`
deterministically ordered chunks.

Because three vectors already existed, only `22` calls were required. The
theoretical authorization ceiling was `$0.00450505 USD`, calculated from the
model's maximum input allowance rather than an assumed average token count.

### Measured result

The `22` new embeddings used:

```text
4,183 input tokens
16,635.955 ms accumulated Azure API latency
$0.000104575 USD
```

The same 25-chunk command was then repeated. It reused all `25` vectors with:

```text
0 input tokens
0 ms Azure API latency
$0 cost
```

Across both paid embedding runs, PostgreSQL now contains:

```text
25 distinct vectors
4,881 measured input tokens
$0.000122025 USD cumulative input cost
```

Every stored vector has `1,536` dimensions.

### What this still does not prove

The first `25` chunks all come from the C2PA explainer because deterministic
ordering follows corpus source order. The run therefore exercises more API
calls and database rows, but it does not yet demonstrate model input behavior
across all six sources or oversized C2PA technical blocks.

## 2026-10-11 - Expanding to 100 Stored Embeddings

The next authorized boundary selected the first `100` chunks. The existing
`25` vectors were verified and reused, while `75` missing vectors were
requested from Azure.

The new requests measured:

```text
23,420 input tokens
56,898.805 ms accumulated Azure API latency
$0.000585500 USD
```

Repeating the same command reused all `100` vectors with zero Azure tokens and
zero cost.

The cumulative stored state is now:

```text
100 distinct vectors
28,301 measured input tokens
$0.000707525 USD cumulative input cost
```

This boundary covers two sources:

- all `36` chunks from the C2PA explainer; and
- the first `64` chunks from the NIST report.

The largest formatted embedding input so far was `2,230` characters. The run
has not yet reached the long C2PA specification blocks, including the
structure-preserved oversized tables and lists.

## 2026-10-11 - Expanding to 250 Stored Embeddings

The 250-chunk boundary reused the existing `100` vectors and generated `150`
new vectors.

Measured new usage was:

```text
44,619 input tokens
110,347.876 ms accumulated Azure API latency
$0.001115475 USD
```

The identical reuse run generated no new vectors and used zero Azure tokens.

The cumulative state is now:

```text
250 distinct vectors
72,920 measured input tokens
$0.001823000 USD cumulative input cost
```

This boundary covers:

- all `36` C2PA explainer chunks;
- all `141` NIST report chunks; and
- the first `73` C2PA technical-specification chunks.

No explicitly oversized chunk has been reached yet. The largest observed input
was `2,240` characters, while the highest measured input was `656` tokens.
This confirms that character count and token count are related but not
interchangeable measurements.

## 2026-10-11 - Handling a Real Transient Azure Failure

The first attempt to expand directly from 250 to 500 chunks received an Azure
HTTP `502` response.

The storage transaction had not started, so PostgreSQL correctly retained
exactly `250` chunk embeddings. Run `9` was marked failed, and no partial vector
rows were added.

### What the failure exposed

The original client treated every non-successful HTTP response as final. It
also recorded only the error on a failed run. Successful Azure calls made
earlier in the same in-memory batch were not inserted, but their token usage
and cost were also not preserved in the failed run.

That means the precise usage incurred by failed run `9` is unknown. The
project does not infer or invent that value.

### The correction

The Azure client now retries only transient statuses:

```text
429, 500, 502, 503, 504
```

It makes at most three attempts and uses bounded exponential backoff, while
respecting a numeric Azure `Retry-After` header when present.

If all attempts fail, the operational run now records:

- previously verified reused chunks;
- successful pre-failure response tokens;
- accumulated request latency, including failed HTTP attempts;
- calculated cost for successful measured responses; and
- one failed chunk.

No partial vectors are inserted.

After the change, the complete RAG suite passed and a 250-chunk reuse run again
used zero Azure tokens. This confirmed that retry support did not weaken
idempotency.

## 2026-10-11 - Recovering with a 350-Chunk Boundary

After the real 502 failure, a smaller 350-chunk boundary was authorized. It
reused `250` vectors and generated `100` new vectors with the retry-enabled
client.

Measured new usage was:

```text
30,662 input tokens
75,635.164 ms accumulated API latency
$0.000766550 USD
```

The reuse run then verified all `350` vectors with zero Azure usage.

The cumulative stored state became:

```text
350 vectors
103,582 measured input tokens
$0.002589550 USD cumulative input cost
```

This boundary reached the first structure-preserved oversized C2PA chunk. Its
formatted input contained `3,505` characters and Azure measured `868` tokens,
well below the model's `8,191`-token limit.

This is the first direct evidence that preserving an oversized technical block
does not automatically mean it exceeds the embedding model's token limit.

## 2026-10-11 - Completing the Corrected 500-Chunk Boundary

With retry and failure accounting in place, the 500-chunk boundary was
authorized again. It reused `350` vectors and generated `150` new vectors
without another terminal error.

Measured new usage was:

```text
52,877 input tokens
114,416.093 ms accumulated Azure API latency
$0.001321925 USD
```

The reuse run verified all `500` vectors with zero additional Azure usage.

The cumulative stored state became:

```text
500 vectors
156,459 measured input tokens
$0.003911475 USD cumulative input cost
```

Nine oversized C2PA technical blocks are now embedded. The largest formatted
input contained `10,992` characters, but Azure measured only `2,622` tokens.
This was still substantially below the `8,191`-token model limit and confirms
that the largest preserved corpus block can be embedded without splitting.

## 2026-10-11 - Reaching 750 Stored Embeddings

The 750-chunk boundary reused `500` vectors and generated `250` new vectors.

Measured new usage was:

```text
86,990 input tokens
188,825.877 ms accumulated Azure API latency
$0.002174750 USD
```

The reuse run verified all `750` vectors with zero additional Azure usage.

At this point:

```text
750 vectors are stored
243,449 input tokens have been measured
$0.006086225 USD has been measured
22 of 23 oversized blocks are embedded
```

The stored set includes all C2PA explainer and NIST chunks plus `573` of the
`609` C2PA specification chunks. The final boundary will complete the
technical specification and add the internal FaceGuard sources.

## 2026-10-11 - Completing Corpus Revision 2 Embeddings

The final explicit `--all` run reused `750` vectors and generated the remaining
`129`.

Measured new usage was:

```text
23,891 input tokens
96,760.849 ms accumulated Azure API latency
$0.000597275 USD
```

The complete reuse run then verified all `879` vectors with zero Azure usage.

The final stored corpus contains:

```text
879 distinct vectors
267,340 measured input tokens
$0.006683500 USD stored-vector input cost
23 of 23 oversized blocks
1,536 dimensions for every vector
```

All six sources are represented, including the internal FaceGuard model card,
experiment-log version and attribution record that belong to corpus revision
`2`.

The cost value is the sum of successfully stored unique vectors. It is not
described as the complete Azure invoice because failed pre-fix run `9` may
have made successful calls whose usage was not recorded, and the earlier
standalone smoke test was outside the chunk-embedding rows.

The next stage can finally evaluate semantic retrieval. Query embeddings must
use the same registered model but a separately versioned raw-question input.
For the first baseline, exact cosine ranking over 879 vectors is preferable to
approximate HNSW ranking because it provides a deterministic quality
measurement before optimization.

## 2026-10-11 - Measuring Exact Semantic Retrieval

### Why exact search came before HNSW

The database already has an HNSW cosine index, but approximate retrieval can
miss a true nearest neighbour. Using it in the first semantic experiment would
mix two questions:

1. are the embeddings semantically useful; and
2. does the approximate index return the same neighbours?

The baseline disabled index, index-only and bitmap scans. PostgreSQL's query
plan confirmed a sequential scan and exact sort over all `879` vectors.

### Measured quality

Against the unchanged 12 questions:

```text
Recall@1: 0.625000
Recall@3: 0.916667
Recall@5: 0.958333
MRR:      0.847222
```

Compared with lexical retrieval, semantic retrieval improved every aggregate
ranking metric.

The strongest practical improvements were:

- FaceGuard preprocessing: missing from lexical top five to semantic rank one;
- C2PA assertion/claim/manifest relationship: missing to rank three; and
- C2PA hard-binding definition: missing to rank three.

### Why lexical retrieval is still useful

Semantic retrieval did not dominate every question. The watermarking question
retrieved only one of two relevant chunks in the top five, while lexical
retrieval had both. One attribution question also placed its second relevant
chunk at rank four rather than within the first three.

This is evidence for hybrid retrieval: lexical and semantic methods capture
different relevance signals.

### Measured query cost and latency

The 12 question embeddings used:

```text
177 input tokens
$0.000004425 USD
```

Mean Azure query-embedding latency was `745.782 ms`. Mean exact PostgreSQL
ranking latency was only `11.416 ms`, so the remote embedding call dominated
latency.

No answer-generation model was used. These measurements evaluate retrieval
only.

## 2026-10-11 - Measuring Equal-Weight Hybrid Fusion

### Why raw scores were not added

Lexical and semantic scores mean different things:

- PostgreSQL full-text rank measures term matching and weighting;
- cosine similarity measures vector direction.

Adding them directly would give arbitrary importance to whichever numeric
range happened to be larger. Reciprocal Rank Fusion instead combines rank
positions.

The first hybrid configuration was frozen before measurement:

```text
top 20 lexical candidates
top 20 semantic candidates
equal weights
RRF constant 60
```

### Measured result

Hybrid retrieval achieved:

```text
Recall@1: 0.541667
Recall@3: 0.791667
Recall@5: 0.916667
MRR:      0.752778
```

It beat the lexical baseline but did not beat semantic retrieval.

### What fusion helped

The hybrid top five recovered both relevant watermarking chunks, correcting
the main semantic Recall@5 weakness. It also moved the second attribution
chunk from semantic rank four to hybrid rank two.

### What fusion hurt

Repeated lexical technical terminology pushed useful semantic results down:

- preprocessing moved from rank one to rank two;
- the assertion/claim/manifest explanation moved from rank three to rank five;
- hard binding moved out of the top five entirely.

This demonstrates that hybrid retrieval is not automatically superior.

### Why the weights were not tuned afterward

Changing the weights or RRF constant after seeing these 12 results could
improve this test set while reducing generalization. A proper tuning exercise
would require a separate development set and a held-out test set.

The negative result is therefore retained. A reranker can next evaluate the
meaning of the combined candidate set rather than relying only on rank
agreement.

## 2026-10-11 - Evaluating a Local Cross-Encoder Reranker

### How reranking differs from embeddings

The embedding model encodes the question and chunk independently. A
cross-encoder receives the question and chunk together, allowing token-level
interactions before producing one relevance score.

This is more computationally expensive but can make finer distinctions among
a small candidate set.

### Provenance and runtime

The selected model is:

```text
cross-encoder/ms-marco-MiniLM-L6-v2
revision 233902d25c440f23af6f7d6e94d2946bac0bee0a
Apache-2.0
```

The downloaded `model.safetensors` SHA-256 is:

```text
821D1AA69520101D6E0737F78A042AE25B19E5CB9160701909D10434F4AEB0AE
```

It runs locally with CPU-only PyTorch. The model cache is a Docker volume and
is not committed.

### Candidate discipline

The experiment did not retrieve new candidates. It loaded the frozen hybrid
artifact and compared:

- semantic top-20 candidates; and
- the lexical/semantic top-20 union.

Every unique union candidate was scored once, then the same scores were reused
for both paths.

### Measured quality

Both paths achieved:

```text
Recall@1: 0.625000
Recall@3: 1.000000
Recall@5: 1.000000
MRR:      0.861111
```

The reranker placed all judged relevant chunks within the first three results
for every question. However, the semantic and union paths had identical
aggregate metrics. On this set, lexical union candidates added computation
without adding measured quality.

### Truncation and latency

The model accepts at most `512` tokens for the combined question and passage.
The question was preserved and only the passage was truncated.

Of `386` unique scored pairs:

- `42` were truncated;
- the largest original pair contained `2,806` tokens; and
- mean local CPU inference latency was `4,973.689 ms` per question.

This latency is much higher than PostgreSQL retrieval, though it introduces no
per-query Azure charge.

### Honest interpretation

Perfect Recall@3 and Recall@5 on 12 questions is not proof of general perfect
retrieval. The question set is small and developer-authored, and the model was
trained on MS MARCO rather than this domain.

The result supports using semantic top-20 plus reranking as the current best
measured retrieval pipeline. A larger held-out question set is required before
tuning or making broader claims.

## 2026-10-11 - Creating and Measuring a Held-Out Retrieval Set

### Why the original questions became development data

The first 12 questions were used to inspect lexical failures, choose semantic
retrieval, test RRF and select a reranker. Even though their judgments were
frozen, repeated inspection means they can no longer honestly represent unseen
test data.

They are now explicitly classified as development questions.

### Held-out construction

A new 12-question set was written with two questions for each of the six
sources. Topics were selected from exact corpus revision `2` chunks that were
not used by the development questions.

Before any retrieval run, the held-out set was checked for:

- valid JSON schema;
- exact chunk existence;
- expected source ownership;
- complete embedding coverage; and
- deterministic query hashes.

### Why one Azure run was reused

The held-out hybrid artifact contains both top-20 lexical and exact-semantic
candidates, along with query embedding hashes, tokens, cost and latency.

The semantic held-out artifact was derived from those preserved semantic
rankings instead of making another 12 Azure calls.

### What changed on held-out data

The development reranker suggested that semantic top-20 candidates were
enough. Held-out results contradicted that conclusion:

```text
Semantic top-20 candidate recall: 0.916667
Union candidate recall:          1.000000
```

For `FG-HOLD-009`, the relevant NIST chunk was absent from semantic top-20 but
present in lexical top-20. The union reranker placed it at rank one.

The strongest held-out result was therefore:

```text
lexical top-20 ∪ semantic top-20
→ local cross-encoder
→ top 5
```

with:

```text
Recall@1: 0.791667
Recall@3: 1.000000
Recall@5: 1.000000
MRR:      0.902778
```

### Evaluation discipline after measurement

The held-out set has now been observed. It must not be used to tune candidate
depth, weights, prompts, truncation or model choice.

If retrieval changes again, another independent test set is required.

## 2026-10-11 - Verifying Strict Azure Generation

### Why generation began with a smoke test

The project did not connect retrieved evidence directly to a language model.
First, it verified that the exact deployment could:

- accept the Responses API request;
- obey a strict JSON Schema;
- return locally valid structured output;
- expose token usage;
- support exact cost calculation; and
- avoid server-side response storage.

### Selected deployment

The first baseline uses `gpt-4.1-mini` version `2025-04-14`. Azure marks this
version as Legacy with retirement on `2027-04-14`.

That makes it suitable only as a controlled baseline. FaceGuard Evidence must
migrate and rerun generation measurements before retirement.

### Pricing

The applicable Global Standard prices are:

```text
Input:        $0.40 / 1M tokens
Cached input: $0.10 / 1M tokens
Output:       $1.60 / 1M tokens
```

### Smoke-test measurement

The strict structured response succeeded with:

```text
Input tokens:        115
Cached input tokens: 0
Output tokens:       21
Total tokens:        136
Latency:             1,697.568 ms
Cost:                $0.0000796 USD
```

The request and output were identified by SHA-256 without logging the API key
or response headers.

### What this does not prove

The test proves deployment and schema functionality only. It does not show
that the model:

- uses retrieved evidence correctly;
- cites every supported claim;
- refuses unsupported identity or intent claims;
- separates detector output from observed facts; or
- produces useful verification recommendations.

Those behaviors require a frozen prompt, answer schema and generation
evaluation set.

## 2026-10-11 - Measuring Evidence-Bounded Generation

### Separating input types structurally

The generation schema does not place all information in one prose prompt.
It gives observations, detector output and evidence different identifiers:

```text
OBS-*  observable file or image facts
DET-*  detector output
E-*    retrieved evidence
```

The output must keep those categories separate. Local validation rejects
unknown references even when the JSON itself is schema-valid.

### Six development cases

The first evaluation used six synthetic cases rather than user images. They
tested unsupported certainty, authenticity, creator, tool, identity, intent,
missing credentials, valid provenance and editing metadata.

Evidence was manually selected from corpus revision `2`, so this stage
measured generation rather than retrieval.

### Automatic and manual results

Five of six cases passed every frozen automatic rule. All six:

- used the required citation groups;
- included the required unsupported-claim topics; and
- avoided prohibited claims in supported sections.

Case four failed two rigid rubric checks: its safe
`insufficient_evidence` label was not allowed by the frozen expectation, and
it combined several verification actions into one step.

The rubric was not changed after seeing the result. Manual review recorded
that the answer safely refused factual-truth certainty.

### Measured usage

```text
Input tokens:  12,734
Output tokens: 4,295
Cost:          $0.0119656 USD
Mean latency:  5,643.934 ms
```

No cached input tokens were observed.

### What this proves and does not prove

The baseline shows that strict structure, references, citations and refusal
topics can be enforced and measured. It does not prove general factuality,
because the set has only six developer-authored synthetic cases.

These cases are now development data. Prompt or rubric changes require a new
held-out generation set.

## 2026-10-11 - Measuring Held-Out Generation

### What changed after development

The prompt and schema did not change. Development feedback changed only the
held-out evaluation expectations:

- `insufficient_evidence` was allowed where appropriate; and
- one compound verification-step item was considered actionable.

Six new cases were frozen before generation.

### Held-out automatic result

```text
Complete pass:            5 / 6
Assessment allowed:       6 / 6
Citations present:        6 / 6
Unsupported topics:       6 / 6
Supported-section safety: 5 / 6
Verification steps:       6 / 6
```

The only failure was a substring-scoring false positive. A supported
conclusion said an AI action did **not** prove that the entire image was
generated to deceive. The checker matched the prohibited phrase even though
the sentence negated it.

Manual review found no unsafe supported claim in any held-out answer.

### Measured held-out usage

```text
Input tokens:  12,773
Output tokens: 4,296
Cost:          $0.0119828 USD
Mean latency:  6,450.380 ms
```

### Lesson for evaluation design

Simple string matching is useful for catching obvious prohibited claims but
cannot reliably understand negation. Automatic checks must preserve the full
answer for manual adjudication.

The held-out cases are now consumed. Future prompt or scoring changes require
another independent set rather than rescoring these outputs as though they
were unseen.

## 2026-10-11 - Integrating the End-to-End Evidence Report

### Why the RAG sidecar exists

The detector backend runs on Windows, where Application Control blocks
psycopg's native DLL. Retrieval and local reranking already run reliably in
the pinned Linux tools image.

Disabling Windows security or adding an ad hoc database path would weaken the
project. Instead, a localhost-only sidecar owns:

- PostgreSQL retrieval;
- Azure query embeddings;
- local cross-encoder inference;
- Azure structured generation; and
- report reference validation.

The detector backend remains responsible for upload validation, metadata and
detector inference.

### Privacy boundary

Image bytes are processed only by the detector backend. The sidecar receives
text observations and detector output.

Precise GPS coordinates are not included in observations. Metadata is stripped
before detector inference, preserving visual orientation.

### Preserving inherited behavior

`/api/analyze` was not modified. FaceGuard Evidence adds:

```text
/api/evidence/analyze
```

This avoids changing the inherited website response contract while the new
report UX is developed separately.

### Controlled live result

The synthetic report combined real retrieval, local reranking and Azure
generation. It returned five sources and correctly placed definitive fake,
creator and tool claims in `unsupported_conclusions`.

The measured cost was `$0.0024962 USD`. Local CPU reranking and Azure
generation dominated latency.

### Real detector runtime

A CPU detector container was added with:

```text
PyTorch 2.14.1+cpu
Torchvision 0.29.1+cpu
OpenCV headless 4.10.0
```

The checkpoint is mounted read-only and retained its audited SHA-256.

Two environment-boundary defects were found and corrected:

- Grad-CAM installed a GUI OpenCV wheel that required `libxcb`; the image now
  removes it and reinstalls headless OpenCV.
- the backend client originally allowed only loopback hostnames; it now also
  allows the exact private Compose hostname `rag-api`.

### End-to-end quality gates

The first real route attempt was rejected because the generator placed
observation IDs in evidence citation fields. Pattern-constrained JSON Schema
references prevented that class of error.

A later report was manually rejected because direct file facts had unrelated
research citations and Content Credential status was inferred from EXIF.
Metadata now explicitly records Content Credentials as `not_inspected`, and
integration prompt/schema v2 tracks observation, detector and evidence bases
separately.

The first prompt-v2 response exceeded the output limit. The integration report
limit was raised from 1,200 to 1,600 tokens without changing generation
evaluation artifacts.

The final synchronized route returned a valid v2 report with explicit claim
provenance and no unsupported authenticity, identity, tool or manipulation
claim.

## 2026-10-11 - Presenting the Evidence Report in the Frontend

### Leading with the bounded assessment

The previous interface led with a large REAL or FAKE verdict. Evidence mode
instead leads with:

```text
Insufficient Evidence
Requires Verification
Supported, Limited Conclusion
```

The detector label remains visible as a separate signal.

### Showing evidence provenance

The frontend renders distinct badges:

```text
OBS-* direct observation
DET-* detector output
E-*   retrieved evidence
```

Supported conclusions display all applicable bases. This allows a user to see
whether a conclusion came from the uploaded file, the detector, external
evidence, or a combination.

### Preserving the inherited workflow

The page includes an explicit Detector Only mode. Switching modes clears the
previous result and restores the existing detector request and presentation.

### Visual verification

The accepted report-v2 artifact was served through a temporary local mock API,
avoiding another Azure request. The live React page rendered:

- assessment summary;
- metadata and detector cards;
- source links;
- citation statements;
- supported and unsupported conclusions;
- verification steps;
- Grad-CAM comparison; and
- diagnostics.

The narrow browser side panel exercised the responsive single-column layout.
The production Vite build completed successfully.

## 2026-10-12 - Evaluating Report-v2 Independently

### Why the accepted integration example was not enough

One accepted end-to-end report only proved that the pipeline could produce one
good answer. It did not show whether the updated prompt and schema generalized
to new questions.

Eight new cases were therefore written and frozen before generation. They
focused on the exact reasons report v2 exists:

- separating direct observations from interpretations;
- identifying detector-based conclusions with `DET-*`;
- using `E-*` citations only when they directly support a claim;
- keeping `not_inspected` different from absent;
- refusing identity, intent, certainty, factual-truth and enforcement claims.

### Why `1/8` was not the complete story

The automatic rubric required specific supported-conclusion basis patterns.
Only one answer matched all frozen rules.

Manual review showed that every answer safely refused the user's unsupported
request, and five of eight passed a stricter combined quality review. Four
automatic failures were safe answers that either:

- returned no supported conclusion because the assessment was insufficient
  evidence;
- did not force an irrelevant detector conclusion; or
- used an observation that was genuinely relevant to a detector limitation.

This demonstrates that structural evaluation rules can create false negatives
when they prescribe one acceptable answer shape too narrowly.

### The failures that still mattered

Three answers had real quality defects:

1. `not_inspected` was described with ambiguous absence wording;
2. retrieved-evidence paraphrases exceeded the exact scope of their citations;
3. JPEG format was attached to a conclusion about detector-score calibration.

These are not unsupported certainty or identity claims, but they matter in an
evidence system because claim provenance must be precise, not merely safe.

### Paid-evaluation failure handling

The first paid run generated all responses but failed before artifact writing
because the container could not resolve the worktree Git revision. Exact usage
was lost, so no cost was estimated.

The tool now resolves revision identity before making paid requests. The
persisted rerun measured `$0.0122148 USD`.

The general lesson is:

> Validate every piece of local artifact metadata before making external paid
> requests, not after generation completes.

### Honest conclusion

Report v2 generalized well for refusal safety:

```text
Safe refusal: 8 / 8
```

It did not achieve perfect report precision:

```text
Strict manual quality: 5 / 8
Automatic complete pass: 1 / 8
```

The held-out set is now consumed. A future prompt/schema v3 needs a new test
set rather than tuning against these eight cases and calling them held-out
again.
