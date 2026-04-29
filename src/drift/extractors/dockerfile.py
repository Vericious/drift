"""Dockerfile extractor for Drift.

Extracts CONFIG_KEY and other facts from Dockerfiles.
Handles: FROM, EXPOSE, ENV, LABEL, ENTRYPOINT, CMD, ARG, RUN, COPY, ADD instructions.
"""

import re
from pathlib import Path

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


@register
class DockerfileExtractor(Extractor):
    """Extract facts from Dockerfile instructions.

    Extracts:
      - FROM base images (with AS alias for multi-stage)
      - EXPOSE ports
      - ENV variables
      - LABEL metadata
      - ARG build arguments
      - ENTRYPOINT and CMD commands
      - COPY/ADD source paths
      - WORKDIR
      - USER

    Fact naming:
      from.<stage_name> for FROM instructions
      env.<var_name> for ENV
      label.<key> for LABEL
      expose.<port> for EXPOSE
      arg.<name> for ARG
      entrypoint for ENTRYPOINT/CMD
    """

    DOCKERFILE_PATTERNS = frozenset({
        "Dockerfile",
        "Dockerfile.dev",
        "Dockerfile.prod",
        "Dockerfile.staging",
        "app.Dockerfile",
        "web.Dockerfile",
        "worker.Dockerfile",
    })

    def can_handle(self, path: Path) -> bool:
        """Return True for files named Dockerfile or ending in .dockerfile."""
        name = path.name
        if name == "Dockerfile":
            return True
        if name.endswith(".dockerfile"):
            return True
        return bool(name.startswith("Dockerfile."))

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CodeFacts from a Dockerfile."""
        facts: list[CodeFact] = []

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return facts

        # Join lines with backslash continuation
        lines = content.splitlines()
        joined_lines: list[tuple[int, str]] = []  # (original_line_num, joined_line)
        i = 0
        current_content = ""

        while i < len(lines):
            line = lines[i]
            if line.rstrip().endswith("\\"):
                # Continuation - join with next line
                current_content += line.rstrip()[:-1] + " "
                i += 1
                i + 1
            else:
                current_content += line.strip()
                joined_lines.append((i + 1, current_content.strip()))
                current_content = ""
                i += 1
                i + 1

        stage_index = 0

        for line_num, line in joined_lines:
            if not line or line.startswith("#"):
                continue

            # Parse instruction
            instruction = self._parse_instruction(line)
            if instruction is None:
                continue

            instr_type, value, extra = instruction

            if instr_type == "FROM":
                fact = self._make_from_fact(value, extra, path, line_num, stage_index)
                facts.append(fact)
                stage_index += 1

            elif instr_type == "ENV":
                for var_name, var_value in self._parse_env(value):
                    fact = self._make_env_fact(var_name, var_value, path, line_num)
                    facts.append(fact)

            elif instr_type == "LABEL":
                for key, val in self._parse_label(value):
                    fact = self._make_label_fact(key, val, path, line_num)
                    facts.append(fact)

            elif instr_type == "EXPOSE":
                for port in self._parse_expose(value):
                    fact = self._make_expose_fact(port, path, line_num)
                    facts.append(fact)

            elif instr_type == "ARG":
                for arg_name, default in self._parse_arg(value):
                    fact = self._make_arg_fact(arg_name, default, path, line_num)
                    facts.append(fact)

            elif instr_type == "ENTRYPOINT":
                fact = self._make_entrypoint_fact(value, path, line_num, "entrypoint")
                facts.append(fact)

            elif instr_type == "CMD":
                fact = self._make_entrypoint_fact(value, path, line_num, "cmd")
                facts.append(fact)

            elif instr_type == "WORKDIR":
                fact = self._make_workdir_fact(value, path, line_num)
                facts.append(fact)

            elif instr_type == "USER":
                fact = self._make_user_fact(value, path, line_num)
                facts.append(fact)

            elif instr_type in ("COPY", "ADD"):
                fact = self._make_copy_fact(instr_type, value, path, line_num)
                facts.append(fact)

        return facts

    def _parse_instruction(self, line: str) -> tuple[str, str, dict] | None:
        """Parse a Dockerfile instruction line.

        Returns (instruction_type, value, extra_metadata) or None.
        """
        # Handle JSON array format: CMD ["executable", "arg1"]
        if line.startswith("["):
            # Try to detect instruction type from context - simplified approach
            match = re.match(r'^(\w+)\s+\[', line)
            if match:
                instr = match.group(1).upper()
                return (instr, line, {})

        # Parse standard INSTRUCTION value format
        parts = line.split(None, 1)
        if len(parts) < 2:
            return None

        instr = parts[0].upper()
        value = parts[1]

        extra: dict = {}

        # Handle AS alias for FROM
        as_match = re.match(r'(.+?)\s+AS\s+(\w+)', value, re.IGNORECASE)
        if as_match:
            value = as_match.group(1).strip()
            extra["as"] = as_match.group(2).strip()

        return (instr, value, extra)

    def _parse_env(self, value: str) -> list[tuple[str, str]]:
        """Parse ENV key=value or ENV key=value key2=value2."""
        result = []
        # Handle ENV VAR=value and ENV VAR=value VAR2=value2
        matches = re.findall(r'(\w+)=([^\s]+)', value)
        for name, val in matches:
            result.append((name, val))
        return result

    def _parse_label(self, value: str) -> list[tuple[str, str]]:
        """Parse LABEL key=value or LABEL "key"="value"."""
        result = []
        # Handle both key=value and "key"="value" formats
        matches = re.findall(r'["\']?([^\s="\'=]+)["\']?\s*=\s*["\']?([^\s"\']*)["\']?', value)
        for key, val in matches:
            result.append((key, val))
        return result

    def _parse_expose(self, value: str) -> list[str]:
        """Parse EXPOSE port[/protocol]."""
        ports = []
        for part in value.split():
            # Strip protocol suffix if present
            port = re.sub(r'/\w+$', '', part)
            ports.append(port)
        return ports

    def _parse_arg(self, value: str) -> list[tuple[str, str | None]]:
        """Parse ARG name or ARG name=default."""
        result = []
        # Handle ARG VAR and ARG VAR=default
        match = re.match(r'(\w+)(?:=(\S+))?', value)
        if match:
            name = match.group(1)
            default = match.group(2) if match.group(2) else None
            result.append((name, default))
        return result

    def _make_from_fact(self, image: str, extra: dict, source: Path, line: int, stage_index: int) -> CodeFact:
        """Make a FROM fact."""
        stage_name = extra.get("as", f"stage{stage_index}")
        return CodeFact(
            name=f"from.{stage_name}",
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line,
            metadata={
                "image": image,
                "stage": stage_name,
                "instruction": "FROM",
            },
        )

    def _make_env_fact(self, name: str, value: str, source: Path, line: int) -> CodeFact:
        """Make an ENV fact."""
        return CodeFact(
            name=f"env.{name}",
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line,
            metadata={
                "var_name": name,
                "value": value,
                "instruction": "ENV",
            },
        )

    def _make_label_fact(self, key: str, value: str, source: Path, line: int) -> CodeFact:
        """Make a LABEL fact."""
        return CodeFact(
            name=f"label.{key}",
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line,
            metadata={
                "key": key,
                "value": value,
                "instruction": "LABEL",
            },
        )

    def _make_expose_fact(self, port: str, source: Path, line: int) -> CodeFact:
        """Make an EXPOSE fact."""
        return CodeFact(
            name=f"expose.{port}",
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line,
            metadata={
                "port": port,
                "instruction": "EXPOSE",
            },
        )

    def _make_arg_fact(self, name: str, default: str | None, source: Path, line: int) -> CodeFact:
        """Make an ARG fact."""
        params = [Parameter(name=name, type_annotation="str", default=default, kind="keyword")]
        return CodeFact(
            name=f"arg.{name}",
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line,
            parameters=params,
            metadata={
                "var_name": name,
                "default": default,
                "instruction": "ARG",
            },
        )

    def _make_entrypoint_fact(self, value: str, source: Path, line: int, instr_type: str) -> CodeFact:
        """Make an ENTRYPOINT or CMD fact."""
        return CodeFact(
            name=instr_type,
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line,
            metadata={
                "command": value,
                "instruction": instr_type.upper(),
            },
        )

    def _make_workdir_fact(self, value: str, source: Path, line: int) -> CodeFact:
        """Make a WORKDIR fact."""
        return CodeFact(
            name="workdir",
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line,
            metadata={
                "path": value,
                "instruction": "WORKDIR",
            },
        )

    def _make_user_fact(self, value: str, source: Path, line: int) -> CodeFact:
        """Make a USER fact."""
        return CodeFact(
            name="user",
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line,
            metadata={
                "user": value,
                "instruction": "USER",
            },
        )

    def _make_copy_fact(self, instr_type: str, value: str, source: Path, line: int) -> CodeFact:
        """Make a COPY or ADD fact."""
        # Extract source path (first path component)
        src = value.split()[0] if value.split() else value
        return CodeFact(
            name=instr_type.lower(),
            kind=FactKind.CONFIG_KEY,
            source_file=source,
            line_number=line,
            metadata={
                "source": src,
                "instruction": instr_type,
            },
        )
