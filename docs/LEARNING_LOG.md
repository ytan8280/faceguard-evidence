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
- Which exact documents will form the first approved retrieval corpus?
- Which embedding and reranking models meet the project's Azure cost and
  reproducibility requirements?
- What evaluation set can be legally retained for independent detector
  validation?

### Current boundary

Phase 0 is complete, and the original website history is preserved in this
repository. The imported application baseline, checkpoint loading, Atlas
connection and one controlled still-image inference have been verified. No RAG
ingestion, chunking, retrieval, prompting or evaluation implementation has
started.

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
