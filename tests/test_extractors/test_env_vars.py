"""Tests for env_vars module."""

from pathlib import Path

from drift.extractors.env_vars import EnvVarExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_env_vars.py"


class TestEnvVarExtractor:
    """Test EnvVarExtractor."""

    def test_can_handle_py_file(self):
        """.can_handle returns True for .py files."""
        extractor = EnvVarExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.txt")) is False

    def test_extracts_config_key_facts(self):
        """Extracts CONFIG_KEY facts from the fixture."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        config_facts = [f for f in facts if f.kind.value == "config_key"]
        assert len(config_facts) > 0

    def test_kind_is_config_key(self):
        """All extracted facts have kind=config_key."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "config_key" for f in facts)

    def test_os_environ_subscript_required(self):
        """/os.environ["VAR"] sets required=True."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        db_url = next((f for f in facts if f.name == "DATABASE_URL"), None)
        assert db_url is not None
        assert db_url.metadata.get("required") is True

    def test_os_environ_get_required_false(self):
        """/os.environ.get("VAR") sets required=False."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        secret = next((f for f in facts if f.name == "SECRET_KEY"), None)
        assert secret is not None
        assert secret.metadata.get("required") is False

    def test_os_getenv_required_false(self):
        """/os.getenv("VAR") sets required=False."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        api_key = next((f for f in facts if f.name == "API_KEY"), None)
        assert api_key is not None
        assert api_key.metadata.get("required") is False

    def test_default_value_extracted(self):
        """Default value is captured when provided."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        debug = next((f for f in facts if f.name == "DEBUG"), None)
        assert debug is not None
        assert debug.metadata.get("default") == "'False'"

    def test_default_int_conversion(self):
        """Default values with int() conversion are handled."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        port = next((f for f in facts if f.name == "PORT"), None)
        assert port is not None
        assert port.metadata.get("default") == "'8000'"

    def test_source_form_in_metadata(self):
        """Source form (os.environ.get vs os.getenv) is stored in metadata."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        db_url = next((f for f in facts if f.name == "DATABASE_URL"), None)
        assert db_url is not None
        assert "environ" in db_url.metadata.get("source", "")

        log_level = next((f for f in facts if f.name == "LOG_LEVEL"), None)
        assert log_level is not None
        assert log_level.metadata.get("source") == "os.getenv"

    def test_env_var_name_in_metadata(self):
        """env_var name is stored in metadata."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        smtp = next((f for f in facts if f.name == "SMTP_PASSWORD"), None)
        assert smtp is not None
        assert smtp.metadata.get("env_var") == "SMTP_PASSWORD"

    def test_no_env_vars_returns_empty(self):
        """File with no env vars returns empty list."""
        no_env = Path(__file__).parent.parent / "test_models.py"
        extractor = EnvVarExtractor()
        facts = extractor.extract(no_env)
        config_facts = [f for f in facts if f.kind.value == "config_key"]
        assert config_facts == []

    def test_deduplication_same_var_same_file(self):
        """Same var referenced multiple times only produces one fact."""
        # sample_env_vars.py uses LOG_LEVEL and REDIS_HOST each once via .get
        # and DEBUG once, so we just check total unique var names
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        var_names = [f.name for f in facts]
        assert len(var_names) == len(set(var_names)), "Duplicate var names found"

    def test_strict_required_true(self):
        """/os.environ["STRICT_MODE"] sets required=True."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        strict = next((f for f in facts if f.name == "STRICT_MODE"), None)
        assert strict is not None
        assert strict.metadata.get("required") is True

    def test_source_file_and_line_number_set(self):
        """Facts have source_file and line_number set."""
        extractor = EnvVarExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.source_file == FIXTURE for f in facts)
        assert all(f.line_number is not None and f.line_number > 0 for f in facts)
