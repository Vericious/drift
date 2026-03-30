"""Dotenv extractor for Drift.

Extracts environment variable names from .env, .env.example, .env.sample files.
Parses KEY=value lines (ignores comments starting with #, blank lines).
"""

import re
from pathlib import Path

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind


@register
class DotenvExtractor(Extractor):
    """Extract ENV_VAR facts from .env files.

    Handles:
      - .env, .env.example, .env.sample, and other .env* variants
      - KEY=value (no quotes)
      - KEY="value" (double quotes)
      - KEY='value' (single quotes)
      - KEY=value with spaces around =
      - KEY= (empty value)
      - KEY=with trailing comment # this is ignored
      - Multiline values with backslash continuation
      - export prefix (export KEY=value)

    Ignores:
      - Lines starting with # (comments)
      - Blank/empty lines
      - Lines without = sign
    """

    def can_handle(self, path: Path) -> bool:
        """Return True for .env* files."""
        name = path.name
        return name.startswith(".env") or "env." in name

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CodeFacts from a .env file."""
        facts: list[CodeFact] = []

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return facts

        # Handle backslash line continuation
        content = self._join_continued_lines(content)

        for line_num, line in enumerate(content.splitlines(), start=1):
            fact = self._parse_line(line, path, line_num)
            if fact is not None:
                facts.append(fact)

        return facts

    def _join_continued_lines(self, content: str) -> str:
        """Join lines ending with backslash continuation."""
        result_lines: list[str] = []
        current = ""

        for line in content.splitlines():
            stripped = line.rstrip()
            if stripped.endswith("\\"):
                current += stripped[:-1] + " "
            else:
                current += stripped
                result_lines.append(current)
                current = ""

        if current:
            result_lines.append(current)

        return "\n".join(result_lines)

    def _parse_line(self, line: str, source: Path, line_num: int) -> CodeFact | None:
        """Parse a single .env line into a CodeFact or None."""
        stripped = line.strip()

        # Skip blank lines
        if not stripped:
            return None

        # Skip comment lines
        if stripped.startswith("#"):
            return None

        # Find the first = sign
        eq_idx = stripped.find("=")
        if eq_idx == -1:
            return None

        # Extract key (strip whitespace, handle export prefix)
        raw_key = stripped[:eq_idx].strip()
        # Remove 'export ' prefix if present
        key = re.sub(r"^export\s+", "", raw_key, flags=re.IGNORECASE).strip()

        if not key or not self._is_valid_key(key):
            return None

        # Extract value
        raw_value = stripped[eq_idx + 1:]
        value, value_type = self._parse_value(raw_value)

        return CodeFact(
            name=key,
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line_num,
            metadata={
                "env_var": key,
                "value": value,
                "value_type": value_type,  # "unquoted", "double_quoted", "single_quoted", "empty"
                "source": ".env",
            },
        )

    def _is_valid_key(self, key: str) -> bool:
        """Check if key is a valid env var name (alphanumeric + underscore, not starting with digit)."""
        return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key))

    def _parse_value(self, raw: str) -> tuple[str, str]:
        """Parse the value part and return (cleaned_value, value_type).

        Handles:
          - "double quoted" -> extract inner, type=double_quoted
          - 'single quoted' -> extract inner, type=single_quoted
          - unquoted -> strip trailing comment only, type=unquoted
          - empty -> "", type=empty
        """
        stripped = raw.strip()

        if not stripped:
            return ("", "empty")

        # Double quoted
        if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
            inner = stripped[1:-1]
            return (inner, "double_quoted")

        # Single quoted
        if stripped.startswith("'") and stripped.endswith("'") and len(stripped) >= 2:
            inner = stripped[1:-1]
            return (inner, "single_quoted")

        # Unquoted: strip trailing inline comment only if # is preceded by space
        # value # comment -> value (space before # indicates comment delimiter)
        # value without comment -> value
        # URL with fragment like https://example.com#fragment -> keep fragment
        # (no space before # means it's part of the value)
        if re.search(r" #", stripped):
            # Space before # indicates a comment delimiter
            unquoted = stripped.split(" #")[0].rstrip()
        else:
            unquoted = stripped

        return (unquoted, "unquoted")
