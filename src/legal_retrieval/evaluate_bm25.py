"""Evaluate paired development questions against provisional evidence labels."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path
from statistics import mean

from .bm25 import TOKENIZER, search

FORMULATIONS = ("formal", "everyday")
METRICS = ("hit_at_5", "hit_at_10", "mrr_at_10", "candidate_recall_at_5", "candidate_recall_at_10")


def score_ranking(ranking: list[dict], relevant: set[str]) -> dict:
    """Score single-chunk retrieval, keeping recall undefined without a label."""
    found = [row["rank"] for row in ranking if row["chunk_id"] in relevant]
    first = min(found, default=None)
    return {
        "first_relevant_rank": first,
        "hit_at_5": int(first is not None and first <= 5),
        "hit_at_10": int(first is not None and first <= 10),
        "mrr_at_10": 1 / first if first is not None and first <= 10 else 0.0,
        "candidate_recall_at_5": sum(rank <= 5 for rank in found) / len(relevant) if relevant else None,
        "candidate_recall_at_10": sum(rank <= 10 for rank in found) / len(relevant) if relevant else None,
    }


def evaluate(index: dict, pairs: list[dict]) -> tuple[list[dict], dict]:
    """Return saved query rankings, aggregate metrics, and everyday-minus-formal changes."""
    queries = []
    differences = []
    seen = set()
    for pair in pairs:
        pair_id = pair["pair_id"]
        if pair_id in seen or pair["verification_status"] != "pending_human_verification":
            raise ValueError(f"Unexpected pair or verification status: {pair_id}")
        seen.add(pair_id)
        relevant = {row["chunk_id"] for row in pair["candidate_relevant_chunks"]}
        partial = {row["chunk_id"] for row in pair["partial_chunk_evidence"]}
        if relevant & partial or any(
            index["chunks"].get(chunk_id, {}).get("document_id") != pair["document_id"]
            for chunk_id in relevant | partial
        ):
            raise ValueError(f"Evidence does not match the frozen dataset: {pair_id}")
        scores = {}
        for formulation in FORMULATIONS:
            query = pair[f"{formulation}_question"]
            ranking = search(index, query, len(index["chunks"]))
            scores[formulation] = metrics = score_ranking(ranking, relevant)
            queries.append({
                "pair_id": pair_id, "formulation": formulation, "query": query,
                "verification_status": pair["verification_status"], "evidence_covered": bool(relevant),
                "candidate_relevant_chunk_ids": sorted(relevant),
                "partial_evidence_ranks": {
                    r["chunk_id"]: r["rank"] for r in ranking if r["chunk_id"] in partial
                },
                "metrics": metrics, "ranking": ranking,
            })
        formal, everyday = (scores[formulation] for formulation in FORMULATIONS)
        differences.append({
            "pair_id": pair_id, "evidence_covered": bool(relevant),
            "formal_first_relevant_rank": formal["first_relevant_rank"],
            "everyday_first_relevant_rank": everyday["first_relevant_rank"],
            **{
                metric: everyday[metric] - formal[metric] if formal[metric] is not None else None
                for metric in METRICS
            },
        })
    groups = {}
    for label, covered_only in (("all_pairs", False), ("covered_pairs", True)):
        groups[label] = {}
        for formulation in FORMULATIONS:
            subset = [
                q for q in queries
                if q["formulation"] == formulation and (not covered_only or q["evidence_covered"])
            ]
            aggregate = {"queries": len(subset)}
            for metric in METRICS:
                values = [q["metrics"][metric] for q in subset if q["metrics"][metric] is not None]
                aggregate[metric] = mean(values) if values else None
            groups[label][formulation] = aggregate
        groups[label]["everyday_minus_formal"] = {
            metric: groups[label]["everyday"][metric] - groups[label]["formal"][metric]
            if groups[label]["formal"][metric] is not None else None
            for metric in METRICS
        }
    return queries, {
        "chunks_sha256": index["chunks_sha256"],
        "tokenizer": index["tokenizer"], "k1": index["k1"], "b": index["b"],
        "pairs": len(pairs), "covered_pairs": sum(row["evidence_covered"] for row in differences),
        "verification_status": "pending_human_verification",
        "aggregates": groups, "paired_differences": differences,
    }


def main() -> None:
    """Load the frozen index, verify its chunk hash, and save evaluation outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("index", "chunks", "pairs", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding="utf-8"))
    with args.chunks.open("rb") as stream:
        if file_digest(stream, "sha256").hexdigest() != index["chunks_sha256"]:
            parser.error("Index and chunk export have different SHA-256 checksums")
    if index["tokenizer"] != TOKENIZER:
        parser.error("Index tokenizer version differs from current tokenizer")
    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))["pairs"]
    queries, summary = evaluate(index, pairs)
    with args.pairs.open("rb") as stream:
        summary["pairs_sha256"] = file_digest(stream, "sha256").hexdigest()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "rankings.jsonl").open("x", encoding="utf-8") as output:
        for query in queries:
            output.write(json.dumps(query, ensure_ascii=False) + "\n")
    (args.output / "metrics.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8",
    )


if __name__ == "__main__":
    main()
