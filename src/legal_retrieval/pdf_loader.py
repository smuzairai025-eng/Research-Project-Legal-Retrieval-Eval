"""Extract PDF pages and record page-level eligibility and quality indicators."""

import logging
from pathlib import Path
import re

import pymupdf

logger = logging.getLogger(__name__)

REPEAL_NOTICE = re.compile(r"this law has been repealed[.!]?", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Normalize line endings and strip only outer ASCII layout whitespace."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip(" \t\n")


def extract_pdf(path: Path) -> tuple[list[dict], str, str | None]:
    """Return page records, document eligibility status, and any open error."""
    pages = []
    try:
        pdf = pymupdf.open(path)
    except (pymupdf.FileDataError, pymupdf.EmptyFileError, OSError) as exc:
        return [], "unreadable", str(exc)

    with pdf:
        if not pdf.is_pdf:
            return [], "unreadable", "File is not a PDF"
        if pdf.needs_pass:
            return [], "unreadable", "PDF requires a password"
        for index in range(pdf.page_count):
            raw_text, cleaned_text, error = "", "", None
            try:
                page = pdf[index]
                raw_text = page.get_text("text")
                cleaned_text = clean_text(raw_text)
                if cleaned_text.strip():
                    status = "text"
                else:
                    status = "image_without_text" if page.get_image_info() else "missing_text"
            except (RuntimeError, ValueError, OSError) as exc:
                status, error = "extraction_error", str(exc)
                logger.warning("Extraction failed for %s page %d: %s", path, index + 1, exc)
            pages.append({
                "page_number": index + 1,
                "raw_text": raw_text,
                "cleaned_text": cleaned_text,
                "status": status,
                "error": error,
            })

        statuses = {page["status"] for page in pages}
        all_text = " ".join(
            " ".join(page["cleaned_text"].split()) for page in pages if page["status"] == "text"
        )
        if statuses == {"text"} and REPEAL_NOTICE.fullmatch(all_text):
            # A raster image may contain a scan under a text notice or overlay.
            try:
                if not any(page.get_image_info() for page in pdf):
                    return pages, "repeal_notice_only", "Verified notice contains no substantive statutory text"
            except (RuntimeError, ValueError, OSError):
                logger.warning("Could not inspect possible repeal notice images in %s", path)
    if "text" in statuses:
        if "image_without_text" in statuses:
            return pages, "mixed_text_scanned", None
        return pages, "text_with_gaps" if len(statuses) > 1 else "text", None
    if "extraction_error" in statuses:
        return pages, "no_text_with_errors", "Page extraction failed and no text was recovered"
    if "image_without_text" in statuses:
        return pages, "image_only", "Image-bearing PDF with no extractable text"
    return pages, "no_text", "No extractable text"
