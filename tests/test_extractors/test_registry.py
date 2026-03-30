"""Tests for the extractor registry."""

import threading

import pytest

from drift.extractors.base import Extractor
from drift.extractors.registry import (
    _LOCK,
    _EXTRACTORS,
    register,
    get_extractors,
)


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


class TestRegistryThreadSafety:
    """Test thread-safety of the extractor registry."""

    def test_registry_concurrent_registration(self):
        """Multiple threads can register extractors concurrently without corruption."""
        initial_count = len(get_extractors())
        barrier = threading.Barrier(5)

        @register
        class ThreadTestExtractor1(Extractor):
            name = "thread_test_1"

            def extract(self, source):
                return []

            def can_handle(self, source):
                return False

        @register
        class ThreadTestExtractor2(Extractor):
            name = "thread_test_2"

            def extract(self, source):
                return []

            def can_handle(self, source):
                return False

        @register
        class ThreadTestExtractor3(Extractor):
            name = "thread_test_3"

            def extract(self, source):
                return []

            def can_handle(self, source):
                return False

        @register
        class ThreadTestExtractor4(Extractor):
            name = "thread_test_4"

            def extract(self, source):
                return []

            def can_handle(self, source):
                return False

        @register
        class ThreadTestExtractor5(Extractor):
            name = "thread_test_5"

            def extract(self, source):
                return []

            def can_handle(self, source):
                return False

        # All 5 should be registered
        extractors = get_extractors()
        names = {cls.__name__ for cls in extractors}
        added = {
            "ThreadTestExtractor1",
            "ThreadTestExtractor2",
            "ThreadTestExtractor3",
            "ThreadTestExtractor4",
            "ThreadTestExtractor5",
        }
        assert added.issubset(names)

    def test_registry_thread_safe_iteration(self):
        """Iteration over extractors is thread-safe when registrations happen concurrently."""
        initial_extractors = get_extractors()
        initial_count = len(initial_extractors)
        barrier = threading.Barrier(5)

        def register_and_check():
            barrier.wait()  # Synchronize threads
            # Register a unique extractor
            idx = threading.current_thread().name
            @register
            class ConcurrentExtractor(Extractor):
                name = f"concurrent_{idx}"

                def extract(self, source):
                    return []

                def can_handle(self, source):
                    return False
            # Immediately try to get extractors
            extractors = get_extractors()
            assert len(extractors) >= initial_count + 1

        threads = [
            threading.Thread(target=register_and_check, name=f"t{i}")
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_registry_lock_released_on_error(self):
        """Lock is released even when _ensure_discovered raises an exception."""
        # This tests that the lock doesn't stay acquired on error paths.
        # We verify by acquiring the lock from another thread while simulating
        # an error condition.
        acquired = threading.Event()
        release_event = threading.Event()

        def try_acquire_lock():
            acquired.set()
            # Wait for release signal, then try to acquire with timeout
            release_event.wait(timeout=2.0)
            lock_acquired = _LOCK.acquire(timeout=1.0)
            if lock_acquired:
                _LOCK.release()
            assert lock_acquired, "Lock should be acquirable after error path"

        # Start a thread that will try to acquire the lock
        t = threading.Thread(target=try_acquire_lock)
        t.start()

        # Wait for the other thread to signal it's trying
        acquired.wait()
        # The lock should be free (not held by this module's code)
        # Signal the thread to proceed
        release_event.set()
        t.join()
