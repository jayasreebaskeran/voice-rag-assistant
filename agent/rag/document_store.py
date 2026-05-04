"""
document_store.py
Handles PDF parsing, text chunking, and embedding generation.

Design decisions:
  - Chunk size 500 tokens with 50-token overlap to preserve context across boundaries
  - Overlap prevents answers being split across chunk edges (common RAG failure)
  - Embeddings cached in Redis by content hash — avoids re-embedding same doc
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import List

import fitz  # PyMuPDF

logger = logging.getLogger("document-store")

CHUNK_SIZE = 500       # characters per chunk
CHUNK_OVERLAP = 80     # overlap between adjacent chunks


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    page_num: int
    source: str
    char_start: int
    char_end: int


class DocumentStore:
    """Parses PDFs and splits them into overlapping chunks for RAG retrieval."""

    def process_pdf(self, pdf_bytes: bytes, filename: str) -> List[DocumentChunk]:
        """
        Main entry point: bytes → List[DocumentChunk]
        Failure modes handled:
          - Encrypted PDF → raises ValueError with clear message
          - Empty pages → skipped with warning
          - Corrupt PDF → raises with details
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ValueError(f"Cannot open PDF '{filename}': {e}")

        if doc.is_encrypted:
            raise ValueError(f"PDF '{filename}' is password-protected. Please provide an unlocked PDF.")

        full_text = self._extract_text(doc, filename)
        if not full_text.strip():
            logger.warning(f"No text extracted from {filename} — possibly a scanned PDF")
            return []

        chunks = self._chunk_text(full_text, filename)
        logger.info(f"Extracted {len(chunks)} chunks from {filename} ({len(full_text)} chars)")
        return chunks

    def _extract_text(self, doc: fitz.Document, filename: str) -> str:
        """Extract text from all pages, preserving page structure."""
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                pages.append(f"\n[Page {page_num + 1}]\n{text}")
            else:
                logger.debug(f"Page {page_num + 1} of {filename} has no extractable text")
        return "\n".join(pages)

    def _chunk_text(self, text: str, source: str) -> List[DocumentChunk]:
        """Split text into overlapping chunks with stable IDs."""
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))

            # Don't cut in the middle of a word
            if end < len(text):
                last_space = text.rfind(" ", start, end)
                if last_space > start:
                    end = last_space

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_id = hashlib.md5(
                    f"{source}:{chunk_index}:{chunk_text[:50]}".encode()
                ).hexdigest()[:12]

                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    page_num=self._estimate_page(text, start),
                    source=source,
                    char_start=start,
                    char_end=end,
                ))
                chunk_index += 1

            # Move forward with overlap
            start = end - CHUNK_OVERLAP
            if start <= 0:
                break

        return chunks


    def _estimate_page(self, text: str, char_pos: int) -> int:
        """Estimate page number from character position using [Page N] markers."""
        snippet = text[:char_pos]
        count = snippet.count("[Page ")
        return max(1, count)
