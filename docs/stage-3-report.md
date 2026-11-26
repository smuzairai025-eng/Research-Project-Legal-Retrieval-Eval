# Stage 3 preprocessing validation and corpus eligibility

The 2,270 candidate paths reduce to **2,221 unique SHA-256 candidates**. The main Stage 3 assessment extracted a 19-document canonical prototype and 64 benchmark documents. Three of those 83 candidates were excluded. Eight of the 10 development pairs have a candidate chunk with the required context. Two have evidence split across chunks. Candidate labels await user review.

## Eligibility and duplicate handling

| Rule | Handling |
|---|---|
| Exact duplicates | Sort corpus-relative paths with forward slashes by Unicode code point, including case. Within each SHA-256 group, retain the first path and list every other path under `duplicate_source_paths`. The 6 groups account for 49 aliases. Use the canonical path for joins to the corpus manifest. |
| Similar titles and amendments | Retain distinct file hashes. Similar titles or references to the same instrument do not establish equivalence. |
| Repeal notices | Exclude an isolated notice with no substantive statutory text. The automated rule recognizes a full-document, case-insensitive match for “THIS LAW HAS BEEN REPEALED” with optional final punctuation and checks for raster images that might contain additional text. Other wording or ambiguous image/text combinations require review. The two matched Federal groups were visually confirmed. |
| Substantive repealed material | Retain the text. Record a repeal status only when a source explicitly supports it, and preserve the reference. The Industrial Relations Act, 2008 is substantive and the corpus copy of the Industrial Relations Act, 2012, §88 (PDF page 48), explicitly describes its earlier repeal. This is a source-reported historical flag. |
| Entirely image-only, unreadable, or no extractable text | Exclude from chunking. Keep the reason and any diagnostic page records. |
| Mixed and missing-text pages | Retain extractable text, record page-level statuses and break the page run at each gap. Treat images on no-text pages as a review indicator. |

Of the 83 main assessment candidates, 63 had text on every page, 13 had text with missing-text gaps, and 4 had text plus at least one image-only page. Two were repeal-only documents and one was an entirely image-only gazette. There were no unreadable documents observed in this sample. The main manifest leaves 2,138 candidates unassessed for text eligibility. A separate source-reported repeal flag records the supplemental 2008 example. [Canonical candidate manifest](../data/processed/stage3-validation/candidate_manifest.jsonl) · [Duplicate groups](../data/processed/candidate-inventory-v1/duplicates.json) · [Supplemental repeal flag](../data/processed/stage3-validation/repeal-evidence.json)

## Extraction quality observations

I compared rendered original PDF pages with the raw and cleaned text and inspected their generated chunks where available. The page references below use physical PDF numbering.

| Source and pages | Observation | Potential retrieval impact |
|---|---|---|
| KP Payment of Wages Act [586], pp. 8–9 | Body text follows the visual order in the reviewed passage. Section 7, subsection (2), clause (i) and the next numbered clauses are preserved. Clause (i) ends p. 8 after “re-payment of” and resumes p. 9 at “advances from”; the chunks split at this break. The extracted p. 9 text retains the header and a line-break hyphen in “sub-section.” | A query about the provident-fund deduction can need both neighboring chunks. Headers add noisy matches and the line-break hyphen can separate lexical tokens. |
| KP Minimum Wages Act [585], pp. 6–7 | Section 3(1)(a)–(f) survives in reading order, with a page header between the two parts. The six roles survive cleaning and are spread across chunks. | DEV-04 cannot receive an independently sufficient single-chunk label under the existing rule. |
| KP Standing Orders Act [581], p. 10 | The schedule sequence, including Standing Orders 4 and 5 and the “if any” qualifier, remains intact. The extractor encodes the possessive at “time-keeper” with U+201F, while the workbook uses U+2019. Hyphenation and the printed ampersand survive. | Exact string matching can miss equivalent punctuation. The candidate chunk still contains the two locations and the qualifier. |
| KP Industrial Relations Act [1487], pp. 33, 53 | Page 33 retains the sequence of subsections in §37, but a chunk boundary splits the qualifying grievance and its response deadline. Page 53’s schedule title, section reference and numbered entries survive as linear text. | Partial matches can retrieve the right deadline without its qualifying context. |
| Constitution, p. 175 | The printed footer appears first in the raw extraction. The pension table extracts in row order, including each label and value, but column alignment, watermark placement and superscript layout do not survive plain text. Footnotes follow the body and can share its chunk. | Numeric values remain retrievable, but row/column relationships and editorial context can become ambiguous. |
| Punjab file `100.pdf`, p. 2 | The rendered page is blank, matching its empty extraction. The neighboring text runs are separate. | Counting all empty pages as lost statutory text would overstate the loss. |
| Sindh Public Procurement Rules, pp. 64–65, and Sindh Rented Premises Ordinance, p. 14 | The inspected image-only ending pages are illustrated back covers. The mixed flag correctly marks the extraction gap, but the review found no operative provision on those image pages. | A mixed flag alone cannot establish that evidence is missing. |
| Sindh Wildlife Protection Rules, p. 1 | The rendered scan has readable gazette text and numbered provisions, while native text extraction returns empty. No extractable text was found in the 93-page PDF. | Exclusion removes any associated evidence from the searchable corpus. |

The current cleaning keeps punctuation, internal whitespace, printed headers and footers, and line-break hyphens. The reviewed pages show that native extraction can change presentation and glyph encoding before cleaning. The audit is selective and does not establish corpus-wide extraction accuracy.

## Development evidence coverage

I matched both workbook sheets by pair ID, checked the cited pages against fresh PDF extraction, and examined the chunk text in the cited source. Each row records exact evidence fragments, page references, source, stable document ID and candidate or partial chunk IDs. I used the full stated conditions when deciding whether a chunk was independently sufficient. Workbook review status is recorded separately from this review. [Development evidence mapping](../evaluation/development-evidence-stage3.json)

| Pair | Provision | PDF pages | Candidate coverage for both formulations |
|---|---|---:|---|
| DEV-01 | [586] §4(2) | 7 | One candidate, one-month limit |
| DEV-02 | [586] §10(1) | 10 | One candidate, opportunity to show cause |
| DEV-03 | [586] §10(2) | 10 | One candidate, prescribed register and deduction context |
| DEV-04 | [585] §3(1)(a)–(f) | 6–7 | Split across chunks, three partial candidates. The workbook requests recheck of the corrected six-member answer. |
| DEV-05 | [585] §9(2)(a) | 10 | One candidate, minimum wage declaration and no authority to reduce wages |
| DEV-06 | [581] §4 | 6 | One candidate, all three languages |
| DEV-07 | [581] Schedule, Standing Order 4 | 10 | One candidate, retirement and service certificate |
| DEV-08 | [581] Schedule, Standing Order 5 | 10 | One candidate, both display locations and the conditional office |
| DEV-09 | [1487] §4 | 11 | One candidate, president and secretary |
| DEV-10 | [1487] §37(1)–(2) | 33 | Split across two chunks. The deadline chunk lacks the full scope of the qualifying written grievance. |

Stage 3 retained the 1,500-character size and 200-character overlap. Before modifying chunking, review DEV-04 and DEV-10. The primary single-chunk metrics could report these as **coverage failures** alongside a separate secondary diagnostic for multi-chunk evidence. Another option is a separately approved preprocessing experiment tested on development pairs before freezing the corpus. For DEV-10, review whether §37(2) alone is sufficient for both formulations under the intended relevance definition. It supports the deadline and personal submission, while §37(1) supplies the qualifying context.

## Measured resources and planning estimates

The benchmark randomly selected 16 canonical candidates per observed source folder outside the 19-document audit, using seed 371506. The 64 benchmark PDFs had 2–182 pages and produced **1,297 pages**, **2,697 chunks**, and **3.20 million chunk characters**. Checksum verification, extraction and chunking took **3.13 seconds** in the already initialized process. The pre-benchmark working set was **85.6 MiB** and the recorded peak of the process was **127.4 MiB**, including earlier audit work. The benchmark did not export a full dataset. [Benchmark observations](../data/processed/stage3-validation/benchmark.json)

The estimates add the known audit totals to the sample means multiplied by each source folder’s remaining canonical candidate count. The sampling ranges are the 2.5th to 97.5th percentiles of 4,000 within-folder bootstrap draws with seed 371507. They reflect variability in this sample. They may understate the effect of a rare, large, or difficult PDF.

| Quantity | Planning estimate | Basis |
|---|---:|---|
| Canonical candidate pages, including excluded pages | 28,112 | Sampling range 23,119–33,791 |
| Searchable chunks | 58,909 | Sampling range 46,124–73,712 |
| Checksum, extraction and chunking | About 72 seconds | Benchmark extrapolation for candidates outside the audit. Excludes final export, cold-start overhead, and manual review. |
| Gemini document-input tokens | 17.30 million | 69.18 million estimated chunk characters divided by 4. Combining the character sampling range with 3.5–5 characters per token gives roughly 10.85–24.89 million. This is a heuristic. |
| Packed local float32 embeddings | 345 MiB | 58,909 × 1,536 × 4 bytes. Chunk-count range implies 270–432 MiB. IDs and container overhead are additional. |
| Gemini embedding input cost | US$2.59 standard or US$1.30 batch | Pricing checked on 25 Nov 2026. Combined token scenario gives US$1.63–3.73 standard and US$0.81–1.87 batch. These figures cover document inputs only. |
| Qdrant planning allowance | About 1 GiB of collection data disk per replica | One unquantized float32 vector per chunk. Raw vectors alone are 345 MiB at the point estimate. A 2× allowance for vector-side overhead plus about 86 MiB for a 1 KiB average payload with Qdrant's 1.5× disk factor gives roughly 0.76 GiB before additional headroom. Confirm actual index, payload, replication, and available capacity during the approved pilot. |

The cost estimate uses the published rates for `gemini-embedding-001` of US$0.15 per million input tokens for standard requests and US$0.075 for batch requests. Vector and payload storage use Qdrant’s documented sizing guidance plus a planning allowance. [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing/) · [Qdrant capacity planning](https://qdrant.tech/documentation/cloud/capacity-sizing/)

## Verification and recommendation

All 14 automated tests passed. They cover canonical selection, alias preservation, distinct amendments, repeal-only exclusion, retention of substantive repealed text, missing-page barriers, and the Stage 2 regressions. The reprocessed prototype contains 19 canonical candidates, 527 recorded PDF pages and 1,123 chunks. The 4 development documents retain their existing chunk IDs because the text and span method are unchanged. Page diagnostics record 97 image-only pages and 13 other no-text pages, including the pages of the excluded gazette. [Page gap log](../data/processed/stage3-validation/page-gaps.jsonl)

The preprocessing pipeline is suitable for a **limited Stage 4 retrieval prototype after review**. Before approving a frozen dataset or a final retrieval comparison, resolve DEV-04 and DEV-10, review uncertain document statuses and scan indicators, and finalize the treatment of coverage failures. This stage accessed published pricing and sizing documentation only. No Gemini or Qdrant operations were performed.
