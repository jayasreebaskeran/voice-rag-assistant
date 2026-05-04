"""
retriever.py
Semantic retrieval over document chunks using embeddings.

Storage strategy:
  Primary  → Redis with vector search (production)
  Fallback → In-memory cosine similarity (if Redis unavailable)

This explicit fallback is key: the system degrades gracefully instead
of crashing when Redis is down — a real failure mode in production.
"""

import logging
import os
from typing import List, Optional

import numpy as np
from openai import OpenAI

from rag.document_store import DocumentChunk

logger = logging.getLogger("rag-retriever")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


class RAGRetriever:
    """
    Retrieves the top-k most relevant chunks for a given query.
    Tries Redis first, falls back to in-memory cosine similarity.
    """

    def __init__(self, chunks: List[DocumentChunk]):
        self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._chunks = chunks
        self._redis_store = None
        self._memory_store: Optional[InMemoryVectorStore] = None

        self._setup_store()

    def _setup_store(self):
        """Try Redis first; fall back to in-memory with a logged warning."""
        try:
            from rag.redis_store import RedisVectorStore
            store = RedisVectorStore()
            self._embed_and_index(store)
            self._redis_store = store
            logger.info("Using Redis vector store")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), falling back to in-memory store")
            self._memory_store = InMemoryVectorStore()
            self._embed_and_index(self._memory_store)

    def _embed_and_index(self, store):
        """Generate embeddings for all chunks and index them."""
        texts = [c.text for c in self._chunks]
        embeddings = self._embed_batch(texts)

        for chunk, embedding in zip(self._chunks, embeddings):
            store.add(chunk.chunk_id, embedding, chunk.text)

        logger.info(f"Indexed {len(self._chunks)} chunks")

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed texts in batches of 100 (OpenAI limit).
        Handles partial failures: failed batches get zero vectors (logged).
        """
        all_embeddings = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self._client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch,
                )
                all_embeddings.extend([e.embedding for e in response.data])
            except Exception as e:
                logger.error(f"Embedding batch {i//batch_size} failed: {e}")
                # Zero vector fallback — chunk won't rank, but system keeps running
                all_embeddings.extend([[0.0] * EMBEDDING_DIM] * len(batch))

        return all_embeddings

    def retrieve(self, query: str, top_k: int = 4) -> List[str]:
        """
        Return top-k chunk texts most relevant to query.
        Returns empty list on failure — caller handles gracefully.
        """
        try:
            query_embedding = self._embed_batch([query])[0]

            store = self._redis_store or self._memory_store
            if not store:
                logger.error("No vector store available")
                return []

            results = store.search(query_embedding, top_k=top_k)
            logger.debug(f"Retrieved {len(results)} chunks for query: {query[:60]}")
            return results

        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []


class InMemoryVectorStore:
    """
    Fallback vector store using cosine similarity over numpy arrays.
    Not for production scale (no persistence, O(n) search) but reliable for demos.
    """

    def __init__(self):
        self._ids: List[str] = []
        self._vectors: List[np.ndarray] = []
        self._texts: List[str] = []

    def add(self, chunk_id: str, vector: List[float], text: str):
        self._ids.append(chunk_id)
        self._vectors.append(np.array(vector, dtype=np.float32))
        self._texts.append(text)

    def search(self, query_vector: List[float], top_k: int = 4) -> List[str]:
        if not self._vectors:
            return []

        q = np.array(query_vector, dtype=np.float32)
        matrix = np.stack(self._vectors)

        # Cosine similarity
        norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(q)
        norms = np.where(norms == 0, 1e-9, norms)  # avoid divide-by-zero
        similarities = (matrix @ q) / norms

        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [self._texts[i] for i in top_indices]
