# Data and Evidence Source Register

## Purpose

This register tracks every dataset, model artifact, source repository,
evaluation record and document considered for FaceGuard Evidence.

An item appearing here is not automatically approved for ingestion,
redistribution or publication. The `Status` field records how it may currently
be used.

## Status Definitions

| Status | Meaning |
|---|---|
| Approved for retrieval | May be included in the RAG evidence corpus under the recorded conditions |
| Approved for integration | May be integrated into the application under the recorded provenance conditions |
| Reference only | May inform design or provenance but must not be ingested into the user-facing corpus |
| Private audit evidence | Retained privately for verification and not committed or published |
| External runtime artifact | Used by the system but stored outside Git |
| Pending review | Terms, provenance or suitability must be resolved before use |
| Prohibited from repository | Must not be committed to this repository |

## Current Register

| ID | Source | Type | Version or identity | Access and terms | Intended use | Repository treatment | Status |
|---|---|---|---|---|---|---|---|
| `FG-SRC-001` | Original FaceGuard repository | Source repository and website codebase | Commit `c46cc8f8170b809f7bf53bd159e81e11d7cdc9cc` | Public repository; no software license; MCS24 Team states all rights reserved; Tan reports team permission to reuse code and weights | Preserve the complete original website history before adding Tan's RAG work | Import full Git history with original authors and commits; do not copy files into a fresh commit | Approved for integration |
| `FG-MOD-001` | FaceGuard `vit3.pth` | Model checkpoint | SHA-256 `6FAE9B18A7A7BAFED65FE5A944FC1B66A8CE070896A8531C6C5857477806C25B`; `343,248,309` bytes | Tan reports team permission to reuse and redistribute; third-party lineage still applies | Initial still-image detector | Store outside Git; configure by local path or approved artifact storage | External runtime artifact |
| `FG-AUD-001` | `NIG.ipynb` | Training and evaluation notebook | SHA-256 `0091A7965AFA4E95CB952EF988B46A3886100034BD665E2FC3E9EA36A877C424` | Private copy; contains private storage paths and authentication-error output | Historical training and evaluation provenance | Do not commit the unsanitized notebook | Private audit evidence |
| `FG-EVAL-001` | Historical `vit3` notebook output | Evaluation record | Fourth completed epoch; 273,559 recorded evaluation rows | Preserved only as notebook output; raw labels and predictions were deleted | Historical context for the model card | Record as historical and not independently verified | Reference only |
| `TP-DATA-001` | AI-Face dataset and annotations | Training dataset | Version used by the original Colab workspace is not cryptographically pinned | Upstream README contains conflicting CC BY-NC and CC BY-NC-ND signals; authoritative terms require confirmation | Historical detector-training provenance; possible future controlled reevaluation | Never commit images or annotations | Prohibited from repository |
| `TP-CODE-001` | AI-Face-FairnessBench | Training source code | Exact historical Drive copy is not pinned | No repository-level license file or GitHub-detected software license found during audit | Understand original training implementation and provenance | Do not copy code until licensing is resolved | Pending review |
| `TP-CODE-002` | DeepfakeBench | Upstream benchmark code | Transitive dependency through AI-Face; exact inherited files not mapped | License and inherited-file scope require review | Transitive provenance only | Link only until scope is established | Pending review |
| `TP-MOD-001` | Torchvision ViT-B/16 ImageNet initialization | Pretrained model weights | `ViT_B_16_Weights.IMAGENET1K_V1`; downloaded file `vit_b_16-c867db91.pth` | Torchvision software terms and pretrained-weight/data terms must be assessed separately | Historical initialization of the original detector | Do not commit the pretrained artifact | Reference only |

## Candidate RAG Evidence Collections

The following source classes are required by the target system. Individual
documents must be registered and reviewed before ingestion.

### Model Documentation

Examples include:

- the versioned FaceGuard `vit3` model card;
- detector preprocessing and threshold documentation;
- independently measured evaluation reports; and
- detector adapter version and artifact-checksum records.

Model documentation is eligible for retrieval only when it identifies the
model version and distinguishes measured facts from assumptions.

### Evaluation Evidence

Evaluation sources must record:

- model artifact checksum;
- dataset or test-set identity;
- preprocessing and threshold;
- retained labels and predictions where permitted;
- metric implementation;
- hardware and software environment; and
- execution date.

Historical screenshots or copied metric values without this context are
reference material, not independently verified evaluation evidence.

### Authoritative Research

Candidate research should preferably be:

- peer-reviewed papers;
- recognized benchmark or standards publications;
- official technical reports from identified institutions; or
- primary-source documentation for a method being described.

Each research item must record its title, authors, publication venue, year,
persistent URL or DOI, document version and usage rights.

### Media-Provenance and Verification Guidance

Candidate guidance should come from identified authoritative organizations,
standards bodies or primary technical documentation. Potential subject areas
include:

- Content Credentials and C2PA;
- image metadata limitations;
- cryptographic provenance;
- reverse-image search;
- source verification; and
- responsible interpretation of synthetic-media detectors.

Guidance must not imply that missing metadata proves AI generation or that
provenance credentials prove the truth of depicted content.

## Source Acceptance Checklist

Before a document enters the retrieval corpus, record:

- [ ] stable source identifier;
- [ ] title and author or issuing organization;
- [ ] publication or retrieval date;
- [ ] version, revision or content hash;
- [ ] authoritative URL or DOI;
- [ ] license or permitted-use basis;
- [ ] whether full text may be stored;
- [ ] source category;
- [ ] model or dataset version referenced;
- [ ] known conflicts of interest or limitations;
- [ ] ingestion status; and
- [ ] review decision and reviewer.

## Storage Rules

- Public documentation approved for retrieval may be stored in a versioned
  source directory or fetched through a reproducible ingestion process.
- Restricted datasets, checkpoints and private audit evidence remain outside
  Git.
- Uploaded user images must not enter the evidence corpus.
- Secrets and private access tokens must remain in local environment
  configuration.
- Extracted text must retain enough metadata to trace every chunk to its exact
  source and version.

## Open Provenance Questions

- What authoritative terms govern the AI-Face source code separately from its
  dataset?
- Which AI-Face dataset release was present in the original Colab workspace?
- Can the exact historical `train_test_vit.py` file or its checksum be
  recovered?
- Can the selected `vit3.pth` checksum be linked to the notebook run through
  an older stored copy or artifact record?
- Which threshold will FaceGuard Evidence adopt after independent validation?
- Which research and media-provenance documents will form the first approved
  retrieval corpus?
