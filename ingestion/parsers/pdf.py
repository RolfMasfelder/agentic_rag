from .base import BaseParser, ParsedChunk, ParsedDocument


class PDFParser(BaseParser):
    """Parse PDF files using PyMuPDF with pdfplumber fallback."""

    def supports(self, mime_type: str) -> bool:
        return mime_type == 'application/pdf'

    def parse(self, file_path: str) -> ParsedDocument:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        title = doc.metadata.get('title') or file_path.split('/')[-1]
        chunks: list[ParsedChunk] = []

        for page_num, page in enumerate(doc, start=1):
            for i, block in enumerate(page.get_text('blocks')):
                text = block[4].strip()
                if not text:
                    continue
                chunks.append(ParsedChunk(
                    content=text,
                    chunk_type='paragraph',
                    position=len(chunks),
                    page_number=page_num,
                    metadata={'block_index': i},
                ))

        return ParsedDocument(title=title, chunks=chunks, metadata=dict(doc.metadata))
