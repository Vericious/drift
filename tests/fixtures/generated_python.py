"""Generated Python fixture for testing extractors."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class UserConfig:
    """User configuration dataclass."""
    name: str
    email: str
    age: int = 0
    active: bool = True


def greet(name: str, greeting: str = "Hello") -> str:
    """Greet a user with a custom greeting.

    Args:
        name: The user's name
        greeting: The greeting to use

    Returns:
        The formatted greeting string
    """
    return f"{greeting}, {name}!"


def process_data(
    data: list[int],
    multiplier: int = 1,
    verbose: bool = False
) -> list[int]:
    """Process a list of integers by multiplying each element.

    Args:
        data: Input list of integers
        multiplier: Factor to multiply by
        verbose: Enable verbose output

    Returns:
        Processed list of integers
    """
    result = [x * multiplier for x in data]
    if verbose:
        print(f"Processed {len(data)} items")
    return result


class Calculator:
    """A simple calculator class."""

    def __init__(self, precision: int = 2):
        """Initialize calculator with precision.

        Args:
            precision: Number of decimal places for results
        """
        self.precision = precision
        self._last_result: Optional[float] = None

    def add(self, a: float, b: float) -> float:
        """Add two numbers.

        Args:
            a: First operand
            b: Second operand

        Returns:
            Sum of a and b
        """
        self._last_result = a + b
        return round(self._last_result, self.precision)

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers.

        Args:
            a: First operand
            b: Second operand

        Returns:
            Product of a and b
        """
        self._last_result = a * b
        return round(self._last_result, self.precision)
