from pathlib import Path
from xml.etree import ElementTree as ET

from .base import BaseParser, ParsedChunk, ParsedDocument


def _element_text(element: ET.Element) -> str:
    """Recursively collect all text content of an element."""
    parts = []
    if element.text and element.text.strip():
        parts.append(element.text.strip())
    for child in element:
        child_text = _element_text(child)
        if child_text:
            parts.append(child_text)
        if child.tail and child.tail.strip():
            parts.append(child.tail.strip())
    return " ".join(parts)


class XMLParser(BaseParser):
    """Parse XML/XSD files.

    Each direct child of the root element becomes one chunk of type
    ``xml_block``.  The tag name and attributes are stored in metadata.
    """

    def supports(self, mime_type: str) -> bool:
        return mime_type in (
            "application/xml",
            "text/xml",
            "application/xsd+xml",
            "application/x-xsd",
        )

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        title = path.stem

        try:
            tree = ET.parse(file_path)
        except ET.ParseError as exc:
            # Return a single error chunk rather than crashing the pipeline.
            return ParsedDocument(
                title=title,
                chunks=[
                    ParsedChunk(
                        content=f"XML parse error: {exc}",
                        chunk_type="xml_block",
                        position=0,
                        metadata={"error": str(exc)},
                    )
                ],
            )

        root = tree.getroot()
        # Strip namespace from tag for display.
        root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        chunks: list[ParsedChunk] = []
        children = list(root)

        if not children:
            # Single-element document – treat the whole thing as one chunk.
            content = _element_text(root)
            if content:
                chunks.append(
                    ParsedChunk(
                        content=content,
                        chunk_type="xml_block",
                        position=0,
                        metadata={"tag": root_tag, "attributes": dict(root.attrib)},
                    )
                )
        else:
            for child in children:
                content = _element_text(child)
                if not content:
                    continue
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                chunks.append(
                    ParsedChunk(
                        content=content,
                        chunk_type="xml_block",
                        position=len(chunks),
                        metadata={
                            "tag": tag,
                            "attributes": dict(child.attrib),
                            "parent_tag": root_tag,
                        },
                    )
                )

        return ParsedDocument(
            title=title,
            chunks=chunks,
            metadata={"root_tag": root_tag, "root_attributes": dict(root.attrib)},
        )
