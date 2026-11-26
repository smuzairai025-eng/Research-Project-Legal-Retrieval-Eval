"""Build and search a local BM25 index over an immutable chunk export."""

import argparse
from collections import Counter, defaultdict
from hashlib import file_digest
import json
import math
from pathlib import Path
import re
import unicodedata

K1 = 1.2
B = 0.75
TOKENIZER = "statutory-en-v1"
PUNCTUATION = str.maketrans({"’": "'", "‘": "'", "‟": '"', "‐": "-", "‑": "-", "–": "-", "−": "-"})
WORD = r"[^\W_]+"
IDENTIFIER = rf"\d+[^\W\d_]*(?:-{WORD})*(?:\({WORD}\))+"
TOKEN = re.compile(rf"{IDENTIFIER}|{WORD}(?:[-']{WORD})*")


def tokenize(text: str) -> list[str]:
    """Normalize case and PDF punctuation while retaining legal identifiers."""
    text = unicodedata.normalize("NFKC", text).translate(PUNCTUATION).casefold()
    tokens = []
    for match in TOKEN.finditer(text):
        token = match[0]
        tokens.append(token)
        if "(" in token or "-" in token:
            base = token.split("(", 1)[0]
            # Keep both the whole citation and its searchable section number.
            for component in dict.fromkeys([base, *re.findall(WORD, base)]):
                if component != token:
                    tokens.append(component)
    return tokens


def build_index(chunks_path: Path) -> dict:
    """Store lengths, term frequencies, and provenance keyed by chunk ID."""
    postings = defaultdict(list)
    chunks = {}
    with chunks_path.open("rb") as source:
        checksum = file_digest(source, "sha256").hexdigest()
        source.seek(0)
        for line in source:
            chunk = json.loads(line)
            chunk_id = chunk["chunk_id"]
            if chunk_id in chunks:
                raise ValueError(f"Duplicate chunk ID: {chunk_id}")
            terms = Counter(tokenize(chunk["text"]))
            chunks[chunk_id] = {
                key: chunk[key] for key in ("document_id", "source", "jurisdiction", "page_start", "page_end")
            }
            chunks[chunk_id]["token_count"] = terms.total()
            for term, frequency in terms.items():
                postings[term].append((chunk_id, frequency))
    if not chunks:
        raise ValueError("The chunk export is empty")
    return {
        "tokenizer": TOKENIZER, "k1": K1, "b": B, "chunks_sha256": checksum,
        "average_length": sum(chunk["token_count"] for chunk in chunks.values()) / len(chunks),
        "chunks": chunks, "postings": dict(postings),
    }


def search(index: dict, query: str, k: int = 10) -> list[dict]:
    """Score lexical matches and break score ties by ascending chunk ID."""
    if k <= 0:
        raise ValueError("k must be positive")
    chunks = index["chunks"]
    average = index["average_length"]
    k1, b = index["k1"], index["b"]
    scores: dict[str, float] = defaultdict(float)
    for term in dict.fromkeys(tokenize(query)):
        posting = index["postings"].get(term, ())
        if not posting:
            continue
        idf = math.log1p((len(chunks) - len(posting) + 0.5) / (len(posting) + 0.5))
        for chunk_id, frequency in posting:
            norm = k1 * (1 - b + b * chunks[chunk_id]["token_count"] / average)
            scores[chunk_id] += idf * frequency * (k1 + 1) / (frequency + norm)
    return [
        {"rank": rank, "chunk_id": chunk_id, "score": score, **chunks[chunk_id]}
        for rank, (chunk_id, score) in enumerate(
            sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k], 1,
        )
    ]


def main() -> None:
    """Build a saved index or search it from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--chunks", type=Path, required=True)
    build.add_argument("--index", type=Path, required=True)
    query = commands.add_parser("search")
    query.add_argument("--index", type=Path, required=True)
    query.add_argument("--query", required=True)
    query.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    if args.command == "build":
        index = build_index(args.chunks)
        args.index.parent.mkdir(parents=True, exist_ok=True)
        with args.index.open("x", encoding="utf-8") as output:
            json.dump(index, output, ensure_ascii=False, separators=(",", ":"))
            output.write("\n")
    else:
        index = json.loads(args.index.read_text(encoding="utf-8"))
        print(json.dumps(search(index, args.query, args.k), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
