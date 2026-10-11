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
