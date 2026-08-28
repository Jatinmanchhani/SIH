"""
rag.py — grounds the model in your organization's own SOPs, manuals, and correspondence.

Design: a small VectorStore interface with two implementations.
  - SimpleTfidfStore: pure Python + scikit-learn, no downloads, no GPU. Works right now,
    in this sandbox, and is genuinely good enough for a hackathon demo corpus of SOPs.
  - QdrantStore (stub below): what you swap in for the real deployment, once you're on
    your GPU box and can pull a proper embedding model (BGE-M3 / nomic-embed-text) locally.

Both implement the same three methods, so nothing else in the codebase — the orchestrator,
the gateway routes — needs to know or care which one is active.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class Chunk:
    doc_id: str
    source: str          # filename / SOP number, for citation
    text: str
    score: float = 0.0


class VectorStore(Protocol):
    def ingest(self, doc_id: str, source: str, text: str, chunk_size: int = 400) -> int:
        """Split text into chunks and index them. Returns number of chunks added."""
        ...

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        """Return the k most relevant chunks, each carrying its source for citation."""
        ...


class SimpleTfidfStore:
    """
    Working, dependency-light retriever. Good enough to demo real grounded answers
    on a real SOP corpus today. Swap for QdrantStore when you have a GPU embedding
    model — the ingest()/search() signatures stay identical.
    """

    def __init__(self):
        self._chunks: list[Chunk] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None

    def ingest(self, doc_id: str, source: str, text: str, chunk_size: int = 400) -> int:
        words = text.split()
        added = 0
        for i in range(0, len(words), chunk_size):
            piece = " ".join(words[i: i + chunk_size])
            if piece.strip():
                self._chunks.append(Chunk(doc_id=doc_id, source=source, text=piece))
                added += 1
        self._reindex()
        return added

    def _reindex(self):
        if not self._chunks:
            return
        corpus = [c.text for c in self._chunks]
        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._matrix = self._vectorizer.fit_transform(corpus)

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        if not self._chunks or self._vectorizer is None:
            return []
        query_vec = self._vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self._matrix).flatten()
        top_idx = np.argsort(sims)[::-1][:k]
        results = []
        for i in top_idx:
            if sims[i] <= 0:
                continue
            c = self._chunks[i]
            results.append(Chunk(doc_id=c.doc_id, source=c.source, text=c.text, score=float(sims[i])))
        return results


class QdrantStore:
    """
    STUB — implement this on your GPU deployment.
    Same interface as SimpleTfidfStore, so orchestrator.py never changes.

    Sketch:
      from qdrant_client import QdrantClient
      from sentence_transformers import SentenceTransformer  # or call your own embed endpoint

      def __init__(self, embed_model="BAAI/bge-m3", collection="sop_corpus"):
          self.client = QdrantClient(url="http://localhost:6333")
          self.embedder = SentenceTransformer(embed_model)   # pulled once, then fully local
          ...

      def ingest(...): embed chunks, client.upsert(...)
      def search(...): embed query, client.search(...), map hits back to Chunk objects
    """
    pass


def ingest_directory(store: VectorStore, folder: Path) -> int:
    """Walk a folder of .txt SOPs/manuals and ingest each as its own document."""
    total = 0
    for path in sorted(folder.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        total += store.ingest(doc_id=path.stem, source=path.name, text=text)
    return total


if __name__ == "__main__":
    # Self-test against the sample SOP corpus — proves grounded, cited retrieval works.
    store = SimpleTfidfStore()
    sample_dir = Path(__file__).parent.parent.parent / "sample_data"
    n = ingest_directory(store, sample_dir)
    print(f"Ingested {n} chunks from {sample_dir}\n")

    queries = [
        "What is the torque spec for flange bolts?",
        "What happens if a vendor certificate has expired?",
    ]
    for q in queries:
        print(f"Query: {q}")
        for hit in store.search(q, k=2):
            print(f"  [{hit.score:.3f}] ({hit.source}) {hit.text[:120]}...")
        print()
