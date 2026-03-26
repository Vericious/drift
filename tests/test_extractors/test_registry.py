"""Tests for the extractor registry."""

from drift.extractors.registry import get_extractors


class TestExtractorRegistry:
    """Test the extractor auto-registration system."""

    def test_get_extractors_returns_non_empty_list(self):
        """get_extractors() returns a non-empty list."""
        extractors = get_extractors()
        assert isinstance(extractors, list)
        assert len(extractors) > 0

    def test_all_extractors_have_extract_and_can_handle(self):
        """Every registered extractor has extract() and can_handle() methods."""
        for cls in get_extractors():
            assert hasattr(cls, "extract"), f"{cls.__name__} missing extract()"
            assert hasattr(cls, "can_handle"), f"{cls.__name__} missing can_handle()"
            # Instantiate and verify methods are callable
            instance = cls()
            assert callable(instance.extract)
            assert callable(instance.can_handle)

    def test_no_duplicates(self):
        """Registry contains no duplicate extractor classes."""
        extractors = get_extractors()
        assert len(extractors) == len(set(extractors))

    def test_all_known_extractors_in_registry(self):
        """All known extractor classes are present in the registry."""
        extractors = get_extractors()
        names = {cls.__name__ for cls in extractors}
        expected = {
            "ArgparseExtractor",
            "ClickExtractor",
            "TyperExtractor",
            "PydanticExtractor",
            "ConfigFileExtractor",
            "DocstringExtractor",
        }
        assert expected.issubset(names), f"Missing: {expected - names}"
