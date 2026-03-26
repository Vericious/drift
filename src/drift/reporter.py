"""Reporter — human-readable (console) and JSON output for drift reports."""
from __future__ import annotations

import json

from rich.console import Console
from rich.text import Text

from drift.models import (
    DocClaim,
    DriftItem,
    DriftReport,
    Severity,
)


def _severity_to_sarif_level(severity: Severity) -> str:
    """Map Drift Severity to SARIF result level."""
    mapping = {
        Severity.ERROR: "error",
        Severity.WARNING: "warning",
        Severity.INFO: "note",
    }
    return mapping.get(severity, "warning")


class DriftReporter:
    """Render a DriftReport as console text or JSON."""

    def __init__(self, report: DriftReport, verbose: bool = False) -> None:
        self.report = report
        self.verbose = verbose
        self.console = Console()

    # -------------------------------------------------------------------------
    # Console output
    # -------------------------------------------------------------------------

    def report_console(self, verbose: bool = False, elapsed: float = 0.0) -> None:
        """Print a rich terminal report to stdout."""
        report = self.report
        verbose = verbose or self.verbose
        scanned = str(report.scanned_path) if report.scanned_path else "."

        # Header
        self.console.print()
        self.console.print("[bold cyan]Drift Scan Report[/bold cyan]")
        self.console.print(f"[cyan]{'=' * 50}[/cyan]")
        self.console.print(f"  [dim]Path:[/dim] {scanned}")
        self.console.print(f"  Summary: {report.summary()}")
        if verbose and elapsed:
            self.console.print(f"  [dim]Scan time:[/dim] {elapsed:.3f}s")
        if verbose:
            self.console.print(f"  [dim]Facts:[/dim] {len(report.facts)}")
            self.console.print(f"  [dim]Claims:[/dim] {len(report.claims)}")
            self.console.print(f"  [dim]Errors logged:[/dim] {len(report.errors)}")
        self.console.print()

        if not report.has_drift and not report.drift_items:
            self.console.print("✅  No drift detected.")
            if verbose and elapsed:
                self.console.print(f"[dim]Completed in {elapsed:.3f}s[/dim]")
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
        t = Text.from_markup(
            f"  [bold {color}]{loc}[/bold {color}] {name}: {item.category}"
        )
        self.console.print(t)

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

    def _claim_signature_str(self, claim: DocClaim) -> str:
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
    # SARIF output
    # -------------------------------------------------------------------------

    def report_sarif(self, verbose: bool = False, elapsed: float = 0.0) -> str:
        """Return the drift report as a SARIF v2.1.0 JSON string."""
        report = self.report
        scanned = str(report.scanned_path) if report.scanned_path else "."

        # Build rule index from drift items
        rules: dict[str, dict[str, object]] = {}
        results: list[dict[str, object]] = []

        for item in report.drift_items:
            rule_id = f"drift/{item.category}"
            if rule_id not in rules:
                rules[rule_id] = {
                    "id": rule_id,
                    "name": item.category,
                    "shortDescription": {"text": item.message or item.category},
                    "properties": {"category": item.category},
                }

            # Map severity: ERROR->error, WARNING->warning, INFO->note
            level = _severity_to_sarif_level(item.severity)

            # Build locations
            locations = []

            # Code location from fact
            if item.fact:
                code_loc = {
                    "physicalLocation": {
                        "artifactLocation": {"uri": str(item.fact.source_file)},
                        "region": {"startLine": item.fact.line_number},
                    }
                }
                if item.fact.name:
                    code_loc["physicalLocation"]["displayName"] = item.fact.name
                locations.append(code_loc)

            # Doc location from claim
            if item.claim:
                doc_loc = {
                    "physicalLocation": {
                        "artifactLocation": {"uri": str(item.claim.doc_file)},
                        "region": {"startLine": item.claim.line_number},
                    }
                }
                if item.claim.name:
                    doc_loc["physicalLocation"]["displayName"] = item.claim.name
                locations.append(doc_loc)

            result: dict[str, object] = {
                "ruleId": rule_id,
                "level": level,
                "message": {"text": item.message or f"[{item.category}]"},
            }
            if locations:
                result["locations"] = locations
            if item.suggestion:
                result["suggestion"] = {"text": item.suggestion}

            results.append(result)

        # Build rules list
        rules_list = [{"id": rid, **r} for rid, r in rules.items()]

        run = {
            "tool": {
                "driver": {
                    "name": "drift",
                    "informationUri": "https://github.com/your-org/drift",
                    "rules": rules_list,
                }
            },
            "results": results,
        }

        if verbose and elapsed:
            run["properties"] = {"scanTimeSeconds": round(elapsed, 3)}

        sarif_output = {
            "version": "2.1.0",
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "runs": [run],
        }

        return json.dumps(sarif_output, indent=2)

    # -------------------------------------------------------------------------
    # JSON output
    # -------------------------------------------------------------------------

    def report_json(self, verbose: bool = False, elapsed: float = 0.0) -> str:
        """Return the drift report as a JSON string."""
        report = self.report
        verbose = verbose or self.verbose

        drift_items_list: list[dict[str, object]] = []
        for item in report.drift_items:
            entry: dict[str, object] = {
                "severity": item.severity.value,
                "category": item.category,
                "message": item.message,
                "suggestion": item.suggestion,
                "fact": item.fact.to_dict() if item.fact else None,
                "claim": item.claim.to_dict() if item.claim else None,
            }
            drift_items_list.append(entry)

        output: dict[str, object] = {
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

        if verbose:
            output["scan_time_seconds"] = round(elapsed, 3)

        return json.dumps(output, indent=2)

    # -------------------------------------------------------------------------
    # HTML output
    # -------------------------------------------------------------------------

    def report_html(self, verbose: bool = False, elapsed: float = 0.0) -> str:
        """Return the drift report as a self-contained HTML string."""
        report = self.report
        scanned = str(report.scanned_path) if report.scanned_path else "."

        errors = [d for d in report.drift_items if d.severity == Severity.ERROR]
        warnings = [d for d in report.drift_items if d.severity == Severity.WARNING]
        infos = [d for d in report.drift_items if d.severity == Severity.INFO]

        def item_rows(items: list[DriftItem]) -> str:
            if not items:
                return "<tr><td colspan='4'>None</td></tr>"
            rows = []
            for item in items:
                loc = ""
                if item.fact:
                    loc = f"{item.fact.source_file}:{item.fact.line_number}"
                elif item.claim:
                    loc = f"{item.claim.doc_file}:{item.claim.line_number}"
                name = (item.fact.name if item.fact else
                        (item.claim.name if item.claim else None)) or "?"
                rows.append(
                    f"<tr>"
                    f"<td>{_escape(loc)}</td>"
                    f"<td>{_escape(name)}</td>"
                    f"<td><span class='cat'>{_escape(item.category)}</span></td>"
                    f"<td>{_escape(item.message or '')}</td>"
                    f"</tr>"
                )
            return "\n".join(rows)

        body = ""
        if not report.has_drift and not report.drift_items:
            body += "<p class='no-drift'>✅ No drift detected.</p>\n"
        else:
            if errors:
                body += f"<h2 class='error-header'>❌ Errors ({len(errors)})</h2>\n"
                body += "<table class='drift-table'>\n"
                body += "<thead><tr><th>Location</th><th>Name</th><th>Category</th><th>Message</th></tr></thead>\n<tbody>\n"
                body += item_rows(errors)
                body += "\n</tbody></table>\n"
            if warnings:
                body += f"<h2 class='warning-header'>⚠️ Warnings ({len(warnings)})</h2>\n"
                body += "<table class='drift-table'>\n"
                body += "<thead><tr><th>Location</th><th>Name</th><th>Category</th><th>Message</th></tr></thead>\n<tbody>\n"
                body += item_rows(warnings)
                body += "\n</tbody></table>\n"
            if infos:
                body += f"<h2 class='info-header'>ℹ️ Info ({len(infos)})</h2>\n"
                body += "<table class='drift-table'>\n"
                body += "<thead><tr><th>Location</th><th>Name</th><th>Category</th><th>Message</th></tr></thead>\n<tbody>\n"
                body += item_rows(infos)
                body += "\n</tbody></table>\n"

        summary_text = report.summary()
        facts_count = len(report.facts)
        claims_count = len(report.claims)
        errors_count = len(errors)
        warnings_count = len(warnings)

        html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>Drift Report — {_escape(scanned)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; background: #f8f9fa; color: #212529; }}
h1 {{ color: #0d6efd; }}
h2 {{ margin-top: 1.5rem; }}
.no-drift {{ font-size: 1.2rem; color: #198754; }}
.error-header {{ color: #dc3545; }}
.warning-header {{ color: #fd7e14; }}
.info-header {{ color: #0dcaf0; }}
.drift-table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.drift-table th, .drift-table td {{ padding: 0.5rem; text-align: left; border-bottom: 1px solid #dee2e6; }}
.drift-table th {{ background: #e9ecef; font-weight: 600; }}
.drift-table tr:hover {{ background: #f8f9fa; }}
.cat {{ background: #e7f1ff; color: #0d6efd; padding: 0.1em 0.4em; border-radius: 3px; font-size: 0.85em; }}
.summary {{ background: white; padding: 1rem; margin-bottom: 1rem; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
</style>
</head>
<body>
<h1>Drift Report</h1>
<div class='summary'>
<p><strong>Path:</strong> {_escape(scanned)}</p>
<p><strong>Summary:</strong> {summary_text}</p>
<p><strong>Facts:</strong> {facts_count} &nbsp; <strong>Claims:</strong> {claims_count} &nbsp;
<strong>Errors:</strong> {errors_count} &nbsp; <strong>Warnings:</strong> {warnings_count}</p>
</div>
{body}
<p style='color:#888;font-size:0.85em;margin-top:2rem'>Generated by Drift v0.4.0</p>
</body>
</html>"""
        return html


def _escape(s: str) -> str:
    """Escape HTML special characters."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))
