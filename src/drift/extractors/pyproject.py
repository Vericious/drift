"""Pyproject.toml extractor for Drift.

Extracts project metadata from pyproject.toml files.
"""

import sys
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


@register
class PyprojectExtractor(Extractor):
    """Extract CONFIG_KEY facts from pyproject.toml.

    Extracts:
      - [project] metadata: name, version, description, dependencies
      - [project.scripts] entry points
      - [tool.*] configuration sections
      - [build-system] information
    """

    def can_handle(self, path: Path) -> bool:
        """Return True for pyproject.toml files."""
        return path.name == "pyproject.toml"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CodeFacts from a pyproject.toml file."""
        facts: list[CodeFact] = []

        data = self._parse_pyproject(path)
        if data is None:
            return facts

        # Extract [project] section
        if "project" in data:
            project_data = data["project"]
            if isinstance(project_data, dict):
                facts.extend(self._extract_project_data(project_data, path))

        # Extract [project.scripts] entry points
        if "project" in data:
            project_data = data["project"]
            if isinstance(project_data, dict) and "scripts" in project_data:
                scripts = project_data["scripts"]
                if isinstance(scripts, dict):
                    facts.extend(self._extract_scripts(scripts, path))

        # Extract [tool.*] sections
        if "tool" in data:
            tool_data = data["tool"]
            if isinstance(tool_data, dict):
                facts.extend(self._extract_tool_data(tool_data, path))

        # Extract [build-system]
        if "build-system" in data:
            build_data = data["build-system"]
            if isinstance(build_data, dict):
                facts.extend(self._extract_build_system(build_data, path))

        return facts

    def _parse_pyproject(self, path: Path) -> dict[str, Any] | None:
        """Parse pyproject.toml using tomllib."""
        if sys.version_info < (3, 11):
            # Python < 3.11 - try tomli
            try:
                import tomli as tomllib
            except ImportError:
                return None
        else:
            import tomllib

        try:
            content = path.read_text(encoding="utf-8")
            return tomllib.loads(content)
        except Exception:
            return None

    def _extract_project_data(self, project_data: dict, source: Path) -> list[CodeFact]:
        """Extract facts from [project] section."""
        facts: list[CodeFact] = []

        # name
        if "name" in project_data:
            facts.append(CodeFact(
                name=f"project.name",
                kind=FactKind.CONFIG_KEY,
                source_file=source,
                line_number=1,
                metadata={"name": project_data["name"], "section": "project"},
            ))

        # version
        if "version" in project_data:
            facts.append(CodeFact(
                name="project.version",
                kind=FactKind.CONFIG_KEY,
                source_file=source,
                line_number=1,
                metadata={"version": str(project_data["version"]), "section": "project"},
            ))

        # description
        if "description" in project_data:
            facts.append(CodeFact(
                name="project.description",
                kind=FactKind.CONFIG_KEY,
                source_file=source,
                line_number=1,
                metadata={"description": project_data["description"], "section": "project"},
            ))

        # dependencies
        if "dependencies" in project_data:
            deps = project_data["dependencies"]
            if isinstance(deps, list):
                for i, dep in enumerate(deps):
                    facts.append(CodeFact(
                        name=f"project.dependencies.{i}",
                        kind=FactKind.CONFIG_KEY,
                        source_file=source,
                        line_number=1,
                        metadata={"dependency": dep, "section": "project"},
                    ))
            elif isinstance(deps, str):
                facts.append(CodeFact(
                    name="project.dependencies",
                    kind=FactKind.CONFIG_KEY,
                    source_file=source,
                    line_number=1,
                    metadata={"dependencies": deps, "section": "project"},
                ))

        # optional-dependencies
        if "optional-dependencies" in project_data:
            opt_deps = project_data["optional-dependencies"]
            if isinstance(opt_deps, dict):
                for group_name, deps in opt_deps.items():
                    if isinstance(deps, list):
                        for i, dep in enumerate(deps):
                            facts.append(CodeFact(
                                name=f"project.optional-dependencies.{group_name}.{i}",
                                kind=FactKind.CONFIG_KEY,
                                source_file=source,
                                line_number=1,
                                metadata={"group": group_name, "dependency": dep, "section": "project"},
                            ))

        # requires-python
        if "requires-python" in project_data:
            facts.append(CodeFact(
                name="project.requires-python",
                kind=FactKind.CONFIG_KEY,
                source_file=source,
                line_number=1,
                metadata={"requires-python": project_data["requires-python"], "section": "project"},
            ))

        # license
        if "license" in project_data:
            license_data = project_data["license"]
            if isinstance(license_data, dict):
                facts.append(CodeFact(
                    name="project.license",
                    kind=FactKind.CONFIG_KEY,
                    source_file=source,
                    line_number=1,
                    metadata={"license": license_data.get("text", str(license_data)), "section": "project"},
                ))

        # authors
        if "authors" in project_data:
            authors = project_data["authors"]
            if isinstance(authors, list):
                for i, author in enumerate(authors):
                    if isinstance(author, dict):
                        name = author.get("name", "unknown")
                        facts.append(CodeFact(
                            name=f"project.authors.{i}",
                            kind=FactKind.CONFIG_KEY,
                            source_file=source,
                            line_number=1,
                            metadata={"author": name, "section": "project"},
                        ))

        return facts

    def _extract_scripts(self, scripts: dict, source: Path) -> list[CodeFact]:
        """Extract facts from [project.scripts] entry points."""
        facts: list[CodeFact] = []

        for cmd_name, entry_point in scripts.items():
            # entry_point can be "module:function" or just "module"
            facts.append(CodeFact(
                name=f"project.scripts.{cmd_name}",
                kind=FactKind.CONFIG_KEY,
                source_file=source,
                line_number=1,
                metadata={
                    "command": cmd_name,
                    "entry_point": entry_point,
                    "section": "project.scripts",
                },
            ))

        return facts

    def _extract_tool_data(self, tool_data: dict, source: Path) -> list[CodeFact]:
        """Extract facts from [tool.*] sections."""
        facts: list[CodeFact] = []

        for tool_name, tool_config in tool_data.items():
            if not isinstance(tool_config, dict):
                continue

            # Flatten tool config
            for key, value in tool_config.items():
                value_str = str(value) if value is not None else ""
                facts.append(CodeFact(
                    name=f"tool.{tool_name}.{key}",
                    kind=FactKind.CONFIG_KEY,
                    source_file=source,
                    line_number=1,
                    metadata={
                        "tool": tool_name,
                        "key": key,
                        "value": value_str,
                        "section": f"tool.{tool_name}",
                    },
                ))

        return facts

    def _extract_build_system(self, build_data: dict, source: Path) -> list[CodeFact]:
        """Extract facts from [build-system] section."""
        facts: list[CodeFact] = []

        # requires
        if "requires" in build_data:
            requires = build_data["requires"]
            if isinstance(requires, list):
                for i, req in enumerate(requires):
                    facts.append(CodeFact(
                        name=f"build-system.requires.{i}",
                        kind=FactKind.CONFIG_KEY,
                        source_file=source,
                        line_number=1,
                        metadata={"requires": req, "section": "build-system"},
                    ))

        # build-backend
        if "build-backend" in build_data:
            facts.append(CodeFact(
                name="build-system.build-backend",
                kind=FactKind.CONFIG_KEY,
                source_file=source,
                line_number=1,
                metadata={"build-backend": build_data["build-backend"], "section": "build-system"},
            ))

        return facts
