"""GitHub Actions step summary reporter for drift.

Writes drift results to GITHUB_STEP_SUMMARY when running in GitHub Actions,
providing a formatted Markdown summary in the workflow run.
"""

from __future__ import annotations

import os
from pathlib import Path

from drift.models import DriftReport, DriftItem, Severity
from drift.reporter import DriftReporter


class GitHubSummaryReporter:
    """Report drift results as GitHub Actions step summary (Markdown).

    Activates only when the GITHUB_STEP_SUMMARY environment variable is set.
    Otherwise this is a graceful no-op.
    """

    def __init__(self, report: DriftReport, verbose: bool = False) -> None:
        self.report = report
        self.verbose = verbose
        self._base_reporter = DriftReporter(report, verbose=verbose)

    def is_active(self) -> bool:
        """Return True if GITHUB_STEP_SUMMARY is set."""
        return bool(os.environ.get("GITHUB_STEP_SUMMARY"))

    def write_summary(self, elapsed: float = 0.0) -> None:
        """Write the drift report as a Markdown summary to GITHUB_STEP_SUMMARY.

        Does nothing if GITHUB_STEP_SUMMARY is not set.
        """
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_path:
            return

        markdown = self._render_markdown(elapsed=elapsed)
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown)

    def _render_markdown(self, elapsed: float = 0.0) -> str:
        """Render the report as GitHub-flavored Markdown."""
        report = self.report
        scanned = str(report.scanned_path) if report.scanned_path else "."

        errors = [d for d in report.drift_items if d.severity == Severity.ERROR]
        warnings = [d for d in report.drift_items if d.severity == Severity.WARNING]
        infos = [d for d in report.drift_items if d.severity == Severity.INFO]

        lines: list[str] = []

        # Title
        lines.append("# Drift Report")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- **Path:** `{scanned}`")
        lines.append(f"- **Facts:** {len(report.facts)}")
        lines.append(f"- **Claims:** {len(report.claims)}")
        lines.append(f"- **Drift Items:** {len(report.drift_items)}")
        lines.append(f"- **Errors:** {len(errors)}")
        lines.append(f"- **Warnings:** {len(warnings)}")
        if self.verbose and elapsed:
            lines.append(f"- **Scan Time:** {elapsed:.3f}s")
        lines.append("")

        if not report.has_drift and not report.drift_items:
            lines.append("✅ **No drift detected.**")
            lines.append("")
            return "\n".join(lines)

        # Errors section
        if errors:
            lines.append("## Errors")
            lines.append("")
            lines.extend(self._items_table(errors))
            lines.append("")

        # Warnings section
        if warnings:
            lines.append("## Warnings")
            lines.append("")
            lines.extend(self._items_table(warnings))
            lines.append("")

        # Info section
        if infos:
            lines.append("## Info")
            lines.append("")
            lines.extend(self._items_table(infos))
            lines.append("")

        return "\n".join(lines)

    def _items_table(self, items: list[DriftItem]) -> list[str]:
        """Render a list of drift items as a Markdown table."""
        if not items:
            return ["_None_", ""]

        header = "| Location | Name | Category | Message | Confidence |"
        separator = "| --- | --- | --- | --- | --- |"
        lines = [header, separator]

        for item in items:
            loc = ""
            if item.fact:
                loc = f"`{item.fact.source_file}:{item.fact.line_number}`"
            elif item.claim:
                loc = f"`{item.claim.doc_file}:{item.claim.line_number}`"

            name = (
                item.fact.name if item.fact else
                (item.claim.name if item.claim else "?")
            ) or "?"

            message = (item.message or "").replace("|", "\\|").replace("\n", " ")
            suggestion = ""
            if item.suggestion:
                suggestion = item.suggestion.replace("|", "\\|").replace("\n", " ")

            lines.append(
                f"| {loc} | `{name}` | {item.category} | "
                f"{message} {suggestion} | {item.confidence:.0%} |"
            )

        return lines
