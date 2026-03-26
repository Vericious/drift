"""Example extractor plugin that extracts TODO/FIXME/NOTE comments as DocClaims."""

from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import ClaimKind, DocClaim, Parameter


@register
class TodoCommentExtractor(Extractor):
    """Extract TODO, FIXME, and NOTE comments as documentation claims.

    This demonstrates the plugin API: third-party packages can define
    an Extractor subclass, register it with @register, and expose it
    via the ``drift.extractors`` entry_point group in their pyproject.toml::

        [project.entry-points."drift.extractors"]
        my-extractor = "my_package.extractor:MyExtractor"

    The extractor will be auto-discovered and loaded when ``drift scan``
    runs, and will appear in ``drift list-extractors`` as a plugin.
    """

    # Class-level attribute used by drift list-extractors for display
    handles_pattern = "*.py"

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix == ".py"

    def extract(self, file_path: Path) -> list[Any]:
        """Extract TODO/FIXME/NOTE comments as DocClaims."""
        import re

        claims: list[DocClaim] = []
        comment_re = re.compile(r"#\s*(TODO|FIXME|NOTE):\s*(.+)", re.IGNORECASE)

        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return claims

        for line_no, line in enumerate(content.splitlines(), start=1):
            m = comment_re.search(line)
            if m:
                keyword = m.group(1).upper()
                raw = m.group(0).strip()
                param = Parameter(
                    name=f"//{keyword}",
                    type_annotation=None,
                    default=None,
                    kind="note",
                )
                claims.append(
                    DocClaim(
                        raw_text=raw,
                        kind=ClaimKind.CODE_EXAMPLE,
                        doc_file=file_path,
                        line_number=line_no,
                        name=f"//{keyword}",
                        parameters=[param],
                    )
                )

        return claims
