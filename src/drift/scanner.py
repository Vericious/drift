"""Scanner — orchestrates the full drift detection pipeline."""
from pathlib import Path

from drift.models import CodeFact, DocClaim, DriftReport
from drift.python_extractor import PythonExtractor
from drift.extractors.markdown import MarkdownExtractor
from drift.extractors.registry import get_extractors
from drift.matcher import SignatureMatcher


class DriftScanner:
    """Walk files, dispatch to extractors, run matcher, produce report."""

    def __init__(self, path: Path, strict: bool = False) -> None:
        self.path = path
        self.strict = strict
        self.py_extractor = PythonExtractor()
        self.md_extractor = MarkdownExtractor()
        self.matcher = SignatureMatcher()
        self._ignore_patterns: list[str] = []
        self._load_driftignore()

    def _load_driftignore(self) -> None:
        """Load .driftignore patterns from the scanned path."""
        driftignore_path = self.path / ".driftignore" if self.path.is_dir() else self.path.parent / ".driftignore"
        if driftignore_path.exists():
            try:
                self._ignore_patterns = [
                    line.strip()
                    for line in driftignore_path.read_text().splitlines()
                    if line.strip() and not line.startswith("#")
                ]
            except Exception:
                self._ignore_patterns = []

    def _is_ignored(self, file_path: Path) -> bool:
        """Return True if the file matches any .driftignore pattern."""
        import fnmatch
        for pattern in self._ignore_patterns:
            if fnmatch.fnmatch(str(file_path), pattern) or fnmatch.fnmatch(file_path.name, pattern):
                return True
        return False

    def _extract_py(self, py_file: Path) -> tuple[list[CodeFact], list[DocClaim]]:
        """Extract facts and claims from a Python file using all registered extractors."""
        facts: list[CodeFact] = []
        claims: list[DocClaim] = []
        errors: list[str] = []

        # Python function/method extractor (not in registry)
        try:
            facts.extend(self.py_extractor.extract(py_file))
        except Exception as e:
            err = f"[PythonExtractor] {py_file}: {e}"
            if self.strict:
                raise
            errors.append(err)

        # Registered extractors
        for extractor_cls in get_extractors():
            try:
                extracted = extractor_cls().extract(py_file)
            except Exception as e:
                err = f"[{extractor_cls.__name__}] {py_file}: {e}"
                if self.strict:
                    raise
                errors.append(err)
                continue

            # Separate CodeFacts from DocClaims
            for item in extracted:
                if isinstance(item, DocClaim):
                    claims.append(item)
                else:
                    facts.append(item)

        return facts, claims, errors

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

        # Filter out ignored files
        py_files = [f for f in py_files if not self._is_ignored(f)]
        md_files = [f for f in md_files if not self._is_ignored(f)]

        # Extract from Python files
        for py_file in py_files:
            facts, claims, errs = self._extract_py(py_file)
            all_facts.extend(facts)
            all_claims.extend(claims)
            errors.extend(errs)

        # Extract from Markdown files
        for md_file in md_files:
            try:
                claims = self.md_extractor.extract(md_file)
                all_claims.extend(claims)
            except Exception as e:
                err = f"[MarkdownExtractor] {md_file}: {e}"
                if self.strict:
                    raise
                errors.append(err)

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
