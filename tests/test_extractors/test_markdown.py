"""Tests for MarkdownExtractor."""
import pytest
from pathlib import Path
import tempfile
import os

from drift.extractors.markdown import MarkdownExtractor
from drift.models import ClaimKind


@pytest.fixture
def extractor():
    return MarkdownExtractor()


@pytest.fixture
def sample_markdown():
    """Sample markdown string with various patterns to extract."""
    return """# Sample Documentation

## Introduction

This is a sample module for testing drift detection.

## Functions

### simple_func

A simple function that takes two parameters.

```python
def simple_func(x: int, y: str = "hello") -> bool:
    pass
```

### old_function

This function was renamed but docs weren't updated.

```python
def old_function(a, b, c)
```

## Usage

You can call `simple_func(42, "world")` directly.

For more complex usage, try `process_data(items, debug=True)`.

## CLI

To scan your project:

$ drift scan ./src

To check version:

$ drift --version

## Plain Prose

This is just plain prose that should be ignored by the extractor.
It mentions simple_func without backticks and talks about
how the function works in natural language.

Another line of prose here.
"""


@pytest.fixture
def malformed_markdown():
    """Markdown with malformed/partial signatures."""
    return """# Malformed Examples

A code block with incomplete signature:

```python
def partial
```

Another with just parameters:

```python
(x: int, y: str)
```

And some edge cases:

```python
# just a comment
```

Inline with extra backticks: `foo(bar, `baz`)

$ command with no args
"""


class TestMarkdownExtractor:
    """Test cases for MarkdownExtractor."""

    def test_can_handle(self, extractor):
        """Test file type detection."""
        assert extractor.can_handle(Path("readme.md")) is True
        assert extractor.can_handle(Path("docs/api.md")) is True
        assert extractor.can_handle(Path("README.MD")) is True
        assert extractor.can_handle(Path("readme.txt")) is False
        assert extractor.can_handle(Path("readme.py")) is False

    def test_extract_full_function_signature_from_code_block(self, extractor, sample_markdown, tmp_path):
        """Test case 1: Extract full function signature from code block."""
        md_file = tmp_path / "test.md"
        md_file.write_text(sample_markdown)

        claims = extractor.extract(md_file)

        # Find function signature claims
        sig_claims = [c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE]

        assert len(sig_claims) >= 1  # At least simple_func found

        # Check simple_func
        simple_func = next((c for c in sig_claims if c.name == 'simple_func'), None)
        assert simple_func is not None
        assert simple_func.line_number >= 1  # Line number in code block
        assert len(simple_func.parameters) == 2
        assert simple_func.parameters[0].name == 'x'
        assert simple_func.parameters[0].type_annotation == 'int'
        assert simple_func.parameters[1].name == 'y'
        assert simple_func.parameters[1].type_annotation == 'str'
        assert simple_func.parameters[1].default == '"hello"'
        assert simple_func.return_type == 'bool'

        # Check old_function (no type annotations, no return)
        old_func = next((c for c in sig_claims if c.name == 'old_function'), None)
        assert old_func is not None
        assert len(old_func.parameters) == 3

    def test_extract_inline_code_reference(self, extractor, sample_markdown, tmp_path):
        """Test case 2: Extract inline code reference."""
        md_file = tmp_path / "test.md"
        md_file.write_text(sample_markdown)

        claims = extractor.extract(md_file)

        # Find code example claims
        code_claims = [c for c in claims if c.kind == ClaimKind.CODE_EXAMPLE]

        # Should have simple_func(42, "world") and process_data(items, debug=True)
        assert len(code_claims) >= 2

        # Check simple_func call
        simple_call = next((c for c in code_claims if c.name == 'simple_func'), None)
        assert simple_call is not None
        assert '42' in simple_call.raw_text
        assert 'world' in simple_call.raw_text

        # Check process_data call
        process_call = next((c for c in code_claims if c.name == 'process_data'), None)
        assert process_call is not None

    def test_extract_cli_usage(self, extractor, sample_markdown, tmp_path):
        """Test case 3: Extract CLI usage."""
        md_file = tmp_path / "test.md"
        md_file.write_text(sample_markdown)

        claims = extractor.extract(md_file)

        # Find CLI usage claims
        cli_claims = [c for c in claims if c.kind == ClaimKind.CLI_USAGE]

        assert len(cli_claims) >= 2

        # Check drift scan
        scan_claim = next((c for c in cli_claims if 'scan' in c.metadata.get('args', '')), None)
        assert scan_claim is not None
        assert scan_claim.name == 'drift'

        # Check drift --version
        version_claim = next((c for c in cli_claims if 'version' in c.raw_text), None)
        assert version_claim is not None

    def test_ignore_plain_prose(self, extractor, sample_markdown, tmp_path):
        """Test case 4: Ignore plain prose (no backticks)."""
        md_file = tmp_path / "test.md"
        md_file.write_text(sample_markdown)

        claims = extractor.extract(md_file)

        # All claims should have raw_text that looks like code
        for claim in claims:
            raw = claim.raw_text
            # raw_text should either be a code block line, backtick-wrapped code,
            # or a CLI command
            assert len(raw) > 0
            # Plain prose words like "This", "function", "was", etc should not appear
            # as standalone raw_text values
            assert not raw.startswith('This function was')

    def test_handle_malformed_signatures(self, extractor, malformed_markdown, tmp_path):
        """Test case 5: Handle malformed/partial signatures gracefully."""
        md_file = tmp_path / "test.md"
        md_file.write_text(malformed_markdown)

        # Should not raise any exceptions
        claims = extractor.extract(md_file)

        # Should return some valid claims or empty list, not crash
        assert isinstance(claims, list)

        # Check that we didn't produce garbage
        for claim in claims:
            assert claim.kind in ClaimKind
            assert claim.line_number > 0
            assert claim.doc_file == md_file

    def test_no_file_returns_empty_list(self, extractor, tmp_path):
        """Test that non-existent files return empty list."""
        claims = extractor.extract(tmp_path / "nonexistent.md")
        assert claims == []

    def test_empty_file_returns_empty_list(self, extractor, tmp_path):
        """Test that empty files return empty list."""
        md_file = tmp_path / "empty.md"
        md_file.write_text("")

        claims = extractor.extract(md_file)
        assert claims == []

    def test_line_numbers_correct(self, extractor, tmp_path):
        """Test that line numbers are correctly reported."""
        content = """# Header

```python
def foo():
    pass
```

Next is `bar(x)`

$ drift run
"""
        md_file = tmp_path / "test.md"
        md_file.write_text(content)

        claims = extractor.extract(md_file)

        # Find foo function
        foo_claim = next((c for c in claims if c.name == 'foo'), None)
        assert foo_claim is not None
        assert foo_claim.line_number >= 1  # The def line within code block

        # Find bar inline
        bar_claim = next((c for c in claims if c.name == 'bar'), None)
        assert bar_claim is not None
        assert bar_claim.line_number >= 1

        # Find drift
        drift_claim = next((c for c in claims if c.name == 'drift'), None)
        assert drift_claim is not None
        assert drift_claim.line_number >= 1


class TestMarkdownExtractorEdgeCases:
    """Edge case tests for MarkdownExtractor."""

    def test_function_with_no_parameters(self, extractor, tmp_path):
        """Function with no parameters."""
        content = """```python
def no_params() -> None:
    pass
```"""
        md_file = tmp_path / "test.md"
        md_file.write_text(content)

        claims = extractor.extract(md_file)
        func_claim = next((c for c in claims if c.name == 'no_params'), None)

        assert func_claim is not None
        assert func_claim.parameters == []
        assert func_claim.return_type == 'None'

    def test_function_with_varargs(self, extractor, tmp_path):
        """Function with *args."""
        content = """```python
def with_args(*args, **kwargs):
    pass
```"""
        md_file = tmp_path / "test.md"
        md_file.write_text(content)

        claims = extractor.extract(md_file)
        func_claim = next((c for c in claims if c.name == 'with_args'), None)

        assert func_claim is not None
        assert len(func_claim.parameters) == 2

    def test_nested_backticks(self, extractor, tmp_path):
        """Inline code with nested backticks should extract outer."""
        content = """Use `foo(`bar`)` syntax.
"""
        md_file = tmp_path / "test.md"
        md_file.write_text(content)

        claims = extractor.extract(md_file)
        # Should extract foo(bar) somehow, not crash
        assert isinstance(claims, list)

    def test_multiple_files_independent(self, extractor, tmp_path):
        """Each file should be processed independently."""
        md1 = tmp_path / "a.md"
        md2 = tmp_path / "b.md"
        md1.write_text("```python\ndef func_a():\n    pass\n```")
        md2.write_text("```python\ndef func_b():\n    pass\n```")

        claims1 = extractor.extract(md1)
        claims2 = extractor.extract(md2)

        assert any(c.name == 'func_a' for c in claims1)
        assert any(c.name == 'func_b' for c in claims2)
        assert not any(c.name == 'func_b' for c in claims1)
        assert not any(c.name == 'func_a' for c in claims2)
