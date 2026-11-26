# Stage 3A · Development evidence coverage and chunking sensitivity

**Recommendation: configuration C, 2,000 characters with 200 overlap, for approval.** It covered nine of the ten development pairs, tied with D, and used the fewest input characters. It recovered DEV-10 with the original evidence criterion. DEV-04 remains a single-chunk coverage failure under all four settings.

## Method

All four runs reused the same **104 cleaned PDF pages from the four verified KP documents** and the ten Stage 3 development pairs. Only chunk size and overlap changed. The splitter, separators, page boundaries and evidence content were held fixed. A reproduced the existing prototype's chunk text, IDs, offsets, page ranges, and candidate labels for these documents.

I matched the required evidence fragments within each cited source and page range, then inspected the boundary cases. For DEV-03, I checked for the operative description of damage caused by the employee's neglect or default. The first pass used the section heading as a proxy and missed one complete candidate under B. The operative description establishes the same antecedent, so I applied that check to all four runs. The first pass is preserved in `stage3a-v1`. All findings below use the reviewed outputs in `stage3a-v2`.

## Measured sample results

| Config | Size / overlap | Chunks | Mean length, characters | Estimated tokens | Pairs with one or more sufficient chunks | Repeated source characters |
|---|---:|---:|---:|---:|---:|---:|
| A | 1,500 / 200 | 199 | 1,180.4 | 58,724 | 8/10 | 16,160 (6.9%) |
| B | 1,500 / 400 | 211 | 1,225.4 | 64,639 | 8/10 | 39,819 (15.4%) |
| C | 2,000 / 200 | 168 | 1,369.6 | 57,523 | 9/10 | 11,355 (4.9%) |
| D | 2,000 / 400 | 168 | 1,447.9 | 60,810 | 9/10 | 24,506 (10.1%) |

Token estimates use total chunk characters divided by four. Repeated source characters count overlap between consecutive chunk spans within each page run and are expressed as a share of all indexed characters.

### Candidate chunks by pair

IDs are abbreviated in the table. Each run's evidence file contains complete IDs, offsets, physical PDF page ranges, and partial evidence. A dash means no independently sufficient candidate. [A evidence](../data/processed/stage3a-v2/A/evidence.json) · [B evidence](../data/processed/stage3a-v2/B/evidence.json) · [C evidence](../data/processed/stage3a-v2/C/evidence.json) · [D evidence](../data/processed/stage3a-v2/D/evidence.json)

| Pair | A | B | C | D |
|---|---|---|---|---|
| DEV-01 | `e604a432c92b` | `3db6e44d472a` | `96bc31fb9ea6` | `1730d9c9c4ea` |
| DEV-02 | `ae698dc15944` | `424560604d0a`, `7ce14f7c9df7` | `f2b7038d0be2` | `f769f1ca18b2` |
| DEV-03 | `ae698dc15944` | `7ce14f7c9df7` | `f2b7038d0be2` | `f769f1ca18b2` |
| DEV-04 | — | — | — | — |
| DEV-05 | `0424982689c5` | `025f82ff19c0` | `27385f1f6db3` | `0954fc4d747d` |
| DEV-06 | `f7011754f2c8` | `2ffa8eff62ea`, `4f9291160841` | `3a09867186ad` | `76c2e0c0c97a` |
| DEV-07 | `f9ec2e439dc5` | `5d38a96f99fb` | `84df01c38ed3` | `a6770774c1ab` |
| DEV-08 | `f9ec2e439dc5` | `5d38a96f99fb` | `84df01c38ed3` | `a6770774c1ab` |
| DEV-09 | `fdfe6ce34d1a` | `67a518f5d7b7` | `f16a8cb8d147` | `ea79e968048d` |
| DEV-10 | — | — | `e4f15fb64f0e` | `613d36b0a9c5` |

### DEV-04 · Minimum Wages Act §3(1)(a)–(f), PDF pages 6–7

Clauses (a)–(d) appear on page 6 and clauses (e)–(f) on page 7. Every configuration leaves those two groups in separate, page-specific chunks. A and B each yield three partial candidates, including a second page 6 chunk repeating clauses (a)–(b). C and D each yield two partial candidates, one per page. The full list is available when the two portions are read together. Under the single-chunk criterion this remains a coverage failure. A separate multi-chunk diagnostic could capture this case without changing the primary criterion.

### DEV-10 · Industrial Relations Act §37(1)–(2), PDF page 33

Both questions ask for the period for a written decision when a worker personally submits a written grievance about a right secured by law, an award, or a settlement. **Section 37(2) alone supplies the 15-day deadline, the personal-submission trigger, and the employer's written decision.** It refers to “his grievance” without stating the worker's written submission or the qualifying right. A reader can extract the short answer from §37(2) alone. Independent evidence for both complete formulations requires §37(1) as well.

A and B split those two parts. C and D capture both in the same page 33 chunk, with identical offsets (64,939–66,864) and text. The following provision gives a different deadline for submission through a representative, which is an additional reason to retain the personal-submission condition in the evidence criterion.

### Evidence duplication

B yields two overlapping complete candidates each for DEV-02 and DEV-06. Those repetitions add no covered pair relative to A. A, C and D each have just one complete candidate per covered pair. D repeats more than twice as many source characters as C while covering the same pairs with the same chunk count. Shared candidates for distinct questions, such as DEV-07 and DEV-08, are one indexed chunk and do not add duplicated indexing input.

## Estimated full-corpus indexing impact

The A baseline comes from Stage 3. Each variant's projected total tokens are the baseline scaled by its four-document character ratio. Vector counts are scaled by its chunk-count ratio. Raw storage assumes one 1,536-dimensional float32 vector per chunk. It excludes IDs, index overhead, payloads, and replication.

| Config | Estimated vectors | Raw vector storage | Estimated input tokens | Standard cost | Batch cost |
|---|---:|---:|---:|---:|---:|
| A | 58,909 | 345 MiB | 17.30 M | US$2.59 | US$1.30 |
| B | 62,461 (+6.0%) | 366 MiB | 19.04 M (+10.1%) | US$2.86 | US$1.43 |
| C | 49,732 (−15.6%) | 291 MiB | 16.94 M (−2.0%) | US$2.54 | US$1.27 |
| D | 49,732 (−15.6%) | 291 MiB | 17.91 M (+3.6%) | US$2.69 | US$1.34 |

Google lists `gemini-embedding-001` at US$0.15 per million input tokens for standard requests and US$0.075 for batch. These scenarios estimate document-input charges only. Four KP statutes are a small sample for estimating the relative effect across the full corpus. Similarity search performance, actual token consumption, and managed index costs remain unmeasured. [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing/)

## Reproduction and decision

Each run has its own configuration, chunk export and evidence mapping under `data/processed/stage3a-v2/`. All 14 existing tests passed. A clean replay reproduced every output byte-for-byte. [Run summary](../data/processed/stage3a-v2/summary.json)

```powershell
.\.venv\Scripts\python.exe -m src.legal_retrieval.chunking_sensitivity --output data\processed\stage3a-replay
```

C improves development evidence coverage over A with fewer vectors and slightly less text to embed. The tradeoff is a longer average chunk, which may affect retrieval ranking and is still unmeasured. The production setting remains A pending approval. The Stage 3 prototype remains intact, and no Gemini requests, Qdrant operations, full-corpus regeneration, or Stage 4 work were performed.
