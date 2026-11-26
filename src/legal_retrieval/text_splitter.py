"""Split consecutive pages and retain the original character positions."""

from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Iterator

from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
SEPARATORS = ("\n\n", "\n", ".", " ", "")
PAGE_SEPARATOR = "\n\n"


class _PositionedText(str):
    """A string carrying its starting offset in the input."""

    def __new__(cls, text: str, start: int) -> "_PositionedText":
        piece = super().__new__(cls, text)
        piece.start = start
        return piece


class _OffsetSplitter(RecursiveCharacterTextSplitter):
    """Record offsets as LangChain merges fragments in input order."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=list(SEPARATORS),
            keep_separator="start",
            strip_whitespace=False,
        )
        self.cursor = 0

    def _merge_splits(self, splits: Iterable[str], separator: str) -> list[str]:
        # Retained separators and the character fallback account for every input
        # character, even when identical paragraphs occur on consecutive pages.
        fragments = []
        for text in splits:
            fragments.append(_PositionedText(text, self.cursor))
            self.cursor += len(text)
        return super()._merge_splits(fragments, separator)

    def _join_docs(self, docs: list[_PositionedText], separator: str) -> str | None:
        text = super()._join_docs(docs, separator)
        return _PositionedText(text, docs[0].start) if text is not None else None


def split_page_run(
    pages: list[tuple[int, str]],
    *, chunk_size: int | None = None, chunk_overlap: int | None = None,
) -> Iterator[tuple[str, int, int, int, int]]:
    """Yield text, run-relative start/end offsets and inclusive PDF page bounds.

    The input must be a consecutive run of nonempty cleaned pages.
    Offsets are zero-based and the end offset is exclusive.
    """
    starts, ends = [], []
    cursor = 0
    for _, text in pages:
        starts.append(cursor)
        ends.append(cursor + len(text))
        cursor = ends[-1] + len(PAGE_SEPARATOR)

    joined = PAGE_SEPARATOR.join(text for _, text in pages)
    splitter = _OffsetSplitter(
        CHUNK_SIZE if chunk_size is None else chunk_size,
        CHUNK_OVERLAP if chunk_overlap is None else chunk_overlap,
    )
    chunks = splitter.split_text(joined)
    if splitter.cursor != len(joined):
        raise RuntimeError("Splitter did not account for every input character")

    for chunk in chunks:
        start = chunk.start
        end = start + len(chunk)
        if joined[start:end] != chunk:
            raise RuntimeError("Splitter returned an inconsistent character span")
        if chunk.strip():
            first = bisect_right(ends, start)
            last = bisect_left(starts, end) - 1
            yield str(chunk), start, end, pages[first][0], pages[last][0]
