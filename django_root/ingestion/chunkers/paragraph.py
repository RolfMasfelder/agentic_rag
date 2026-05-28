from ..parsers.base import ParsedChunk
from .base import BaseChunker

# Chunk types that represent semantic units (produced by specialised parsers).
# They are passed through unchanged so the parser's structural decisions are
# preserved.  Only generic "paragraph" chunks are eligible for splitting.
_PASS_THROUGH_TYPES = frozenset({"xml_block", "function", "class", "clause"})


class ParagraphChunker(BaseChunker):
    """Splits long paragraph-type chunks into sub-chunks with overlap.

    Chunks whose ``chunk_type`` is a recognised semantic unit (``xml_block``,
    ``function``, ``class``, ``clause``) are passed through unchanged so that
    the structural information added by specialised parsers/chunkers is
    preserved.
    """

    def __init__(self, max_chars: int = 1500, overlap_chars: int = 100):
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, chunks: list[ParsedChunk]) -> list[ParsedChunk]:
        result: list[ParsedChunk] = []
        for chunk in chunks:
            if chunk.chunk_type in _PASS_THROUGH_TYPES:
                result.append(chunk)
            elif len(chunk.content) <= self.max_chars:
                result.append(chunk)
            else:
                result.extend(self._split(chunk))
        return result

    def _split(self, chunk: ParsedChunk) -> list[ParsedChunk]:
        sub_chunks: list[ParsedChunk] = []
        text = chunk.content
        start = 0
        while start < len(text):
            end = min(start + self.max_chars, len(text))
            sub_chunks.append(
                ParsedChunk(
                    content=text[start:end],
                    chunk_type=chunk.chunk_type,
                    position=chunk.position + len(sub_chunks),
                    page_number=chunk.page_number,
                    metadata={**chunk.metadata, "split_index": len(sub_chunks)},
                )
            )
            if end == len(text):
                break
            start = end - self.overlap_chars
        return sub_chunks
