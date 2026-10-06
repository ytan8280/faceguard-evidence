# Experiments

This file records experiments run specifically for FaceGuard Evidence.
Results must be measured, reproducible and linked to the relevant code, data,
model and configuration versions.

Historical values copied from the original FaceGuard notebook do not count as
FaceGuard Evidence experiments. They are documented separately in
[`MODEL_CARD.md`](MODEL_CARD.md).

## Experiment Record Requirements

Every experiment entry must include:

- experiment identifier and date;
- question or hypothesis;
- code revision;
- model and artifact versions;
- dataset or query-set identity;
- configuration and random seed;
- hardware and software environment;
- procedure;
- raw-output location;
- measured results;
- interpretation;
- limitations; and
- next decision.

Do not record estimated, expected or invented values as results.

## Experiment Index

| ID | Date | Experiment | Status | Result |
|---|---|---|---|---|
| - | - | No FaceGuard Evidence experiments completed yet | Not started | No measured result |

## Planned Experiment Areas

These are plans, not results:

1. detector-adapter equivalence against the pinned original implementation;
2. detector latency on the selected local or hosted environment;
3. PostgreSQL full-text retrieval baseline;
4. pgvector semantic-retrieval baseline;
5. hybrid-fusion comparison;
6. reranking comparison;
7. retrieval evaluation using a versioned question set;
8. generation evaluation using supported-claim and citation checks; and
9. Azure token, latency and cost measurement.

Planned work remains in this section until it has been executed and measured.
