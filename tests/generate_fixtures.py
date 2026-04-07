#!/usr/bin/env python3
"""Generate standardized test fixtures for reproducible test data.

This script creates:
- Python files with known functions/classes
- TypeScript files with interfaces/enums
- Markdown files with API references

Each fixture has a companion .expected.json with expected extraction results.

Usage:
    python tests/generate_fixtures.py [--output tests/fixtures]
"""

import argparse
import json
from pathlib import Path


def generate_python_fixture() -> tuple[str, dict]:
    """Generate a Python file with known structures and its expected output."""
    code = '''"""Generated Python fixture for testing extractors."""

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
'''

    expected = {
        "facts": [
            {
                "name": "UserConfig",
                "kind": "class",
                "parameters": [
                    {"name": "name", "type_annotation": "str", "default": None, "kind": "required"},
                    {"name": "email", "type_annotation": "str", "default": None, "kind": "required"},
                    {"name": "age", "type_annotation": "int", "default": "0", "kind": "required"},
                    {"name": "active", "type_annotation": "bool", "default": "True", "kind": "required"},
                ],
                "return_type": None,
            },
            {
                "name": "greet",
                "kind": "function",
                "parameters": [
                    {"name": "name", "type_annotation": "str", "default": None, "kind": "required"},
                    {"name": "greeting", "type_annotation": "str", "default": '"Hello"', "kind": "required"},
                ],
                "return_type": "str",
            },
            {
                "name": "process_data",
                "kind": "function",
                "parameters": [
                    {"name": "data", "type_annotation": "list[int]", "default": None, "kind": "required"},
                    {"name": "multiplier", "type_annotation": "int", "default": "1", "kind": "required"},
                    {"name": "verbose", "type_annotation": "bool", "default": "False", "kind": "required"},
                ],
                "return_type": "list[int]",
            },
            {
                "name": "Calculator",
                "kind": "class",
                "parameters": [
                    {"name": "precision", "type_annotation": "int", "default": "2", "kind": "required"},
                ],
                "return_type": None,
            },
            {
                "name": "Calculator.add",
                "kind": "method",
                "parameters": [
                    {"name": "a", "type_annotation": "float", "default": None, "kind": "required"},
                    {"name": "b", "type_annotation": "float", "default": None, "kind": "required"},
                ],
                "return_type": "float",
            },
            {
                "name": "Calculator.multiply",
                "kind": "method",
                "parameters": [
                    {"name": "a", "type_annotation": "float", "default": None, "kind": "required"},
                    {"name": "b", "type_annotation": "float", "default": None, "kind": "required"},
                ],
                "return_type": "float",
            },
        ],
        "claims": [],
    }

    return code, expected


def generate_typescript_fixture() -> tuple[str, dict]:
    """Generate a TypeScript file with known interfaces and enums."""
    code = '''/**
 * Generated TypeScript fixture for testing extractors
 */

export interface User {
  /** User's full name */
  name: string;
  /** User's email address */
  email: string;
  /** User's age in years */
  age?: number;
  /** Whether user is active */
  active: boolean;
}

export interface Config {
  /** API endpoint URL */
  apiUrl: string;
  /** API key (read-only after initialization) */
  readonly apiKey: string;
  /** Timeout in milliseconds */
  timeout?: number;
}

export enum UserRole {
  Admin = "ADMIN",
  User = "USER",
  Guest = "GUEST",
}

export enum HttpStatus {
  Ok = 200,
  NotFound = 404,
  Error = 500,
}

export type UserOrGuest = User | { guest: true; name: string };

export function greet(name: string, greeting: string = "Hello"): string {
  return `${greeting}, ${name}!`;
}

export async function fetchData<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}
'''

    expected = {
        "facts": [
            {
                "name": "User",
                "kind": "interface",
                "parameters": [
                    {"name": "name", "type_annotation": "string", "default": None, "kind": "required"},
                    {"name": "email", "type_annotation": "string", "default": None, "kind": "required"},
                    {"name": "age", "type_annotation": "number", "default": None, "kind": "optional"},
                    {"name": "active", "type_annotation": "boolean", "default": None, "kind": "required"},
                ],
                "return_type": None,
            },
            {
                "name": "Config",
                "kind": "interface",
                "parameters": [
                    {"name": "apiUrl", "type_annotation": "string", "default": None, "kind": "required"},
                    {"name": "apiKey", "type_annotation": "string", "default": None, "kind": "required", "is_readonly": True},
                    {"name": "timeout", "type_annotation": "number", "default": None, "kind": "optional"},
                ],
                "return_type": None,
            },
            {
                "name": "UserRole",
                "kind": "enum",
                "parameters": [
                    {"name": "Admin", "type_annotation": None, "default": '"ADMIN"', "kind": "required"},
                    {"name": "User", "type_annotation": None, "default": '"USER"', "kind": "required"},
                    {"name": "Guest", "type_annotation": None, "default": '"GUEST"', "kind": "required"},
                ],
                "return_type": None,
            },
            {
                "name": "HttpStatus",
                "kind": "enum",
                "parameters": [
                    {"name": "Ok", "type_annotation": None, "default": "200", "kind": "required"},
                    {"name": "NotFound", "type_annotation": None, "default": "404", "kind": "required"},
                    {"name": "Error", "type_annotation": None, "default": "500", "kind": "required"},
                ],
                "return_type": None,
            },
            {
                "name": "UserOrGuest",
                "kind": "type_alias",
                "parameters": [],
                "return_type": None,
            },
            {
                "name": "greet",
                "kind": "function",
                "parameters": [
                    {"name": "name", "type_annotation": "string", "default": None, "kind": "required"},
                    {"name": "greeting", "type_annotation": "string", "default": '"Hello"', "kind": "required"},
                ],
                "return_type": "string",
            },
            {
                "name": "fetchData",
                "kind": "function",
                "parameters": [
                    {"name": "url", "type_annotation": "string", "default": None, "kind": "required"},
                    {"name": "options", "type_annotation": "RequestInit", "default": None, "kind": "optional"},
                ],
                "return_type": "Promise<T>",
            },
        ],
        "claims": [],
    }

    return code, expected


def generate_markdown_fixture() -> tuple[str, dict]:
    """Generate a Markdown file with API documentation."""
    code = '''# API Documentation

## User Management

### `greet(name: str, greeting: str = "Hello") -> str`

Greets a user with a custom greeting.

**Parameters:**
- `name` (str): The user's name
- `greeting` (str, optional): The greeting to use. Defaults to "Hello".

**Returns:**
- `str`: The formatted greeting string

**Example:**
```python
result = greet("Alice", "Hi")
# Returns: "Hi, Alice!"
```

### `process_data(data: list[int], multiplier: int = 1) -> list[int]`

Processes a list of integers by multiplying each element.

**Parameters:**
- `data` (list[int]): Input list of integers
- `multiplier` (int, optional): Factor to multiply by. Defaults to 1.

**Returns:**
- `list[int]`: Processed list of integers

## Calculator Class

### `class Calculator`

A simple calculator for basic arithmetic operations.

#### `Calculator.__init__(precision: int = 2)`

Initialize the calculator.

**Parameters:**
- `precision` (int): Number of decimal places for results. Defaults to 2.

#### `Calculator.add(a: float, b: float) -> float`

Add two numbers.

**Parameters:**
- `a` (float): First operand
- `b` (float): Second operand

**Returns:**
- `float`: Sum of a and b

#### `Calculator.multiply(a: float, b: float) -> float`

Multiply two numbers.

**Parameters:**
- `a` (float): First operand
- `b` (float): Second operand

**Returns:**
- `float`: Product of a and b
'''

    expected = {
        "facts": [],
        "claims": [
            {
                "name": "greet",
                "kind": "function",
                "parameters": [
                    {"name": "name", "type_annotation": "str", "default": None, "kind": "required"},
                    {"name": "greeting", "type_annotation": "str", "default": '"Hello"', "kind": "required"},
                ],
                "return_type": "str",
            },
            {
                "name": "process_data",
                "kind": "function",
                "parameters": [
                    {"name": "data", "type_annotation": "list[int]", "default": None, "kind": "required"},
                    {"name": "multiplier", "type_annotation": "int", "default": "1", "kind": "required"},
                ],
                "return_type": "list[int]",
            },
            {
                "name": "Calculator",
                "kind": "class",
                "parameters": [
                    {"name": "precision", "type_annotation": "int", "default": "2", "kind": "required"},
                ],
                "return_type": None,
            },
            {
                "name": "Calculator.add",
                "kind": "method",
                "parameters": [
                    {"name": "a", "type_annotation": "float", "default": None, "kind": "required"},
                    {"name": "b", "type_annotation": "float", "default": None, "kind": "required"},
                ],
                "return_type": "float",
            },
            {
                "name": "Calculator.multiply",
                "kind": "method",
                "parameters": [
                    {"name": "a", "type_annotation": "float", "default": None, "kind": "required"},
                    {"name": "b", "type_annotation": "float", "default": None, "kind": "required"},
                ],
                "return_type": "float",
            },
        ],
    }

    return code, expected


def main(output_dir: Path) -> None:
    """Generate all fixtures and write to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    fixtures = [
        ("generated_python.py", *generate_python_fixture()),
        ("generated_typescript.ts", *generate_typescript_fixture()),
        ("generated_markdown.md", *generate_markdown_fixture()),
    ]

    for filename, content, expected in fixtures:
        # Write the source file
        source_path = output_dir / filename
        source_path.write_text(content)
        print(f"Created: {source_path}")

        # Write the expected JSON
        expected_path = output_dir / f"{filename}.expected.json"
        expected_path.write_text(json.dumps(expected, indent=2))
        print(f"Created: {expected_path}")

    print(f"\nGenerated {len(fixtures)} fixture sets in {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate standardized test fixtures"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "fixtures",
        help="Output directory for fixtures",
    )
    args = parser.parse_args()

    main(args.output)
