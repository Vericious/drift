"""Tests for DotenvExtractor."""

from pathlib import Path

import pytest

from drift.extractors.dotenv import DotenvExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor():
    """Return a DotenvExtractor instance."""
    return DotenvExtractor()


@pytest.fixture
def tmp_dotenv(tmp_path):
    """Factory: create a .env file with given content, return Path."""
    def _make(content: str, name: str = ".env") -> Path:
        f = tmp_path / name
        f.write_text(content)
        return f
    return _make


# ---------------------------------------------------------------------------
# can_handle tests
# ---------------------------------------------------------------------------


class TestCanHandle:
    """Tests for can_handle() method."""

    def test_can_handle_dotenv(self, extractor, tmp_dotenv):
        path = tmp_dotenv("KEY=value", ".env")
        assert extractor.can_handle(path) is True

    def test_can_handle_dotenv_example(self, extractor, tmp_dotenv):
        assert extractor.can_handle(Path(".env.example")) is True
        assert extractor.can_handle(Path(".env.sample")) is True

    def test_can_handle_env_local(self, extractor, tmp_dotenv):
        assert extractor.can_handle(Path(".env.local")) is True
        assert extractor.can_handle(Path(".env.production")) is True
        assert extractor.can_handle(Path(".env.development")) is True

    def test_can_handle_env_with_suffix(self, extractor, tmp_dotenv):
        assert extractor.can_handle(Path(".env.staging")) is True
        assert extractor.can_handle(Path(".env.test")) is True

    def test_cannot_handle_regular_files(self, extractor):
        assert extractor.can_handle(Path(".gitignore")) is False
        assert extractor.can_handle(Path(".bashrc")) is False
        assert extractor.can_handle(Path("app.py")) is False
        assert extractor.can_handle(Path(".npmrc")) is False
        assert extractor.can_handle(Path("docker-compose.yml")) is False


# ---------------------------------------------------------------------------
# Basic KEY=value tests (unquoted)
# ---------------------------------------------------------------------------


class TestUnquotedValues:
    """Tests for unquoted KEY=value pairs."""

    def test_simple_key_value(self, extractor, tmp_dotenv):
        path = tmp_dotenv("DATABASE_URL=postgresql://localhost/mydb")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "DATABASE_URL"
        assert facts[0].metadata["value"] == "postgresql://localhost/mydb"
        assert facts[0].metadata["value_type"] == "unquoted"

    def test_key_with_underscore(self, extractor, tmp_dotenv):
        path = tmp_dotenv("MY_VAR_NAME=value")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "MY_VAR_NAME"

    def test_key_starting_with_underscore(self, extractor, tmp_dotenv):
        path = tmp_dotenv("_PRIVATE=value")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "_PRIVATE"

    def test_multiple_keys(self, extractor, tmp_dotenv):
        content = """FOO=bar
BAZ=qux
SECRET=123"""
        path = tmp_dotenv(content)
        facts = extractor.extract(path)
        assert len(facts) == 3
        names = {f.name for f in facts}
        assert names == {"FOO", "BAZ", "SECRET"}

    def test_key_with_trailing_comment(self, extractor, tmp_dotenv):
        path = tmp_dotenv("KEY=value # this is ignored")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "KEY"
        assert facts[0].metadata["value"] == "value"

    def test_key_with_spaces_around_equals(self, extractor, tmp_dotenv):
        path = tmp_dotenv("KEY = value")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "KEY"
        assert facts[0].metadata["value"] == "value"


# ---------------------------------------------------------------------------
# Quoted value tests
# ---------------------------------------------------------------------------


class TestQuotedValues:
    """Tests for quoted KEY=value pairs."""

    def test_double_quoted_value(self, extractor, tmp_dotenv):
        path = tmp_dotenv('MESSAGE="Hello World"')
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "MESSAGE"
        assert facts[0].metadata["value"] == "Hello World"
        assert facts[0].metadata["value_type"] == "double_quoted"

    def test_single_quoted_value(self, extractor, tmp_dotenv):
        path = tmp_dotenv("MESSAGE='Hello World'")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "MESSAGE"
        assert facts[0].metadata["value"] == "Hello World"
        assert facts[0].metadata["value_type"] == "single_quoted"

    def test_double_quoted_with_special_chars(self, extractor, tmp_dotenv):
        path = tmp_dotenv('PATH="/usr/local/bin:$PATH"')
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == "/usr/local/bin:$PATH"
        assert facts[0].metadata["value_type"] == "double_quoted"

    def test_single_quoted_preserves_content(self, extractor, tmp_dotenv):
        path = tmp_dotenv("ESCAPE='$VAR and \\n special'")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == "$VAR and \\n special"

    def test_empty_double_quoted(self, extractor, tmp_dotenv):
        path = tmp_dotenv('EMPTY=""')
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == ""
        assert facts[0].metadata["value_type"] == "double_quoted"

    def test_empty_single_quoted(self, extractor, tmp_dotenv):
        path = tmp_dotenv("EMPTY=''")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == ""
        assert facts[0].metadata["value_type"] == "single_quoted"


# ---------------------------------------------------------------------------
# Empty value tests
# ---------------------------------------------------------------------------


class TestEmptyValues:
    """Tests for empty KEY= values."""

    def test_empty_value(self, extractor, tmp_dotenv):
        path = tmp_dotenv("EMPTY_VAR=")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "EMPTY_VAR"
        assert facts[0].metadata["value"] == ""
        assert facts[0].metadata["value_type"] == "empty"

    def test_empty_value_with_space(self, extractor, tmp_dotenv):
        path = tmp_dotenv("EMPTY_VAR= ")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == ""

    def test_value_with_only_spaces(self, extractor, tmp_dotenv):
        path = tmp_dotenv("EMPTY_VAR=   ")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == ""


# ---------------------------------------------------------------------------
# Comment tests
# ---------------------------------------------------------------------------


class TestComments:
    """Tests for comment handling."""

    def test_comment_line_ignored(self, extractor, tmp_dotenv):
        path = tmp_dotenv("# This is a comment\nREAL_KEY=value")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "REAL_KEY"

    def test_inline_comment_only(self, extractor, tmp_dotenv):
        path = tmp_dotenv("# just a comment line")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_multiple_comment_lines(self, extractor, tmp_dotenv):
        content = """# Database config
DB_HOST=localhost
# API keys
API_KEY=secret123
# More comments"""
        path = tmp_dotenv(content)
        facts = extractor.extract(path)
        assert len(facts) == 2
        names = {f.name for f in facts}
        assert names == {"DB_HOST", "API_KEY"}

    def test_value_with_hash_not_comment(self, extractor, tmp_dotenv):
        path = tmp_dotenv("URL=https://example.com#fragment")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == "https://example.com#fragment"


# ---------------------------------------------------------------------------
# Blank line tests
# ---------------------------------------------------------------------------


class TestBlankLines:
    """Tests for blank/empty line handling."""

    def test_blank_lines_ignored(self, extractor, tmp_dotenv):
        content = """KEY1=value1

KEY2=value2

KEY3=value3"""
        path = tmp_dotenv(content)
        facts = extractor.extract(path)
        assert len(facts) == 3

    def test_whitespace_only_lines_ignored(self, extractor, tmp_dotenv):
        content = "KEY=value\n   \n\t\nKEY2=value2"
        path = tmp_dotenv(content)
        facts = extractor.extract(path)
        assert len(facts) == 2


# ---------------------------------------------------------------------------
# Export prefix tests
# ---------------------------------------------------------------------------


class TestExportPrefix:
    """Tests for 'export' prefix handling."""

    def test_export_prefix_removed(self, extractor, tmp_dotenv):
        path = tmp_dotenv("export DATABASE_URL=postgres://localhost")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "DATABASE_URL"

    def test_export_uppercase_removed(self, extractor, tmp_dotenv):
        path = tmp_dotenv("EXPORT KEY=value")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "KEY"

    def test_export_with_spaces(self, extractor, tmp_dotenv):
        path = tmp_dotenv("export   KEY=value")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "KEY"


# ---------------------------------------------------------------------------
# Multiline / continuation tests
# ---------------------------------------------------------------------------


class TestMultilineContinuation:
    """Tests for backslash line continuation."""

    def test_continued_lines_joined(self, extractor, tmp_dotenv):
        content = "MULTILINE=first \\\nsecond \\\nthird"
        path = tmp_dotenv(content)
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "MULTILINE"
        assert "first second third" in facts[0].metadata["value"]

    def test_continuation_with_whitespace(self, extractor, tmp_dotenv):
        content = "KEY=value1 \\\n   value2"
        path = tmp_dotenv(content)
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert "value1 value2" in facts[0].metadata["value"]

    def test_continuation_at_end(self, extractor, tmp_dotenv):
        content = "KEY=value1 \\"
        path = tmp_dotenv(content)
        # Should just ignore the incomplete continuation
        facts = extractor.extract(path)
        # The line without proper termination may or may not produce a fact
        # depending on implementation


# ---------------------------------------------------------------------------
# Invalid key tests
# ---------------------------------------------------------------------------


class TestInvalidKeys:
    """Tests for invalid KEY= lines that should be skipped."""

    def test_key_starting_with_digit_ignored(self, extractor, tmp_dotenv):
        path = tmp_dotenv("123KEY=value")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_key_with_dash_ignored(self, extractor, tmp_dotenv):
        path = tmp_dotenv("MY-KEY=value")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_key_with_dot_ignored(self, extractor, tmp_dotenv):
        path = tmp_dotenv("MY.KEY=value")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_line_without_equals_ignored(self, extractor, tmp_dotenv):
        path = tmp_dotenv("JUST_A_KEY_WITHOUT_VALUE")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_empty_key_ignored(self, extractor, tmp_dotenv):
        path = tmp_dotenv("=value")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_whitespace_key_ignored(self, extractor, tmp_dotenv):
        path = tmp_dotenv("   =value")
        facts = extractor.extract(path)
        assert len(facts) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests."""

    def test_value_with_equals_sign(self, extractor, tmp_dotenv):
        path = tmp_dotenv("EQUATION=1+1=2")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == "1+1=2"

    def test_value_with_colon(self, extractor, tmp_dotenv):
        path = tmp_dotenv("TIMEOUT=30s:45s")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == "30s:45s"

    def test_unicode_in_value(self, extractor, tmp_dotenv):
        path = tmp_dotenv("GREETING=你好世界")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].metadata["value"] == "你好世界"

    def test_empty_file(self, extractor, tmp_dotenv):
        path = tmp_dotenv("")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_only_comments_and_blanks(self, extractor, tmp_dotenv):
        path = tmp_dotenv("# comment\n\n# another\n\n")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_line_number_tracked(self, extractor, tmp_dotenv):
        content = """# comment on line 1
# comment on line 2
KEY1=value1  # line 3
# comment on line 4
KEY2=value2  # line 5"""
        path = tmp_dotenv(content)
        facts = extractor.extract(path)
        key1 = next(f for f in facts if f.name == "KEY1")
        key2 = next(f for f in facts if f.name == "KEY2")
        assert key1.line_number == 3
        assert key2.line_number == 5

    def test_source_file_in_fact(self, extractor, tmp_dotenv):
        path = tmp_dotenv("KEY=value")
        facts = extractor.extract(path)
        assert facts[0].source_file == path


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests."""

    def test_realistic_env_file(self, extractor, tmp_dotenv):
        content = """# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/mydb
DB_POOL_SIZE=10

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD="secret123"

# Feature Flags
ENABLE_DEBUG=false
ENABLE_ANALYTICS='true'

# API Keys (use environment-specific .env.local)
API_KEY=sk_test_abcdef123456
# API_SECRET is stored in .env.local only
"""
        path = tmp_dotenv(content)
        facts = extractor.extract(path)
        assert len(facts) == 7
        names = {f.name for f in facts}
        expected = {
            "DATABASE_URL", "DB_POOL_SIZE", "REDIS_URL", "REDIS_PASSWORD",
            "ENABLE_DEBUG", "ENABLE_ANALYTICS", "API_KEY"
        }
        assert names == expected

    def test_dotenv_extractor_registered(self):
        """DotenvExtractor is registered in the extractor registry."""
        from drift.extractors.registry import get_extractors
        extractor_classes = get_extractors()
        class_names = [cls.__name__ for cls in extractor_classes]
        assert "DotenvExtractor" in class_names

    def test_fact_kind_is_config_key(self, extractor, tmp_dotenv):
        from drift.models import FactKind
        path = tmp_dotenv("KEY=value")
        facts = extractor.extract(path)
        assert facts[0].kind == FactKind.CONFIG_KEY

    def test_env_var_in_metadata(self, extractor, tmp_dotenv):
        path = tmp_dotenv("MY_VAR=value")
        facts = extractor.extract(path)
        assert facts[0].metadata["env_var"] == "MY_VAR"
        assert facts[0].metadata["source"] == ".env"
