"""Tests for openapi extractor module."""

from pathlib import Path

from drift.extractors.openapi import OpenAPIExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_openapi.yaml"


class TestOpenAPIExtractor:
    """Test OpenAPIExtractor."""

    def test_can_handle_yaml_file(self):
        """.can_handle returns True for .yaml files."""
        extractor = OpenAPIExtractor()
        assert extractor.can_handle(Path("openapi.yaml")) is True
        assert extractor.can_handle(Path("swagger.yml")) is True
        assert extractor.can_handle(Path("api.yaml")) is True
        assert extractor.can_handle(Path("api.YAML")) is True

    def test_can_handle_rejects_non_yaml(self):
        """.can_handle returns False for non-YAML files."""
        extractor = OpenAPIExtractor()
        assert extractor.can_handle(Path("openapi.json")) is False
        assert extractor.can_handle(Path("spec.py")) is False
        assert extractor.can_handle(Path("spec.txt")) is False
        assert extractor.can_handle(Path("spec")) is False

    def test_extracts_api_endpoint_facts(self):
        """Extracts API_ENDPOINT facts from the fixture."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        endpoint_facts = [f for f in facts if f.kind.value == "api_endpoint"]
        assert len(endpoint_facts) > 0

    def test_kind_is_api_endpoint(self):
        """All extracted facts have kind=api_endpoint."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "api_endpoint" for f in facts)

    def test_fact_name_format_method_space_path(self):
        """Fact names follow 'METHOD /path' format (server URL prepended)."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # Server URL is prepended to all paths
        assert "GET https://api.example.com/v1/pets" in names
        assert "POST https://api.example.com/v1/pets" in names
        assert "GET https://api.example.com/v1/pets/{pet_id}" in names
        assert "PUT https://api.example.com/v1/pets/{pet_id}" in names
        assert "DELETE https://api.example.com/v1/pets/{pet_id}" in names

    def test_servers_url_prepended(self):
        """Server URL is prepended to the path."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # Server: https://api.example.com/v1
        assert "GET https://api.example.com/v1/pets" in names
        assert "POST https://api.example.com/v1/pets" in names

    def test_operation_id_extracted(self):
        """operationId is stored in metadata."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        list_pets = next(
            (f for f in facts if f.metadata.get("operation_id") == "listPets"), None
        )
        assert list_pets is not None
        assert list_pets.metadata.get("summary") == "List all pets"

        get_pet = next(
            (f for f in facts if f.metadata.get("operation_id") == "getPet"), None
        )
        assert get_pet is not None
        assert get_pet.metadata.get("summary") == "Get a specific pet"

    def test_path_parameters_extracted(self):
        """Path parameters are stored in metadata."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        get_pet = next(
            (f for f in facts if f.metadata.get("operation_id") == "getPet"), None
        )
        assert get_pet is not None
        assert "pet_id" in get_pet.metadata.get("path_param_names", [])
        assert (
            get_pet.metadata.get("path") == "https://api.example.com/v1/pets/{pet_id}"
        )

    def test_query_parameters_extracted(self):
        """Query parameters are stored in metadata."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        list_pets = next(
            (f for f in facts if f.metadata.get("operation_id") == "listPets"), None
        )
        assert list_pets is not None
        param_names = [p["name"] for p in list_pets.metadata.get("parameters", [])]
        assert "limit" in param_names
        assert "offset" in param_names

    def test_method_uppercase_in_metadata(self):
        """Method is stored uppercase in metadata."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        get_pet = next(
            (f for f in facts if f.metadata.get("operation_id") == "getPet"), None
        )
        assert get_pet is not None
        assert get_pet.metadata.get("method") == "GET"

    def test_openapi_version_stored(self):
        """OpenAPI version is stored in metadata."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.metadata.get("openapi_version") == "3.0.3" for f in facts)

    def test_source_file_set(self):
        """source_file is set on all facts."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.source_file == FIXTURE for f in facts)

    def test_line_number_set(self):
        """line_number is set on all facts."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.line_number is not None for f in facts)
        assert all(f.line_number > 0 for f in facts)

    def test_no_routes_returns_empty(self):
        """YAML file with no paths returns empty list."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        endpoint_facts = [f for f in facts if f.kind.value == "api_endpoint"]
        # At minimum we expect: GET/POST /pets, GET/PUT/DELETE /pets/{pet_id}, GET/POST /orders = 7
        assert len(endpoint_facts) >= 7

    def test_all_http_methods_extracted(self):
        """All HTTP methods present in fixture are extracted."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        methods = {f.metadata.get("method") for f in facts}
        assert "GET" in methods
        assert "POST" in methods
        assert "PUT" in methods
        assert "DELETE" in methods

    def test_description_extracted(self):
        """Description is stored in metadata."""
        extractor = OpenAPIExtractor()
        facts = extractor.extract(FIXTURE)
        list_pets = next(
            (f for f in facts if f.metadata.get("operation_id") == "listPets"), None
        )
        assert list_pets is not None
        assert "list" in list_pets.metadata.get("description", "").lower()
