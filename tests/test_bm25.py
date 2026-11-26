"""Tests for statutory tokenization, BM25 scores, and paired evaluation."""

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.legal_retrieval.bm25 import B, K1, build_index, search, tokenize
from src.legal_retrieval.evaluate_bm25 import evaluate, score_ranking


class BM25Tests(unittest.TestCase):
    def build(self, texts: dict[str, str]) -> dict:
        """Build a tiny index with distinct IDs and fixed source metadata."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "chunks.jsonl"
            rows = [
                {"chunk_id": chunk_id, "document_id": "doc", "text": text,
                 "source": "statute.pdf", "jurisdiction": "KP", "page_start": 2, "page_end": 3}
                for chunk_id, text in texts.items()
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            return build_index(path)

    def test_normalization_preserves_citations_and_legal_terms(self) -> None:
        self.assertEqual(tokenize("§５‑A(2)(iii) Act IX; non-payment; worker’s rights."),
                         ["5-a(2)(iii)", "5-a", "5", "a", "act", "ix",
                          "non-payment", "non", "payment", "worker's", "rights"])

    def test_bm25_matches_hand_calculation_and_reloads(self) -> None:
        index = self.build({"a": "deduction deduction wage", "b": "wage"})
        result, = search(json.loads(json.dumps(index)), "deduction deduction", 1)
        expected = math.log(2) * 2 * (K1 + 1) / (2 + K1 * (1 - B + B * 3 / 2))
        self.assertAlmostEqual(result["score"], expected)
        self.assertEqual((result["chunk_id"], result["page_start"], result["page_end"]), ("a", 2, 3))
        self.assertEqual(search(index, "unknown", 4), [])
        with self.assertRaises(ValueError):
            search(index, "wage", 0)

    def test_top_k_breaks_score_ties_by_chunk_id(self) -> None:
        index = self.build({"z": "matching text", "a": "matching text"})
        self.assertEqual([row["chunk_id"] for row in search(index, "matching", 2)], ["a", "z"])

    def test_recall_uses_all_candidate_labels(self) -> None:
        ranking = [{"rank": 2, "chunk_id": "b"}, {"rank": 9, "chunk_id": "c"}]
        scores = score_ranking(ranking, {"b", "c", "d"})
        self.assertEqual(scores["candidate_recall_at_5"], 1 / 3)
        self.assertEqual(scores["candidate_recall_at_10"], 2 / 3)
        self.assertEqual(scores["mrr_at_10"], 0.5)

    def test_paired_metrics_keep_uncovered_query_and_separate_partial_evidence(self) -> None:
        index = self.build({"a": "subsection employee", "b": "other"})
        pairs = [
            {"pair_id": "one", "document_id": "doc", "formal_question": "subsection",
             "everyday_question": "other", "verification_status": "pending_human_verification",
             "candidate_relevant_chunks": [{"chunk_id": "a"}], "partial_chunk_evidence": []},
            {"pair_id": "two", "document_id": "doc", "formal_question": "subsection",
             "everyday_question": "employee", "verification_status": "pending_human_verification",
             "candidate_relevant_chunks": [], "partial_chunk_evidence": [{"chunk_id": "a"}]},
        ]
        rankings, metrics = evaluate(index, pairs)
        self.assertEqual(len(rankings), 4)
        self.assertEqual(rankings[2]["partial_evidence_ranks"], {"a": 1})
        self.assertEqual(rankings[2]["metrics"]["hit_at_5"], 0)
        self.assertIsNone(rankings[2]["metrics"]["candidate_recall_at_5"])
        self.assertEqual(metrics["aggregates"]["all_pairs"]["everyday_minus_formal"]["hit_at_5"], -0.5)
        self.assertEqual(metrics["aggregates"]["covered_pairs"]["formal"]["hit_at_5"], 1)


if __name__ == "__main__":
    unittest.main()
