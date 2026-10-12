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
| `FG-DOC-001` | FaceGuard `vit3` model card | Internal model documentation | SHA-256 `5284318A3A8403ECBED991D78BC87039CE63FB09E995FB036FAE79D412C58862` | Project-authored provenance record with original-team and third-party attribution | Explain model identity, intended use, preprocessing, historical evidence and limitations | Ingest committed `docs/MODEL_CARD.md`; preserve headings and tables | Approved for retrieval |
| `FG-DOC-002` | FaceGuard Evidence experiment log | Internal measured evidence | SHA-256 `0621346F3401C42C62756AA7B8DCFC60E84C376B2520AD51D1BA0145A82D0B71` | Project-authored experiment records; user images and raw generated outputs excluded | Retrieve actual measured baseline, checkpoint, inference and adapter results | Ingest committed `docs/EXPERIMENTS.md`; treat each experiment as a separate top-level unit | Approved for retrieval |
| `FG-DOC-003` | FaceGuard attribution record | Internal provenance documentation | SHA-256 `B9F1C636C3729247120E8F0EAAD6A3212CDAB70EFC9F8BC0001A97393162132D` | Project-authored record based on preserved Git history and Tan's reported contribution statement | Answer ownership and contribution questions without presenting collective work as Tan's sole work | Ingest committed `ATTRIBUTION.md`; retain links to original repository and team context | Approved for retrieval |
| `TP-DATA-001` | AI-Face dataset and annotations | Training dataset | Version used by the original Colab workspace is not cryptographically pinned | Upstream README contains conflicting CC BY-NC and CC BY-NC-ND signals; authoritative terms require confirmation | Historical detector-training provenance; possible future controlled reevaluation | Never commit images or annotations | Prohibited from repository |
| `TP-CODE-001` | AI-Face-FairnessBench | Training source code | Exact historical Drive copy is not pinned | No repository-level license file or GitHub-detected software license found during audit | Understand original training implementation and provenance | Do not copy code until licensing is resolved | Pending review |
| `TP-CODE-002` | DeepfakeBench | Upstream benchmark code | Transitive dependency through AI-Face; exact inherited files not mapped | License and inherited-file scope require review | Transitive provenance only | Link only until scope is established | Pending review |
| `TP-MOD-001` | Torchvision ViT-B/16 ImageNet initialization | Pretrained model weights | `ViT_B_16_Weights.IMAGENET1K_V1`; downloaded file `vit_b_16-c867db91.pth` | Torchvision software terms and pretrained-weight/data terms must be assessed separately | Historical initialization of the original detector | Do not commit the pretrained artifact | Reference only |
| `EXT-STD-001` | C2PA Technical Specification | Media-provenance standard | Version `2.3`; tag commit `6998a277b4519fc652550686861f0b97a64e5c19`; final release published 2026-01-11 | Coalition for Content Provenance and Authenticity; CC BY 4.0 | Explain Content Credentials, manifest validation, cryptographic binding and provenance limitations | Commit normalized text snapshot and metadata from the official versioned source; retain attribution and license | Approved for retrieval |
| `EXT-GUIDE-001` | C2PA and Content Credentials Explainer | Official media-provenance guidance | Version `2.3`; same release commit as `EXT-STD-001` | Coalition for Content Provenance and Authenticity; CC BY 4.0 | Provide accessible guidance that credentials describe tamper-evident provenance rather than truth | Commit normalized text snapshot and metadata from the official versioned source; retain attribution and license | Approved for retrieval |
| `EXT-REPORT-001` | *Reducing Risks Posed by Synthetic Content: An Overview of Technical Approaches to Digital Content Transparency* | Government technical report | NIST AI 100-4; DOI `10.6028/NIST.AI.100-4`; published 2024-11-20 | NIST Technical Series; NIST grants worldwide royalty-free reuse rights for employee-authored technical publications with acknowledgment | Explain detection, provenance, watermarking, metadata and responsible risk interpretation | Commit normalized text snapshot and metadata from the official DOI/PDF; acknowledge NIST and preserve notices | Approved for retrieval |
| `EXT-RES-001` | *DeepfakeBench: A Comprehensive Benchmark of Deepfake Detection* | Peer-reviewed benchmark paper and associated code | arXiv `2307.01426v2`, updated 2023-10-28; NeurIPS 2023 Datasets and Benchmarks; repository current main observed at `f188b1c105465e2e5377eb536a95022ae0e4522d` | Repository code is CC BY-NC 4.0; paper full-text reuse terms were not established by the repository license | Candidate evidence about standardized preprocessing, metrics and cross-dataset evaluation | Record metadata and links only until paper reuse terms and the exact proceedings identity are confirmed | Pending review |

## Initial Retrieval Corpus v0

The first corpus is intentionally limited to six approved documents:

1. `FG-DOC-001` - versioned model identity and limitations;
2. `FG-DOC-002` - measured FaceGuard Evidence experiments;
3. `FG-DOC-003` - ownership and contribution boundaries;
4. `EXT-STD-001` - normative media-provenance standard;
5. `EXT-GUIDE-001` - accessible explanation of that standard; and
6. `EXT-REPORT-001` - authoritative synthetic-content risk and transparency
   research.

This is a mixed corpus: project-specific evidence can answer questions about
the actual detector, while external sources can explain what detection and
provenance can and cannot establish.

`EXT-RES-001` is not part of corpus v0. Public access and a code license do not
automatically establish permission to redistribute or commit a paper's full
text. It may be reconsidered after its publication identity and reuse terms
are verified.

### Snapshot Storage Decision

Approved external sources will be preserved under `data/sources/<source-id>/`
as normalized UTF-8 text plus source metadata. Raw downloaded PDFs and HTML
will not be committed.

Each source snapshot must record:

- source ID;
- exact title and issuing organization or authors;
- version or revision;
- canonical URL or DOI;
- retrieval date;
- applicable license or permitted-use basis;
- original downloaded-content SHA-256;
- normalized-text SHA-256;
- normalization steps and tool version; and
- any removed non-content elements.

Normalized source snapshots are inputs to ingestion. They are not pre-made
chunks. Tan's ingestion code must read the source metadata and generate chunks
reproducibly.

### Captured Snapshot Identities

| Source ID | Retrieval time (UTC) | Original SHA-256 | Normalized SHA-256 |
|---|---|---|---|
| `EXT-GUIDE-001` | `2026-10-06T16:15:32+00:00` | `C40695D9091A21853D32BDA7AF05317CB1B5447D6C2498CDB6F27D7449A68775` | `EA688ECCEC74CB763FBDEA8814D6A52BF7626AB9FE104FF67C50926479540049` |
| `EXT-REPORT-001` | `2026-10-06T16:15:36+00:00` | `A387A4977DB70D65CDBC178C8B0CB8AA5DEDB85FA80D6F473C244E2767A4FD54` | `3FDE169446464461B89279CF8019D249EA2FCA7E4AA41F90949F3EC9F3F2915D` |
| `EXT-STD-001` | `2026-10-06T16:15:38+00:00` | `C8C3DD79C68DF36042D1DA1719BBF7662493D53C7410D5F50C32010131D2ECA0` | `921DFD0AFF4C55278C57FDD823A236DAECED9336DE450156B5B02BC3C94C240F` |

The capture utility verifies each original hash before replacing a snapshot.
An upstream change therefore stops recapture for review instead of silently
changing the corpus.

### Selection Notes

- C2PA `2.3`, not the browsable `2.4` path, was selected because the official
  C2PA repository identifies `2.3` as its latest final release.
- The C2PA explainer explicitly states that Content Credentials validate
  provenance structures and associations, not whether depicted claims are
  true.
- NIST AI 100-4 is an identified technical-series publication with a
  persistent DOI and explicit reuse guidance.
- DeepfakeBench remains useful research, but its code's CC BY-NC 4.0 license
  must not be misreported as Apache 2.0 or assumed to govern the paper.

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
