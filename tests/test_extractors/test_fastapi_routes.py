"""Tests for fastapi_routes module."""
from pathlib import Path

import pytest

from drift.extractors.fastapi_routes import FastAPIRoutesExtractor


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_fastapi.py"


class TestFastAPIRoutesExtractor:
    """Test FastAPIRoutesExtractor."""

    def test_can_handle_py_file(self):
        """.can_handle returns True for .py files."""
        extractor = FastAPIRoutesExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.txt")) is False

    def test_extracts_api_endpoint_facts(self):
        """Extracts API_ENDPOINT facts from the fixture."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        endpoint_facts = [f for f in facts if f.kind.value == "api_endpoint"]
        assert len(endpoint_facts) > 0

    def test_kind_is_api_endpoint(self):
        """All extracted facts have kind=api_endpoint."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "api_endpoint" for f in facts)

    def test_fact_name_format_method_space_path(self):
        """Fact names follow 'METHOD /path' format."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "GET /" in names
        assert "GET /items" in names
        assert "POST /items" in names
        assert "DELETE /items/{item_id}" in names
        assert "PATCH /items/{item_id}/price" in names

    def test_app_get_post_put_delete(self):
        """@app.get/post/put/delete decorators are extracted."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "GET /items" in names
        assert "POST /items" in names
        assert "PUT /items/{item_id}" in names
        assert "DELETE /items/{item_id}" in names
        assert "PATCH /items/{item_id}/price" in names

    def test_router_routes_extracted(self):
        """APIRouter routes are extracted with their prefixed paths."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # router has prefix="/api/v1"
        assert "GET /api/v1/posts" in names
        assert "POST /api/v1/posts" in names
        assert "GET /api/v1/posts/{post_id}" in names
        assert "DELETE /api/v1/posts/{post_id}" in names
        # users_router has prefix="/users"
        assert "GET /users/" in names
        assert "GET /users/{user_id}" in names
        assert "POST /users/" in names

    def test_status_code_in_metadata(self):
        """status_code kwarg is captured in metadata."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        create = next((f for f in facts if f.name == "POST /items"), None)
        assert create is not None
        assert create.metadata.get("status_code") == "201"

    def test_response_model_in_metadata(self):
        """response_model kwarg is captured in metadata."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        list_items = next((f for f in facts if f.name == "GET /items"), None)
        assert list_items is not None
        assert list_items.metadata.get("response_model") is not None

    def test_tags_in_metadata(self):
        """tags kwarg is captured in metadata."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        get_items = next((f for f in facts if f.name == "GET /items"), None)
        assert get_items is not None
        assert get_items.metadata.get("tags") == ["items"]

    def test_function_name_in_metadata(self):
        """Function name is stored in metadata."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        root = next((f for f in facts if f.name == "GET /"), None)
        assert root is not None
        assert root.metadata.get("function_name") == "root"

    def test_api_route_with_multiple_methods(self):
        """/ping via api_route has GET, /legacy has GET and POST."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "GET /ping" in names
        assert "GET /legacy" in names
        assert "POST /legacy" in names

    def test_second_fastapi_app_routes(self):
        """Routes from admin_app are also extracted."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "GET /admin/dashboard" in names
        assert "POST /admin/purge" in names

    def test_parameters_extracted(self):
        """Function parameters are extracted."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        create_item = next((f for f in facts if f.name == "POST /items"), None)
        assert create_item is not None
        param_names = {p.name for p in create_item.parameters}
        assert "name" in param_names
        assert "price" in param_names

    def test_no_routes_returns_empty(self):
        """File with no FastAPI routes returns empty list."""
        no_routes = Path(__file__).parent.parent / "test_models.py"
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(no_routes)
        endpoint_facts = [f for f in facts if f.kind.value == "api_endpoint"]
        assert endpoint_facts == []

    def test_multiple_routers_all_extracted(self):
        """Multiple APIRouters contribute distinct routes."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        routers = {
            f.metadata.get("router")
            for f in facts
            if f.metadata.get("router")
        }
        assert len(routers) >= 2

    def test_source_file_and_line_number_set(self):
        """Facts have source_file and line_number set."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.source_file == FIXTURE for f in facts)
        assert all(f.line_number is not None and f.line_number > 0 for f in facts)

    def test_router_prefix_prepended_to_path(self):
        """APIRouter prefix is prepended to route paths."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # users_router prefix="/users"
        assert "GET /users/" in names
        assert "GET /users/{user_id}" in names
        # search and get_item_detail from router
        assert "GET /api/v1/search" in names
        assert "GET /api/v1/items/{item_id}/detail" in names

    def test_delete_returns_204(self):
        """DELETE /items/{item_id} has status_code 204."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        delete_item = next((f for f in facts if f.name == "DELETE /items/{item_id}"), None)
        assert delete_item is not None
        assert delete_item.metadata.get("status_code") == "204"

    def test_app_api_route_methods_extracted(self):
        """/legacy api_route correctly extracts methods list."""
        extractor = FastAPIRoutesExtractor()
        facts = extractor.extract(FIXTURE)
        legacy_get = next((f for f in facts if f.name == "GET /legacy"), None)
        assert legacy_get is not None
        assert legacy_get.metadata.get("methods") == ["GET", "POST"]
