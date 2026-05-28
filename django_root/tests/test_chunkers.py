"""Unit tests for chunkers (no DB required)."""

import pytest

from ingestion.parsers.base import ParsedChunk


def _chunk(content: str, chunk_type: str = "paragraph", position: int = 0) -> ParsedChunk:
    return ParsedChunk(content=content, chunk_type=chunk_type, position=position)


# ---------------------------------------------------------------------------
# ParagraphChunker
# ---------------------------------------------------------------------------


class TestParagraphChunker:
    def test_short_chunk_unchanged(self):
        from ingestion.chunkers.paragraph import ParagraphChunker

        c = _chunk("Short text.")
        result = ParagraphChunker().chunk([c])
        assert len(result) == 1
        assert result[0].content == "Short text."

    def test_empty_input(self):
        from ingestion.chunkers.paragraph import ParagraphChunker

        assert ParagraphChunker().chunk([]) == []

    def test_long_chunk_is_split(self):
        from ingestion.chunkers.paragraph import ParagraphChunker

        long_text = "W" * 3000
        result = ParagraphChunker(max_chars=1000, overlap_chars=0).chunk([_chunk(long_text)])
        assert len(result) == 3
        for sub in result:
            assert len(sub.content) <= 1000

    def test_overlap_preserved(self):
        from ingestion.chunkers.paragraph import ParagraphChunker

        text = "A" * 2000
        result = ParagraphChunker(max_chars=1500, overlap_chars=200).chunk([_chunk(text)])
        assert len(result) == 2
        # Second chunk starts with the same 200 chars that end the first chunk
        assert result[1].content[:200] == result[0].content[-200:]

    @pytest.mark.parametrize("chunk_type", ["xml_block", "function", "class", "clause"])
    def test_semantic_types_passed_through(self, chunk_type):
        from ingestion.chunkers.paragraph import ParagraphChunker

        c = _chunk("A" * 5000, chunk_type=chunk_type)
        result = ParagraphChunker().chunk([c])
        assert len(result) == 1, f"Expected pass-through for type '{chunk_type}'"
        assert result[0].chunk_type == chunk_type

    def test_split_sets_split_index_metadata(self):
        from ingestion.chunkers.paragraph import ParagraphChunker

        c = _chunk("B" * 4000)
        result = ParagraphChunker(max_chars=1500, overlap_chars=0).chunk([c])
        for i, sub in enumerate(result):
            assert sub.metadata["split_index"] == i

    def test_multiple_chunks_mixed(self):
        from ingestion.chunkers.paragraph import ParagraphChunker

        chunks = [
            _chunk("Short.", position=0),
            _chunk("M" * 3000, position=1),
            _chunk("X" * 100, chunk_type="function", position=2),
        ]
        result = ParagraphChunker(max_chars=1500, overlap_chars=0).chunk(chunks)
        # short → 1, long → 2+, function → 1
        assert len(result) >= 4


# ---------------------------------------------------------------------------
# ClauseChunker
# ---------------------------------------------------------------------------


class TestClauseChunker:
    def test_numbered_clauses_detected(self):
        from ingestion.chunkers.clause import ClauseChunker

        text = (
            "Preamble text.\n\n"
            "1. First clause with some content.\n\n"
            "2. Second clause with different content.\n\n"
            "3. Third clause at the end."
        )
        result = ClauseChunker().chunk([_chunk(text)])
        clause_chunks = [c for c in result if c.chunk_type == "clause"]
        assert len(clause_chunks) >= 2

    def test_article_markers(self):
        from ingestion.chunkers.clause import ClauseChunker

        text = (
            "Article 1 General Provisions.\nThis article covers definitions.\n\n"
            "Article 2 Obligations.\nThe parties agree to the following."
        )
        result = ClauseChunker().chunk([_chunk(text)])
        clause_chunks = [c for c in result if c.chunk_type == "clause"]
        assert len(clause_chunks) >= 2

    def test_section_markers(self):
        from ingestion.chunkers.clause import ClauseChunker

        text = "Section 1 Scope.\nThis agreement covers software.\n\nSection 2 Definitions.\nThe following terms apply."
        result = ClauseChunker().chunk([_chunk(text)])
        clause_chunks = [c for c in result if c.chunk_type == "clause"]
        assert len(clause_chunks) >= 2

    def test_no_clause_markers_returns_chunk(self):
        from ingestion.chunkers.clause import ClauseChunker

        text = "Just plain text without any clause markers at all."
        result = ClauseChunker().chunk([_chunk(text)])
        assert len(result) >= 1

    def test_non_paragraph_passed_through(self):
        from ingestion.chunkers.clause import ClauseChunker

        xml = _chunk("<tag>data</tag>", chunk_type="xml_block")
        result = ClauseChunker().chunk([xml])
        assert len(result) == 1
        assert result[0].chunk_type == "xml_block"

    def test_preamble_included(self):
        from ingestion.chunkers.clause import ClauseChunker

        text = "This agreement is made between parties.\n\n1. First clause."
        result = ClauseChunker().chunk([_chunk(text)])
        all_content = " ".join(c.content for c in result)
        assert "agreement" in all_content

    def test_empty_input(self):
        from ingestion.chunkers.clause import ClauseChunker

        assert ClauseChunker().chunk([]) == []
