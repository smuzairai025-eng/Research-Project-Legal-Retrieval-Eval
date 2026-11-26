# Research decision log

## Stage 1 approved

- The study compares BM25, Gemini dense retrieval with Qdrant Cloud, and BM25–dense Reciprocal Rank Fusion on identical frozen chunks. The research question concerns paired formal and everyday prompts.
- The locked preprocessing configuration uses recursive character splitting with a 1,500-character size and 200-character overlap. Statutory section detection is optional metadata.
- The evaluation target is 20 development pairs and 80 held-out test pairs. Evidence verification and independent review are tracked separately.

## Stage 2 approved scope

- Use the 2,270 extracted PDFs as the candidate corpus. Compute SHA-256 for the candidate inventory and report exact duplicates. Extract and chunk only the prototype sample.
- Include development documents 586, 585, 581, and 1487. Verify their title and Act number on page 1. Sample across all four source folders.
- Preserve extractable text from mixed documents. A page with missing text or an extraction error ends a text run. Store original extracted and cleaned text together as separate fields in each page record.

## Stage 2 implementation decisions

- Use PyMuPDF 1.26.7 for local native-order text extraction and LangChain Text Splitters 1.0.0 for recursive splitting. Use standard-library `unittest` and SQLite for testing and checkpoints.
- Clean line endings and outer ASCII layout whitespace only. Retain hyphens, internal whitespace, punctuation, statutory identifiers, and apparent headers or footers.
- Keep the prior separator order. Capture offsets as the splitter merges fragments so repeated text retains its source position. The overlap setting is a target bounded by the separator structure. Chunk IDs include the document path-based ID, PDF checksum, method ID, and text span.
- Record duplicate checksums alongside distinct source paths. Review the research treatment of duplicated content and repeal notices before freezing the corpus.

## Stage 3 approved scope and findings

- Deduplicate by exact SHA-256, using the lexically first corpus-relative path as canonical and preserving alternate paths. Distinct hashes remain distinct candidates.
- Exclude confirmed repeal-only notices, image-only PDFs and unreadable PDFs. Retain substantive statutory text irrespective of repeal and record documented repeal evidence. Missing-text pages remain chunk boundaries.
- The single-chunk evidence audit found eight provisional matches and two pairs with split context. Candidate labels remain pending user review. The locked chunk size and overlap are unchanged.
- Use measured sample data to estimate corpus size, cost and storage. Record the token conversion and Qdrant overhead as planning assumptions.

See the [Stage 3 report](stage-3-report.md).

## Stage 3A chunking sensitivity

- Four isolated configurations were compared on the same ten development pairs and four KP statutes. A and B covered eight pairs. C and D covered nine. DEV-04 remained split, while C and D covered DEV-10 with the existing evidence criterion.
- C is recommended for approval. The locked 1,500/200 configuration remains in effect pending that decision. [Stage 3A report](stage-3a-report.md)

## Stage 4A approved decisions

- Configuration C is approved for the retrieval prototype. Use the versioned 2,000/200 chunk export as the shared BM25, dense and hybrid input. Preserve earlier exports and experiments.
- Keep DEV-04 as a single-chunk evidence coverage failure. Record both partial chunks separately. Candidate relevance labels await human verification.
- Record BM25 development scores as a descriptive baseline with fixed parameters. [Stage 4A report](stage-4a-report.md)
