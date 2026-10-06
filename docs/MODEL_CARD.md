# FaceGuard `vit3` Model Card

## Status

**Draft provenance record.**

This model card documents the initial detector selected for FaceGuard Evidence.
Historical measurements are included only when supported by the preserved
training notebook. They have not yet been independently reproduced by the
FaceGuard Evidence project.

## Model Summary

| Field | Value |
|---|---|
| Model name | FaceGuard `vit3` |
| Task | Binary classification of face images as real or AI-generated |
| Architecture | ViT-B/16 |
| Framework | PyTorch and Torchvision |
| Original project | FaceGuard, MCS24 Team |
| Original repository | <https://github.com/MCS24-Team/FaceGuard-AI-Detector-MVP> |
| Audited source revision | `c46cc8f8170b809f7bf53bd159e81e11d7cdc9cc` |
| Artifact filename | `vit3.pth` |
| Artifact size | `343,248,309` bytes |
| Artifact SHA-256 | `6FAE9B18A7A7BAFED65FE5A944FC1B66A8CE070896A8531C6C5857477806C25B` |

The checkpoint is stored outside this repository.

## Ownership and Attribution

The original FaceGuard detector was collective MCS24 Team work and is not
presented as Tan Yan Yi's sole work. Tan reports personally training the
`vit3` model and contributing to its integration, system design, Grad-CAM
explainability and deployment.

See [`ATTRIBUTION.md`](../ATTRIBUTION.md) and
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

## Intended Use

The detector is intended to provide one probabilistic signal for research and
educational analysis of still images containing human faces.

Within FaceGuard Evidence, its output must be combined with:

- observable image and file facts;
- retrieved model documentation and measured evaluation evidence;
- authoritative research and media-provenance guidance; and
- explicit statements of uncertainty and unsupported conclusions.

The detector score is not proof that an image is real or AI-generated.

## Out-of-Scope Uses

The detector must not be used by itself to:

- identify a depicted person;
- determine who created an image;
- attribute an image to a specific model or generation tool;
- infer intent, deception, criminality or trustworthiness;
- make automatic moderation, employment, legal or enforcement decisions;
- analyze video or audio; or
- claim certainty about an image's origin.

## Input and Inference Behavior

The audited original inference implementation records:

- RGB still-image input;
- resize to `224 x 224`;
- conversion to a PyTorch tensor;
- ImageNet normalization:
  - mean: `(0.485, 0.456, 0.406)`;
  - standard deviation: `(0.229, 0.224, 0.225)`;
- a single output logit converted with a sigmoid; and
- an optional face-cropping stage that is disabled by default.

The original service applies EXIF orientation and converts the uploaded image
to RGB before inference. FaceGuard Evidence must verify behavioral equivalence
when its detector adapter is implemented.

### Decision Threshold

The original materials are inconsistent:

- the audited source configuration defaults to `0.25`;
- the deployed Hugging Face Space records `0.5`; and
- documentation examples also use `0.5`.

FaceGuard Evidence has not yet selected a canonical threshold. The chosen
threshold must be versioned, justified with measured evaluation results and
returned with every prediction.

## Training Data Provenance

The preserved notebook records use of the AI-Face dataset and benchmark:

<https://github.com/Purdue-M2/AI-Face-FairnessBench>

The final split-generation cell selected real images from:

- FFHQ; and
- IMDB-WIKI.

It selected AI-generated or manipulated images from recorded diffusion, GAN
and deepfake source directories, including:

- CommercialTools;
- DCFACe;
- latent diffusion;
- Palette;
- Stable Diffusion 1.5 and inpainting;
- AttGAN;
- MMD-GAN;
- MSG-StyleGAN;
- StarGAN;
- STGAN;
- StyleGAN2 and StyleGAN3;
- VQGAN;
- Celeb-DF; and
- DFDC.

The exact dataset redistribution terms remain under review. No dataset images
or annotations are included in FaceGuard Evidence.

### Historical Split Construction

The final notebook cell records:

| Field | Recorded value |
|---|---:|
| Fake sampling fraction | `0.33` |
| Split sampling seed | `42` |
| Training rows | `527,076` |
| Training real rows | `263,192` |
| Training fake rows | `263,884` |
| Evaluation rows | `273,559` |
| Evaluation real rows | `74,274` |
| Evaluation fake rows | `199,285` |

The generated filenames contained `fake30`, but the final executed sampling
fraction was `0.33`. The evaluation split was materially class-imbalanced.

The exact generated CSV files are no longer available, and the notebook does
not record a train/evaluation image-overlap check.

## Historical Training Procedure

The preserved notebook records the following command-level settings:

| Setting | Recorded value |
|---|---:|
| Epochs | `10` |
| Evaluation interval | Every `2` epochs |
| Learning rate | `0.0001` |
| Training batch size | `512` |
| Evaluation batch size | `128` |
| Training workers | `12` |
| Evaluation workers | `8` |
| Optimizer | AdamW |
| Weight decay | `0.01` |
| Hardware | NVIDIA A100-SXM4-80GB |
| Initialization | Torchvision ImageNet ViT-B/16 weights |
| Downloaded weight artifact | `vit_b_16-c867db91.pth` |

The training command did not explicitly pass a model-training seed. The
audited repository script defaults to seed `5`, but the notebook copied its
training source from Google Drive without recording a Git revision or source
checksum. Seed `5` is therefore not confirmed for this run.

The notebook explicitly installed several supporting packages, but it did not
record the exact PyTorch or Torchvision versions.

## Historical Evaluation Evidence

The notebook records evaluation after every second completed epoch. It names
checkpoints using the zero-based epoch index.

| Checkpoint | Completed epoch | Loss | AUC | Accuracy | EER |
|---|---:|---:|---:|---:|---:|
| `vit1.pth` | 2 | `0.0340` | `0.99602` | `0.96758` | `0.03686` |
| `vit3.pth` | 4 | `0.0142` | `0.99756` | `0.97001` | `0.02646` |
| `vit5.pth` | 6 | `0.0056` | `0.99745` | `0.96950` | `0.02834` |
| `vit7.pth` | 8 | `0.0012` | `0.99842` | `0.97989` | `0.02147` |
| `vit9.pth` | 10 | `0.0001` | `0.99879` | `0.98056` | `0.01764` |

These are **historical notebook outputs**, not independently verified
FaceGuard Evidence results.

The original evaluation generated label and prediction arrays temporarily, but
the training script deleted the `.npy` files after calculating metrics. The
printed values cannot currently be independently recalculated.

The notebook proves that its run generated a checkpoint named `vit3.pth` after
the fourth completed epoch. Because it did not record a checkpoint checksum,
it does not prove that the currently selected artifact is byte-for-byte
identical to that historical checkpoint.

## Known Limitations and Risks

- Performance may degrade on image generators, editing methods, compression
  levels or demographic distributions not represented in training.
- The historical evaluation used an imbalanced test set.
- Dataset leakage has not been ruled out because no preserved overlap check is
  available.
- A score threshold can materially change false-positive and false-negative
  rates.
- Missing metadata is not evidence that an image is AI-generated.
- Grad-CAM highlights influential image regions but does not provide a causal
  explanation or proof of manipulation.
- High confidence does not establish identity, authorship, intent or the exact
  generation method.
- The historical metrics may not represent performance on real-world,
  post-processed or newly generated images.

## Required FaceGuard Evidence Validation

Before presenting detector performance as independently measured, FaceGuard
Evidence must:

1. implement a versioned detector adapter;
2. confirm preprocessing and output equivalence;
3. choose and document a canonical threshold;
4. evaluate the hashed checkpoint on a documented test set;
5. preserve raw labels and predictions;
6. check for train/test overlap where source data permits;
7. calculate aggregate and subgroup metrics from retained outputs; and
8. record runtime environment, latency and hardware.

Results from that work will be recorded in
[`docs/EXPERIMENTS.md`](EXPERIMENTS.md).

## Provenance Evidence

| Evidence | SHA-256 or revision |
|---|---|
| Selected `vit3.pth` artifact | `6FAE9B18A7A7BAFED65FE5A944FC1B66A8CE070896A8531C6C5857477806C25B` |
| Preserved `NIG.ipynb` notebook | `0091A7965AFA4E95CB952EF988B46A3886100034BD665E2FC3E9EA36A877C424` |
| Audited FaceGuard repository | `c46cc8f8170b809f7bf53bd159e81e11d7cdc9cc` |

The notebook is retained as private audit evidence and is not committed because
it contains private storage paths and nonessential authentication-error output.
