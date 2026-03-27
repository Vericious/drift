"""Tests for graphql module."""

from pathlib import Path

from drift.extractors.graphql import GraphQLExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_schema.graphql"


class TestGraphQLExtractor:
    """Test GraphQLExtractor."""

    def test_can_handle_graphql_file(self):
        """can_handle returns True for .graphql files."""
        extractor = GraphQLExtractor()
        assert extractor.can_handle(Path("schema.graphql")) is True
        assert extractor.can_handle(Path("types.gql")) is True
        assert extractor.can_handle(Path("schema.graphql")) is True

    def test_cannot_handle_other_files(self):
        """can_handle returns False for non-GraphQL files."""
        extractor = GraphQLExtractor()
        assert extractor.can_handle(Path("schema.py")) is False
        assert extractor.can_handle(Path("schema.ts")) is False
        assert extractor.can_handle(Path("schema.json")) is False

    def test_query_extraction(self):
        """Extracts Query type fields as API endpoints."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        query_facts = [f for f in facts if f.module == "Query" and f.kind.value == "api_endpoint"]
        assert len(query_facts) > 0
        names = {f.name for f in query_facts}
        assert "user" in names
        assert "users" in names
        assert "currentUser" in names

    def test_mutation_extraction(self):
        """Extracts Mutation type fields as API endpoints."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        mutation_facts = [f for f in facts if f.module == "Mutation" and f.kind.value == "api_endpoint"]
        assert len(mutation_facts) > 0
        names = {f.name for f in mutation_facts}
        assert "createUser" in names
        assert "deleteUser" in names
        assert "updatePost" in names

    def test_subscription_extraction(self):
        """Extracts Subscription type fields as API endpoints."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        sub_facts = [f for f in facts if f.module == "Subscription" and f.kind.value == "api_endpoint"]
        assert len(sub_facts) > 0
        names = {f.name for f in sub_facts}
        assert "newPost" in names
        assert "userUpdated" in names

    def test_query_field_arguments(self):
        """Extracts arguments from Query fields."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        users = next((f for f in facts if f.name == "users"), None)
        assert users is not None
        param_names = {p.name for p in users.parameters}
        assert "limit" in param_names
        assert "offset" in param_names

    def test_mutation_field_arguments(self):
        """Extracts input argument from Mutation fields."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        create = next((f for f in facts if f.name == "createUser"), None)
        assert create is not None
        assert len(create.parameters) == 1
        assert create.parameters[0].name == "input"
        assert create.parameters[0].type_annotation == "CreateUserInput"

    def test_input_type_extraction(self):
        """Extracts input type definitions with their fields."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        input_facts = [f for f in facts if f.metadata.get("graphql_kind") == "input"]
        assert len(input_facts) > 0

        create_input = next((f for f in input_facts if f.name == "CreateUserInput"), None)
        assert create_input is not None
        assert create_input.kind.value == "class"
        param_names = {p.name for p in create_input.parameters}
        assert "name" in param_names
        assert "email" in param_names
        assert "password" in param_names

    def test_input_type_field_types(self):
        """Input type fields have correct type annotations."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        update_input = next((f for f in facts if f.name == "UpdatePostInput"), None)
        assert update_input is not None
        title_param = next((p for p in update_input.parameters if p.name == "title"), None)
        assert title_param is not None
        # Nullable fields (ending in !) - wait, in GraphQL ! means non-null
        # So title: String (nullable) and tags: [String!]! (non-null list of non-null)
        assert title_param.type_annotation == "String"

    def test_enum_extraction(self):
        """Extracts enum type definitions with their values."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        enum_facts = [f for f in facts if f.metadata.get("graphql_kind") == "enum"]
        assert len(enum_facts) > 0

        post_status = next((f for f in enum_facts if f.name == "PostStatus"), None)
        assert post_status is not None
        assert post_status.kind.value == "class"
        assert set(post_status.metadata["values"]) == {"DRAFT", "PUBLISHED", "ARCHIVED"}

    def test_user_role_enum(self):
        """Extracts UserRole enum with correct values."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        user_role = next((f for f in facts if f.name == "UserRole"), None)
        assert user_role is not None
        assert set(user_role.metadata["values"]) == {"ADMIN", "EDITOR", "VIEWER"}

    def test_gql_extension(self):
        """.gql files are handled correctly."""
        extractor = GraphQLExtractor()
        assert extractor.can_handle(Path("schema.gql")) is True
        assert extractor.can_handle(Path("queries.gql")) is True

    def test_api_endpoint_kind(self):
        """Operation type fields have kind=api_endpoint."""
        from drift.models import FactKind
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)
        api_facts = [f for f in facts if f.kind.value == "api_endpoint"]
        assert len(api_facts) > 0
        for f in api_facts:
            assert f.kind == FactKind.API_ENDPOINT

    def test_operation_type_metadata(self):
        """Operation type facts have correct metadata."""
        extractor = GraphQLExtractor()
        facts = extractor.extract(FIXTURE)

        user = next((f for f in facts if f.name == "user"), None)
        assert user is not None
        assert user.metadata["operation_type"] == "query"

        delete = next((f for f in facts if f.name == "deleteUser"), None)
        assert delete is not None
        assert delete.metadata["operation_type"] == "mutation"

        new_post = next((f for f in facts if f.name == "newPost"), None)
        assert new_post is not None
        assert new_post.metadata["operation_type"] == "subscription"
