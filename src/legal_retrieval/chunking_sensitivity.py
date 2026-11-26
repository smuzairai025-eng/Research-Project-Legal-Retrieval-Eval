"""Replay the Stage 3 development evidence with four isolated splitter settings."""

import argparse
from collections import defaultdict
from collections.abc import Iterator
from itertools import groupby
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from . import text_splitter
from .corpus import stable_id

CONFIGURATIONS = {"A": (1500, 200), "B": (1500, 400), "C": (2000, 200), "D": (2000, 400)}
PROTOTYPE = Path("data/processed/stage3-validation/prototype-v2")
EVIDENCE = Path("evaluation/development-evidence-stage3.json")


def rows(path: Path) -> Iterator[dict]:
    """Read records from a JSONL file."""
    with path.open(encoding="utf-8") as source:
        yield from (json.loads(line) for line in source)


def assess_pair(pair: dict, chunks: list[dict]) -> dict:
    """Apply the same required evidence fragments to each candidate chunk."""
    evidence = pair["candidate_relevant_chunks"] + pair["partial_chunk_evidence"]
    required = list(dict.fromkeys(fragment for item in evidence for fragment in item["evidence_fragments"]))
    if pair["pair_id"] == "DEV-03":
        # The operative antecedent identifies the deduction even if the
        # section heading is outside the chunk. Use it in all four runs.
        required[required.index("Deductions for damage or loss")] = (
            "the damage or loss caused to the employer by the neglect or default of the employed person"
        )
    if not required:
        raise ValueError(f"No Stage 3 evidence fragments for {pair['pair_id']}")
    complete, partial = [], []
    for chunk in chunks:
        if chunk["document_id"] != pair["document_id"] or not any(
            chunk["page_start"] <= page <= chunk["page_end"] for page in pair["pdf_pages"]
        ):
            continue
        text = " ".join(chunk["text"].split())
        present = [fragment for fragment in required if fragment in text]
        if present:
            item = {
                "chunk_id": chunk["chunk_id"],
                "pdf_pages": [chunk["page_start"], chunk["page_end"]],
                "start_offset": chunk["start_offset"], "end_offset": chunk["end_offset"],
                "evidence_fragments": present,
            }
            (complete if present == required else partial).append(item)
    return {
        "pair_id": pair["pair_id"], "document_id": pair["document_id"],
        "provision": pair["provision"], "evidence_pages": pair["pdf_pages"],
        "required_fragments": required,
        "candidate_relevant_chunks": complete, "partial_chunk_evidence": partial,
    }


def generate_chunks(page_records: list[dict], method_id: str) -> list[dict]:
    """Use the same page-run boundaries and chunk identifiers as Stage 3."""
    chunks = []
    for _, pages in groupby(page_records, key=lambda page: page["document_id"]):
        for has_text, run in groupby(pages, key=lambda page: page["status"] == "text"):
            if not has_text:
                continue
            records = list(run)
            first = records[0]
            text_pages = [(page["page_number"], page["cleaned_text"]) for page in records]
            page_numbers = {number for number, _ in text_pages}
            joined = text_splitter.PAGE_SEPARATOR.join(text for _, text in text_pages)
            for text, start, end, page_start, page_end in text_splitter.split_page_run(text_pages):
                assert text == joined[start:end]
                assert 0 < len(text) <= text_splitter.CHUNK_SIZE
                assert all(page in page_numbers for page in range(page_start, page_end + 1))
                chunks.append({
                    **{key: first[key] for key in ("source", "jurisdiction", "document_id")},
                    "chunk_id": stable_id(
                        "chunk", first["document_id"], first["sha256"], method_id,
                        first["page_number"], start, end,
                    ),
                    "text": text, "page_start": page_start, "page_end": page_end,
                    "run_page_start": first["page_number"], "start_offset": start, "end_offset": end,
                })
    return chunks


def main() -> None:
    """Save each configuration, its chunks, and its evidence in a new directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output
    if destination.exists():
        raise FileExistsError(destination)

    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))["pairs"]
    assert len(evidence) == 10
    document_ids = {pair["document_id"] for pair in evidence}
    assert len(document_ids) == 4
    documents = {
        row["document_id"]: row
        for row in rows(PROTOTYPE / "corpus_manifest.jsonl")
        if row["document_id"] in document_ids
    }
    pages = [
        {**row, "sha256": documents[row["document_id"]]["sha256"]}
        for row in rows(PROTOTYPE / "pages.jsonl")
        if row["document_id"] in document_ids
    ]
    reference = [row for row in rows(PROTOTYPE / "chunks.jsonl") if row["document_id"] in document_ids]
    settings = json.loads((PROTOTYPE / "processing_config.json").read_text(encoding="utf-8"))["settings"]
    summaries = {}
    with TemporaryDirectory(prefix=".stage3a-", dir=destination.parent) as temporary:
        staging = Path(temporary) / destination.name
        staging.mkdir()
        for label, (size, overlap) in CONFIGURATIONS.items():
            variant = {**settings, "chunk_size": size, "chunk_overlap": overlap}
            span = {key: value for key, value in variant.items() if key != "eligibility"}
            span["pipeline_revision"] = 1
            method_id = stable_id(json.dumps(span, sort_keys=True))
            with patch.multiple(text_splitter, CHUNK_SIZE=size, CHUNK_OVERLAP=overlap):
                chunks = generate_chunks(pages, method_id)
            assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
            assessed = [assess_pair(pair, chunks) for pair in evidence]
            if label == "A":
                assert chunks == reference
                for new, original in zip(assessed, evidence, strict=True):
                    assert [c["chunk_id"] for c in new["candidate_relevant_chunks"]] == original["candidate_relevant_chunk_ids"]

            previous_ends: dict[tuple[str, int], int] = defaultdict(int)
            duplicated = 0
            for chunk in chunks:
                key = (chunk["document_id"], chunk["run_page_start"])
                shared = max(previous_ends[key] - chunk["start_offset"], 0)
                assert shared <= overlap
                duplicated += shared
                previous_ends[key] = chunk["end_offset"]
            characters = sum(len(chunk["text"]) for chunk in chunks)
            stats = {
                "documents": len(documents), "pages": len(pages),
                "chunks": len(chunks), "chunk_characters": characters,
                "average_chunk_characters": characters / len(chunks),
                "estimated_input_tokens": characters / 4,
                "repeated_source_characters": duplicated,
                "covered_pairs": sum(bool(pair["candidate_relevant_chunks"]) for pair in assessed),
                "pairs_with_multiple_sufficient_chunks": [
                    pair["pair_id"] for pair in assessed if len(pair["candidate_relevant_chunks"]) > 1
                ],
            }
            run = staging / label
            run.mkdir()
            (run / "config.json").write_text(json.dumps({
                "label": label, "parent_dataset": PROTOTYPE.as_posix(), "method_id": method_id,
                "settings": variant, "document_ids": list(documents),
            }, indent=2) + "\n", encoding="utf-8")
            with (run / "chunks.jsonl").open("w", encoding="utf-8") as out:
                for chunk in chunks:
                    out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            (run / "evidence.json").write_text(
                json.dumps(assessed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            summaries[label] = stats
        (staging / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
        staging.rename(destination)


if __name__ == "__main__":
    main()
