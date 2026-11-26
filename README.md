# Evaluating Linguistic Robustness of Lexical, Dense, and Hybrid Retrieval for Pakistani Statutory Question Answering

This project measures how meaning-preserving changes from formal legal English to everyday English affect retrieval of supporting Pakistani statutory passages. Stage 2 builds and tests a local preprocessing prototype from an explicit sample.

## Reproduce the prototype

Run these commands from the project root in PowerShell with Python 3.12.6. The final command documents the historical Stage 2 run. Use the Stage 3 command below with the current eligibility rules.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-stage2.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.legal_retrieval.corpus --corpus 'D:\Uplaw-Data' --output data\processed\candidate-inventory-v1
.\.venv\Scripts\python.exe -m src.legal_retrieval.preprocess --corpus 'D:\Uplaw-Data' --sample configs\stage2-sample.json --inventory data\processed\candidate-inventory-v1\checksums.jsonl --output data\processed\prototype-v1
```

The inventory reads candidate files for SHA-256 checksums. The preprocessing command extracts text from the listed sample PDFs, checks each sample checksum against the inventory, and commits one complete document at a time to SQLite under `data/processed/.checkpoints/`. Rerun with the same inputs to resume. The command publishes the dataset directory when all document checkpoints are present, and a published version with matching inputs is reused. Changing the inputs or configuration requires a new version name.

## Outputs

| File | Contents |
|---|---|
| `checksums.jsonl` | Candidate paths and file SHA-256 checksums |
| `duplicates.json` | Groups of byte-identical candidate PDFs |
| `corpus_manifest.jsonl` | Sample source, checksum, identity, eligibility and extraction counts |
| `pages.jsonl` | One record per enumerated page with original extracted text in `raw_text` and its cleaned copy in `cleaned_text` |
| `chunks.jsonl` | Chunk text, source, jurisdiction, deterministic IDs, and page provenance |
| `excluded_documents.csv` | Documents that could not supply extractable text, with reasons |
| `processing_config.json` | Dataset version, exact sample, dependency versions, and method settings |

PDF page numbers are one-based. Chunk offsets are zero-based with an exclusive end, relative to the consecutive run of cleaned pages beginning at `run_page_start`. The run joins pages with two newline characters. Pages without usable text break the run. Jurisdiction labels derive from the source folder and should be checked against the instrument where accuracy matters.

See the [research decision log](docs/research-decision-log.md) and [Stage 2 report](docs/stage-2-report.md).

## Reproduce the Stage 3 corpus audit

Use the existing candidate inventory and a fresh audit output directory.

```powershell
New-Item -ItemType Directory -Path data\processed\stage3-audit-repeat
.\.venv\Scripts\python.exe -m src.legal_retrieval.validate_corpus --corpus 'D:\Uplaw-Data' --output data\processed\stage3-audit-repeat
```

The benchmark uses a fixed seed. Timing and peak working set can vary. See the [Stage 3 report](docs/stage-3-report.md) and [development evidence mapping](evaluation/development-evidence-stage3.json).
