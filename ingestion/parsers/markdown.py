import re
from pathlib import Path

from .base import BaseParser, ParsedChunk, ParsedDocument


class MarkdownParser(BaseParser):
    """Parse Markdown files into section-based chunks."""

    def supports(self, mime_type: str) -> bool:
        return mime_type in ('text/markdown', 'text/x-markdown')

    def parse(self, file_path: str) -> ParsedDocument:
        text = Path(file_path).read_text(encoding='utf-8')
        title = Path(file_path).stem
        chunks: list[ParsedChunk] = []
        current_heading = ''
        current_lines: list[str] = []

        for line in text.splitlines():
            if re.match(r'^#{1,6}\s', line):
                if current_lines:
                    chunks.append(ParsedChunk(
                        content='\n'.join(current_lines).strip(),
                        chunk_type='markdown_section',
                        position=len(chunks),
                        metadata={'heading': current_heading},
                    ))
                current_heading = line.lstrip('#').strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            chunks.append(ParsedChunk(
                content='\n'.join(current_lines).strip(),
                chunk_type='markdown_section',
                position=len(chunks),
                metadata={'heading': current_heading},
            ))

        return ParsedDocument(title=title, chunks=chunks)
