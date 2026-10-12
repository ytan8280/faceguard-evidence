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

## Semantic Retriever Version 1

Retriever version `pgvector-exact-cosine-v1` uses the complete
`text-embedding-3-small` vector set for corpus revision `2`.

For each question:

1. normalize only surrounding whitespace under `raw-question-v1`;
2. request one `1,536`-dimensional Azure query embedding;
3. verify the exact registered deployment and model identity;
4. disable PostgreSQL index, index-only and bitmap scans for the ranking
   transaction;
5. calculate cosine distance against all `879` stored vectors;
6. sort by ascending distance and deterministic chunk ID;
7. return the top five chunks; and
8. score them against the unchanged judgments.

Exact ranking is intentional. It isolates semantic-model quality from
approximate-index recall. The existing HNSW index remains available for a
later latency/quality comparison.

## Lexical versus Semantic Baseline

| Metric | Lexical | Exact semantic | Change |
|---|---:|---:|---:|
| Mean Recall@1 | `0.291667` | `0.625000` | `+0.333333` |
| Mean Recall@3 | `0.625000` | `0.916667` | `+0.291667` |
| Mean Recall@5 | `0.750000` | `0.958333` | `+0.208333` |
| MRR | `0.548611` | `0.847222` | `+0.298611` |
| Zero-result questions | `0` | `0` | No change |

Semantic retrieval moved the preprocessing question from absent in the
lexical top five to rank one. The assertion/claim/manifest and hard-binding
questions moved from absent to rank three.

Semantic retrieval did not improve every individual recall value:

- `FG-RET-005` placed its second relevant attribution chunk at rank four, so
  Recall@3 fell to `0.5` while Recall@5 remained `1.0`;
- `FG-RET-010` returned only one of two relevant watermarking chunks in the
  top five, reducing Recall@5 from `1.0` to `0.5`; and
- `FG-RET-009` retained its first relevant result at rank two.

These weaknesses remain part of the measured comparison and motivate hybrid
fusion rather than replacing lexical retrieval outright.

## Semantic Cost and Latency

The 12 query embeddings used:

```text
177 input tokens
$0.000004425 USD
```

Mean query-embedding latency was `745.782 ms`, while mean exact PostgreSQL
ranking latency was `11.416 ms`. The network model call therefore dominates
semantic retrieval latency at this corpus size.

The complete result artifact is:

```text
data/evaluation/results/semantic_baseline_v1.json
SHA-256: 35E6895C24A2760A578D418921F03A15EC42E3A81278585B19DD76A3BE97B96A
```

It contains query input/vector hashes, tokens, cost, Azure latency, database
latency, cosine scores and complete top-five rankings for every question.

## Hybrid RRF Baseline

Retriever version `rrf-lexical-semantic-v1` was frozen before measurement:

```text
Lexical candidates: top 20
Semantic candidates: top 20 exact cosine
Fusion: equal-weight Reciprocal Rank Fusion
RRF constant: 60
Final evaluation: top 5
```

Rank fusion was used instead of adding raw scores because PostgreSQL
`TS_RANK_CD` scores and cosine similarities are not calibrated to the same
scale.

### Three-Way Comparison

| Metric | Lexical | Semantic | Hybrid RRF |
|---|---:|---:|---:|
| Mean Recall@1 | `0.291667` | `0.625000` | `0.541667` |
| Mean Recall@3 | `0.625000` | `0.916667` | `0.791667` |
| Mean Recall@5 | `0.750000` | `0.958333` | `0.916667` |
| MRR | `0.548611` | `0.847222` | `0.752778` |

The hybrid baseline remained better than lexical retrieval on every aggregate
metric but did not beat semantic retrieval.

Fusion helped by:

- recovering both watermarking chunks for `FG-RET-010`;
- moving the second attribution chunk into rank two for `FG-RET-005`; and
- retaining strong results for most FaceGuard and provenance questions.

Fusion hurt by:

- moving preprocessing from semantic rank one to hybrid rank two;
- moving the assertion/claim/manifest answer from semantic rank three to
  hybrid rank five;
- moving the provenance-evaluation answer from rank two to rank three; and
- pushing the hard-binding definition out of the hybrid top five.

The result is retained as a negative comparison. The RRF constant and weights
are not tuned on the same 12 questions because doing so would overfit the test
set.

The complete artifact is:

```text
data/evaluation/results/hybrid_rrf_baseline_v1.json
SHA-256: 163F90ADA3B57738E9993E2E940DFFCDC076A55ED3080368FBA481141C853876
```

It preserves all top-20 lexical candidates, all top-20 semantic candidates and
the fused top five for every question.

## Local Cross-Encoder Reranking

The first reranker is:

```text
cross-encoder/ms-marco-MiniLM-L6-v2
revision 233902d25c440f23af6f7d6e94d2946bac0bee0a
model SHA-256 821D1AA69520101D6E0737F78A042AE25B19E5CB9160701909D10434F4AEB0AE
```

It is an English MS MARCO passage-ranking model declared under Apache-2.0. The
artifact is cached outside Git and scored locally on CPU.

Two frozen candidate paths were compared:

1. semantic top-20; and
2. the deduplicated union of lexical top-20 and semantic top-20.

Each unique candidate in the union was scored once. Both paths reused those
same scores.

### Reranker Results

| Metric | Semantic baseline | Reranked semantic top-20 | Reranked union |
|---|---:|---:|---:|
| Mean Recall@1 | `0.625000` | `0.625000` | `0.625000` |
| Mean Recall@3 | `0.916667` | `1.000000` | `1.000000` |
| Mean Recall@5 | `0.958333` | `1.000000` | `1.000000` |
| MRR | `0.847222` | `0.861111` | `0.861111` |

Both top-20 candidate paths contained every judged relevant chunk, producing
mean candidate recall of `1.0`. The union therefore added candidates but no
aggregate reranking improvement on this set.

The reranker scored `386` unique query-passage pairs. `42` pairs exceeded the
512-token pair limit and truncated only the passage. The largest original pair
contained `2,806` tokens.

Mean local CPU inference latency was `4,973.689 ms` per question, excluding
retrieval. This is materially slower than exact vector ranking but requires no
additional cloud-model cost.

The result artifact is:

```text
data/evaluation/results/reranker_baseline_v1.json
SHA-256: D39719DB9881328226766DA5264540CA88ECB3E51B1B965D769B84A163E06422
```

The result is promising but must not be described as general perfect
retrieval. The evaluation set contains only 12 developer-authored questions,
and the reranker was trained on MS MARCO rather than FaceGuard or C2PA data.

## Development and Held-Out Split

The original 12 questions were inspected repeatedly during lexical, semantic,
hybrid and reranker development. They are therefore development data, not a
held-out test set.

The versioned split manifest is:

```text
data/evaluation/retrieval_split_v1.json
SHA-256: 0B8F44A33F8E35B8BBEF5C59933889E38EEF74243A72CD5DDAAE672EEAF335E6
```

It references:

| Split | Questions | SHA-256 |
|---|---:|---|
| Development | `12` | `AFCCB3E4F06CA53BA704592549AC478E1437159CB030BE1853B65753EC87FA2F` |
| Held-out | `12` | `1E106EFC4F172A1C7D6E8470EACF5C043EE892461BAAE58034226208B1A41B1D` |

Both sets contain two questions per source and are pinned to corpus revision
`2`.

The held-out questions were manually judged and validated against exact chunk
IDs before any retriever was run on them.

## Held-Out Results

| Method | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---:|---:|---:|---:|
| Lexical | `0.083333` | `0.250000` | `0.291667` | `0.250000` |
| Exact semantic | `0.583333` | `0.750000` | `0.750000` | `0.750000` |
| Hybrid RRF | `0.333333` | `0.583333` | `0.875000` | `0.576389` |
| Reranked semantic top-20 | `0.708333` | `0.916667` | `0.916667` | `0.819444` |
| **Reranked lexical/semantic union** | **`0.791667`** | **`1.000000`** | **`1.000000`** | **`0.902778`** |

The held-out set changed the candidate-path conclusion. On development data,
semantic top-20 and union reranking had identical aggregate metrics. On
held-out data, one NIST question's relevant chunk was missing from semantic
top-20 but present in lexical top-20. The union candidate set recovered it,
and the reranker placed it first.

This demonstrates that:

- semantic retrieval remains much stronger than lexical retrieval alone;
- lexical candidates can recover evidence absent from semantic candidates;
- rank fusion is weaker than cross-encoder reranking; and
- candidate recall places a hard ceiling on reranker quality.

The held-out reranker scored `394` unique pairs. `63` were passage-truncated at
512 tokens, and mean CPU inference latency was `5,228.104 ms` per question.

The held-out set has now been observed and must not be used for further tuning.
Future retrieval changes require another independent test set.
