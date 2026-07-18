"""Simple text chunking for the local ingest pipeline (Glue-ish transform)."""
from __future__ import annotations


def chunk_text(
    text: str,
    *,
    max_chars: int = 400,
    min_chars: int = 40,
) -> list[str]:
    """Split on blank lines, then soft-wrap long paragraphs.

    Keeps chunks small enough for RAG embeddings without needing LangChain.
    """
    paragraphs = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            if len(para) >= min_chars:
                chunks.append(para)
            elif chunks:
                # Merge tiny leftovers onto the previous chunk when possible.
                merged = f"{chunks[-1]}\n{para}"
                if len(merged) <= max_chars:
                    chunks[-1] = merged
                elif len(para) >= 20:
                    chunks.append(para)
            elif len(para) >= 20:
                chunks.append(para)
            continue
        # Soft-wrap long paragraphs on sentence boundaries when possible.
        start = 0
        while start < len(para):
            end = min(start + max_chars, len(para))
            if end < len(para):
                cut = para.rfind(". ", start, end)
                if cut > start + min_chars:
                    end = cut + 1
            piece = para[start:end].strip()
            if piece:
                chunks.append(piece)
            start = end
    return chunks
