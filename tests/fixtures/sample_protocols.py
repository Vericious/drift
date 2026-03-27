"""Sample Protocol and ABC definitions for testing."""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


@runtime_checkable
class SupportsClose(Protocol):
    """A protocol for resources that can be closed."""

    def close(self) -> None:
        """Close the resource."""
        ...


class DataReader(Protocol):
    """Protocol for reading data from a source."""

    def read(self, n: int) -> bytes:
        """Read up to n bytes."""
        ...

    def get_size(self) -> int:
        """Get the total size."""
        ...


class AbstractBase(ABC):
    """A base class using ABC."""

    @abstractmethod
    def process(self, data: str) -> None:
        """Process some data."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate the state."""
        pass

    def helper(self) -> str:
        """A concrete (non-abstract) method."""
        return "helper"


class ConcreteImplementation(AbstractBase):
    """A concrete implementation of AbstractBase."""

    def process(self, data: str) -> None:
        pass

    def validate(self) -> bool:
        return True


class MixedBase(ABC):
    """A class with both abstract and concrete methods."""

    @abstractmethod
    def step_one(self) -> None:
        pass

    def step_two(self) -> None:
        """Concrete — not extracted."""
        pass


class Animal(Protocol):
    """A protocol for animals."""

    @property
    def name(self) -> str:
        ...

    def speak(self) -> str:
        ...
