from abc import ABC, abstractmethod

from ..parsers.base import ParsedChunk


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, chunks: list[ParsedChunk]) -> list[ParsedChunk]: ...
