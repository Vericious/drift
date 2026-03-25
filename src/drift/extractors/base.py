"""Base extractor interface for Drift."""
from abc import ABC, abstractmethod
from pathlib import Path


class Extractor(ABC):
    """Abstract base class for all extractors."""

    @abstractmethod
    def extract(self, file_path: Path) -> list:
        """Extract facts/claims from a file."""
        ...

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """Return True if this extractor can handle this file type."""
        ...
