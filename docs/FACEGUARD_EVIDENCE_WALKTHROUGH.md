# FaceGuard Evidence: Complete Project Walkthrough

## Why This Document Exists

This document explains the complete FaceGuard Evidence system in simple terms.
Return to it whenever you need to remember:

- what the project does;
- why each component exists;
- how an uploaded image moves through the system;
- what was measured;
- what conclusions are allowed;
- what the current limitations are; and
- how to explain the project in an interview.

## The One-Sentence Idea

> FaceGuard Evidence analyzes a still image, retrieves relevant model and
> provenance evidence, reranks the best sources, and produces a structured,
> cited report that separates observations, detector predictions, supported
> conclusions, unsupported conclusions, and verification steps.

## The Main Problem

A normal deepfake detector may return:

```text
FAKE
Confidence: 94%
```

That output creates important unanswered questions:

- Does 94% mean the image is definitely fake?
- Was the detector threshold properly validated?
- Could compression or editing affect the result?
- Does the score identify the creator or AI tool?
- Does it prove malicious intent?
- What should the user verify next?

FaceGuard Evidence does not treat the detector score as the final truth. It
surrounds the score with observations, documentation, citations, limitations,
and recommended verification steps.

## The Complete Flow

```text
User uploads a still image
        |
        v
Validate file type and size
        |
        v
Extract privacy-limited metadata observations
        |
        v
Strip metadata and normalize image orientation
        |
        v
Run FaceGuard vit3 detector
        |
        v
Search evidence with lexical retrieval
        |
        +-------------------+
        |                   |
        v                   v
PostgreSQL keywords    Azure query embedding
                            |
                            v
                     pgvector similarity
        |                   |
        +---------+---------+
                  |
                  v
     Combine lexical and semantic top 20
                  |
                  v
      Local cross-encoder reranking
                  |
                  v
          Select top 5 evidence chunks
                  |
                  v
        Strict Azure structured generation
                  |
                  v
 Validate schema, references, and claim bases
                  |
                  v
       Render the FaceGuard Evidence report
```

---

# Part 1: The Original FaceGuard Detector

## What It Does

The original detector is a ViT-B/16 image classifier called `vit3`.

It:

1. accepts an RGB still image;
2. resizes it to `224 x 224`;
3. converts it to a PyTorch tensor;
4. applies ImageNet normalization;
5. runs the ViT model;
6. converts the output through a sigmoid function;
7. returns a fake probability; and
8. compares that probability with the configured threshold.

Example:

```text
Fake probability: 0.94
Threshold: 0.25
Label: FAKE
```

The correct interpretation is:

> The detector classified the image as FAKE using its current configuration.

The incorrect interpretation is:

> The image has been proven fake.

## Current Detector Identity

```text
Model: FaceGuard vit3
Architecture: ViT-B/16
Framework: PyTorch and Torchvision
Adapter: faceguard-detector-adapter-v1
Preprocessing: faceguard-rgb-resize-normalize-v1
```

Checkpoint SHA-256:

```text
6FAE9B18A7A7BAFED65FE5A944FC1B66A8CE070896A8531C6C5857477806C25B
```

The checkpoint remains outside Git and is mounted read-only into the detector
container.

## Important Threshold Limitation

The inherited source uses:

```text
0.25
```

Historical deployment material also records:

```text
0.5
```

FaceGuard Evidence has not independently selected a canonical threshold.
Therefore, every report treats the current threshold as inherited and
unvalidated.

## What the Detector Cannot Establish

The detector cannot prove:

- depicted-person identity;
- creator identity;
- the exact AI generation tool;
- authorship;
- malicious intent;
- deception;
- criminality;
- trustworthiness;
- factual truth;
- whether an image should be removed or punished.

---

# Part 2: Direct File and Image Observations

## Why Observations Are Separate

File facts are not detector predictions and are not retrieved research.

FaceGuard Evidence assigns them IDs such as:

```text
OBS-1
OBS-2
OBS-3
```

## What Is Extracted

The current metadata extractor can report:

- image format;
- MIME type;
- width and height;
- decoded color mode;
- file size;
- whether EXIF metadata exists;
- a sanitized software field;
- a sanitized timestamp;
- whether GPS metadata exists.

Precise GPS coordinates are not sent to the RAG system.

Example observations:

```text
OBS-1: The uploaded file is a PNG still image.
OBS-2: The dimensions are 512 by 512 pixels.
OBS-3: The file size is 4,595 bytes.
OBS-4: No EXIF metadata was present.
OBS-5: Content Credentials were not inspected.
```

## Content Credentials Status

Content Credentials are not currently parsed from uploaded images.

The API therefore reports:

```text
content_credentials_status: not_inspected
```

The report must interpret that as:

> Their presence or absence is unknown.

It must not say:

> No Content Credentials were found.

## Privacy Boundary

Before detector inference:

1. EXIF orientation is applied;
2. the image is converted to RGB;
3. metadata is removed from the inference image.

The uploaded image and Grad-CAM heatmap are not sent to the language model.
Only text observations, detector output, and retrieved evidence are sent to
the RAG sidecar.

---

# Part 3: The Evidence Corpus

## What a Corpus Is

The corpus is the controlled evidence library searched by the RAG system.

It is not training data for the detector or language model.

## The Six Approved Sources

### Internal FaceGuard sources

1. FaceGuard `vit3` model card;
2. FaceGuard measured experiment log;
3. FaceGuard attribution record.

### External authoritative sources

4. C2PA technical specification;
5. C2PA and Content Credentials explainer;
6. NIST report on synthetic-content transparency.

## Why These Sources Matter

The internal sources explain:

- how FaceGuard works;
- model preprocessing;
- threshold uncertainty;
- historical measurements;
- limitations;
- project attribution.

The external sources explain:

- detector evaluation;
- false-positive concerns;
- watermark limitations;
- provenance;
- Content Credentials;
- what valid or missing provenance does not prove.

---

# Part 4: Structure-Aware Chunking

## Why Documents Are Split

The source documents are too large to retrieve as whole files.

They are divided into smaller retrieval units called chunks.

## What the Chunker Preserves

The chunker preserves:

- Markdown headings;
- heading ancestry;
- tables;
- lists;
- fenced code;
- NIST PDF page markers;
- atomic technical blocks.

The normal soft limit is:

```text
2,000 characters
```

Some C2PA tables and lists remain larger because splitting them could corrupt
their technical meaning.

## Deterministic Chunk IDs

Each chunk receives an identity such as:

```text
FG-DOC-001:0007:C1010E17492A
```

This ID includes:

- source ID;
- source ordinal;
- part of the content SHA-256.

The evaluation corpus contains:

```text
879 chunks
```

---

# Part 5: PostgreSQL and Corpus Versioning

## Database Responsibilities

MongoDB keeps the inherited application responsibilities:

- login;
- profile;
- analysis history.

PostgreSQL handles the new RAG responsibilities:

- source versions;
- corpus revisions;
- chunks;
- ingestion runs;
- embedding models;
- embedding runs;
- chunk vectors;
- migration history.

## Immutable Corpus Revisions

When a source changes, the old content is not overwritten.

A new immutable corpus revision is created.

This makes it possible to say:

> This retrieval result used these exact source bytes, chunks, model
> configuration, and question set.

## Evaluation Corpus

The main retrieval experiments are pinned to corpus revision `2`:

```text
842CBBEFA28D2B8389FF2694420F771A12DFAEBF9F9DDFA5A214BF258F596CEB
```

---

# Part 6: Lexical Retrieval

## The Simple Explanation

Lexical retrieval is advanced keyword search.

If the user asks:

> What threshold does FaceGuard use?

PostgreSQL searches for terms related to:

```text
threshold
FaceGuard
use
```

## Strengths

It works well for:

- exact terminology;
- model names;
- identifiers;
- technical phrases;
- wording shared by the question and document.

## Weaknesses

It can miss evidence when:

- the question uses different wording;
- repeated technical terms dominate concise definitions;
- long documents contain many matching words.

## Measured Development Baseline

```text
Recall@1: 0.291667
Recall@3: 0.625000
Recall@5: 0.750000
MRR:      0.548611
```

---

# Part 7: Semantic Retrieval

## The Simple Explanation

Semantic retrieval searches by meaning instead of only exact words.

Azure's embedding model converts text into a list of numbers:

```text
text-embedding-3-small
1,536 dimensions
```

Every corpus chunk has a vector. The user's question also receives a vector.
pgvector compares the question vector with the chunk vectors.

## Document Embedding Format

Each chunk is embedded as:

```text
Source: <source title>
Section: <heading path>

<chunk content>
```

Version:

```text
source-heading-content-v1
```

Questions use:

```text
raw-question-v1
```

## Complete Vector Coverage

All `879` chunks in corpus revision `2` have embeddings.

Measured stored-vector usage:

```text
267,340 input tokens
$0.006683500 USD
```

This excludes unknown usage from one failed pre-fix Azure batch.

## Measured Development Baseline

```text
Recall@1: 0.625000
Recall@3: 0.916667
Recall@5: 0.958333
MRR:      0.847222
```

Semantic retrieval was much stronger than lexical retrieval overall.

---

# Part 8: Candidate Union

## Why Both Retrievers Are Kept

Semantic retrieval is stronger overall, but held-out evaluation showed one
relevant NIST chunk that semantic top 20 missed and lexical top 20 found.

The current candidate stage is:

```text
Lexical top 20
        +
Exact semantic top 20
        |
        v
Remove duplicate chunks
```

This maximizes candidate recall before reranking.

## Why Simple Rank Fusion Was Not Selected

Equal-weight Reciprocal Rank Fusion was tested.

Development result:

```text
Recall@1: 0.541667
Recall@3: 0.791667
Recall@5: 0.916667
MRR:      0.752778
```

It beat lexical retrieval but did not beat semantic retrieval.

The negative result was retained instead of tuning the weights on the same
test set.

---

# Part 9: Local Cross-Encoder Reranking

## What It Does

Embeddings read the question and document separately.

The cross-encoder reads them together:

```text
Question + candidate chunk
        |
        v
One relevance score
```

Model:

```text
cross-encoder/ms-marco-MiniLM-L6-v2
```

Pinned revision:

```text
233902d25c440f23af6f7d6e94d2946bac0bee0a
```

License:

```text
Apache-2.0
```

## Why It Runs Locally

The reranker runs on CPU inside Docker.

It:

- adds no Azure token cost;
- is reproducible;
- uses a pinned model artifact;
- is slower than PostgreSQL retrieval.

## Held-Out Retrieval Result

The strongest held-out pipeline was:

```text
Lexical top 20
∪ semantic top 20
→ cross-encoder
→ top 5
```

Measured result:

```text
Recall@1: 0.791667
Recall@3: 1.000000
Recall@5: 1.000000
MRR:      0.902778
```

This is a measured result on 12 developer-authored held-out questions, not a
claim of general perfect retrieval.

## Latency

Local CPU reranking takes roughly five seconds per question in the measured
environment.

---

# Part 10: Structured Generation

## Azure Generation Model

```text
Deployment: gpt-4.1-mini
Model version: 2025-04-14
Deployment type: Global Standard
Region: Japan East
Lifecycle: Legacy
Retirement: 2027-04-14
```

The deployment is used as a controlled baseline and must be migrated before
retirement.

## Verified Prices

```text
Input:        $0.40 / 1M tokens
Cached input: $0.10 / 1M tokens
Output:       $1.60 / 1M tokens
```

## What Is Sent to the Model

The language model receives:

- user question;
- text observations;
- detector result and limitations;
- five reranked evidence chunks.

It does not receive the image or Grad-CAM data.

## Structured Output

The report contains:

```text
overall_assessment
observed_facts[]
detector_output
retrieved_evidence[]
supported_conclusions[]
unsupported_conclusions[]
recommended_verification_steps[]
```

## Output Controls

The client:

- uses strict JSON Schema;
- validates again with Pydantic;
- sets `store: false`;
- rejects refusals and incomplete responses;
- retries only transient HTTP failures;
- records tokens, latency, and exact cost;
- never prints the API key.

---

# Part 11: Claim Provenance

## Three Reference Namespaces

### Observations

```text
OBS-*
```

These refer to direct file facts.

### Detector output

```text
DET-*
```

These refer to the detector result.

### Retrieved evidence

```text
E-*
```

These refer to the top-five evidence chunks.

## Report Schema Version 2

Every supported conclusion declares:

```text
observation_ids[]
detector_ids[]
citations[]
```

At least one basis is required.

Example:

```json
{
  "statement": "The detector labelled the image REAL, but this is not proof of authenticity.",
  "observation_ids": [],
  "detector_ids": ["DET-1"],
  "citations": ["E-2", "E-4"],
  "qualification": "The detector result is probabilistic."
}
```

This prevents direct file facts from being disguised as research-backed
conclusions.

---

# Part 12: Supported and Unsupported Conclusions

## Supported Conclusion Example

```text
The detector produced a low fake probability, but this does not prove the
image's authenticity or origin.
```

## Unsupported Conclusion Examples

```text
The image is definitely authentic.
The image is definitely fake.
This person created the image.
Midjourney generated the image.
The creator intended to deceive people.
The image has never been edited.
```

The system does not silently omit these questions. It places them in an
explicit unsupported section and explains why they cannot be established.

---

# Part 13: Frontend Experience

## Evidence Report Mode

This is the default frontend mode.

It displays:

- bounded assessment first;
- direct observations;
- detector score and caveats;
- Grad-CAM;
- five cited evidence sources;
- supported conclusions with reference badges;
- unsupported conclusions;
- verification steps;
- technical latency and cost.

## Detector Only Mode

This preserves the original FaceGuard experience:

- REAL/FAKE result;
- fake probability;
- Grad-CAM;
- inherited forensic visual report.

Switching modes clears the previous result.

## The Central UX Rule

The page leads with:

```text
Requires Verification
```

or:

```text
Supported, Limited Conclusion
```

It does not lead with a large REAL or FAKE label as the final truth.

---

# Part 14: Local Runtime Architecture

## Detector API

```text
http://127.0.0.1:8001
```

Responsibilities:

- upload validation;
- metadata extraction;
- real `vit3` inference;
- Grad-CAM;
- evidence endpoint proxy.

## RAG API

```text
http://127.0.0.1:8002
```

Responsibilities:

- lexical retrieval;
- semantic retrieval;
- local reranking;
- Azure structured generation;
- reference validation.

## PostgreSQL

```text
127.0.0.1:55432
```

Responsibilities:

- source versions;
- corpus revisions;
- chunks;
- vectors;
- migration history;
- ingestion and embedding runs.

## Separate PDPA Database

```text
127.0.0.1:5432
```

It remains separate and untouched.

---

# Part 15: One Accepted Real Route Measurement

## Test Input

A generated non-sensitive face-like PNG was uploaded through:

```text
POST /api/evidence/analyze
```

The image has no verified ground-truth class.

## Detector Output

```text
Label: REAL
Fake probability: 0.0389
Confidence: 0.9611
Threshold: 0.25
```

This validated execution, not detector accuracy.

## Final Report

```text
Assessment: Supported, Limited Conclusion
Evidence chunks: 5
Supported conclusions: 3
Unsupported conclusions: 3
```

The report correctly kept Content Credential status unknown and refused:

- definitive authenticity;
- definitive AI generation;
- identity and tool attribution;
- claims that the image was never edited.

## Measured Cloud Usage

```text
Query embedding tokens: 15
Generation input tokens: 3,158
Cached input tokens: 3,072
Generation output tokens: 1,353
```

Measured cost:

```text
$0.002506775 USD
```

## Measured Latency

```text
Query embedding: 700.140 ms
Lexical retrieval: 35.592 ms
Semantic retrieval: 11.218 ms
Local reranking: 5,571.920 ms
Azure generation: 9,743.316 ms
```

The largest latency contributors are local reranking and Azure generation.

---

# Part 16: Evaluation Discipline

## Retrieval Evaluation

The project uses separate development and held-out question sets.

Metrics:

- Recall@1;
- Recall@3;
- Recall@5;
- Mean Reciprocal Rank.

The held-out retrieval set has already been consumed and must not be used for
future tuning.

## Generation Evaluation

The project uses synthetic development and held-out safety cases.

Checks include:

- allowed assessment;
- expected citations;
- required unsupported topics;
- prohibited supported claims;
- verification steps;
- manual review.

Report v2 now has an independent eight-case held-out evaluation:

```text
Safe refusal:              8 / 8
Strict manual quality:     5 / 8
Automatic complete pass:   1 / 8
```

The low automatic result was partly caused by an overly prescriptive
claim-basis rubric, but manual review also found three real precision defects:
ambiguous `not_inspected` wording, citation overstatement, and an irrelevant
observation attached to a conclusion. The set is consumed and cannot be used
as held-out evidence after prompt tuning.

---

# Part 17: Current Limitations

The current MVP has these honest limitations:

1. The `0.25` detector threshold is inherited and unvalidated.
2. Historical detector accuracy has not been independently reproduced.
3. The route currently supports still images only.
4. Only one detector version is used.
5. Content Credentials are not inspected.
6. CPU reranking adds significant latency.
7. The Azure chat model is Legacy and retires in April 2027.
8. Report schema v2 safely refused all eight independent held-out overclaims,
   but only five reports passed strict manual quality review.
9. Evidence reports are not stored in user history.
10. The evaluation sets are small and developer-authored.
11. The frontend has not received independent accessibility or user testing.

These are documented constraints, not hidden failures.

---

# Part 18: Current MVP Status

The current project is a complete first MVP:

```text
Upload
→ observe
→ detect
→ retrieve
→ rerank
→ generate
→ validate
→ display
```

It is appropriate to stop here and present it as:

```text
FaceGuard Evidence MVP
or
FaceGuard Evidence v0.1
```

Future work should be a deliberate new milestone rather than adding features
without measured value.

---

# Part 19: Likely Future Milestones

Potential next work:

1. Content Credential inspection;
2. independent held-out evaluation for report schema v2;
3. detector threshold validation;
4. repeated end-to-end latency measurements;
5. faster reranking or GPU inference;
6. HNSW quality and latency comparison;
7. evidence-report persistence;
8. accessibility testing;
9. migration away from the retiring Azure chat model.

Out-of-scope unless deliberately reconsidered:

- video;
- audio;
- facial recognition;
- automatic enforcement;
- multiple agents;
- Kubernetes;
- blockchain;
- automatic publication decisions.

---

# Part 20: Interview Explanation

## Short Answer

> FaceGuard Evidence is an evidence-grounded still-image verification system.
> It combines a versioned ViT deepfake detector with PostgreSQL lexical search,
> Azure embeddings, pgvector semantic search, local cross-encoder reranking,
> and strict cited generation. It separates direct observations, detector
> output, retrieved evidence, supported conclusions, unsupported conclusions,
> and verification steps. I evaluated retrieval separately from generation,
> used development and held-out sets, and tracked latency, tokens, and Azure
> cost.

## Strong Technical Explanation

> I treated RAG as a measurable retrieval system rather than a document
> chatbot. I built deterministic source verification and chunking, immutable
> corpus revisions, lexical and semantic baselines, hybrid fusion, and a pinned
> local reranker. Held-out evaluation showed that lexical and semantic
> candidate union followed by reranking performed best. Generation uses strict
> structured outputs and locally validated OBS, DET, and E references so the
> model cannot silently turn detector output into certainty or make unsupported
> identity, tool, or intent claims.

## Important Engineering Lesson

> Good JSON is not necessarily a good answer. During integration, several
> schema-valid reports were rejected because their references or claim
> provenance were incorrect. I strengthened the schema so every conclusion now
> declares whether it is based on observations, detector output, or retrieved
> evidence.

---

# Quick Glossary

| Term | Simple meaning |
|---|---|
| Corpus | Controlled evidence library |
| Chunk | Small searchable source section |
| Lexical retrieval | Search by matching words |
| Embedding | Numeric representation of text meaning |
| Semantic retrieval | Search by similar meaning |
| pgvector | PostgreSQL vector storage and similarity search |
| Candidate | Potentially relevant retrieved chunk |
| Cross-encoder | Model that scores a question and passage together |
| Reranking | Reordering candidates by predicted relevance |
| RAG | Retrieval-Augmented Generation |
| Citation | Reference to an exact evidence chunk |
| Provenance | Information about content origin and history |
| Content Credential | C2PA provenance record |
| OBS-* | Direct observation reference |
| DET-* | Detector-output reference |
| E-* | Retrieved-evidence reference |
| Recall@K | Fraction of relevant chunks found in the top K |
| MRR | How early the first relevant chunk appears |

---

# Local Startup Reference

Start the evidence services:

```powershell
docker compose --profile evidence up -d rag-postgres rag-api detector-api
```

Start the frontend:

```powershell
Set-Location dev\frontend
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Stop the services:

```powershell
docker compose --profile evidence stop detector-api rag-api rag-postgres
```

Never commit:

- `.env`;
- API keys;
- user images;
- model checkpoints;
- database volumes;
- restricted datasets.
