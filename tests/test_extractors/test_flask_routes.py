"""Tests for flask_routes module."""

from pathlib import Path

from drift.extractors.flask_routes import FlaskRoutesExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_flask.py"


class TestFlaskRoutesExtractor:
    """Test FlaskRoutesExtractor."""

    def test_can_handle_py_file(self):
        """.can_handle returns True for .py files."""
        extractor = FlaskRoutesExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.txt")) is False
        assert extractor.can_handle(Path("foo.pyx")) is False

    def test_extracts_api_endpoint_facts(self):
        """Extracts API_ENDPOINT facts from the fixture."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        endpoint_facts = [f for f in facts if f.kind.value == "api_endpoint"]
        assert len(endpoint_facts) > 0

    def test_kind_is_api_endpoint(self):
        """All extracted facts have kind=api_endpoint."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "api_endpoint" for f in facts)

    def test_fact_name_format_method_space_path(self):
        """Fact names follow 'METHOD /path' format."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "GET /" in names
        assert "GET /users" in names
        assert "POST /users" in names
        assert "DELETE /users/<int:user_id>" in names

    def test_app_route_basic(self):
        """Basic @app.route('/') is extracted."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "GET /" in names

    def test_app_route_methods_list(self):
        """Route with multiple methods produces multiple facts."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # The /users route has GET and POST
        assert "GET /users" in names
        assert "POST /users" in names
        # GET /users/<int:user_id> and PUT and DELETE
        assert "GET /users/<int:user_id>" in names
        assert "PUT /users/<int:user_id>" in names
        assert "DELETE /users/<int:user_id>" in names

    def test_flask_20_shortcut_get_post(self):
        """Flask 2.0+ @app.get/post shortcuts are extracted."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "GET /api/health" in names
        assert "POST /api/items" in names
        assert "PUT /api/items/<item_id>" in names
        assert "PATCH /api/items/<item_id>" in names
        assert "DELETE /api/items/<item_id>" in names

    def test_blueprint_route_extracted(self):
        """Blueprint routes are extracted with correct path."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # Blueprint routes
        assert "GET /api/v1/posts" in names
        assert "POST /api/v1/posts" in names
        assert "GET /api/v1/posts/<int:post_id>" in names
        assert "DELETE /api/v1/posts/<int:post_id>" in names

    def test_blueprint_shortcut_methods(self):
        """Blueprint with Flask 2.0+ shortcuts."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "GET /auth/login" in names
        assert "POST /auth/login" in names
        assert "POST /auth/logout" in names
        assert "GET /auth/register" in names

    def test_metadata_contains_methods_and_endpoint(self):
        """Metadata stores methods list and endpoint path."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        users_get = next((f for f in facts if f.name == "GET /users"), None)
        assert users_get is not None
        assert users_get.metadata.get("methods") == ["GET", "POST"]
        assert users_get.metadata.get("endpoint") == "/users"

    def test_metadata_contains_blueprint_name(self):
        """Blueprint routes store the blueprint name in metadata."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        api_get = next((f for f in facts if f.name == "GET /api/v1/posts"), None)
        assert api_get is not None
        assert api_get.metadata.get("blueprint") == "api"

        auth_get = next((f for f in facts if f.name == "GET /auth/login"), None)
        assert auth_get is not None
        assert auth_get.metadata.get("blueprint") == "auth"

    def test_metadata_contains_function_name(self):
        """Function name is stored in metadata."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        health = next((f for f in facts if f.name == "GET /api/health"), None)
        assert health is not None
        assert health.metadata.get("function_name") == "health_check"

    def test_other_app_instance_routes(self):
        """Routes from a second Flask instance are also extracted."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "GET /hello" in names
        assert "GET /status" in names

    def test_no_routes_returns_empty(self):
        """File with no Flask routes returns empty list."""
        no_routes = Path(__file__).parent.parent / "test_models.py"
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(no_routes)
        endpoint_facts = [f for f in facts if f.kind.value == "api_endpoint"]
        assert endpoint_facts == []

    def test_multiple_blueprints_all_extracted(self):
        """Multiple blueprints all contribute facts."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        # At least 3 different blueprints
        blueprints = {
            f.metadata.get("blueprint") for f in facts if f.metadata.get("blueprint")
        }
        assert len(blueprints) >= 3

    def test_source_file_and_line_number_set(self):
        """Extracted facts have source_file and line_number set."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.source_file == FIXTURE for f in facts)
        assert all(f.line_number is not None for f in facts)
        assert all(f.line_number > 0 for f in facts)

    def test_app_get_shortcut_single_method(self):
        """@app.get produces exactly one GET fact."""
        extractor = FlaskRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        get_status = [f for f in facts if f.name == "GET /status"]
        assert len(get_status) == 1
        assert get_status[0].metadata.get("methods") == ["GET"]
