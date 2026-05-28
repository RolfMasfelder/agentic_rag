import re
from pathlib import Path

from .base import BaseParser, ParsedChunk, ParsedDocument


class PlainTextParser(BaseParser):
    """Parse plain-text files into paragraph-based chunks.

    Paragraphs are separated by one or more blank lines.
    """

    def supports(self, mime_type: str) -> bool:
        return mime_type in ("text/plain",)

    def parse(self, file_path: str) -> ParsedDocument:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        title = Path(file_path).stem

        raw_paragraphs = re.split(r"\n{2,}", text)
        chunks: list[ParsedChunk] = []

        for para in raw_paragraphs:
            content = para.strip()
            if not content:
                continue
            chunks.append(
                ParsedChunk(
                    content=content,
                    chunk_type="paragraph",
                    position=len(chunks),
                )
            )

        return ParsedDocument(title=title, chunks=chunks)
