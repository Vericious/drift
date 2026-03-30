"""Reporter — human-readable (console) and JSON output for drift reports."""
from __future__ import annotations

import json

from rich.console import Console
from rich.text import Text

from drift import __version__
from drift.models import (
    ClaimKind,
    ConfidenceSignals,
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

    def __init__(
        self,
        report: DriftReport,
        verbose: bool = False,
        min_confidence: float | None = None,
    ) -> None:
        self.report = report
        self.verbose = verbose
        self.min_confidence = min_confidence
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
        if report.files_skipped > 0:
            self.console.print(f"  [dim]Files skipped (unchanged):[/dim] {report.files_skipped}")
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

        # Confidence percentage
        conf_pct = int(item.confidence * 100)
        self.console.print(f"    [dim]Confidence:[/dim] {conf_pct}%")

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
                "rank": item.confidence * 100,
                "properties": {"confidence": item.confidence},
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
                "confidence": item.confidence,
                "message": item.message,
                "suggestion": item.suggestion,
                "fact": item.fact.to_dict() if item.fact else None,
                "claim": item.claim.to_dict() if item.claim else None,
            }
            if item.signals is not None:
                entry["signals"] = item.signals.to_dict()
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

        if self.min_confidence is not None:
            output["confidence_filter"] = {
                "min": self.min_confidence,
                "shown": len(report.drift_items),
                "total": len(report.facts) + len(report.claims),
            }

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
                return "<tr><td colspan='5'>None</td></tr>"
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
                    f"<td>{item.confidence:.0%}</td>"
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
                body += "<thead><tr><th>Location</th><th>Name</th><th>Category</th><th>Message</th><th>Confidence</th></tr></thead>\n<tbody>\n"
                body += item_rows(errors)
                body += "\n</tbody></table>\n"
            if warnings:
                body += f"<h2 class='warning-header'>⚠️ Warnings ({len(warnings)})</h2>\n"
                body += "<table class='drift-table'>\n"
                body += "<thead><tr><th>Location</th><th>Name</th><th>Category</th><th>Message</th><th>Confidence</th></tr></thead>\n<tbody>\n"
                body += item_rows(warnings)
                body += "\n</tbody></table>\n"
            if infos:
                body += f"<h2 class='info-header'>ℹ️ Info ({len(infos)})</h2>\n"
                body += "<table class='drift-table'>\n"
                body += "<thead><tr><th>Location</th><th>Name</th><th>Category</th><th>Message</th><th>Confidence</th></tr></thead>\n<tbody>\n"
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
<p style='color:#888;font-size:0.85em;margin-top:2rem'>Generated by Drift v{__version__}</p>
</body>
</html>"""
        return html


        return html

    # -------------------------------------------------------------------------
    # Diff-style output
    # -------------------------------------------------------------------------

    def report_diff(self, verbose: bool = False, elapsed: float = 0.0) -> str:
        """Return diff-style output showing exact changes needed.

        Format:
          --- docs/<file>
          +++ code/<file>
          @@ -old,+new @@
          <content>
        """
        report = self.report
        output_parts: list[str] = []

        if not report.drift_items:
            return "No drift to display.\n"

        output_parts.append("[bold cyan]Drift — Diff View[/bold cyan]")
        output_parts.append(f"[cyan]{'=' * 50}[/cyan]")

        errors = [d for d in report.drift_items if d.severity == Severity.ERROR]
        warnings = [d for d in report.drift_items if d.severity == Severity.WARNING]
        infos = [d for d in report.drift_items if d.severity == Severity.INFO]

        for group_name, items in [
            ("Errors", errors),
            ("Warnings", warnings),
            ("Info", infos),
        ]:
            if not items:
                continue
            output_parts.append(f"\n[bold {group_name} ({len(items)})[/bold {group_name}]")

            for item in items:
                diff_output = self._item_diff(item)
                if diff_output:
                    output_parts.append(diff_output)
                    output_parts.append("")

        return "\n".join(output_parts)

    # -------------------------------------------------------------------------
    # Unified patch output
    # -------------------------------------------------------------------------

    # Categories that can be represented as a unified patch
    _PATCHABLE_CATEGORIES = frozenset([
        "wrong_default",
        "wrong_type",
        "wrong_return_type",
        "documented_but_missing",
    ])

    def report_patch(self, verbose: bool = False, elapsed: float = 0.0) -> str:
        """Return git-compatible unified patches for fixable drift categories.

        Produces proper 'diff --git a/ b/' unified patches for:
        - wrong_default: update doc to show correct parameter default
        - wrong_type: update doc to show correct parameter type
        - wrong_return_type: update doc to show correct return type
        - documented_but_missing: remove the doc entry (the item was removed from code)

        Non-fixable categories are skipped with a comment.
        """
        report = self.report
        output_parts: list[str] = []

        if not report.drift_items:
            return "No drift to display.\n"

        patch_count = 0
        skip_count = 0

        for item in report.drift_items:
            if item.category in self._PATCHABLE_CATEGORIES:
                patch_output = self._item_patch(item)
                if patch_output:
                    output_parts.append(patch_output)
                    output_parts.append("")
                    patch_count += 1
                else:
                    skip_count += 1
            else:
                skip_count += 1

        if skip_count > 0:
            output_parts.append(f"# {skip_count} item(s) skipped (not patchable)\n")

        if patch_count == 0 and skip_count > 0:
            return (
                "".join(output_parts)
                + "No patchable drift items found.\n"
            )

        return "\n".join(output_parts)

    def _item_patch(self, item: DriftItem) -> str | None:
        """Generate a unified patch for a single fixable drift item.

        Returns None if the patch cannot be generated (e.g., file not readable).
        """
        if item.category == "documented_but_missing":
            return self._patch_documented_but_missing(item)
        elif item.category == "wrong_default":
            return self._patch_wrong_default(item)
        elif item.category == "wrong_type":
            return self._patch_wrong_type(item)
        elif item.category == "wrong_return_type":
            return self._patch_wrong_return_type(item)
        return None

    def _read_doc_lines(self, doc_file: Path, start_line: int, end_line: int) -> list[str]:
        """Read lines from a doc file, returning lines in [start_line, end_line] inclusive.

        Returns empty list if file cannot be read.
        """
        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Convert 1-indexed to 0-indexed, inclusive
            start = max(0, start_line - 1)
            end = min(len(lines), end_line)
            return lines[start:end]
        except (OSError, IOError):
            return []

    def _build_patch_hunk(
        self,
        doc_file: Path,
        claim_line: int,
        context_before: int = 3,
        context_after: int = 3,
        old_lines: list[str] | None = None,
        new_lines: list[str] | None = None,
    ) -> str | None:
        """Build a unified patch hunk for changes to a doc file.

        Args:
            doc_file: Path to the doc file being patched
            claim_line: The primary line number associated with the drift item (1-indexed)
            context_before: Number of context lines before the change
            context_after: Number of context lines after the change
            old_lines: Lines being removed (without leading +/-)
            new_lines: Lines being added (without leading +/-)

        Returns:
            A unified diff string, or None if the file cannot be read.
        """
        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
        except (OSError, IOError):
            return None

        # Compute hunk range: we want context around the change
        # old_lines are at claim_line, new_lines replace them
        hunk_start = max(0, claim_line - 1 - context_before)
        hunk_end = min(len(all_lines), claim_line - 1 + context_after)

        # If old_lines provided, extend range to include them
        if old_lines:
            # Find where in the file these lines appear near claim_line
            pass  # We'll search for the old content

        # Simple approach: use claim_line as center, read context around it
        # Build the hunk body
        body_lines: list[str] = []
        # Add context before
        for i in range(hunk_start, claim_line - 1):
            body_lines.append(f" {all_lines[i].rstrip()}")

        # Add old lines (removed)
        if old_lines:
            for line in old_lines:
                body_lines.append(f"-{line.rstrip()}")

        # Add new lines (added)
        if new_lines:
            for line in new_lines:
                body_lines.append(f"+{line}")

        # Add context after
        for i in range(claim_line - 1, hunk_end):
            body_lines.append(f" {all_lines[i].rstrip()}")

        # Compute hunk ranges
        old_count = len([l for l in body_lines if l.startswith(" ")]) + len(old_lines) if old_lines else 0
        new_count = len([l for l in body_lines if l.startswith(" ")]) + len(new_lines) if new_lines else 0
        # Actually compute from actual context + removals/additions
        old_range_lines = [l for l in body_lines if l.startswith(" ") or l.startswith("-")]
        new_range_lines = [l for l in body_lines if l.startswith(" ") or l.startswith("+")]

        # We need the actual line numbers in the file for @@ header
        old_start = hunk_start + 1  # 1-indexed
        old_count_final = len(old_range_lines)
        new_start = hunk_start + 1
        new_count_final = len(new_range_lines)

        file_str = str(doc_file)
        git_path = file_str  # Use the file path as-is

        hunk_header = (
            f"diff --git a/{git_path} b/{git_path}\n"
            f"--- a/{git_path}\n"
            f"+++ b/{git_path}\n"
            f"@@ -{old_start},{old_count_final} +{new_start},{new_count_final} @@"
        )

        return hunk_header + "\n" + "\n".join(body_lines) + "\n"

    def _patch_documented_but_missing(self, item: DriftItem) -> str | None:
        """Generate a patch that removes a documented-but-missing item from docs.

        The patch removes the doc claim line from the doc file.
        """
        if not item.claim:
            return None

        doc_file = item.claim.doc_file
        claim_line = item.claim.line_number

        # Try to read the doc file to find the line
        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, IOError):
            return None

        if claim_line < 1 or claim_line > len(lines):
            return None

        # Find the line content and surrounding context
        context_before = 3
        context_after = 3

        # claim_line is 1-indexed. Context before covers [claim_line-1-context_before, claim_line-2].
        # Context after covers [claim_line, claim_line+context_after-1].
        hunk_start = max(0, claim_line - 1 - context_before)
        hunk_end = min(len(lines), claim_line + context_after)  # claim_line is 1-idx, so this is exclusive bound

        # The line at claim_line is the one to remove
        body_lines: list[str] = []

        # Context before: indices [hunk_start, claim_line-2] = range(hunk_start, claim_line-1)
        for i in range(hunk_start, claim_line - 1):
            body_lines.append(f" {lines[i].rstrip()}")

        # The line to remove (at 1-indexed claim_line = 0-indexed claim_line-1)
        body_lines.append(f"-{lines[claim_line - 1].rstrip()}")

        # Context after: indices [claim_line, hunk_end-1] = range(claim_line, hunk_end)
        for i in range(claim_line, hunk_end):
            body_lines.append(f" {lines[i].rstrip()}")

        # old_count: context_before + 1 (removed line) + context_after
        old_count = (claim_line - 1 - hunk_start) + 1 + (hunk_end - claim_line)
        # new_count: context_before + context_after (removed line not present)
        new_count = (claim_line - 1 - hunk_start) + (hunk_end - claim_line)

        file_str = str(doc_file)
        hunk_header = (
            f"diff --git a/{file_str} b/{file_str}\n"
            f"--- a/{file_str}\n"
            f"+++ b/{file_str}\n"
            f"@@ -{hunk_start + 1},{old_count} +{hunk_start + 1},{new_count} @@ [documented_but_missing] remove missing item"
        )

        return hunk_header + "\n" + "\n".join(body_lines) + "\n"

    def _patch_wrong_default(self, item: DriftItem) -> str | None:
        """Generate a patch to fix a wrong parameter default in docs."""
        if not item.claim or not item.fact:
            return None

        doc_file = item.claim.doc_file
        claim_line = item.claim.line_number

        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, IOError):
            return None

        if claim_line < 1 or claim_line > len(lines):
            return None

        # Find the parameter with wrong default
        # The claim has parameters with their documented defaults
        # The fact has the actual defaults
        claim_params = {p.name: p for p in item.claim.parameters}
        fact_params = {p.name: p for p in item.fact.parameters}

        old_line = lines[claim_line - 1].rstrip()
        new_line = old_line

        # Try to update the default for matching params
        for param_name, fact_param in fact_params.items():
            if param_name in claim_params:
                claim_param = claim_params[param_name]
                if claim_param.default is not None and fact_param.default is not None:
                    if claim_param.default != fact_param.default:
                        # Replace old default with new default in the line
                        # The old format likely has "= <old_default>"
                        old_default_str = f"= {claim_param.default}"
                        new_default_str = f"= {fact_param.default}"
                        if old_default_str in new_line:
                            new_line = new_line.replace(old_default_str, new_default_str)
                        elif claim_param.default in new_line:
                            new_line = new_line.replace(claim_param.default, fact_param.default)

        if old_line == new_line:
            return None  # No change needed

        context_before = 3
        context_after = 3
        # claim_line is 1-indexed; context after starts at claim_line+1 (0-indexed = claim_line)
        hunk_start = max(0, claim_line - 1 - context_before)
        hunk_end = min(len(lines), claim_line + context_after)  # claim_line is 1-idx, exclusive end

        body_lines: list[str] = []
        for i in range(hunk_start, claim_line - 1):
            body_lines.append(f" {lines[i].rstrip()}")
        body_lines.append(f"-{old_line}")
        body_lines.append(f"+{new_line}")
        for i in range(claim_line, hunk_end):
            body_lines.append(f" {lines[i].rstrip()}")

        # For substitution: old = ctx_before + 1(removed) + ctx_after, new = ctx_before + 1(added) + ctx_after
        # old_count = (claim_line - 1 - hunk_start) + 1 + (hunk_end - claim_line)
        # new_count = (claim_line - 1 - hunk_start) + 1 + (hunk_end - claim_line)
        # But the @@ counts: for substitution at a single line, old gets +1, new gets +1 (the sub line counts in both)
        # Actually: old_count = ctx_before + 1(removed) + ctx_after, new_count = ctx_before + 1(added) + ctx_after
        old_count = (claim_line - 1 - hunk_start) + 1 + (hunk_end - claim_line)
        new_count = old_count  # same total line count (1 removed, 1 added, net 0)

        file_str = str(doc_file)
        hunk_header = (
            f"diff --git a/{file_str} b/{file_str}\n"
            f"--- a/{file_str}\n"
            f"+++ b/{file_str}\n"
            f"@@ -{hunk_start + 1},{old_count} +{hunk_start + 1},{new_count} @@ [wrong_default] fix parameter default"
        )

        return hunk_header + "\n" + "\n".join(body_lines) + "\n"

    def _patch_wrong_type(self, item: DriftItem) -> str | None:
        """Generate a patch to fix a wrong parameter type in docs."""
        if not item.claim or not item.fact:
            return None

        doc_file = item.claim.doc_file
        claim_line = item.claim.line_number

        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, IOError):
            return None

        if claim_line < 1 or claim_line > len(lines):
            return None

        claim_params = {p.name: p for p in item.claim.parameters}
        fact_params = {p.name: p for p in item.fact.parameters}

        old_line = lines[claim_line - 1].rstrip()
        new_line = old_line

        for param_name, fact_param in fact_params.items():
            if param_name in claim_params:
                claim_param = claim_params[param_name]
                if claim_param.type_annotation and fact_param.type_annotation:
                    if claim_param.type_annotation != fact_param.type_annotation:
                        if f": {claim_param.type_annotation}" in new_line:
                            new_line = new_line.replace(
                                f": {claim_param.type_annotation}",
                                f": {fact_param.type_annotation}",
                            )
                        elif claim_param.type_annotation in new_line:
                            new_line = new_line.replace(
                                claim_param.type_annotation,
                                fact_param.type_annotation,
                            )

        if old_line == new_line:
            return None

        context_before = 3
        context_after = 3
        hunk_start = max(0, claim_line - 1 - context_before)
        hunk_end = min(len(lines), claim_line - 1 + context_after)

        body_lines: list[str] = []
        for i in range(hunk_start, claim_line - 1):
            body_lines.append(f" {lines[i].rstrip()}")
        body_lines.append(f"-{old_line}")
        body_lines.append(f"+{new_line}")
        for i in range(claim_line, hunk_end):
            body_lines.append(f" {lines[i].rstrip()}")

        old_count = hunk_end - hunk_start
        new_count = old_count

        file_str = str(doc_file)
        hunk_header = (
            f"diff --git a/{file_str} b/{file_str}\n"
            f"--- a/{file_str}\n"
            f"+++ b/{file_str}\n"
            f"@@ -{hunk_start + 1},{old_count} +{hunk_start + 1},{new_count} @@ [wrong_type] fix parameter type"
        )

        return hunk_header + "\n" + "\n".join(body_lines) + "\n"

    def _patch_wrong_return_type(self, item: DriftItem) -> str | None:
        """Generate a patch to fix a wrong return type in docs."""
        if not item.claim or not item.fact:
            return None

        doc_file = item.claim.doc_file
        claim_line = item.claim.line_number

        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, IOError):
            return None

        if claim_line < 1 or claim_line > len(lines):
            return None

        old_line = lines[claim_line - 1].rstrip()
        new_line = old_line

        if item.claim.return_type and item.fact.return_type:
            if item.claim.return_type != item.fact.return_type:
                old_ret = f"-> {item.claim.return_type}"
                new_ret = f"-> {item.fact.return_type}"
                if old_ret in new_line:
                    new_line = new_line.replace(old_ret, new_ret)
                elif item.claim.return_type in new_line:
                    new_line = new_line.replace(
                        item.claim.return_type,
                        item.fact.return_type,
                    )

        if old_line == new_line:
            return None

        context_before = 3
        context_after = 3
        hunk_start = max(0, claim_line - 1 - context_before)
        hunk_end = min(len(lines), claim_line - 1 + context_after)

        body_lines: list[str] = []
        for i in range(hunk_start, claim_line - 1):
            body_lines.append(f" {lines[i].rstrip()}")
        body_lines.append(f"-{old_line}")
        body_lines.append(f"+{new_line}")
        for i in range(claim_line, hunk_end):
            body_lines.append(f" {lines[i].rstrip()}")

        old_count = hunk_end - hunk_start
        new_count = old_count

        file_str = str(doc_file)
        hunk_header = (
            f"diff --git a/{file_str} b/{file_str}\n"
            f"--- a/{file_str}\n"
            f"+++ b/{file_str}\n"
            f"@@ -{hunk_start + 1},{old_count} +{hunk_start + 1},{new_count} @@ [wrong_return_type] fix return type"
        )

        return hunk_header + "\n" + "\n".join(body_lines) + "\n"

    def _item_diff(self, item: DriftItem) -> str:
        """Generate diff-style output for a single drift item."""
        lines: list[str] = []

        if item.category == "documented_but_missing":
            lines = self._diff_documented_but_missing(item)
        elif item.category == "fuzzy_renamed":
            lines = self._diff_renamed(item)
        elif item.category == "undocumented":
            lines = self._diff_undocumented(item)
        elif item.category == "code_without_docs":
            lines = self._diff_undocumented(item)
        elif item.category == "parameter_mismatch":
            lines = self._diff_parameter_mismatch(item)
        else:
            lines = self._diff_generic(item)

        return "\n".join(lines)

    def _diff_documented_but_missing(self, item: DriftItem) -> list[str]:
        """Diff for documented_but_missing: show claim vs 'not found in code'."""
        lines: list[str] = []

        claim = item.claim
        fact = item.fact

        claim_file = str(claim.doc_file) if claim else "docs"
        claim_name = claim.name if claim else "?"
        fact_file = str(fact.source_file) if fact else "code"
        fact_name = fact.name if fact else claim_name

        lines.append(f"--- {claim_file}")
        lines.append(f"+++ {fact_file} (not found)")
        lines.append(f"@@ -1,0 +1,? @@ [documented_but_missing] {claim_name}")

        # Show what the docs say
        if claim:
            sig = self._claim_signature_str(claim)
            lines.append(f"- {sig}")
            if claim.raw_text:
                for doc_line in claim.raw_text.split("\n"):
                    lines.append(f"- {doc_line}")

        # Show what the code actually has (nothing = missing)
        lines.append(f"+ (function not found in code)")
        lines.append(f"+ ")
        lines.append(f"+ # MISSING: {fact_name} is documented but does not exist in code")
        lines.append(f"+ # Add the implementation or remove from docs")

        if item.suggestion:
            lines.append(f"+ # Suggestion: {item.suggestion}")

        return lines

    def _diff_renamed(self, item: DriftItem) -> list[str]:
        """Diff for fuzzy_renamed: show old name vs new name."""
        lines: list[str] = []

        claim = item.claim
        fact = item.fact

        claim_file = str(claim.doc_file) if claim else "docs"
        fact_file = str(fact.source_file) if fact else "code"
        claim_name = claim.name if claim else "?"
        fact_name = fact.name if fact else "?"

        old_sig = f"def {claim_name}("
        new_sig = f"def {fact_name}("

        lines.append(f"--- {claim_file} (old name)")
        lines.append(f"+++ {fact_file} (new name)")
        lines.append(f"@@ -1 +1 @@ [fuzzy_renamed] {claim_name} -> {fact_name}")
        lines.append(f"- {old_sig}...")
        lines.append(f"+ {new_sig}...")

        if item.suggestion:
            lines.append(f"+ # Suggestion: {item.suggestion}")

        return lines

    def _diff_undocumented(self, item: DriftItem) -> list[str]:
        """Diff for undocumented: show suggested doc snippet."""
        lines: list[str] = []

        fact = item.fact
        fact_file = str(fact.source_file) if fact else "code"
        fact_name = fact.name if fact else "?"
        fact_sig = fact.signature_str() if fact else f"{fact_name}()"

        lines.append(f"--- {fact_file} (undocumented)")
        lines.append(f"+++ {fact_file} (suggested doc)")
        lines.append(f"@@ -0,0 +1,? @@ [undocumented] {fact_name}")
        lines.append(f"+ # Documentation to add:")
        lines.append(f"+ def {fact_sig}:")
        if fact and fact.docstring:
            for doc_line in fact.docstring.split("\n"):
                lines.append(f"+    {doc_line}")
        else:
            lines.append(f"+    [describe what this does]")

        if item.suggestion:
            lines.append(f"+ # Suggestion: {item.suggestion}")

        return lines

    def _diff_parameter_mismatch(self, item: DriftItem) -> list[str]:
        """Diff for parameter_mismatch: show expected vs actual params."""
        lines: list[str] = []

        claim = item.claim
        fact = item.fact

        claim_file = str(claim.doc_file) if claim else "docs"
        fact_file = str(fact.source_file) if fact else "code"
        claim_name = claim.name if claim else "?"
        fact_name = fact.name if fact else claim_name

        lines.append(f"--- {claim_file} (docs)")
        lines.append(f"+++ {fact_file} (code)")
        lines.append(f"@@ -1 +1 @@ [parameter_mismatch] {fact_name}")

        # Show what docs claim
        if claim:
            sig = self._claim_signature_str(claim)
            lines.append(f"- {sig}")
        # Show what code has
        if fact:
            sig = fact.signature_str()
            lines.append(f"+ {sig}")

        if item.suggestion:
            lines.append(f"+ # Suggestion: {item.suggestion}")

        return lines

    def _diff_generic(self, item: DriftItem) -> list[str]:
        """Generic diff for other categories."""
        lines: list[str] = []

        claim = item.claim
        fact = item.fact

        claim_file = str(claim.doc_file) if claim else "docs"
        fact_file = str(fact.source_file) if fact else "code"

        lines.append(f"--- {claim_file}")
        lines.append(f"+++ {fact_file}")
        lines.append(f"@@ ... @@ [{item.category}]")

        if item.message:
            lines.append(f"    {item.message}")
        if item.suggestion:
            lines.append(f"    Suggestion: {item.suggestion}")

        return lines


def _escape(s: str) -> str:
    """Escape HTML special characters."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))
