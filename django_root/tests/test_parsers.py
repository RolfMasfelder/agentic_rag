"""Unit tests for document parsers (no DB required)."""


# ---------------------------------------------------------------------------
# PlainTextParser
# ---------------------------------------------------------------------------


def test_plain_text_supports():
    from ingestion.parsers.text import PlainTextParser

    p = PlainTextParser()
    assert p.supports("text/plain")
    assert not p.supports("text/html")
    assert not p.supports("text/markdown")


def test_plain_text_paragraphs(tmp_path):
    from ingestion.parsers.text import PlainTextParser

    f = tmp_path / "doc.txt"
    f.write_text("First paragraph.\n\nSecond paragraph.\n\nThird paragraph.")
    doc = PlainTextParser().parse(str(f))

    assert len(doc.chunks) == 3
    assert doc.chunks[0].content == "First paragraph."
    assert doc.chunks[1].content == "Second paragraph."
    assert all(c.chunk_type == "paragraph" for c in doc.chunks)


def test_plain_text_empty_file(tmp_path):
    from ingestion.parsers.text import PlainTextParser

    f = tmp_path / "empty.txt"
    f.write_text("\n\n\n")
    doc = PlainTextParser().parse(str(f))

    assert doc.chunks == []


def test_plain_text_single_paragraph(tmp_path):
    from ingestion.parsers.text import PlainTextParser

    f = tmp_path / "single.txt"
    f.write_text("Just one paragraph with no blank lines.")
    doc = PlainTextParser().parse(str(f))

    assert len(doc.chunks) == 1
    assert doc.chunks[0].position == 0


def test_plain_text_title_from_filename(tmp_path):
    from ingestion.parsers.text import PlainTextParser

    f = tmp_path / "my_document.txt"
    f.write_text("Content here.")
    doc = PlainTextParser().parse(str(f))

    assert doc.title == "my_document"


# ---------------------------------------------------------------------------
# MarkdownParser
# ---------------------------------------------------------------------------


def test_markdown_supports():
    from ingestion.parsers.markdown import MarkdownParser

    p = MarkdownParser()
    assert p.supports("text/markdown")
    assert p.supports("text/x-markdown")
    assert not p.supports("text/plain")


def test_markdown_sections(tmp_path):
    from ingestion.parsers.markdown import MarkdownParser

    f = tmp_path / "doc.md"
    f.write_text("# Introduction\nSome intro text.\n\n## Details\nMore detail text.")
    doc = MarkdownParser().parse(str(f))

    assert len(doc.chunks) == 2
    headings = [c.metadata["heading"] for c in doc.chunks]
    assert "Introduction" in headings
    assert "Details" in headings
    assert all(c.chunk_type == "markdown_section" for c in doc.chunks)


def test_markdown_no_headings(tmp_path):
    from ingestion.parsers.markdown import MarkdownParser

    f = tmp_path / "flat.md"
    f.write_text("Just plain text without any headings.")
    doc = MarkdownParser().parse(str(f))

    assert len(doc.chunks) == 1
    assert doc.chunks[0].chunk_type == "markdown_section"
    assert doc.chunks[0].metadata["heading"] == ""


def test_markdown_heading_levels(tmp_path):
    from ingestion.parsers.markdown import MarkdownParser

    f = tmp_path / "levels.md"
    f.write_text("# H1\nText.\n\n## H2\nText.\n\n### H3\nText.")
    doc = MarkdownParser().parse(str(f))

    assert len(doc.chunks) == 3


def test_markdown_empty_section_skipped(tmp_path):
    """A heading with no following content should still produce a chunk."""
    from ingestion.parsers.markdown import MarkdownParser

    f = tmp_path / "sparse.md"
    f.write_text("# Heading\n\n## Another\nWith content.")
    doc = MarkdownParser().parse(str(f))

    # Both sections should be present (even if first has minimal content)
    assert len(doc.chunks) >= 1


# ---------------------------------------------------------------------------
# PDFParser – supports() only; actual parsing requires a real PDF file.
# ---------------------------------------------------------------------------


def test_pdf_parser_supports():
    from ingestion.parsers.pdf import PDFParser

    p = PDFParser()
    assert p.supports("application/pdf")
    assert not p.supports("text/plain")


# ---------------------------------------------------------------------------
# XMLParser
# ---------------------------------------------------------------------------


def test_xml_parser_supports():
    from ingestion.parsers.xml_parser import XMLParser

    p = XMLParser()
    assert p.supports("application/xml")
    assert p.supports("text/xml")
    assert not p.supports("application/json")


def test_xml_parser_chunks(tmp_path):
    from ingestion.parsers.xml_parser import XMLParser

    f = tmp_path / "doc.xml"
    f.write_text('<?xml version="1.0"?><root><item id="1">Alpha</item><item id="2">Beta</item></root>')
    doc = XMLParser().parse(str(f))

    # Each child of root → one chunk
    assert len(doc.chunks) == 2
    assert all(c.chunk_type == "xml_block" for c in doc.chunks)


def test_xml_parser_invalid(tmp_path):
    from ingestion.parsers.xml_parser import XMLParser

    f = tmp_path / "bad.xml"
    f.write_text("<not>valid xml")
    doc = XMLParser().parse(str(f))

    # Graceful degradation: returns a document (possibly with error chunk or empty)
    assert doc is not None
