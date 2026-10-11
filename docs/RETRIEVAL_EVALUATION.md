# Retrieval Evaluation

## Purpose

FaceGuard Evidence evaluates retrieval separately from answer generation.

A language model can produce a fluent answer even when retrieval supplied the
wrong evidence. Measuring retrieval first makes that failure visible before
generation, citations or prompt quality can hide it.

## Versioned Question Set

The first question set is:

```text
data/evaluation/retrieval_questions_v1.json
```

It contains `12` manually reviewed questions covering all six approved
sources:

- detector configuration and preprocessing;
- measured FaceGuard experiments;
- attribution and personal/team boundaries;
- C2PA provenance guidance;
- NIST detector evaluation and watermarking tradeoffs; and
- C2PA technical definitions.

Each question records:

- one stable question ID;
- the natural-language question;
- one or more relevant chunk IDs;
- the expected source IDs;
- the human judgment rationale; and
- descriptive tags.

The question set is pinned to one exact `corpus_sha256`. Evaluation fails if a
judged chunk is absent from that corpus or belongs to an unexpected source.

Judgments are written before measuring a retriever. They must not be edited
merely because a relevant chunk received a poor rank.

## Lexical Retriever Version 1

Retriever version `postgresql-fts-v1` uses the generated weighted
`search_vector` stored with each chunk.

For each question:

1. PostgreSQL normalizes the question using the English full-text
   configuration.
2. An OR query retrieves chunks containing any normalized term.
3. `WEBSEARCH_TO_TSQUERY` creates a stricter query.
4. `TS_RANK_CD` scores the broad query.
5. Chunks matching the strict query receive an additional rank contribution.
6. Ties are resolved by deterministic chunk ID ordering.

The OR candidate query favors recall. It prevents one unmatched question word
from producing no candidates, but may retrieve high-frequency terms from
unrelated long documents.

## Metrics

### Recall@K

For one question:

```text
relevant chunks retrieved in the first K results
------------------------------------------------
total judged relevant chunks
```

A question with two relevant chunks receives Recall@1 of `0.5` when one of
them is ranked first.

Mean Recall@K averages that value across all questions.

### Mean Reciprocal Rank

For one question, reciprocal rank is:

```text
1 / rank of the first relevant chunk
```

It is zero when no relevant chunk occurs within the retrieved result list.
Mean Reciprocal Rank averages the per-question values.

MRR rewards placing at least one relevant result near the top. Recall@K also
captures whether all judged evidence for a question was retrieved.

## Running the Baseline

From the repository root:

```bash
python tools/evaluate_lexical_retrieval.py \
  --output data/evaluation/results/lexical_baseline_v1.json
```

The result artifact contains:

- question-set and corpus identities;
- retriever version;
- aggregate metrics;
- per-question latency;
- first relevant rank;
- Recall@1, Recall@3 and Recall@5;
- each returned chunk ID and source;
- PostgreSQL score; and
- whether each result matched the strict query.

## Baseline Interpretation

`FG-EXP-010` records the measured results. The lexical baseline retrieved at
least one candidate for every question, but it missed the relevant chunk
within the top five for:

- detector preprocessing;
- the assertion/claim/manifest relationship; and
- the C2PA hard-binding definition.

The technical C2PA specification contains many repeated terms. Long,
term-dense chunks can outrank short glossary definitions even though the
definition is more directly relevant.

These failures are retained as the baseline for later experiments involving:

- lexical query refinement;
- semantic retrieval with pgvector;
- hybrid rank fusion; and
- reranking.
