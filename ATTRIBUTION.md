# Attribution

## FaceGuard Evidence

FaceGuard Evidence is a personal post-graduation project by Tan Yan Yi. Its
evidence-grounded multimodal retrieval-augmented generation (RAG) components
are separate from the original FaceGuard final-year project described below.

## Original FaceGuard Project

The detector used by this project originates from:

- **Project:** FaceGuard: a Privacy-Preserving AI for Detecting Deepfake
  Profile Photos
- **Team:** MCS24 Team, Monash University Malaysia
- **Repository:** <https://github.com/MCS24-Team/FaceGuard-AI-Detector-MVP>
- **Audited revision:** `c46cc8f8170b809f7bf53bd159e81e11d7cdc9cc`

FaceGuard was collective team work and is not presented as Tan Yan Yi's sole
work. The original repository and its history remain the authoritative record
of the team project and its contributors.

The original group members explicitly agreed that Tan Yan Yi may reuse the
original code and model weights. This permission does not replace or override
the licenses and terms of third-party datasets, pretrained models, libraries,
or adapted source code.

## Tan Yan Yi's Contributions

Based on Tan Yan Yi's account, supported in part by the original repository's
Git history and project documentation, his contributions included:

- training the ViT-B/16 `vit3` detector checkpoint;
- integrating the detector with the application APIs;
- contributing to the system design;
- implementing Grad-CAM explainability;
- deploying the detector service; and
- serving as Scrum Master and Technical Lead.

These statements describe Tan Yan Yi's individual contributions without
claiming exclusive authorship of the original FaceGuard system.

## Detector Artifact

The initial detector artifact selected for FaceGuard Evidence is:

- **Filename:** `vit3.pth`
- **Size:** `343,248,309` bytes
- **SHA-256:** `6FAE9B18A7A7BAFED65FE5A944FC1B66A8CE070896A8531C6C5857477806C25B`

The checksum identifies the exact checkpoint bytes intended for use. The
checkpoint is not committed to this repository.

The original training notebook provides historical evidence that a checkpoint
named `vit3.pth` was saved after the fourth completed training epoch. It does
not contain a checksum linking that historical artifact to the checkpoint
listed above, so the byte-for-byte lineage remains unverified.

## Third-Party Materials

Third-party datasets, pretrained weights, libraries, research implementations,
and other external materials remain the property of their respective
rightsholders and are subject to their original licenses and terms.

FaceGuard Evidence will document those dependencies separately and will not
redistribute restricted datasets, user images, secrets, or model artifacts
without verified permission.
