"""Inventory the corpus without modifying or extracting its PDFs."""

import argparse
from collections import Counter
from hashlib import file_digest, sha256
import json
from pathlib import Path

JURISDICTIONS = {
    "kp_code_pdfs": "Khyber Pakhtunkhwa",
    "pakistan_code_pdfs": "Federal",
    "punjab_laws_pdfs": "Punjab",
    "sindh_laws_pdfs": "Sindh",
}


def stable_id(*values: str | int) -> str:
    """Hash an ordered list of fields without ambiguity at field boundaries."""
    return sha256(json.dumps(values, ensure_ascii=False).encode("utf-8")).hexdigest()


def pdf_checksum(path: Path) -> str:
    """Read the original PDF in bounded blocks and return its SHA-256."""
    with path.open("rb") as pdf:
        return file_digest(pdf, "sha256").hexdigest()


def inventory_corpus(root: Path) -> tuple[list[dict], dict]:
    """Return file-level checksums and exact duplicate groups."""
    records = []
    groups: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() != ".pdf" or not path.is_file():
            continue
        source = path.relative_to(root).as_posix()
        try:
            checksum = pdf_checksum(path)
            groups.setdefault(checksum, []).append(source)
            records.append({"source": source, "sha256": checksum, "error": None})
        except OSError as exc:
            records.append({"source": source, "sha256": None, "error": str(exc)})
    if not records:
        raise ValueError(f"No PDFs found in {root}")
    return records, {
        "pdfs": len(records),
        "by_source_folder": dict(Counter(row["source"].split("/")[0] for row in records)),
        "hash_failures": sum(row["error"] is not None for row in records),
        "duplicate_groups": [
            {"sha256": digest, "sources": sources}
            for digest, sources in groups.items()
            if len(sources) > 1
        ],
    }


def canonical_candidates(records: list[dict]) -> list[dict]:
    """Group byte-identical sources, keeping the lexically first relative path."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for record in sorted(records, key=lambda row: row["source"]):
        checksum = record["sha256"]
        key = ("sha256", checksum) if checksum else ("unverified", record["source"])
        groups.setdefault(key, []).append(record)
    return [
        {**group[0], "duplicate_source_paths": [record["source"] for record in group[1:]]}
        for group in groups.values()
    ]


def main() -> None:
    """Write candidate inventory and duplicate report into a new output folder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records, report = inventory_corpus(args.corpus)
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "checksums.jsonl").open("x", encoding="utf-8") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
    (args.output / "duplicates.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Inventory: {report['pdfs']} PDFs, {report['hash_failures']} hash failures, "
          f"{len(report['duplicate_groups'])} duplicate groups")


if __name__ == "__main__":
    main()
