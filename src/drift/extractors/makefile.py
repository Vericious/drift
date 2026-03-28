"""Makefile extractor for Drift.

Extracts facts from Makefiles - targets, prerequisites, and descriptions.
"""

import re
from pathlib import Path

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind


@register
class MakefileExtractor(Extractor):
    """Extract CODE_TARGET facts from Makefile targets.

    Parses Makefiles to extract:
      - Build targets (matching ^[a-zA-Z_-]+:)
      - Target prerequisites
      - Comments describing targets
      - .PHONY targets (special handling)

    Note: .PHONY directive itself is not extracted as a target.
    """

    def can_handle(self, path: Path) -> bool:
        """Return True for files named Makefile, makefile, or *.mk."""
        name = path.name
        if name == "Makefile":
            return True
        if name == "makefile":
            return True
        if name.endswith(".mk"):
            return True
        return False

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CodeFacts from a Makefile."""
        facts: list[CodeFact] = []

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return facts

        lines = content.splitlines()

        # Track which targets are marked as .PHONY
        phony_targets: set[str] = set()

        # First pass: find .PHONY directive
        for line in lines:
            line = line.strip()
            if line.startswith(".PHONY:"):
                # Extract targets listed in .PHONY
                rest = line.split(":", 1)[1]
                for t in rest.split():
                    t = t.strip()
                    if t:
                        phony_targets.add(t)
                break

        # Second pass: extract targets
        prev_comment: str | None = None
        pending_comment: str | None = None
        after_target = False

        for line_num, line in enumerate(lines, start=1):
            original_line = line
            line = line.strip()

            # Empty line resets everything
            if not line:
                prev_comment = None
                pending_comment = None
                after_target = False
                continue

            # Comment lines update pending comment (accumulate if consecutive)
            if line.startswith("#"):
                comment_text = line.lstrip("#").strip()
                if pending_comment:
                    pending_comment = f"{pending_comment} {comment_text}"
                else:
                    pending_comment = comment_text
                continue

            # If we see a target-like line after another target, the pending
            # comment was actually after the previous target's recipe
            if after_target:
                # The pending comment was after the recipe, not before this target
                prev_comment = None
                pending_comment = None
                after_target = False

            # Skip continuation lines (starting with tab - recipe lines)
            if original_line.startswith("\t"):
                after_target = True
                continue

            # Skip variable assignments (not targets)
            if "=" in line and not line.startswith("."):
                if ":" not in line:
                    prev_comment = None
                    pending_comment = None
                    after_target = False
                    continue

            # Look for target pattern: ^[a-zA-Z_-]+:
            match = re.match(r"^([a-zA-Z_-][a-zA-Z0-9_-]*):(.*)$", line)
            if match:
                target_name = match.group(1)

                # Skip .PHONY directive itself
                if target_name == ".PHONY":
                    after_target = True
                    continue

                prerequisites_str = match.group(2).strip()

                # Check if target is in .PHONY list
                is_phony = target_name in phony_targets

                # Parse prerequisites
                prerequisites = []
                if prerequisites_str:
                    prerequisites = [p.strip() for p in prerequisites_str.split() if p.strip()]

                # Use accumulated pending comment as description
                description = pending_comment if pending_comment else f"Makefile target: {target_name}"

                # Build metadata
                metadata = {
                    "target": target_name,
                    "description": description,
                }
                if is_phony:
                    metadata["phony"] = True
                if prerequisites:
                    metadata["prerequisites"] = prerequisites

                fact = CodeFact(
                    name=f"make:{target_name}",
                    kind=FactKind.CONFIG_KEY,
                    source_file=path,
                    line_number=line_num,
                    metadata=metadata,
                )
                facts.append(fact)

                # Reset comments and mark that we just saw a target
                prev_comment = None
                pending_comment = None
                after_target = True
            else:
                after_target = False

        return facts
