import re

from ..parsers.base import ParsedChunk
from .base import BaseChunker

# Patterns that typically indicate the start of a new contract clause.
# Examples matched:
#   "1."  "1.2"  "1.2.3"   "Article 3"   "Section 4"   "(a)"   "§ 5"
_CLAUSE_PATTERN = re.compile(
    r"(?m)^(?:"
    r"\d+(?:\.\d+)*\.?"  # 1.  /  1.2  /  1.2.3
    r"|Article\s+\w+"  # Article 3 / Article III
    r"|Section\s+\w+"  # Section 4
    r"|\([a-zA-Z]\)"  # (a) (b) (c)
    r"|§+\s*\d+"  # § 5 / §§ 5
    r")\s"
)


def _split_into_clauses(text: str) -> list[str]:
    """Split *text* into clause strings using _CLAUSE_PATTERN as delimiters."""
    boundaries = [m.start() for m in _CLAUSE_PATTERN.finditer(text)]
    if not boundaries:
        return [text.strip()] if text.strip() else []

    clauses: list[str] = []
    # Text before the first numbered clause (preamble).
    preamble = text[: boundaries[0]].strip()
    if preamble:
        clauses.append(preamble)
    for idx, start in enumerate(boundaries):
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(text)
        clause = text[start:end].strip()
        if clause:
            clauses.append(clause)
    return clauses


class ClauseChunker(BaseChunker):
    """Extract contract clauses from paragraph-type chunks.

    The chunker merges all incoming paragraph chunks into a single text,
    detects clause boundaries (numbered sections, Article/Section headers,
    lettered sub-clauses, § markers) and emits one ``clause``-type
    :class:`~ingestion.parsers.base.ParsedChunk` per clause.

    Non-paragraph chunks (e.g. ``xml_block``, ``function``) are passed
    through unchanged.
    """

    def chunk(self, chunks: list[ParsedChunk]) -> list[ParsedChunk]:
        pass_through: list[ParsedChunk] = []
        paragraph_chunks: list[ParsedChunk] = []

        for c in chunks:
            if c.chunk_type == "paragraph":
                paragraph_chunks.append(c)
            else:
                pass_through.append(c)

        if not paragraph_chunks:
            return pass_through

        # Merge all paragraph text preserving page information where possible.
        combined = "\n\n".join(c.content for c in paragraph_chunks)
        first_page = paragraph_chunks[0].page_number

        raw_clauses = _split_into_clauses(combined)

        result: list[ParsedChunk] = list(pass_through)
        for i, clause_text in enumerate(raw_clauses):
            result.append(
                ParsedChunk(
                    content=clause_text,
                    chunk_type="clause",
                    position=i,
                    page_number=first_page,
                    metadata={"clause_index": i},
                )
            )
        return result
