import ast
import textwrap
from pathlib import Path

from .base import BaseParser, ParsedChunk, ParsedDocument

_MIME_TO_LANG: dict[str, str] = {
    "text/x-python": "python",
    "application/x-python-code": "python",
    "text/x-python-script": "python",
    # Extend with other languages as tree-sitter support is added.
}


def _parse_python(source: str, title: str) -> list[ParsedChunk]:
    """Extract top-level classes and functions from Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [
            ParsedChunk(
                content=f"Syntax error: {exc}",
                chunk_type="paragraph",
                position=0,
                metadata={"error": str(exc)},
            )
        ]

    chunks: list[ParsedChunk] = []
    lines = source.splitlines()

    def _node_source(node: ast.AST) -> str:
        start = node.lineno - 1  # type: ignore[attr-defined]
        end = node.end_lineno  # type: ignore[attr-defined]
        return "\n".join(lines[start:end])

    def _docstring(node: ast.AST) -> str:
        try:
            return ast.get_docstring(node) or ""  # type: ignore[arg-type]
        except Exception:
            return ""

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        # Only include top-level and class-level definitions (skip nested functions).
        chunk_type = "class" if isinstance(node, ast.ClassDef) else "function"
        name = node.name  # type: ignore[attr-defined]
        docstring = _docstring(node)
        node_source = _node_source(node)

        # Truncate very large definitions to keep chunks manageable.
        if len(node_source) > 3000:
            node_source = textwrap.shorten(node_source, width=3000, placeholder="\n    ...")

        content_parts = [node_source]
        if docstring:
            content_parts.insert(0, docstring)

        chunks.append(
            ParsedChunk(
                content="\n".join(content_parts),
                chunk_type=chunk_type,
                position=len(chunks),
                metadata={
                    "name": name,
                    "lineno": node.lineno,  # type: ignore[attr-defined]
                    "language": "python",
                },
            )
        )

    return chunks


class CodeParser(BaseParser):
    """Parse source-code files into function/class-level chunks.

    Currently supports Python via the built-in ``ast`` module.
    Other languages fall back to paragraph splitting.
    """

    def supports(self, mime_type: str) -> bool:
        return mime_type in _MIME_TO_LANG

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        title = path.stem
        source = path.read_text(encoding="utf-8", errors="replace")
        mime_type = _mime_for_path(path)
        lang = _MIME_TO_LANG.get(mime_type, "unknown")

        if lang == "python":
            chunks = _parse_python(source, title)
        else:
            # Fallback: one chunk per non-empty paragraph
            import re

            paragraphs = re.split(r"\n{2,}", source)
            chunks = [
                ParsedChunk(
                    content=p.strip(),
                    chunk_type="paragraph",
                    position=i,
                    metadata={"language": lang},
                )
                for i, p in enumerate(paragraphs)
                if p.strip()
            ]

        return ParsedDocument(
            title=title,
            chunks=chunks,
            metadata={"language": lang, "file": path.name},
        )


def _mime_for_path(path: Path) -> str:
    """Derive MIME type from file extension."""
    ext = path.suffix.lower()
    return {
        ".py": "text/x-python",
        ".pyw": "text/x-python",
    }.get(ext, "text/plain")
