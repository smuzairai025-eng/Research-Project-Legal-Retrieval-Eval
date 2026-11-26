"""Regression tests for statutory wording, provenance, and safe resumption."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from langchain_text_splitters import RecursiveCharacterTextSplitter
import pymupdf

from src.legal_retrieval import preprocess
from src.legal_retrieval.corpus import canonical_candidates, inventory_corpus
from src.legal_retrieval.pdf_loader import clean_text, extract_pdf
from src.legal_retrieval.text_splitter import (
    CHUNK_OVERLAP, CHUNK_SIZE, PAGE_SEPARATOR, SEPARATORS, split_page_run,
)


def make_pdf(path: Path, pages: list[str | None]) -> None:
    """Create a fixture PDF with text or an image-only page for each entry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as pdf:
        for content in pages:
            page = pdf.new_page()
            if content is None:
                image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
                image.clear_with(125)
                page.insert_image(page.rect, pixmap=image)
            elif content:
                page.insert_text((50, 50), content)
        pdf.save(path)


def read_jsonl(path: Path) -> list[dict]:
    """Read all records from a small fixture output."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class TextTests(unittest.TestCase):
    def test_cleaning_preserves_legal_wording_and_layout(self) -> None:
        content = (
            "Section 5-A(2)(iii)—Rs. 12,500.50;\r\n"
            "The term ‘non-\r\npayment’ appears in Schedule [IV].\r\n"
            "Page 2 of 7\r\n\r\n\r\n[Image 2]"
        )
        self.assertEqual(clean_text("  \r\n" + content + "\r\t "), content.replace("\r\n", "\n"))

    def test_chunk_size_and_overlap_at_character_fallback(self) -> None:
        text = "x" * 3400
        chunks = list(split_page_run([(1, text)]))
        self.assertEqual([len(chunk[0]) for chunk in chunks], [1500, 1500, 800])
        for previous, current in zip(chunks, chunks[1:]):
            self.assertEqual(previous[2] - current[1], CHUNK_OVERLAP)

    def test_cross_page_chunk_provenance(self) -> None:
        pages = [(7, "The employer shall pay"), (8, "within seven days.")]
        self.assertEqual(list(split_page_run(pages)), [
            ("The employer shall pay\n\nwithin seven days.", 0, 42, 7, 8),
        ])

    def test_repeated_page_text_preserves_exact_offsets(self) -> None:
        repeated = "A" * 1500
        chunks = list(split_page_run([(1, repeated), (2, repeated), (3, repeated)]))
        joined = PAGE_SEPARATOR.join([repeated] * 3)
        self.assertEqual([(chunk[1], chunk[3], chunk[4]) for chunk in chunks],
                         [(0, 1, 1), (1501, 2, 2), (2801, 2, 2),
                          (3003, 3, 3), (4303, 3, 3)])
        for text, start, end, _, _ in chunks:
            self.assertEqual(text, joined[start:end])

    def test_keeps_langchain_recursive_splitting_behavior(self) -> None:
        pages = [(1, ("Section 1. [Rule]\n" * 180)), (2, "ordinary words " * 400)]
        reference = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
            separators=list(SEPARATORS), keep_separator="start", strip_whitespace=False,
        )
        expected = reference.split_text(PAGE_SEPARATOR.join(text for _, text in pages))
        self.assertEqual([chunk[0] for chunk in split_page_run(pages)], [c for c in expected if c.strip()])
        self.assertTrue(all(len(chunk) <= CHUNK_SIZE for chunk in expected))


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "corpus"
        self.first = "kp_code_pdfs/a/same.pdf"
        self.second = "punjab_laws_pdfs/b/same.pdf"
        self.destination = self.base / "prototype-v1"

    def write_run_inputs(self, sources: list[str]) -> tuple[Path, Path]:
        """Write an explicit sample and an inventory for this test run."""
        sample_path = self.base / "sample.json"
        inventory_path = self.base / "inventory.jsonl"
        sample_path.write_text(json.dumps([{"source": source} for source in sources]), encoding="utf-8")
        inventory, _ = inventory_corpus(self.root)
        inventory_path.write_text("".join(json.dumps(row) + "\n" for row in inventory), encoding="utf-8")
        return sample_path, inventory_path

    def test_deterministic_ids_and_identical_filenames(self) -> None:
        make_pdf(self.root / self.first, ["Section 5A. Payment shall be made."])
        second = self.root / self.second
        second.parent.mkdir(parents=True)
        second.write_bytes((self.root / self.first).read_bytes())
        inventory, report = inventory_corpus(self.root)
        self.assertEqual(len(report["duplicate_groups"]), 1)
        self.assertCountEqual(report["duplicate_groups"][0]["sources"], [self.first, self.second])
        sources = preprocess.prepare_sources(
            self.root, [{"source": self.first}, {"source": self.second}],
            {row["source"]: row["sha256"] for row in inventory},
        )
        a, b = [preprocess.preprocess_document(self.root, source, "method") for source in sources]
        self.assertEqual(a, preprocess.preprocess_document(self.root, sources[0], "method"))
        self.assertEqual(a["manifest"]["sha256"], b["manifest"]["sha256"])
        self.assertNotEqual(a["manifest"]["document_id"], b["manifest"]["document_id"])
        self.assertNotEqual(a["chunks"][0]["chunk_id"], b["chunks"][0]["chunk_id"])

    def test_empty_unreadable_blank_and_image_only(self) -> None:
        for filename, data in (("empty.pdf", b""), ("broken.pdf", b"%PDF-incomplete\x00")):
            path = self.base / filename
            path.write_bytes(data)
            pages, status, error = extract_pdf(path)
            self.assertEqual((pages, status), ([], "unreadable"))
            self.assertTrue(error)
        for content, expected in (("", "no_text"), (None, "image_only")):
            path = self.base / f"{expected}.pdf"
            make_pdf(path, [content])
            pages, status, error = extract_pdf(path)
            self.assertEqual(status, expected)
            self.assertEqual(pages[0]["page_number"], 1)
            self.assertTrue(error)

    def test_mixed_document_and_blank_page_break_chunk_runs(self) -> None:
        make_pdf(self.root / self.first, ["Page one text", "Page two text", None, "Page four text", "", "Page six text"])
        sample, inventory = self.write_run_inputs([self.first])
        preprocess.run_prototype(self.root, sample, inventory, self.destination)
        chunks = read_jsonl(self.destination / "chunks.jsonl")
        self.assertEqual([(c["page_start"], c["page_end"]) for c in chunks], [(1, 2), (4, 4), (6, 6)])
        document, = read_jsonl(self.destination / "corpus_manifest.jsonl")
        self.assertEqual(document["status"], "mixed_text_scanned")
        pages = read_jsonl(self.destination / "pages.jsonl")
        self.assertEqual(pages[2]["status"], "image_without_text")
        self.assertEqual(pages[4]["status"], "missing_text")
        self.assertEqual(pages[0]["raw_text"], "Page one text\n")
        self.assertEqual(pages[0]["cleaned_text"], "Page one text")

    def test_interrupted_run_resumes_without_duplicate_records(self) -> None:
        make_pdf(self.root / self.first, ["First statutory passage."])
        make_pdf(self.root / self.second, ["Second statutory passage."])
        sample, inventory = self.write_run_inputs([self.first, self.second])
        original = preprocess.preprocess_document

        def interrupt(root: Path, source: dict, method: str) -> dict:
            if source["source"] == self.second:
                raise KeyboardInterrupt
            return original(root, source, method)

        with patch.object(preprocess, "preprocess_document", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                preprocess.run_prototype(self.root, sample, inventory, self.destination)
        self.assertFalse(self.destination.exists())

        with patch.object(preprocess, "preprocess_document", wraps=original) as process:
            preprocess.run_prototype(self.root, sample, inventory, self.destination)
            process.assert_called_once()
            self.assertEqual(process.call_args.args[1]["source"], self.second)
            preprocess.run_prototype(self.root, sample, inventory, self.destination)
            process.assert_called_once()
        for filename, field in (
            ("corpus_manifest.jsonl", "document_id"), ("pages.jsonl", "document_id"),
            ("chunks.jsonl", "chunk_id"),
        ):
            rows = read_jsonl(self.destination / filename)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len({row[field] for row in rows}), 2)
        sample.write_text(json.dumps([{"source": self.second}]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists with different inputs"):
            preprocess.run_prototype(self.root, sample, inventory, self.destination)

    def test_repeated_sample_source_is_rejected(self) -> None:
        make_pdf(self.root / self.first, ["A statutory passage."])
        sample, inventory = self.write_run_inputs([self.first, self.first])
        with self.assertRaisesRegex(ValueError, "Repeated source"):
            preprocess.run_prototype(self.root, sample, inventory, self.destination)
        self.assertFalse(self.destination.exists())

    def test_excluded_document_keeps_diagnostic_page_without_chunks(self) -> None:
        make_pdf(self.root / self.first, [None])
        sample, inventory = self.write_run_inputs([self.first])
        preprocess.run_prototype(self.root, sample, inventory, self.destination)
        exclusions = (self.destination / "excluded_documents.csv").read_text(encoding="utf-8")
        self.assertIn("image_only", exclusions)
        self.assertIn(self.first, exclusions)
        self.assertEqual(len(read_jsonl(self.destination / "pages.jsonl")), 1)
        self.assertEqual(read_jsonl(self.destination / "chunks.jsonl"), [])

    def test_canonical_manifest_keeps_aliases_and_distinct_revisions(self) -> None:
        make_pdf(self.root / self.first, ["Section 1. Original text."])
        second = self.root / self.second
        second.parent.mkdir(parents=True)
        second.write_bytes((self.root / self.first).read_bytes())
        revised = "kp_code_pdfs/a/same (amended).pdf"
        make_pdf(self.root / revised, ["Section 1. Amended text."])
        sample, inventory = self.write_run_inputs([self.first, revised])
        preprocess.run_prototype(self.root, sample, inventory, self.destination)
        rows = read_jsonl(self.destination / "corpus_manifest.jsonl")
        self.assertEqual([row["source"] for row in rows], [self.first, revised])
        self.assertEqual(rows[0]["duplicate_source_paths"], [self.second])
        self.assertEqual(rows[1]["duplicate_source_paths"], [])
        records = read_jsonl(inventory)
        self.assertEqual(canonical_candidates(records), canonical_candidates(records[::-1]))
        sample, inventory = self.write_run_inputs([self.second])
        with self.assertRaisesRegex(ValueError, "missing from inventory"):
            preprocess.run_prototype(self.root, sample, inventory, self.base / "alias-run")

    def test_repeal_notice_exclusion_retains_substantive_instrument(self) -> None:
        make_pdf(self.root / self.first, ["THIS LAW HAS BEEN REPEALED."])
        make_pdf(self.root / self.second, ["This law has been repealed.", "Section 1. Operative text."])
        sample, inventory = self.write_run_inputs([self.first, self.second])
        sample.write_text(json.dumps([
            {"source": self.first},
            {"source": self.second, "repeal_status": "repealed", "repeal_reference": "Fixture citation"},
        ]), encoding="utf-8")
        preprocess.run_prototype(self.root, sample, inventory, self.destination)
        notice, substantive = read_jsonl(self.destination / "corpus_manifest.jsonl")
        self.assertEqual((notice["status"], notice["chunks"]), ("repeal_notice_only", 0))
        self.assertGreater(substantive["chunks"], 0)
        self.assertEqual(substantive["repeal_status"], "repealed")
        self.assertEqual(substantive["repeal_reference"], "Fixture citation")

    def test_repeal_notice_overlay_does_not_hide_unassessed_image(self) -> None:
        path = self.base / "repeal-with-image.pdf"
        with pymupdf.open() as pdf:
            page = pdf.new_page()
            raster = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
            raster.clear_with(125)
            page.insert_image(page.rect, pixmap=raster)
            page.insert_text((50, 50), "THIS LAW HAS BEEN REPEALED")
            pdf.save(path)
        _, status, error = extract_pdf(path)
        self.assertEqual(status, "text")
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
