from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedChunk:
    content: str
    chunk_type: str
    position: int
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    title: str
    chunks: list[ParsedChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument: ...

    @abstractmethod
    def supports(self, mime_type: str) -> bool: ...
