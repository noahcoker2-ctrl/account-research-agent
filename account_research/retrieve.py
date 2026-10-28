"""Splits pages into labelled chunks and picks the most relevant ones (BM25).

Only the selected chunks are shown to the model, each with a source label
like [S4]. That keeps the prompt small and lets every claim be traced back.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from .fetch import Page

_STOP = set(
    "a an and are as at be by for from has have in is it its of on or our that the their this to was we "
    "with you your does do any such than other rather".split()
)


@dataclass
class Chunk:
    id: str
    url: str
    kind: str
    title: str
    text: str


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP]


def chunk_pages(pages: list[Page], size: int = 110, overlap: int = 25) -> list[Chunk]:
    """Split each page into overlapping word windows, labelled S1, S2, ..."""
    chunks: list[Chunk] = []
    step = size - overlap
    for page in pages:
        words = page.text.split()
        if not words:
            continue
        for start in range(0, len(words), step):
            piece = " ".join(words[start:start + size])
            chunks.append(Chunk(f"S{len(chunks) + 1}", page.url, page.kind, page.title, piece))
            if start + size >= len(words):
                break
    return chunks


class Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.bm25 = BM25Okapi([tokenize(c.text + " " + c.kind) for c in chunks]) if chunks else None

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        if not self.bm25:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        return [self.chunks[i] for i in ranked[:k] if scores[i] > 0]


def select_context(chunks: list[Chunk], queries: list[str], k_per_query: int = 3, max_chunks: int = 18) -> list[Chunk]:
    """Always keep the start of the homepage, then the best chunks for each question.
    Small sites that fit within the budget are passed through whole."""
    if len(chunks) <= max_chunks:
        return list(chunks)
    retriever = Retriever(chunks)
    picked: dict[str, Chunk] = {}
    for c in chunks:
        if c.kind == "homepage":
            picked[c.id] = c
            break
    for q in queries:
        for c in retriever.search(q, k_per_query):
            if len(picked) >= max_chunks:
                break
            picked.setdefault(c.id, c)
    # Present sources in their original order so the prompt reads naturally.
    order = {c.id: i for i, c in enumerate(chunks)}
    return sorted(picked.values(), key=lambda c: order[c.id])
