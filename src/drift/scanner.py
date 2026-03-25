"""Scanner — orchestrates the full drift detection pipeline."""
from pathlib import Path

from drift.models import CodeFact, DocClaim, DriftReport
from drift.python_extractor import PythonExtractor
from drift.extractors.markdown import MarkdownExtractor
from drift.matcher import SignatureMatcher


class DriftScanner:
    """Walk files, dispatch to extractors, run matcher, produce report."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.py_extractor = PythonExtractor()
        self.md_extractor = MarkdownExtractor()
        self.matcher = SignatureMatcher()

    def scan(self) -> DriftReport:
        """Scan the path recursively, extract facts and claims, match, return report."""
        errors: list[str] = []
        all_facts: list[CodeFact] = []
        all_claims: list[DocClaim] = []

        # Determine files to scan
        if self.path.is_file():
            py_files = [self.path] if self.py_extractor.can_handle(self.path) else []
            md_files = [self.path] if self.md_extractor.can_handle(self.path) else []
        else:
            py_files = list(self.path.rglob("*.py"))
            md_files = list(self.path.rglob("*.md"))

        # Filter out excluded directories
        exclude_dirs = {".git", "__pycache__", ".venv", "node_modules", ".tox", ".pytest_cache", ".mypy_cache"}
        py_files = [f for f in py_files if not any(part in exclude_dirs for part in f.parts)]
        md_files = [f for f in md_files if not any(part in exclude_dirs for part in f.parts)]

        # Extract from Python files
        for py_file in py_files:
            try:
                facts = self.py_extractor.extract(py_file)
                all_facts.extend(facts)
            except Exception as e:
                errors.append(f"Error reading {py_file}: {e}")

        # Extract from Markdown files
        for md_file in md_files:
            try:
                claims = self.md_extractor.extract(md_file)
                all_claims.extend(claims)
            except Exception as e:
                errors.append(f"Error reading {md_file}: {e}")

        # Match facts against claims
        drift_items = self.matcher.match(all_facts, all_claims)

        # Build and return report
        report = DriftReport(
            scanned_path=self.path,
            facts=all_facts,
            claims=all_claims,
            drift_items=drift_items,
            errors=errors,
        )
        return report
