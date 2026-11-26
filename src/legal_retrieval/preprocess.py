"""Build a versioned preprocessing prototype from an explicit PDF sample."""

import argparse
from collections import Counter
import csv
from hashlib import sha256
from importlib.metadata import version
from itertools import groupby
import json
import logging
from pathlib import Path
import platform
import sqlite3
from tempfile import TemporaryDirectory

from .corpus import JURISDICTIONS, canonical_candidates, pdf_checksum, stable_id
from .pdf_loader import extract_pdf
from .text_splitter import CHUNK_OVERLAP, CHUNK_SIZE, PAGE_SEPARATOR, SEPARATORS, split_page_run

logger = logging.getLogger(__name__)

SETTINGS = {
    "pipeline_revision": 2,
    "eligibility": "exact duplicate canonical path, exact repeal-only notice exclusion, text eligibility",
    "extraction": "pymupdf.get_text(text), native order",
    "cleaning": "line endings and outer ASCII layout whitespace",
    "missing_text": "break page run",
    "chunk_size": CHUNK_SIZE,
    "chunk_overlap": CHUNK_OVERLAP,
    "separators": SEPARATORS,
    "page_separator": PAGE_SEPARATOR,
    "keep_separator": "start",
    "strip_chunk_whitespace": False,
    "page_number_base": 1,
}


def prepare_sources(
    root: Path, sample: list[dict], checksums: dict[str, str | None],
    duplicate_paths: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Validate explicit sample paths and match each to the candidate inventory."""
    sources = []
    seen = set()
    root = root.resolve()
    for entry in sample:
        source = entry["source"]
        path = (root / source).resolve()
        if not path.is_relative_to(root) or path.relative_to(root).as_posix() != source:
            raise ValueError(f"Expected a canonical corpus-relative path: {source}")
        if source in seen or path.suffix.lower() != ".pdf":
            raise ValueError(f"Repeated source or non-PDF sample entry: {source}")
        jurisdiction = JURISDICTIONS.get(source.split("/")[0])
        if jurisdiction is None:
            raise ValueError(f"Unknown source folder: {source}")
        if source not in checksums:
            raise ValueError(f"Sample source missing from inventory: {source}")
        checksum = checksums[source]
        try:
            actual_checksum = pdf_checksum(path)
        except OSError:
            if checksum is not None:
                raise
            actual_checksum = None
        if actual_checksum != checksum:
            raise ValueError(f"PDF changed since candidate inventory: {source}")
        seen.add(source)
        sources.append({
            **entry, "source": source, "jurisdiction": jurisdiction, "sha256": checksum,
            "document_id": stable_id("document", source),
            "duplicate_source_paths": (duplicate_paths or {}).get(source, []),
        })
    if not sources:
        raise ValueError("The sample is empty")
    return sources


def preprocess_document(
    root: Path, source: dict, method_id: str, *,
    chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP,
) -> dict:
    """Extract pages, split consecutive text runs, and assemble document records."""
    pages, status, error = extract_pdf(root / source["source"])
    identity_page = None
    if "development_document" in source:
        first_page = " ".join(pages[0]["raw_text"].casefold().split()) if pages else ""
        if source["title"].casefold() not in first_page or source["act_number"].casefold() not in first_page:
            raise ValueError(f"Development title or Act number could not be verified: {source['source']}")
        identity_page = 1
    metadata = {key: source[key] for key in ("source", "jurisdiction", "document_id")}
    page_counts = Counter(page["status"] for page in pages)
    chunks = []
    for has_text, run in groupby(pages, key=lambda page: not error and page["status"] == "text"):
        if not has_text:
            continue
        text_pages = [(page["page_number"], page["cleaned_text"]) for page in run]
        run_start = text_pages[0][0]
        for text, start, end, page_start, page_end in split_page_run(
            text_pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        ):
            chunks.append({
                **metadata,
                "chunk_id": stable_id(
                    "chunk", metadata["document_id"], source["sha256"] or "",
                    method_id, run_start, start, end,
                ),
                "text": text,
                "page_start": page_start,
                "page_end": page_end,
                "run_page_start": run_start,
                "start_offset": start,
                "end_offset": end,
            })
    manifest = {
        **source, "status": status, "error": error, "pages": len(pages),
        "development_identity_page": identity_page,
        "repeal_status": (
            "notice_only" if status == "repeal_notice_only" else source.get("repeal_status", "unverified")
        ),
        "page_status_counts": dict(page_counts), "chunks": len(chunks),
        "cross_page_chunks": sum(chunk["page_start"] != chunk["page_end"] for chunk in chunks),
    }
    log = logger.warning if error or status != "text" else logger.info
    log("%s: %s, %d pages, %d chunks%s", source["source"], status, len(pages),
        len(chunks), f" ({error})" if error else "")
    return {
        "manifest": manifest,
        "pages": [{**metadata, **page} for page in pages],
        "chunks": chunks,
    }


def export_dataset(connection: sqlite3.Connection, config: dict, destination: Path) -> None:
    """Publish all exports together after every document checkpoint is committed."""
    with TemporaryDirectory(prefix=".export-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "dataset"
        staged.mkdir()
        with (
            (staged / "corpus_manifest.jsonl").open("w", encoding="utf-8") as manifest_file,
            (staged / "pages.jsonl").open("w", encoding="utf-8") as pages_file,
            (staged / "chunks.jsonl").open("w", encoding="utf-8") as chunks_file,
            (staged / "excluded_documents.csv").open("w", newline="", encoding="utf-8") as exclusions,
        ):
            writer = csv.DictWriter(exclusions, ["document_id", "source", "jurisdiction", "status", "error"])
            writer.writeheader()
            for payload, in connection.execute("SELECT payload FROM documents ORDER BY position"):
                document = json.loads(payload)
                manifest = document["manifest"]
                manifest_file.write(json.dumps(manifest, ensure_ascii=False) + "\n")
                for stream, records in ((pages_file, document["pages"]), (chunks_file, document["chunks"])):
                    for record in records:
                        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                if manifest["error"]:
                    writer.writerow({key: manifest[key] for key in writer.fieldnames})
        (staged / "processing_config.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        try:
            staged.rename(destination)
        except OSError:
            # Another identical invocation may have published while we exported.
            existing_config = destination / "processing_config.json"
            if not existing_config.is_file() or json.loads(existing_config.read_text(encoding="utf-8")) != config:
                raise


def run_prototype(
    root: Path, sample_path: Path, inventory_path: Path, destination: Path, *,
    chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP,
) -> None:
    """Process the explicit sample, resuming a matching version if interrupted."""
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    inventory_bytes = inventory_path.read_bytes()
    inventory = [json.loads(line) for line in inventory_bytes.splitlines()]
    candidates = canonical_candidates(inventory)
    sources = prepare_sources(
        root, sample, {row["source"]: row["sha256"] for row in candidates},
        {row["source"]: row["duplicate_source_paths"] for row in candidates},
    )
    settings = {
        **SETTINGS, "separators": list(SEPARATORS), "python": platform.python_version(),
        "chunk_size": chunk_size, "chunk_overlap": chunk_overlap,
        "dependencies": {
            package: version(package)
            for package in ("PyMuPDF", "langchain-text-splitters", "langchain-core")
        },
    }
    # Eligibility changes do not alter the identity of an unchanged text span.
    span_settings = {key: value for key, value in settings.items() if key not in ("pipeline_revision", "eligibility")}
    span_settings["pipeline_revision"] = 1
    method_id = stable_id(json.dumps(span_settings, sort_keys=True))
    config = {
        "dataset_version": destination.name,
        "candidate_inventory_sha256": sha256(inventory_bytes).hexdigest(),
        "method_id": method_id, "settings": settings, "sample": sources,
    }
    if destination.exists():
        existing = destination / "processing_config.json"
        if existing.is_file() and json.loads(existing.read_text(encoding="utf-8")) == config:
            logger.info("Completed dataset already exists at %s", destination)
            return
        raise ValueError(f"Dataset version already exists with different inputs: {destination}")

    checkpoint_directory = destination.parent / ".checkpoints"
    checkpoint_directory.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoint_directory / f"{destination.name}.sqlite3"
    connection = sqlite3.connect(checkpoint, timeout=30)
    try:
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, payload TEXT)")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS documents (position INTEGER PRIMARY KEY, payload TEXT)"
            )
            encoded = json.dumps(config, sort_keys=True)
            connection.execute("INSERT OR IGNORE INTO config VALUES (1, ?)", (encoded,))
            if connection.execute("SELECT payload FROM config WHERE id = 1").fetchone()[0] != encoded:
                raise ValueError(f"Checkpoint inputs differ for {destination.name}; use a new version")

        for position, source in enumerate(sources):
            if connection.execute("SELECT 1 FROM documents WHERE position = ?", (position,)).fetchone():
                logger.info("Resumed completed document %s", source["source"])
                continue
            if (chunk_size, chunk_overlap) == (CHUNK_SIZE, CHUNK_OVERLAP):
                document = preprocess_document(root, source, method_id)
            else:
                document = preprocess_document(
                    root, source, method_id, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                )
            with connection:
                connection.execute(
                    "INSERT OR IGNORE INTO documents VALUES (?, ?)", (position, json.dumps(document))
                )
        export_dataset(connection, config, destination)
        logger.info("Dataset exported to %s", destination)
    finally:
        connection.close()


def main() -> None:
    """Run the prototype against explicit local paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP)
    args = parser.parse_args()
    if not 0 <= args.chunk_overlap < args.chunk_size:
        parser.error("require 0 <= chunk overlap < chunk size")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_prototype(
        args.corpus, args.sample, args.inventory, args.output,
        chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap,
    )


if __name__ == "__main__":
    main()
