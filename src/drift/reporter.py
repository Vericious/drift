"""Reporter — human-readable (console) and JSON output for drift reports."""
from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from drift.models import (
    ClaimKind,
    DriftItem,
    DriftReport,
    FactKind,
    Parameter,
    Severity,
)


class DriftReporter:
    """Render a DriftReport as console text or JSON."""

    def __init__(self, report: DriftReport) -> None:
        self.report = report
        self.console = Console()

    # -------------------------------------------------------------------------
    # Console output
    # -------------------------------------------------------------------------

    def report_console(self) -> None:
        """Print a rich terminal report to stdout."""
        report = self.report
        scanned = str(report.scanned_path) if report.scanned_path else "."

        # Header
        self.console.print()
        self.console.print(f"[bold cyan]Drift Scan Report[/bold cyan]")
        self.console.print(f"[cyan]{'=' * 50}[/cyan]")
        self.console.print(f"  [dim]Path:[/dim] {scanned}")
        self.console.print(
            f"  Summary: {report.summary()}"
        )
        self.console.print()

        if not report.has_drift and not report.drift_items:
            self.console.print("✅  No drift detected.")
            self.console.print()
            return

        # Errors
        errors = [d for d in report.drift_items if d.severity == Severity.ERROR]
        if errors:
            self._print_section("Errors", errors, "red")

        # Warnings
        warnings = [d for d in report.drift_items if d.severity == Severity.WARNING]
        if warnings:
            self._print_section("Warnings", warnings, "yellow")

        # Info
        infos = [d for d in report.drift_items if d.severity == Severity.INFO]
        if infos:
            self._print_section("Info", infos, "blue")

        self.console.print()

    def _print_section(
        self, title: str, items: list[DriftItem], color: str
    ) -> None:
        count = len(items)
        self.console.print(f"[bold {color}]{title} ({count})[/bold {color}]")
        self.console.print(f"[{color}]{'-' * 50}[/{color}]")

        for item in items:
            self._print_item(item, color)

        self.console.print()

    def _print_item(self, item: DriftItem, color: str) -> None:
        # Location header
        if item.fact:
            loc = f"{item.fact.source_file}:{item.fact.line_number}"
        elif item.claim:
            loc = f"{item.claim.doc_file}:{item.claim.line_number}"
        else:
            loc = "unknown"

        name = (item.fact.name if item.fact else item.claim.name if item.claim else "?")
        self.console.print(f"  [bold {color}][{loc}][/bold {color}] {name}: {item.category}")

        # Show fact signature if available
        if item.fact:
            sig = item.fact.signature_str()
            self.console.print(f"    [dim]Fact:[/dim] {sig}")

        # Show claim signature if available
        if item.claim and item.claim.name:
            claim_sig = self._claim_signature_str(item.claim)
            if claim_sig:
                self.console.print(f"    [dim]Claim says:[/dim] {claim_sig}")

        # Message
        if item.message:
            self.console.print(f"    [dim]→[/dim] {item.message}")

        # Suggestion
        if item.suggestion:
            self.console.print(f"    [dim]Suggestion:[/dim] {item.suggestion}")

    def _claim_signature_str(self, claim) -> str:
        """Render a DocClaim's signature as a string."""
        name = claim.name or "?"
        params = ", ".join(
            p.name + (f": {p.type_annotation}" if p.type_annotation else "")
            + (f" = {p.default}" if p.default else "")
            for p in claim.parameters
        )
        ret = f" -> {claim.return_type}" if claim.return_type else ""
        return f"{name}({params}){ret}"

    # -------------------------------------------------------------------------
    # JSON output
    # -------------------------------------------------------------------------

    def report_json(self) -> str:
        """Return the drift report as a JSON string."""
        report = self.report

        drift_items_list = []
        for item in report.drift_items:
            entry: dict = {
                "severity": item.severity.value,
                "category": item.category,
                "message": item.message,
                "suggestion": item.suggestion,
                "fact": item.fact.to_dict() if item.fact else None,
                "claim": item.claim.to_dict() if item.claim else None,
            }
            drift_items_list.append(entry)

        output = {
            "scanned_path": str(report.scanned_path) if report.scanned_path else ".",
            "summary": {
                "facts": len(report.facts),
                "claims": len(report.claims),
                "drift_items": len(report.drift_items),
                "errors": report.errors_count,
                "warnings": report.warnings_count,
            },
            "has_drift": report.has_drift,
            "drift_items": drift_items_list,
        }

        return json.dumps(output, indent=2)
