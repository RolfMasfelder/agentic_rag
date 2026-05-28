import json
from pathlib import Path
from typing import Any

from .base import BaseParser, ParsedChunk, ParsedDocument


def _load_spec(file_path: str) -> dict[str, Any]:
    """Load an OpenAPI spec from JSON or YAML."""
    path = Path(file_path)
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]

            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except ImportError:
            raise RuntimeError("PyYAML is required to parse YAML OpenAPI specs. Install it with: pip install pyyaml")
    else:
        return json.loads(path.read_text(encoding="utf-8"))


def _operation_text(method: str, path: str, operation: dict[str, Any]) -> str:
    """Build a human-readable description for a single operation."""
    parts = [f"{method.upper()} {path}"]
    if summary := operation.get("summary"):
        parts.append(summary)
    if description := operation.get("description"):
        parts.append(description)
    if tags := operation.get("tags"):
        parts.append("Tags: " + ", ".join(tags))
    if params := operation.get("parameters"):
        param_names = [p.get("name", "?") for p in params if isinstance(p, dict)]
        parts.append("Parameters: " + ", ".join(param_names))
    if req_body := operation.get("requestBody", {}).get("description"):
        parts.append("Request body: " + req_body)
    if responses := operation.get("responses"):
        codes = list(responses.keys())
        parts.append("Responses: " + ", ".join(str(c) for c in codes))
    return "\n".join(parts)


class OpenAPIParser(BaseParser):
    """Parse OpenAPI 3.x / Swagger 2.x specs.

    Produces one chunk per API operation (path + method) and one chunk per
    schema component.  chunk_type is always ``paragraph`` so the standard
    ParagraphChunker can post-process them.
    """

    HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")

    def supports(self, mime_type: str) -> bool:
        return mime_type in (
            "application/openapi+json",
            "application/openapi+yaml",
            "application/vnd.oai.openapi",
            "application/vnd.oai.openapi+json",
        )

    def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        title = path.stem
        spec: dict[str, Any] = _load_spec(file_path)

        api_title: str = spec.get("info", {}).get("title", title)
        api_version: str = spec.get("info", {}).get("version", "")
        description: str = spec.get("info", {}).get("description", "")
        chunks: list[ParsedChunk] = []

        # -- Overview chunk --------------------------------------------------
        overview_parts = [api_title]
        if api_version:
            overview_parts.append(f"Version: {api_version}")
        if description:
            overview_parts.append(description)
        if servers := spec.get("servers"):
            urls = [s.get("url", "") for s in servers if isinstance(s, dict)]
            overview_parts.append("Servers: " + ", ".join(u for u in urls if u))
        chunks.append(
            ParsedChunk(
                content="\n".join(overview_parts),
                chunk_type="paragraph",
                position=len(chunks),
                metadata={"section": "overview"},
            )
        )

        # -- Path / operation chunks -----------------------------------------
        for api_path, path_item in (spec.get("paths") or {}).items():
            if not isinstance(path_item, dict):
                continue
            for method in self.HTTP_METHODS:
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue
                content = _operation_text(method, api_path, operation)
                chunks.append(
                    ParsedChunk(
                        content=content,
                        chunk_type="paragraph",
                        position=len(chunks),
                        metadata={
                            "section": "operation",
                            "method": method.upper(),
                            "path": api_path,
                            "operation_id": operation.get("operationId", ""),
                            "tags": operation.get("tags", []),
                        },
                    )
                )

        # -- Schema / component chunks ----------------------------------------
        components = spec.get("components") or spec.get("definitions") or {}
        schemas = components.get("schemas") if isinstance(components, dict) else components
        for schema_name, schema_def in (schemas or {}).items():
            if not isinstance(schema_def, dict):
                continue
            parts = [f"Schema: {schema_name}"]
            if schema_type := schema_def.get("type"):
                parts.append(f"Type: {schema_type}")
            if schema_desc := schema_def.get("description"):
                parts.append(schema_desc)
            if properties := schema_def.get("properties"):
                parts.append("Properties: " + ", ".join(properties.keys()))
            if required := schema_def.get("required"):
                parts.append("Required: " + ", ".join(required))
            chunks.append(
                ParsedChunk(
                    content="\n".join(parts),
                    chunk_type="paragraph",
                    position=len(chunks),
                    metadata={"section": "schema", "schema_name": schema_name},
                )
            )

        return ParsedDocument(
            title=api_title,
            chunks=chunks,
            metadata={"version": api_version, "file": path.name},
        )
