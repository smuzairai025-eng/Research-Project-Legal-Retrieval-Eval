# Stage 2 preprocessing prototype

The candidate inventory contains 2,270 PDFs. Native text extraction and chunking ran on 20 selected PDFs across all four source folders. The prototype recorded 530 PDF pages, including 526 pages with extractable text, and produced 1,128 chunks. Eight chunks span two adjacent pages.

## Sample and selection

For development documents 586, 585, 581 and 1487, the extracted first page matched both the expected title and the printed Act number. The sample covers 1–176 pages per PDF, including numbered Punjab files, statute and rules compilations, schedules and amendment markings. For example, the Payment of Wages Act continues the deductions provision over PDF pages 8–9. Individual selection reasons and exact filenames are in the [sample configuration](../configs/stage2-sample.json).

| Source | Prototype PDF | PDF pages | Chunks |
|---|---|---:|---:|
| KP | Payment of Wages Act, 2013 [586], Act IX of 2013 | 17 | 30 |
| KP | Minimum Wages Act, 2013 [585], Act XII of 2013 | 13 | 25 |
| KP | Industrial and Commercial Employment (Standing Orders) Act, 2013 [581], Act XI of 2013 | 21 | 43 |
| KP | Industrial Relations Act, 2010 [1487], Act XVI of 2010 | 53 | 101 |
| KP | Factories Act, 2013 [1488] | 38 | 89 |
| KP | Right to Information Act, 2013 [590] | 18 | 32 |
| Federal | Constitution of the Islamic Republic of Pakistan | 176 | 415 |
| Federal | Payment of Wages Act, 1936 | 15 | 32 |
| Federal | Industrial and Commercial Employment (Standing Orders) Ordinance, 1968 | 18 | 43 |
| Federal | Agricultural Development Bank Ordinance filename, 21-file duplicate group | 1 | 1 |
| Federal | Banking Companies (Recovery of Loans, Advances, Credits and Finances) Act filename, 26-file duplicate group | 1 | 1 |
| Punjab | `100.pdf`, Punjab Land Dispositions (Saving of Shamilat) Ordinance, 1959 | 4 | 5 |
| Punjab | `1251a.pdf`, Workers’ Children (Education) Ordinance, 1972 | 3 | 7 |
| Punjab | `10.pdf`, Provincial Small Cause Courts Act, 1887 | 14 | 37 |
| Punjab | `237.pdf`, Punjab Privy Purses (Charged Expenditure) Ordinance, 1969 | 3 | 3 |
| Punjab | `237(1).pdf`, exact copy of `237.pdf` | 3 | 3 |
| Sindh | Sindh Consumer Protection Act, 2014 | 35 | 68 |
| Sindh | Sindh Right of Children to Free and Compulsory Education Act, 2013 | 14 | 28 |
| Sindh | Sindh Public Procurement Rules, 2010, amended compilation | 65 | 131 |
| Sindh | Sindh Criminal Prosecution Service Act, 2009, with rules | 18 | 34 |
| **Total** | **20 files** | **530** | **1,128** |

## Extraction and duplicate findings

- There were zero extraction errors and zero document-level exclusions. Sindh Public Procurement Rules was flagged as mixed because PDF page 65 has images and no extractable text. PDF page 2 of each of `100.pdf`, `237.pdf` and `237(1).pdf` had no extractable text or detected images. All four gaps are recorded in [pages.jsonl](../data/processed/prototype-v1/pages.jsonl).
- SHA-256 succeeded for all 2,270 files. Six groups contain 55 member files and 49 copies beyond one member per group. The group sizes are 21 and 26 in the Federal folder and 2 each in four Punjab groups. Both sampled Federal groups consist of identical byte copies within their respective group. The two sampled representatives each extract only the words “THIS LAW HAS BEEN REPEALED.” They remain in the prototype as extractable text and are flagged here for statutory eligibility review. The pipeline recorded both sampled members of the Punjab pair under distinct source IDs. [Duplicate groups](../data/processed/candidate-inventory-v1/duplicates.json)

## Sample chunks

These whitespace-normalized excerpts come from the exported chunks. Offsets refer to the unmodified chunk text in the corresponding page run.

| Chunk record | Source and jurisdiction | PDF pages | Run-relative offsets | Excerpt near the page break |
|---|---|---|---|---|
| [Line 1](../data/processed/prototype-v1/chunks.jsonl#L1) | Payment of Wages Act [586], Khyber Pakhtunkhwa | 1–2 | 0–1292 | “21. Procedure in trial of offences. 2 \| P a g e 22. Bar of suits.” |
| [Line 199](../data/processed/prototype-v1/chunks.jsonl#L199) | Industrial Relations Act [1487], Khyber Pakhtunkhwa | 52–53 | 111401–112314 | “(Khyber Pakhtunkhwa Ordinance No. III of 2010) is hereby repealed. SCHEDULE PUBLIC UTILITY SERVICES [See section 2(xxiv)]” |

| Record | Document ID | Chunk ID |
|---|---|---|
| 1 | `cf23b3f52d0783cd61853ec048fd46f05e1809529fecef9dc62dab661d361b4b` | `4c8dc311f4da24a7e741cb079ea6fba4b76e928af30435c292bd21de046fba86` |
| 199 | `79bed8e4c849906373cac308e641b98c6f5797ac75b8919fb469945af41c9069` | `fefed564c0a876b7eb45cb87d79f2ca9e295be92ef1646aefc7e3dde5c6f93a2` |

## Verification and limitations

All 11 tests passed, including simulated interruption and resumption, exact offsets for repeated page text, same-name files, and document exclusions. `pip check` found no broken requirements. An independent check reconstructed page runs from the exports and verified every chunk span, inclusive page range, maximum chunk length, overlap bound and non-whitespace coverage. Record keys were unique. Rerunning the published prototype left all output file checksums unchanged.

The extractor uses native PDF text order. Tables, multi-column text, page furniture, embedded font mappings and scanned material can affect readability and evidence coverage. The mixed flag detects an image on a page with no extractable text as a scan indicator. It can miss partially scanned content on a page that also contains extractable text. A text-bearing document can contain only a repeal notice or omit a provision. The separators can produce less than 200 characters of overlap and can split an actual cross-page provision. Candidate files beyond the 20-document sample have checksum coverage only.

## Proposed Stage 3 validation

1. Compare a manually selected set of source pages with raw text, cleaned text and chunks. Include clauses crossing page breaks, repeated language, schedules, and all four development documents.
2. Audit a stratified set of source PDFs for mixed pages, OCR layers, poor reading order, and filename-to-title mismatches. Record the criteria and any false classifications.
3. Review whether duplicate content and repeal-only notices should remain eligible before any corpus freeze. Estimate how these choices could affect retrieval and relevance labels.
4. Measure prototype resource use by source and PDF-length range. Estimate full-corpus runtime, disk usage, and checkpoints with explicit uncertainty. Apply any approved eligibility or extraction changes in a new version.
