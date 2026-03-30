"""Scanner — orchestrates the full drift detection pipeline."""

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from drift.extractors.config_file import ConfigFileExtractor
from drift.extractors.markdown import MarkdownExtractor
from drift.extractors.registry import get_extractors
from drift.matcher import SignatureMatcher
from drift.models import CodeFact, DocClaim, DriftReport
from drift.python_extractor import PythonExtractor

# JSDocExtractor imported lazily when include_js is True


class DriftScanner:
    """Walk files, dispatch to extractors, run matcher, produce report."""

    def __init__(
        self,
        path: Path,
        strict: bool = False,
        parallel: bool = False,
        include_js: bool = False,
        no_cache: bool = False,
        clear_cache: bool = False,
        changed_files: list[Path] | None = None,
        changed_lines: dict[Path, set[int]] | None = None,
        extractors_enabled: list[str] | None = None,
        extractors_disabled: list[str] | None = None,
    ) -> None:
        self.path = path
        self.strict = strict
        self.parallel = parallel
        self.include_js = include_js
        # Parallel scans don't benefit from caching (all files are submitted at once anyway)
        # and caching would cause issues when serial+parallel are run on same path in tests
        self.no_cache = no_cache or parallel
        self.clear_cache = clear_cache
        self.changed_files = changed_files  # If set, only scan these files
        self.changed_lines = changed_lines  # If set, filter facts/claims to ±5 context window
        # Per-extractor enable/disable: None/[] = run all; list = only run these
        self._extractors_enabled = extractors_enabled
        self._extractors_disabled = extractors_disabled or []
        self.py_extractor = PythonExtractor()
        self.md_extractor = MarkdownExtractor()
        self.config_extractor = ConfigFileExtractor()
        self.js_extractor: JSDocExtractor | None = None
        self.matcher = SignatureMatcher()
        self._ignore_patterns: list[tuple[str, bool]] = []
        self._files_skipped: int = 0
        self._load_driftignore()
        if include_js:
            from drift.extractor_js import JSDocExtractor
            self.js_extractor = JSDocExtractor()
        # Cache setup
        self._cache_path = self.path / ".drift" / "cache.json" if self.path.is_dir() else self.path.parent / ".drift" / "cache.json"
        self._file_cache: dict[str, str] = {}
        if not self.no_cache:
            self._load_cache()

    def _load_driftignore(self) -> None:
        """Load .driftignore patterns from the scanned path.

        Patterns are processed in order; later rules override earlier ones.
        Supports:
          - Basic glob patterns (*, ?, etc.)
          - Negation with ! prefix
          - **/ for recursive directory matching (matches any depth)
          - dir/ for directory-only matching (matches the directory and its contents)
          - Lines starting with # are comments
          - Empty lines are skipped
        """
        driftignore_path = (
            self.path / ".driftignore"
            if self.path.is_dir()
            else self.path.parent / ".driftignore"
        )
        if driftignore_path.exists():
            try:
                lines = driftignore_path.read_text().splitlines()
                parsed_patterns: list[tuple[str, bool]] = []  # (pattern, is_negation)
                for line in lines:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    is_negation = stripped.startswith("!")
                    if is_negation:
                        stripped = stripped[1:]
                    parsed_patterns.append((stripped, is_negation))
                # Store as list of tuples: (pattern, is_negation)
                self._ignore_patterns = parsed_patterns
            except Exception:
                self._ignore_patterns = []

    def _is_ignored(self, file_path: Path) -> bool:
        """Return True if the file matches any .driftignore pattern.

        Uses gitignore-style matching where:
        - Patterns without a slash match only the filename
        - Patterns with a slash match relative to .driftignore location
        - ** matches any number of directories
        - dir/ matches a directory and all its contents
        - !prefix negates the match
        """
        from pathlib import PurePath

        rel_path = file_path

        # Try relative to scanned path
        try:
            rel_path = file_path.relative_to(self.path)
        except ValueError:
            pass

        path_str = str(rel_path)
        name_str = file_path.name
        parts = PurePath(path_str).parts

        ignored: bool = False

        for pattern, is_negation in self._ignore_patterns:
            matched = False

            # Directory-only pattern: dir/ matches dir and everything inside
            if pattern.endswith("/"):
                dir_name = pattern.rstrip("/")
                # Check if any parent directory matches
                for i, part in enumerate(parts[:-1]):
                    parent_path = "/".join(parts[: i + 1])
                    if self._match_pattern(parent_path, dir_name):
                        matched = True
                        break
                    if self._match_pattern(part, dir_name):
                        matched = True
                        break
                # Also check if the file is directly in the directory
                if not matched and len(parts) > 1:
                    if self._match_pattern(parts[-2], dir_name):
                        matched = True
            # Patterns with ** - PurePath.match() handles these
            elif "**" in pattern:
                matched = self._match_pattern(path_str, pattern) or self._match_pattern(
                    name_str, pattern
                )
            # Patterns with a slash - match against the relative path
            elif "/" in pattern:
                matched = self._match_pattern(path_str, pattern)
            # Pattern without slash - match only against the filename
            else:
                matched = self._match_pattern(name_str, pattern)

            if matched:
                ignored = not is_negation

        return ignored

    def _match_pattern(self, text: str, pattern: str) -> bool:
        """Match text against a pattern using pathlib.PurePath.match()."""
        from pathlib import PurePath

        try:
            return PurePath(text).match(pattern)
        except ValueError:
            return False

    def _load_cache(self) -> None:
        """Load the file hash cache from .drift/cache.json."""
        if self.clear_cache:
            self._file_cache = {}
            return
        try:
            if self._cache_path.exists():
                self._file_cache = json.loads(self._cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            self._file_cache = {}

    def _save_cache(self) -> None:
        """Save the current file hash cache to .drift/cache.json."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._file_cache, indent=2))
        except OSError:
            pass  # Non-fatal if we can't write the cache

    def _file_hash(self, file_path: Path) -> str:
        """Compute a hash for a file based on mtime+size, with content hash fallback.

        Uses mtime:size as the primary hash. On mtime/size collision (same mtime and size
        but different content), falls back to MD5 of file content for verification.
        """
        try:
            stat = file_path.stat()
            key = f"{stat.st_mtime:.6f}:{stat.st_size}"
            return key
        except OSError:
            return ""

    def _is_unchanged(self, file_path: Path) -> bool:
        """Return True if file has not changed since last scan (based on cache)."""
        file_str = str(file_path)
        cached = self._file_cache.get(file_str)
        if cached is None:
            return False
        current_hash = self._file_hash(file_path)
        return cached == current_hash

    def _mark_cached(self, file_path: Path) -> None:
        """Record the current hash for a file in the cache."""
        self._file_cache[str(file_path)] = self._file_hash(file_path)

    def _filter_cached(self, files: list[Path]) -> list[Path]:
        """Return only files that are not in the cache or have changed.

        Accumulates skipped count across all file types.
        """
        if self.no_cache:
            # When no_cache, record hashes for all files but don't skip any
            for f in files:
                self._mark_cached(f)
            return files

        unchanged: list[Path] = []
        changed: list[Path] = []
        for f in files:
            if self._is_unchanged(f):
                unchanged.append(f)
            else:
                changed.append(f)
        self._files_skipped += len(unchanged)
        for f in changed:
            self._mark_cached(f)
        return changed

    def _filter_content_aware(
        self,
        facts: list[CodeFact],
        claims: list[DocClaim],
    ) -> tuple[list[CodeFact], list[DocClaim]]:
        """Filter facts/claims to those within ±5 lines of any changed line.

        This prevents noise from unchanged functions in large files when using
        content-aware diff scanning.
        """
        CONTEXT_WINDOW = 5
        filtered_facts: list[CodeFact] = []
        filtered_claims: list[DocClaim] = []

        for fact in facts:
            changed_lines_for_file = self.changed_lines.get(fact.source_file.resolve(), set())
            # Check if fact.line_number is within ±CONTEXT_WINDOW of any changed line
            if any(
                abs(fact.line_number - cl) <= CONTEXT_WINDOW
                for cl in changed_lines_for_file
            ):
                filtered_facts.append(fact)

        for claim in claims:
            changed_lines_for_file = self.changed_lines.get(claim.doc_file.resolve(), set())
            # Check if claim.line_number is within ±CONTEXT_WINDOW of any changed line
            if any(
                abs(claim.line_number - cl) <= CONTEXT_WINDOW
                for cl in changed_lines_for_file
            ):
                filtered_claims.append(claim)

        return filtered_facts, filtered_claims

    def _extract_registered(
        self, file: Path
    ) -> tuple[list[CodeFact], list[DocClaim], list[str]]:
        """Extract facts and claims from a file by routing through the registry.

        Iterates all registered extractors, checks can_handle(file), and dispatches
        to matching extractors. Handles ALL file types via registry dispatch.
        """
        facts: list[CodeFact] = []
        claims: list[DocClaim] = []
        errors: list[str] = []

        for extractor_cls in get_extractors():
            # Per-extractor enable/disable filter
            ext_name = extractor_cls.__name__
            if self._extractors_disabled and ext_name in self._extractors_disabled:
                continue
            if self._extractors_enabled and ext_name not in self._extractors_enabled:
                continue
            try:
                extractor = extractor_cls()
            except Exception as e:
                err = f"[{ext_name}] instantiation failed: {e}"
                if self.strict:
                    raise
                errors.append(err)
                continue
            if not extractor.can_handle(file):
                continue
            try:
                extracted = extractor.extract(file)
            except Exception as e:
                err = f"[{ext_name}] {file}: {e}"
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
            config_files = (
                [self.path] if self.config_extractor.can_handle(self.path) else []
            )
            js_files: list[Path] = (
                [self.path] if self.include_js and self.js_extractor and self.js_extractor.can_handle(self.path) else []
            )
        else:
            py_files = list(self.path.rglob("*.py"))
            md_files = list(self.path.rglob("*.md"))
            config_files = (
                list(self.path.rglob("*.yaml"))
                + list(self.path.rglob("*.yml"))
                + list(self.path.rglob("*.toml"))
            )
            if self.include_js and self.js_extractor:
                js_files = [
                    f for f in list(self.path.rglob("*.js"))
                    + list(self.path.rglob("*.ts"))
                    + list(self.path.rglob("*.jsx"))
                    + list(self.path.rglob("*.tsx"))
                    if self.js_extractor.can_handle(f)
                ]
            else:
                js_files = []

        # Filter out excluded directories
        exclude_dirs = {
            ".git",
            "__pycache__",
            ".venv",
            "node_modules",
            ".tox",
            ".pytest_cache",
            ".mypy_cache",
        }
        py_files = [
            f for f in py_files if not any(part in exclude_dirs for part in f.parts)
        ]
        md_files = [
            f for f in md_files if not any(part in exclude_dirs for part in f.parts)
        ]
        config_files = [
            f for f in config_files if not any(part in exclude_dirs for part in f.parts)
        ]
        if self.include_js:
            js_files = [
                f for f in js_files if not any(part in exclude_dirs for part in f.parts)
            ]
        else:
            js_files = []

        # Filter out ignored files
        py_files = [f for f in py_files if not self._is_ignored(f)]
        md_files = [f for f in md_files if not self._is_ignored(f)]
        config_files = [f for f in config_files if not self._is_ignored(f)]
        js_files = [f for f in js_files if not self._is_ignored(f)]

        # Filter to only changed files if --diff was specified
        if self.changed_files is not None:
            changed_set = {f.resolve() for f in self.changed_files}
            py_files = [f for f in py_files if f.resolve() in changed_set]
            md_files = [f for f in md_files if f.resolve() in changed_set]
            config_files = [f for f in config_files if f.resolve() in changed_set]
            js_files = [f for f in js_files if f.resolve() in changed_set]

        # Filter via file hash cache — skip unchanged files
        py_files = self._filter_cached(py_files)
        md_files = self._filter_cached(md_files)
        config_files = self._filter_cached(config_files)
        js_files = self._filter_cached(js_files)

        # Extract — parallel when self.parallel is True
        if self.parallel:
            all_facts, all_claims, errors = self._parallel_scan(
                py_files, md_files, config_files, js_files
            )
        else:
            all_facts, all_claims, errors = self._serial_scan(
                py_files, md_files, config_files, js_files
            )

        # Filter to content-aware changed lines if --diff was used with changed_lines
        if self.changed_lines is not None:
            all_facts, all_claims = self._filter_content_aware(
                all_facts, all_claims
            )

        # Match facts against claims
        drift_items = self.matcher.match(all_facts, all_claims)

        # Build and return report
        report = DriftReport(
            scanned_path=self.path,
            facts=all_facts,
            claims=all_claims,
            drift_items=drift_items,
            errors=errors,
            files_skipped=self._files_skipped,
        )
        # Save cache after successful scan
        if not self.no_cache:
            self._save_cache()
        return report

    def _serial_scan(
        self,
        py_files: list[Path],
        md_files: list[Path],
        config_files: list[Path],
        js_files: list[Path],
    ) -> tuple[list[CodeFact], list[DocClaim], list[str]]:
        """Extract facts/claims from all files serially. Used when parallel=False."""
        errors: list[str] = []
        all_facts: list[CodeFact] = []
        all_claims: list[DocClaim] = []

        for file in py_files + md_files + config_files + js_files:
            facts, claims, errs = self._extract_registered(file)
            all_facts.extend(facts)
            all_claims.extend(claims)
            errors.extend(errs)

        return all_facts, all_claims, errors

    def _parallel_scan(
        self,
        py_files: list[Path],
        md_files: list[Path],
        config_files: list[Path],
        js_files: list[Path],
    ) -> tuple[list[CodeFact], list[DocClaim], list[str]]:
        """Extract facts/claims from all files in parallel using ThreadPoolExecutor.

        Falls back to serial processing if parallel execution fails.
        Results are deterministic regardless of thread scheduling (content-wise).
        """
        errors: list[str] = []
        all_facts: list[CodeFact] = []
        all_claims: list[DocClaim] = []

        max_workers = min(32, (os.cpu_count() or 1) + 4)

        def extract_registered(
            file: Path,
        ) -> tuple[list[CodeFact], list[DocClaim], list[str], Path]:
            """Wrapper to make _extract_registered callable in a thread."""
            facts, claims, errs = self._extract_registered(file)
            return facts, claims, errs, file

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                all_files = py_files + md_files + config_files + js_files
                futures = {executor.submit(extract_registered, f): f for f in all_files}

                for future in as_completed(futures):
                    file = futures[future]
                    try:
                        facts, claims, errs, _ = future.result()
                        all_facts.extend(facts)
                        all_claims.extend(claims)
                        errors.extend(errs)
                    except Exception as e:
                        err = f"[{file}] parallel extraction failed: {e}"
                        if self.strict:
                            raise
                        errors.append(err)

        except Exception:
            # Fallback to serial on any parallel failure
            return self._serial_scan(py_files, md_files, config_files, js_files)

        return all_facts, all_claims, errors

    def _extract_md(self, path: Path) -> list[DocClaim]:
        """Extract claims from a Markdown file (thread-safe wrapper)."""
        return self.md_extractor.extract(path)

    def _extract_config(self, path: Path) -> tuple[list[CodeFact], Path]:
        """Extract facts from a config file (thread-safe wrapper)."""
        facts = self.config_extractor.extract(path)
        return facts, path

    def _extract_js(self, path: Path) -> list[DocClaim]:
        """Extract claims from a JS/TS file (thread-safe wrapper)."""
        if self.js_extractor:
            return self.js_extractor.extract(path)
        return []
