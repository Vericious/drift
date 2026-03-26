"""Plugin system for Drift extractors via entry_points.

Scans the `drift.extractors` entry_point group to discover and auto-load
third-party extractor plugins at startup.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points

from drift.extractors.base import Extractor

logger = logging.getLogger(__name__)

# Cache for loaded plugin extractor classes
_loaded_plugins: list[type[Extractor]] = []


def load_plugins() -> list[type[Extractor]]:
    """Discover and load extractor plugins from the drift.extractors entry_point group.

    Iterates over the `drift.extractors` entry point group. Each plugin must
    expose an Extractor subclass at the module level as the default export.

    Returns:
        List of loaded plugin Extractor classes (already registered via their
        own @register decorator if they use one, or raw for inspection).
    """
    global _loaded_plugins

    if _loaded_plugins:
        return _loaded_plugins

    loaded: list[type[Extractor]] = []

    try:
        # Python 3.12+ / importlib.metadata API change
        eps = entry_points(group="drift.extractors")
    except (TypeError, AttributeError, OSError):
        # Python < 3.12: entry_points() returns a dict-of-dicts.
        # If this also fails (no such group), eps stays [].
        try:
            eps = entry_points().get("drift.extractors", [])  # type: ignore[arg-type]
        except Exception:
            eps = []  # type: ignore[assignment]

    for ep in eps:
        try:
            plugin_module = ep.load()
            # Assume the plugin exposes its Extractor class as the default
            # or as a named attribute. Try common patterns.
            extractor_cls: type[Extractor] | None = None

            # Pattern 1: entry point value is "module:ClassName" — extract ClassName
            # and getattr it from the module directly.
            if ":" in ep.value:
                class_name = ep.value.rsplit(":", 1)[1]
                if hasattr(plugin_module, class_name):
                    attr = getattr(plugin_module, class_name)
                    if isinstance(attr, type) and issubclass(attr, Extractor):
                        extractor_cls = attr

            # Pattern 2: module-level class named after the entry point (kebab-case → CamelCase)
            if extractor_cls is None:
                # Convert "my-extractor" → "MyExtractor"
                candidate = "".join(p.capitalize() for p in ep.name.split("-"))
                if hasattr(plugin_module, candidate):
                    attr = getattr(plugin_module, candidate)
                    if isinstance(attr, type) and issubclass(attr, Extractor):
                        extractor_cls = attr

            # Pattern 3: module has an 'extractor' attribute
            if extractor_cls is None and hasattr(plugin_module, "extractor"):
                attr = plugin_module.extractor
                if isinstance(attr, type) and issubclass(attr, Extractor):
                    extractor_cls = attr

            # Pattern 4: the entry point itself is the class (module is the class)
            if extractor_cls is None and isinstance(plugin_module, type) and issubclass(plugin_module, Extractor):
                extractor_cls = plugin_module

            if extractor_cls is not None:
                loaded.append(extractor_cls)
                logger.debug("Loaded plugin extractor: %s (%s)", ep.name, ep.value)
            else:
                logger.warning(
                    "Plugin %s (%s) did not expose a valid Extractor class. "
                    "Make sure your plugin exports an Extractor subclass.",
                    ep.name,
                    ep.value,
                )
        except Exception as e:
            logger.warning("Failed to load plugin extractor %s (%s): %s", ep.name, ep.value, e)

    _loaded_plugins = loaded
    return loaded


def get_plugins() -> list[type[Extractor]]:
    """Return all loaded plugin extractor classes."""
    return list(_loaded_plugins)


def clear_plugin_cache() -> None:
    """Clear the plugin cache. Useful for testing."""
    global _loaded_plugins
    _loaded_plugins = []
