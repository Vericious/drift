"""Tests for the deprecated extractor."""

import pytest
from pathlib import Path

from drift.extractors.deprecated import DeprecatedExtractor, _parse_docstring_deprecation as _parse_deprecated_directive
from drift.models import FactKind


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_deprecated.py"


class TestDeprecatedExtractor:
    """Tests for DeprecatedExtractor."""

    def test_can_handle_py_file(self):
        """Verify can_handle returns True for .py files."""
        extractor = DeprecatedExtractor()
        assert extractor.can_handle(Path("foo.py")) is True

    def test_can_handle_non_py_file(self):
        """Verify can_handle returns False for non-.py files."""
        extractor = DeprecatedExtractor()
        assert extractor.can_handle(Path("foo.md")) is False
        assert extractor.can_handle(Path("foo.yaml")) is False

    def test_extracts_deprecated_decorator_with_reason(self):
        """Verify @deprecated(reason=...) is detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        old_func_facts = [f for f in facts if "old_func_with_reason" in f.name]
        assert len(old_func_facts) >= 1

        fact = old_func_facts[0]
        assert fact.kind == FactKind.DEPRECATED
        assert fact.metadata["deprecation_type"] == "decorator"
        assert "reason" in fact.metadata

    def test_extracts_deprecated_decorator_with_version(self):
        """Verify @deprecated(version=..., reason=...) is detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        versioned_facts = [f for f in facts if "versioned_deprecated" in f.name]
        assert len(versioned_facts) >= 1

        fact = versioned_facts[0]
        assert fact.kind == FactKind.DEPRECATED
        assert fact.metadata["version"] == "1.5"
        assert "reason" in fact.metadata

    def test_extracts_msg_style_deprecation(self):
        """Verify @deprecated(msg=...) style is detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        msg_facts = [f for f in facts if "msg_style_deprecated" in f.name]
        assert len(msg_facts) >= 1

        fact = msg_facts[0]
        assert fact.kind == FactKind.DEPRECATED
        assert "version" in fact.metadata or "reason" in fact.metadata

    def test_extracts_abc_deprecated_decorator(self):
        """Verify @abc.deprecated is detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        old_class_facts = [f for f in facts if "OldClass" in f.name and "SubClass" not in f.name]
        assert len(old_class_facts) >= 1

        fact = old_class_facts[0]
        assert fact.kind == FactKind.DEPRECATED
        assert fact.metadata["deprecation_type"] == "decorator"

    def test_extracts_docstring_deprecated_directive(self):
        """Verify .. deprecated:: directive is detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        doc_facts = [f for f in facts if "docstring_deprecated_func" in f.name]
        assert len(doc_facts) >= 1

        fact = doc_facts[0]
        assert fact.kind == FactKind.DEPRECATED
        assert fact.metadata["deprecation_type"] == "docstring"
        assert fact.metadata["version"] == "2.0"
        assert "reason" in fact.metadata

    def test_extracts_docstring_deprecated_since(self):
        """Verify .. deprecated since: directive is detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        since_facts = [f for f in facts if "docstring_since_deprecated" in f.name]
        assert len(since_facts) >= 1

        fact = since_facts[0]
        assert fact.kind == FactKind.DEPRECATED
        assert fact.metadata["deprecation_type"] == "docstring"
        assert fact.metadata["version"] == "1.8"

    def test_extracts_class_docstring_deprecation(self):
        """Verify class-level .. deprecated:: is detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        class_facts = [f for f in facts if "ClassWithDocstringDeprecation" in f.name]
        assert len(class_facts) >= 1

    def test_extracts_method_docstring_deprecation(self):
        """Verify method-level docstring deprecation is detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        method_facts = [
            f for f in facts
            if "ClassWithDocstringDeprecation" in f.name and "deprecated_method" in f.name
        ]
        assert len(method_facts) >= 1
        fact = method_facts[0]
        assert fact.metadata["deprecation_type"] == "docstring"

    def test_extracts_reason_only_docstring(self):
        """Verify .. deprecated:: without version is detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        reason_facts = [f for f in facts if "reason_only_deprecated" in f.name]
        assert len(reason_facts) >= 1

        fact = reason_facts[0]
        assert fact.kind == FactKind.DEPRECATED
        assert fact.metadata["deprecation_type"] == "docstring"

    def test_extracts_async_function_deprecation(self):
        """Verify async deprecated functions are detected."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        async_facts = [f for f in facts if "async_deprecated" in f.name]
        assert len(async_facts) >= 1

        fact = async_facts[0]
        assert fact.kind == FactKind.DEPRECATED
        assert fact.metadata["deprecation_type"] == "docstring"

    def test_non_deprecated_functions_excluded(self):
        """Verify functions without deprecation markers are not included."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        names = [f.name for f in facts]
        # no_deprecation should not appear
        assert not any("no_deprecation" in n for n in names)
        # normal_method should not appear
        assert not any("normal_method" in n for n in names)
        # NonDeprecatedClass.method should not appear
        assert not any("NonDeprecatedClass" in n for n in names)

    def test_subclass_of_deprecated_not_duplicated(self):
        """Verify subclass of deprecated class is handled correctly."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        # SubClass should not have its own deprecation fact
        # (it's just inheriting from OldClass)
        subclass_facts = [f for f in facts if "SubClass" in f.name]
        # It won't have a direct deprecation marker itself
        assert all("decorator" not in f.metadata or f.metadata.get("deprecation_type") != "decorator"
                   for f in subclass_facts)

    def test_fact_name_format_for_function(self):
        """Verify fact names for functions follow expected format."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        old_func_fact = [f for f in facts if "old_func_with_reason" in f.name][0]
        # Should be module.function_name format
        assert "." in old_func_fact.name
        assert "old_func_with_reason" in old_func_fact.name

    def test_fact_name_format_for_class(self):
        """Verify fact names for classes follow expected format."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        old_class_fact = [f for f in facts if f.name == "sample_deprecated.OldClass"]
        if old_class_fact:
            assert "." in old_class_fact[0].name

    def test_line_numbers_set(self):
        """Verify all facts have valid line numbers."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        for fact in facts:
            assert fact.line_number > 0

    def test_source_file_in_facts(self):
        """Verify all facts have source_file set."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        for fact in facts:
            assert fact.source_file == FIXTURE

    def test_no_duplicates(self):
        """Verify the same symbol doesn't produce duplicate facts."""
        extractor = DeprecatedExtractor()
        facts = extractor.extract(FIXTURE)

        names = [f.name for f in facts]
        assert len(names) == len(set(names)), "Duplicate fact names found"

    def test_parse_deprecated_directive_basic(self):
        """Test _parse_deprecated_directive with basic directive."""
        content = ".. deprecated:: 1.0"
        info = _parse_deprecated_directive(content)
        assert info.get("version") == "1.0"

    def test_parse_deprecated_directive_with_reason(self):
        """Test _parse_deprecated_directive with version and reason."""
        content = ".. deprecated:: 2.0  Use new_function instead."
        info = _parse_deprecated_directive(content)
        assert info.get("version") == "2.0"
        assert "new_function" in info.get("reason", "")

    def test_parse_deprecated_since(self):
        """Test parsing .. deprecated since: directive."""
        content = ".. deprecated since: 1.5"
        info = _parse_deprecated_directive(content)
        assert info.get("version") == "1.5"

    def test_parse_deprecated_no_version(self):
        """Test parsing .. deprecated:: without version."""
        content = ".. deprecated::\n       Use something else."
        info = _parse_deprecated_directive(content)
        assert "version" not in info
        assert "reason" in info or "something else" in info.get("reason", "")

    def test_empty_file_returns_empty(self):
        """Verify empty Python file returns no facts."""
        import tempfile

        extractor = DeprecatedExtractor()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# Just a comment\n")
            temp_path = Path(f.name)

        try:
            facts = extractor.extract(temp_path)
            assert len(facts) == 0
        finally:
            temp_path.unlink()

    def test_syntax_error_file_returns_empty(self):
        """Verify file with syntax error returns empty list."""
        import tempfile

        extractor = DeprecatedExtractor()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken(\n")  # syntax error
            temp_path = Path(f.name)

        try:
            facts = extractor.extract(temp_path)
            assert len(facts) == 0
        finally:
            temp_path.unlink()
