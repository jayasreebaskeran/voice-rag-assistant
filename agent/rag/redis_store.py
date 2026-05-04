"""
redis_store.py
Redis-backed vector store using RediSearch.

Why Redis:
  - Sub-millisecond retrieval even at 100k+ vectors
  - Persistent across agent restarts
  - Same instance can cache session state
"""

import json
import logging
import os
from typing import List

import numpy as np
import redis
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

logger = logging.getLogger("redis-store")

INDEX_NAME = "voice_rag_idx"
DOC_PREFIX = "chunk:"
EMBEDDING_DIM = 1536


class RedisVectorStore:
    """
    Stores and retrieves document chunk embeddings using Redis vector search.
    Index is created once per session; subsequent adds go directly to the index.
    """

    def __init__(self):
        self._client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD", None),
            decode_responses=False,
        )
        # Raises immediately if Redis is unavailable (triggering fallback in retriever.py)
        self._client.ping()
        self._ensure_index()

    def _ensure_index(self):
        """Create RediSearch index if it doesn't exist."""
        try:
            self._client.ft(INDEX_NAME).info()
            logger.debug("RediSearch index already exists")
        except Exception:
            schema = (
                TextField("text"),
                VectorField(
                    "embedding",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": EMBEDDING_DIM,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            )
            self._client.ft(INDEX_NAME).create_index(
                schema,
                definition=IndexDefinition(prefix=[DOC_PREFIX], index_type=IndexType.HASH),
            )
            logger.info(f"Created RediSearch index '{INDEX_NAME}'")

    def add(self, chunk_id: str, vector: List[float], text: str):
        """Store chunk with its embedding in Redis."""
        key = f"{DOC_PREFIX}{chunk_id}"
        embedding_bytes = np.array(vector, dtype=np.float32).tobytes()
        self._client.hset(
            key,
            mapping={
                "text": text.encode("utf-8"),
                "embedding": embedding_bytes,
            },
        )

    def search(self, query_vector: List[float], top_k: int = 4) -> List[str]:
        """KNN vector search — returns top-k chunk texts by cosine similarity."""
        query_bytes = np.array(query_vector, dtype=np.float32).tobytes()

        q = (
            Query(f"*=>[KNN {top_k} @embedding $vec AS score]")
            .sort_by("score")
            .return_fields("text", "score")
            .dialect(2)
        )

        results = self._client.ft(INDEX_NAME).search(
            q, query_params={"vec": query_bytes}
        )

        return [doc.text for doc in results.docs]

    def clear(self):
        """Remove all chunks — useful for new document uploads in same session."""
        keys = self._client.keys(f"{DOC_PREFIX}*")
        if keys:
            self._client.delete(*keys)
            logger.info(f"Cleared {len(keys)} chunks from Redis")
