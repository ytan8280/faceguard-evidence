# Third-Party Notices

This document records known third-party materials in the provenance chain of
the original FaceGuard detector. It is an audit record, not legal advice and
not a substitute for the authoritative license text supplied by each
rightsholder.

FaceGuard Evidence does not currently include the original training dataset,
the original detector source code, or pretrained model binaries.

## AI-Face Dataset and Benchmark

- **Project:** AI-Face: A Million-Scale Demographically Annotated
  AI-Generated Face Dataset and Fairness Benchmark
- **Authors:** Li Lin, Santosh, Mingyang Wu, Xin Wang, and Shu Hu
- **Repository:** <https://github.com/Purdue-M2/AI-Face-FairnessBench>
- **Paper:** <https://arxiv.org/abs/2406.00783>

The original FaceGuard ViT training workflow used the AI-Face dataset and code
derived from the AI-Face training implementation.

The upstream repository presents conflicting license signals:

- its README license badge links to CC BY-NC 4.0; and
- its dataset text states CC BY-NC-ND 4.0.

No repository-level `LICENSE` file or GitHub-detected software license was
present during the FaceGuard Evidence provenance audit. The license for the
dataset must not be assumed to license the accompanying source code.

Until the authoritative terms are confirmed:

- do not commit or redistribute AI-Face images or annotations;
- do not publish a modified dataset;
- do not assume commercial use is permitted; and
- do not copy AI-Face source code into this repository.

The original FaceGuard training script is substantially based on AI-Face's
`training/train_test_vit.py`, with project-specific modifications. Any future
reuse of that code requires a separate source-code licensing review and clear
attribution.

Suggested academic citation, as supplied by the upstream project:

```bibtex
@inproceedings{lin2025aiface,
  title={AI-Face: A Million-Scale Demographically Annotated AI-Generated Face Dataset and Fairness Benchmark},
  author={Li Lin and Santosh and Mingyang Wu and Xin Wang and Shu Hu},
  booktitle={Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year={2025}
}
```

## DeepfakeBench

- **Project:** DeepfakeBench
- **Repository:** <https://github.com/SCLBD/DeepfakeBench>
- **Paper:** <https://arxiv.org/abs/2307.01426>

The AI-Face project states that part of its code was adapted from
DeepfakeBench. DeepfakeBench is therefore part of the transitive provenance
chain for the original training workflow.

No DeepfakeBench code is currently included in FaceGuard Evidence. Its exact
license and the files inherited through AI-Face must be reviewed before any
training implementation is copied or adapted.

## Torchvision ViT-B/16 and ImageNet Weights

- **Software project:** Torchvision
- **Repository:** <https://github.com/pytorch/vision>
- **Architecture used:** ViT-B/16
- **Historical weight identifier:** `ViT_B_16_Weights.IMAGENET1K_V1`
- **Downloaded artifact recorded by the training notebook:**
  `vit_b_16-c867db91.pth`

The original training notebook records initialization from Torchvision's
ImageNet-pretrained ViT-B/16 weights. The Torchvision software license and the
terms associated with pretrained weights and their source data must be
considered separately.

FaceGuard Evidence does not redistribute the ImageNet dataset or the original
Torchvision pretrained weight artifact.

## Original FaceGuard Detector

- **Project:** FaceGuard: a Privacy-Preserving AI for Detecting Deepfake
  Profile Photos
- **Repository:** <https://github.com/MCS24-Team/FaceGuard-AI-Detector-MVP>
- **Audited revision:** `c46cc8f8170b809f7bf53bd159e81e11d7cdc9cc`

The original repository contains no software `LICENSE` file and describes its
original materials as MCS24 Team intellectual property with all rights
reserved. Tan Yan Yi reports explicit permission from the original group
members to reuse the original code and model weights.

That team permission applies only to rights controlled by the team. It does
not override third-party terms for datasets, pretrained weights, libraries, or
adapted implementations.

## Runtime Libraries

FaceGuard Evidence will record direct runtime dependencies, versions and
licenses when its dependency manifest is introduced. A package's inclusion in
a public package registry does not by itself establish that every associated
dataset, pretrained model or external artifact may be redistributed.

## Redistribution Policy

Unless a later verified record states otherwise, this repository will not
commit:

- third-party or restricted datasets;
- uploaded user images;
- model checkpoints or pretrained weight files;
- secrets or private environment files; or
- copied training implementations with unresolved source-code licensing.
