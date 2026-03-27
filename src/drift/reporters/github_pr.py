"""GitHub PR comment reporter for drift results."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

import requests

from drift.models import DriftItem, DriftReport, Severity
from drift.reporter import DriftReporter


# Marker we use to identify our own comment so we can edit it
COMMENT_MARKER = "<!-- drift-report -->"


class GitHubPRReporter:
    """Post drift results as a GitHub PR comment.

    Auto-detects GITHUB_* environment variables when running in GitHub Actions.
    Also accepts explicit --github-pr-token and --github-pr-number arguments.
    """

    GITHUB_API = "https://api.github.com"

    def __init__(
        self,
        report: DriftReport,
        token: Optional[str] = None,
        pr_number: Optional[int] = None,
        repo: Optional[str] = None,  # "owner/repo"
        commit_sha: Optional[str] = None,
        verbose: bool = False,
    ) -> None:
        self.report = report
        self.verbose = verbose

        # Token: explicit > env var
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self._session = requests.Session()
        if self.token:
            self._session.headers["Authorization"] = f"token {self.token}"
        self._session.headers["Accept"] = "application/vnd.github.v3+json"
        self._session.headers["User-Agent"] = "drift-reporter"

        # PR number: explicit > env var
        self.pr_number: Optional[int] = pr_number or self._env_int("GITHUB_PR_NUMBER")
        self.commit_sha = commit_sha or os.environ.get("GITHUB_SHA")

        # Repo: explicit > env var
        self.repo: Optional[str] = repo or os.environ.get("GITHUB_REPOSITORY")

        # Base URL for GitHub API
        self.api_base = f"{self.GITHUB_API}/repos/{self.repo}" if self.repo else None

    @staticmethod
    def _env_int(name: str) -> Optional[int]:
        try:
            return int(os.environ.get(name, ""))
        except (ValueError, TypeError):
            return None

    def in_github_actions(self) -> bool:
        """Return True if we detect GitHub Actions environment."""
        return bool(os.environ.get("GITHUB_ACTIONS"))

    def detect_pr_from_github_output(self) -> tuple[Optional[int], Optional[str]]:
        """Read GITHUB_OUTPUT file to extract PR number and repo.

        Returns (pr_number, repo).
        """
        output_path = os.environ.get("GITHUB_OUTPUT")
        if not output_path or not Path(output_path).exists():
            return None, None

        pr_number: Optional[int] = None
        repo: Optional[str] = None

        content = Path(output_path).read_text()
        for line in content.splitlines():
            # GITHUB_OUTPUT uses: name=value  or  name<<EOF\nvalue\nEOF
            # We only handle the simple key=value form
            if "=" not in line:
                continue
            key, _, raw_val = line.partition("=")
            # Strip heredoc marker if present
            val = raw_val.strip()
            if key == "pr_number":
                try:
                    pr_number = int(val)
                except ValueError:
                    pass
            elif key == "repo":
                repo = val

        return pr_number, repo

    def _find_existing_comment_id(self) -> Optional[int]:
        """Find the ID of our existing drift PR comment, if any."""
        if not self.api_base or not self.pr_number:
            return None

        url = f"{self.api_base}/issues/{self.pr_number}/comments"
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            return None

        for comment in resp.json():
            body = comment.get("body", "")
            if body.startswith(COMMENT_MARKER):
                return comment["id"]
        return None

    def _build_comment_body(self) -> str:
        """Render the drift report as a Markdown table comment."""
        report = self.report
        reporter = DriftReporter(report, verbose=self.verbose)

        lines: list[str] = []
        lines.append(f"{COMMENT_MARKER}")
        lines.append("## 📋 Drift Report")
        lines.append("")

        # Summary
        summary = report.summary()
        scanned = str(report.scanned_path) if report.scanned_path else "."
        lines.append(f"**Scanned:** `{scanned}`")
        lines.append(f"**Summary:** {summary}")
        lines.append("")

        # Stats
        errors = [d for d in report.drift_items if d.severity == Severity.ERROR]
        warnings = [d for d in report.drift_items if d.severity == Severity.WARNING]
        infos = [d for d in report.drift_items if d.severity == Severity.INFO]

        lines.append(
            f"<!-- drift-stats: "
            f"errors={len(errors)} warnings={len(warnings)} info={len(infos)} -->"
        )
        lines.append("| Severity | Category | Fact | Detail |")
        lines.append("|----------|----------|------|--------|")

        for item in report.drift_items:
            sev = item.severity.value
            cat = item.category

            if item.fact:
                loc = f"{item.fact.source_file}:{item.fact.line_number}"
                name = item.fact.name or "?"
                sig = item.fact.signature_str()
                fact_str = f"`{name}` at {loc}\n```python\n{sig}\n```"
            elif item.claim:
                loc = f"{item.claim.doc_file}:{item.claim.line_number}"
                name = item.claim.name or "?"
                fact_str = f"`{name}` at {loc}"
            else:
                fact_str = "?"

            detail_parts: list[str] = []
            if item.message:
                detail_parts.append(item.message)
            if item.suggestion:
                detail_parts.append(f"**Suggestion:** {item.suggestion}")

            detail = "<br>".join(detail_parts) if detail_parts else "—"

            # Emoji for severity
            sev_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(sev, "⚪")

            # Escape pipes in content for markdown table
            fact_cell = fact_str.replace("|", "\\|").replace("\n", "<br>")
            detail_cell = detail.replace("|", "\\|")

            lines.append(f"| {sev_icon} {sev} | {cat} | {fact_cell} | {detail_cell} |")

        lines.append("")
        lines.append(
            f"*Generated by [drift](https://github.com/your-org/drift) · "
            f"{len(report.drift_items)} item(s) · "
            f"{len(errors)} 🔴 · {len(warnings)} 🟡 · {len(infos)} 🔵*"
        )

        return "\n".join(lines)

    def report_github_pr(self) -> bool:
        """Post or update the drift report as a GitHub PR comment.

        Returns True on success, False on failure.
        Exit code logic: callers should use has_errors() on the report
        to determine exit code.
        """
        if not self.api_base:
            # Try to detect from GITHUB_OUTPUT
            pr_num, repo = self.detect_pr_from_github_output()
            if pr_num and repo:
                self.pr_number = pr_num
                self.repo = repo
                self.api_base = f"{self.GITHUB_API}/repos/{repo}"
            else:
                print("drift: GITHUB_PR_REPORTER: no repo/PR info available, skipping")
                return False

        if not self.pr_number:
            print("drift: GITHUB_PR_REPORTER: no PR number, skipping")
            return False

        if not self.token:
            print("drift: GITHUB_PR_REPORTER: no GitHub token, skipping")
            return False

        existing_id = self._find_existing_comment_id()
        body = self._build_comment_body()

        url = f"{self.api_base}/issues/{self.pr_number}/comments"

        try:
            if existing_id:
                # Patch existing comment
                patch_url = f"{self.api_base}/issues/comments/{existing_id}"
                resp = self._session.patch(patch_url, json={"body": body}, timeout=10)
                resp.raise_for_status()
                print(f"drift: updated PR comment {existing_id}")
            else:
                # Post new comment
                resp = self._session.post(url, json={"body": body}, timeout=10)
                resp.raise_for_status()
                new_id = resp.json().get("id")
                print(f"drift: posted PR comment {new_id}")
        except requests.RequestException as e:
            print(f"drift: failed to post PR comment: {e}")
            return False

        return True

    def has_errors(self) -> bool:
        """Return True if the report contains any ERROR-severity items."""
        return any(d.severity == Severity.ERROR for d in self.report.drift_items)
