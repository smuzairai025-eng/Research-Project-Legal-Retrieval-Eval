# Stage 4A · BM25 retrieval prototype

The Configuration C prototype contains **890 chunks from 17 eligible PDFs**. BM25 found provisional single-chunk evidence in the top ten for **8 of 10 formal queries** and **3 of 10 everyday queries**. Evidence coverage was **9 of 10 pairs**. All relevance labels remain pending human verification.

## Frozen retrieval dataset

The pipeline regenerated the same Stage 3 prototype sample with **2,000 characters and 200 overlap**. The sample had 19 canonical candidates. Two repeal-only files contributed no chunks. The 168 chunks for the four development statutes match Configuration C in Stage 3A exactly, including IDs and provenance. Previous datasets and experiments are preserved.

Use `data/processed/prototype-c-v1/chunks.jsonl` as the shared chunk export for subsequent dense and hybrid retrieval. Its SHA-256 is `e5cbaa3bd1d8db0d38f136c9322e883a5aecd9963f926243daaf6bdff93bdbab`. The BM25 index stores this hash and the evaluator checks it against the supplied export. [Frozen chunk export](../data/processed/prototype-c-v1/chunks.jsonl) · [Processing configuration](../data/processed/prototype-c-v1/processing_config.json)

## Tokenization and scoring

- Apply Unicode NFKC, case folding, and normalization of selected curly apostrophes, quote marks, and dash characters. Other punctuation separates tokens, with exceptions for interior apostrophes, hyphens, and parenthesized suffixes on numeric identifiers. For example, `§5‑A(2)(iii)` yields `5-a(2)(iii)`, `5-a`, `5`, and `a`. A hyphenated term such as `non-payment` keeps the compound and its components. Section numbers, Roman numerals, and words such as “shall” and “not” are retained.
- Use the same tokenizer for documents and queries, without stemming, synonym expansion, or stop-word removal. This preserves legally significant terms and avoids changing statutory phrasing. Broad matches from common terms and compound components can still affect ranks. Formatting such as spaces inside a citation can change whether it also matches as a compound.
- Use BM25 with **k1 = 1.2** for term-frequency saturation and **b = 0.75** for partial chunk-length normalization. Use positive IDF, `ln(1 + (N − df + 0.5) / (df + 0.5))`, and score each distinct query token once. Chunk lengths include the emitted compound and component tokens. The parameters were fixed before inspecting the rankings.
- Return matching chunks by descending score, breaking ties by ascending chunk ID. Each result includes rank, score, chunk ID, document ID, source, jurisdiction, and inclusive PDF page bounds. The persisted inverted index can be loaded without PDF extraction.

## Development evaluation

All ten unchanged pairs from the workbook were evaluated in both formulations. Configuration C provides one provisional independently sufficient label for each covered pair. DEV-04 has partial evidence only. It contributes a zero to Hit and reciprocal rank in the all-pair summary. Recall is undefined for DEV-04. Candidate Recall divides the retrieved provisional labels by the known provisional labels per covered query, so its values here coincide with covered-pair Hit. The study has no exhaustive relevance judgments for the rest of this corpus.

| Scope and metric | Formal | Everyday | Everyday − formal |
|---|---:|---:|---:|
| All ten · Hit@5 | 0.500 | 0.200 | −0.300 |
| All ten · Hit@10 | 0.800 | 0.300 | −0.500 |
| All ten · MRR@10 | 0.4435 | 0.1375 | −0.3060 |
| Nine covered · Hit@5 / candidate Recall@5 | 0.5556 | 0.2222 | −0.3333 |
| Nine covered · Hit@10 / candidate Recall@10 | 0.8889 | 0.3333 | −0.5556 |
| Nine covered · MRR@10 | 0.4927 | 0.1528 | −0.3399 |

At cutoff five, three pairs changed from a hit to a miss and zero changed from a miss to a hit. At cutoff ten, five changed from a hit to a miss and zero changed in the other direction. Rank below is the first sufficient candidate among all lexical matches. MRR uses zero when that rank exceeds ten.

| Pair | Citation | Formal rank | Everyday rank | Rank change |
|---|---|---:|---:|---:|
| DEV-01 | [586] §4(2) | 37 | 209 | +172 |
| DEV-02 | [586] §10(1) | 6 | 32 | +26 |
| DEV-03 | [586] §10(2) | 2 | 27 | +25 |
| DEV-04 | [585] §3(1)(a)–(f) | — | — | — |
| DEV-05 | [585] §9(2)(a) | 1 | 4 | +3 |
| DEV-06 | [581] §4 | 1 | 1 | 0 |
| DEV-07 | [581] Schedule, Standing Order 4 | 8 | 159 | +151 |
| DEV-08 | [581] Schedule, Standing Order 5 | 7 | 12 | +5 |
| DEV-09 | [1487] §4 | 2 | 14 | +12 |
| DEV-10 | [1487] §37(1)–(2) | 1 | 8 | +7 |

The full lexical rankings, including scores and metadata, are saved for all 20 queries. The metrics file records per-pair deltas and both input hashes. [Questions and candidate evidence](../evaluation/development-pairs-c-v1.json) · [Individual rankings](../results/bm25-c-v1/rankings.jsonl) · [Metrics](../results/bm25-c-v1/metrics.json)

## Failure analysis

- **DEV-01:** Both queries missed the top ten. The everyday wording uses “pay period” and “longest,” while the evidence uses “wage-periods” and “shall exceed one month.” The everyday query and candidate share only five tokenizer terms, including the generic “period” and “time.”
- **DEV-03:** The formal question's top result is a contents chunk from the correct Act. Its provision terminology makes it a close lexical competitor even though the operative evidence is at rank 2. The everyday query's top result is a Factories Act chunk, and the candidate falls to rank 27.
- **DEV-04:** The two partial candidates together contain all six board roles. They appear at ranks 3 and 11 for the formal query and 16 and 26 for the everyday query. Both formulations remain single-chunk misses, including when a partial candidate appears before rank five.
- **DEV-07:** The everyday query asks about “paperwork” when a worker retires, while the source uses “service certificate” and “retirement.” Its candidate shares only four tokenizer terms with the query and falls from rank 8 to 159.
- **DEV-10:** The complete §37 candidate reaches rank 1 for the formal query and rank 8 for the everyday query. The latter ranks a Constitution chunk first despite the question being about an employment grievance.

No failure case was used to tune the tokenizer, parameters, or chunking. All ten questions are development cases and their candidate labels still need human review. The small, four-statute question set supports a descriptive comparison.

## Reproduction and verification

Run from the repository root. Use fresh paths for a rebuild because the commands protect published outputs.

```powershell
.\.venv\Scripts\python.exe -m src.legal_retrieval.preprocess --corpus 'D:\Uplaw-Data' --sample data\processed\stage3-validation\prototype-sample.json --inventory data\processed\candidate-inventory-v1\checksums.jsonl --output data\processed\prototype-c-v1 --chunk-size 2000 --chunk-overlap 200
.\.venv\Scripts\python.exe -m src.legal_retrieval.bm25 build --chunks data\processed\prototype-c-v1\chunks.jsonl --index indexes\bm25-c-v1\index.json
.\.venv\Scripts\python.exe -m src.legal_retrieval.bm25 search --index indexes\bm25-c-v1\index.json --query 'wage period' --k 5
.\.venv\Scripts\python.exe -m src.legal_retrieval.evaluate_bm25 --index indexes\bm25-c-v1\index.json --chunks data\processed\prototype-c-v1\chunks.jsonl --pairs evaluation\development-pairs-c-v1.json --output results\bm25-c-v1
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

All **19 automated tests passed**. The five new tests cover statutory tokens, a hand-calculated BM25 score, reload and provenance, tie-breaking, multiple candidate labels, and paired scoring with partial evidence. A clean rebuild reproduced the saved index, rankings, and metrics byte-for-byte. No dependencies were added.
