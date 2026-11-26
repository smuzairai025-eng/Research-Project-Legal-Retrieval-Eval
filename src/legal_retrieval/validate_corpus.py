"""Build the Stage 3 canonical manifest and benchmark a stratified sample."""

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable
import ctypes
import json
from pathlib import Path
import random
import time

from .corpus import canonical_candidates, stable_id
from .preprocess import prepare_sources, preprocess_document, run_prototype


def working_set() -> tuple[int, int]:
    """Return current and peak working-set bytes for this Windows process."""
    size = ctypes.c_size_t

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (name, size) for name in (
                "peak", "current", "quota1", "quota2", "quota3", "quota4",
                "pagefile", "peak_pagefile",
            )
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32")
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    read_memory = kernel.K32GetProcessMemoryInfo
    read_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong]
    if not read_memory(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return counters.current, counters.peak


def write_json(path: Path, payload: object) -> None:
    """Write a new JSON artifact without replacing an existing result."""
    with path.open("x", encoding="utf-8") as out:
        json.dump(payload, out, ensure_ascii=False, indent=2)
        out.write("\n")


def record_page_gaps(pages: Iterable[dict], gaps: dict[str, list[dict]]) -> None:
    """Save page-level diagnostics without retaining benchmark text."""
    for page in pages:
        if page["status"] != "text":
            gaps[page["document_id"]].append({
                key: page[key] for key in ("page_number", "status", "error")
            })


def main() -> None:
    """Validate the original sample and profile 16 other randomly drawn per stratum."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = args.output.parent / "candidate-inventory-v1" / "checksums.jsonl"
    candidates = canonical_candidates([json.loads(line) for line in inventory.read_text(encoding="utf-8").splitlines()])
    canonical = {path: row["source"] for row in candidates for path in [row["source"], *row["duplicate_source_paths"]]}
    by_path = {row["source"]: row for row in candidates}
    prototype = json.loads(Path("configs/stage2-sample.json").read_text(encoding="utf-8"))
    audit = {}
    for row in prototype:
        source = canonical[row["source"]]
        entry = {**row, "source": source}
        if source != row["source"]:
            entry["reason"] = "Canonical path for the exact-copy pair selected in Stage 2."
        audit.setdefault(source, entry)
    sample_path = args.output / "prototype-sample.json"
    write_json(sample_path, list(audit.values()))
    prototype_output = args.output / "prototype-v2"
    run_prototype(args.corpus, sample_path, inventory, prototype_output)
    audited = [json.loads(line) for line in (prototype_output / "corpus_manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    gaps: dict[str, list[dict]] = defaultdict(list)
    with (prototype_output / "pages.jsonl").open(encoding="utf-8") as pages:
        record_page_gaps((json.loads(line) for line in pages), gaps)

    strata = defaultdict(list)
    for row in candidates:
        if row["source"] not in audit:
            strata[row["source"].split("/")[0]].append(row)
    rng = random.Random(371506)
    metrics = {}
    sampled = []
    baseline, _ = working_set()
    started = time.perf_counter()
    for stratum, population in sorted(strata.items()):
        records = rng.sample(population, min(len(population), 16))
        observations = []
        for row in records:
            start = time.perf_counter()
            source, = prepare_sources(args.corpus, [{"source": row["source"]}], {row["source"]: row["sha256"]})
            result = preprocess_document(args.corpus, source, "benchmark")
            manifest = result["manifest"]
            record_page_gaps(result["pages"], gaps)
            observations.append({
                "source": source["source"], "status": manifest["status"], "pages": manifest["pages"],
                "page_status_counts": manifest["page_status_counts"],
                "chunks": len(result["chunks"]),
                "chunk_characters": sum(len(chunk["text"]) for chunk in result["chunks"]),
                "seconds": time.perf_counter() - start,
            })
            sampled.append(manifest)
        metrics[stratum] = {"population_outside_audit": len(population), "observations": observations}
    duration = time.perf_counter() - started
    _, peak = working_set()
    with (prototype_output / "chunks.jsonl").open(encoding="utf-8") as chunks:
        audit_chars = sum(len(json.loads(line)["text"]) for line in chunks)
    write_json(args.output / "benchmark.json", {
        "seed": 371506, "sample_per_source_folder": 16, "strata": metrics,
        "audit_pages": sum(row["pages"] for row in audited),
        "audit_chunks": sum(row["chunks"] for row in audited),
        "audit_chunk_characters": audit_chars,
        "benchmark_wall_seconds": duration, "benchmark_baseline_working_set_bytes": baseline,
        "benchmark_process_peak_working_set_bytes": peak,
    })

    observed = {row["source"]: row for row in audited + sampled}
    with (
        (args.output / "candidate_manifest.jsonl").open("x", encoding="utf-8") as manifest,
        (args.output / "page-gaps.jsonl").open("x", encoding="utf-8") as gap_file,
    ):
        for row in candidates:
            assessment = observed.get(row["source"])
            result = {
                **row, "document_id": stable_id("document", row["source"]),
                "status": assessment["status"] if assessment else "not_assessed",
                "repeal_status": assessment["repeal_status"] if assessment else "unverified",
                "page_status_counts": assessment["page_status_counts"] if assessment else None,
                "eligibility_reason": assessment["error"] if assessment else None,
            }
            manifest.write(json.dumps(result, ensure_ascii=False) + "\n")
            document_gaps = gaps.get(result["document_id"])
            if document_gaps:
                gap_file.write(json.dumps({
                    "source": row["source"], "document_id": result["document_id"],
                    "document_status": result["status"], "missing_text_pages": document_gaps,
                }) + "\n")
    write_json(args.output / "canonical_summary.json", {
        "candidate_paths": sum(1 + len(row["duplicate_source_paths"]) for row in candidates),
        "unique_candidates": len(candidates),
        "duplicate_groups": sum(bool(row["duplicate_source_paths"]) for row in candidates),
        "assessed_statuses": dict(Counter(row["status"] for row in observed.values())),
    })


if __name__ == "__main__":
    main()
