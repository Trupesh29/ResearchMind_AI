"""ResearchMind AI — BM25 Sparse Keyword Search Service (Phase 5).

Implements deterministic Okapi BM25 for sparse retrieval across eligible chunk manifests.
Features:
- Regex word tokenization matching standard IR preprocessing
- Parameterized BM25Okapi scoring (k1=1.5, b=0.75)
- Documented serialization/deserialization to atomic JSON artifacts
- Filtered candidate querying with score sorting and deterministic tie-breaking
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

WORD_REGEX = re.compile(r"\b\w+\b", re.UNICODE)


def tokenize_bm25(text: str) -> list[str]:
    """Tokenize text into lowercase words for keyword retrieval."""
    if not text:
        return []
    return WORD_REGEX.findall(text.lower())


class BM25Index:
    """In-memory and file-backed BM25 keyword index."""

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size: int = 0
        self.avgdl: float = 0.0
        self.doc_ids: list[str] = []
        self.paper_ids: list[str] = []
        self.doc_lengths: list[int] = []
        self.idf: dict[str, float] = {}
        # Inverted index: term -> list of [doc_index, term_frequency]
        self.inverted_index: dict[str, list[list[int]]] = {}

    def fit(self, chunks: list[dict[str, Any]]) -> BM25Index:
        """Build BM25 index from a manifest of eligible chunk dictionaries.

        Each dictionary must have:
        - "chunk_id": str
        - "paper_id": str
        - "text": str
        """
        self.corpus_size = len(chunks)
        self.doc_ids = []
        self.paper_ids = []
        self.doc_lengths = []
        self.idf = {}
        self.inverted_index = {}

        if self.corpus_size == 0:
            self.avgdl = 0.0
            return self

        # Document frequencies for IDF
        doc_frequencies: Counter[str] = Counter()
        total_len = 0

        for doc_idx, chunk in enumerate(chunks):
            cid = chunk.get("chunk_id") or chunk.get("id") or str(doc_idx)
            self.doc_ids.append(cid)
            self.paper_ids.append(chunk.get("paper_id", ""))

            tokens = tokenize_bm25(chunk.get("text", ""))
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_len += doc_len

            term_counts = Counter(tokens)
            for term, count in term_counts.items():
                doc_frequencies[term] += 1
                if term not in self.inverted_index:
                    self.inverted_index[term] = []
                self.inverted_index[term].append([doc_idx, count])

        self.avgdl = total_len / float(self.corpus_size) if self.corpus_size > 0 else 0.0

        # Calculate Okapi BM25 IDF: ln(1 + (N - n + 0.5) / (n + 0.5))
        for term, df in doc_frequencies.items():
            idf_val = math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))
            self.idf[term] = max(1e-4, idf_val)

        return self

    build = fit

    @property
    def doc_count(self) -> int:
        """Return the number of documents in the index."""
        return self.corpus_size

    def search(
        self,
        query: str,
        top_k: int = 30,
        eligible_indices: set[int] | None = None,
    ) -> list[tuple[int, float]]:
        """Search the index with BM25 Okapi scoring.

        Returns list of (doc_index, score) sorted descending by score.
        Ties are broken deterministically by doc_index ascending.
        """
        if self.corpus_size == 0 or not query.strip():
            return []

        q_tokens = tokenize_bm25(query)
        if not q_tokens:
            return []

        scores: dict[int, float] = {}

        for term in q_tokens:
            if term not in self.inverted_index:
                continue

            term_idf = self.idf.get(term, 0.0)
            postings = self.inverted_index[term]

            for doc_idx, tf in postings:
                if eligible_indices is not None and doc_idx not in eligible_indices:
                    continue

                doc_len = self.doc_lengths[doc_idx]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                term_score = term_idf * (numerator / denominator)

                scores[doc_idx] = scores.get(doc_idx, 0.0) + term_score

        # Sort descending by score, tie-break by index ascending
        scored_docs = [(idx, score) for idx, score in scores.items() if score > 0.0]
        scored_docs.sort(key=lambda x: (-x[1], x[0]))
        return scored_docs[:top_k]

    def save(self, file_path: str | Path) -> None:
        """Save the index to a JSON file."""
        data = {
            "k1": self.k1,
            "b": self.b,
            "corpus_size": self.corpus_size,
            "avgdl": self.avgdl,
            "doc_ids": self.doc_ids,
            "paper_ids": self.paper_ids,
            "doc_lengths": self.doc_lengths,
            "idf": self.idf,
            "inverted_index": self.inverted_index,
        }
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, file_path: str | Path) -> BM25Index:
        """Load an index from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        idx = cls(k1=data.get("k1", 1.5), b=data.get("b", 0.75))
        idx.corpus_size = data.get("corpus_size", 0)
        idx.avgdl = data.get("avgdl", 0.0)
        idx.doc_ids = data.get("doc_ids", [])
        idx.paper_ids = data.get("paper_ids", [])
        idx.doc_lengths = data.get("doc_lengths", [])
        idx.idf = data.get("idf", {})
        idx.inverted_index = data.get("inverted_index", {})
        return idx
