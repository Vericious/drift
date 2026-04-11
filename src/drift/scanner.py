"""Scanner — orchestrates the full drift detection pipeline."""

import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from drift.extractors.config_file import ConfigFileExtractor
from drift.extractors.markdown import MarkdownExtractor
from drift.extractors.registry import get_extractors
from drift.matcher import SignatureMatcher
from drift.models import CodeFact, DocClaim, DriftReport, ScanMetrics

# JSDocExtractor imported lazily when include_js is True


def _extract_py_worker(
    py_file: Path,
    extractors_enabled: list[str] | None,
    extractors_disabled: list[str],
    strict: bool,
) -> tuple[list[CodeFact], list[DocClaim], list[str], Path]:
    """Module-level worker for ProcessPoolExecutor — extracts facts/claims from a Python file.

    This function lives at module level so it can be pickled by ProcessPoolExecutor.
    """
    from drift.extractors.registry import get_extractors

    facts: list[CodeFact] = []
    claims: list[DocClaim] = []
    errors: list[str] = []

    for extractor_cls in get_extractors():
        if not extractor_cls().can_handle(py_file):
            continue
        extractor = extractor_cls()
        ext_name = extractor_cls.__name__
        if extractors_disabled and ext_name in extractors_disabled:
            continue
        if extractors_enabled and ext_name not in extractors_enabled:
            continue
        try:
            extracted = extractor.extract(py_file)
        except Exception as e:
            err = f"[{extractor_cls.__name__}] {py_file}: {e}"
            if strict:
                raise
            errors.append(err)
            continue

        for item in extracted:
            if isinstance(item, DocClaim):
                claims.append(item)
            else:
                facts.append(item)

    return facts, claims, errors, py_file


class DriftScanner:
    """Walk files, dispatch to extractors, run matcher, produce report."""

    def __init__(
        self,
        path: Path,
        strict: bool = False,
        parallel: bool = False,
        jobs: int | None = None,
        include_js: bool = False,
        no_cache: bool = False,
        clear_cache: bool = False,
        changed_files: list[Path] | None = None,
        changed_lines: dict[Path, set[int]] | None = None,
        extractors_enabled: list[str] | None = None,
        extractors_disabled: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
    ) -> None:
        self.path = path
        self.strict = strict
        self.parallel = parallel
        self.jobs = jobs
        self.include_js = include_js
        # Parallel scans don't benefit from caching (all files are submitted at once anyway)
        # and caching would cause issues when serial+parallel are run on same path in tests
        self.no_cache = no_cache or parallel or (jobs is not None and jobs > 1)
        self.clear_cache = clear_cache
        self.changed_files = changed_files  # If set, only scan these files
        self.changed_lines = changed_lines  # If set, filter facts/claims to ±5 context window
        # Per-extractor enable/disable: None/[] = run all; list = only run these
        self._extractors_enabled = extractors_enabled
        self._extractors_disabled = extractors_disabled or []
        # Config ignore_patterns: fnmatch-style glob patterns from .drift.toml [scan] section
        self._config_ignore_patterns = ignore_patterns or []
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
        """Return True if the file matches any ignore pattern.

        Checks two sources:
        1. ignore_patterns from config (.drift.toml [scan] section) — fnmatch glob patterns
        2. .driftignore patterns — gitignore-style patterns with negation (!prefix)

        Uses gitignore-style matching where:
        - Patterns without a slash match only the filename
        - Patterns with a slash match relative to .driftignore location
        - ** matches any number of directories
        - dir/ matches a directory and all its contents
        - !prefix negates the match (only for .driftignore)
        """
        import fnmatch

        # Check config ignore_patterns first (fnmatch-style glob patterns)
        if self._config_ignore_patterns:
            rel_path = file_path
            try:
                rel_path = file_path.relative_to(self.path)
            except ValueError:
                pass
            path_str = str(rel_path)
            name_str = file_path.name

            for pattern in self._config_ignore_patterns:
                # Pattern with slash matches relative path
                if "/" in pattern:
                    if fnmatch.fnmatch(path_str, pattern):
                        return True
                # Pattern without slash matches filename only
                else:
                    if fnmatch.fnmatch(name_str, pattern):
                        return True

        # Check .driftignore patterns (gitignore-style)
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

    def _extract_py(
        self, py_file: Path
    ) -> tuple[list[CodeFact], list[DocClaim], list[str]]:
        """Extract facts and claims from a Python file using all registered extractors."""
        facts: list[CodeFact] = []
        claims: list[DocClaim] = []
        errors: list[str] = []

        # Registered extractors (PythonExtractor is now in the registry)
        for extractor_cls in get_extractors():
            # Skip extractors that don't claim to handle this file type
            extractor = extractor_cls()
            if not extractor.can_handle(py_file):
                continue
            # Per-extractor enable/disable filter
            ext_name = extractor_cls.__name__
            if self._extractors_disabled and ext_name in self._extractors_disabled:
                continue
            if self._extractors_enabled and ext_name not in self._extractors_enabled:
                continue
            try:
                extracted = extractor.extract(py_file)
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
            py_files = [self.path] if self.path.suffix.lower() == ".py" else []
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

        # Time each major phase
        t0 = time.perf_counter()

        # Extract — parallel when self.parallel is True
        if self.parallel:
            all_facts, all_claims, errors = self._parallel_scan(
                py_files, md_files, config_files, js_files
            )
        else:
            all_facts, all_claims, errors = self._serial_scan(
                py_files, md_files, config_files, js_files
            )

        t1 = time.perf_counter()
        extract_ms = (t1 - t0) * 1000

        # Filter to content-aware changed lines if --diff was used with changed_lines
        filter_ms = 0.0
        if self.changed_lines is not None:
            t_filter_start = time.perf_counter()
            all_facts, all_claims = self._filter_content_aware(
                all_facts, all_claims
            )
            filter_ms = (time.perf_counter() - t_filter_start) * 1000

        # Match facts against claims
        t_match_start = time.perf_counter()
        drift_items = self.matcher.match(all_facts, all_claims)
        match_ms = (time.perf_counter() - t_match_start) * 1000

        total_ms = (time.perf_counter() - t0) * 1000

        # Build and return report
        metrics = ScanMetrics(
            extract_ms=round(extract_ms, 2),
            match_ms=round(match_ms, 2),
            filter_ms=round(filter_ms, 2),
            total_ms=round(total_ms, 2),
        )
        report = DriftReport(
            scanned_path=self.path,
            facts=all_facts,
            claims=all_claims,
            drift_items=drift_items,
            errors=errors,
            files_skipped=self._files_skipped,
            metrics=metrics,
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

        for py_file in py_files:
            facts, claims, errs = self._extract_py(py_file)
            all_facts.extend(facts)
            all_claims.extend(claims)
            errors.extend(errs)

        for md_file in md_files:
            try:
                claims = self.md_extractor.extract(md_file)
                all_claims.extend(claims)
            except Exception as e:
                err = f"[MarkdownExtractor] {md_file}: {e}"
                if self.strict:
                    raise
                errors.append(err)

        for config_file in config_files:
            try:
                facts = self.config_extractor.extract(config_file)
                all_facts.extend(facts)
            except Exception as e:
                err = f"[ConfigFileExtractor] {config_file}: {e}"
                if self.strict:
                    raise
                errors.append(err)

        for js_file in js_files:
            if self.js_extractor:
                try:
                    claims = self.js_extractor.extract(js_file)
                    all_claims.extend(claims)
                except Exception as e:
                    err = f"[JSDocExtractor] {js_file}: {e}"
                    if self.strict:
                        raise
                    errors.append(err)

        return all_facts, all_claims, errors

    def _parallel_scan(
        self,
        py_files: list[Path],
        md_files: list[Path],
        config_files: list[Path],
        js_files: list[Path],
    ) -> tuple[list[CodeFact], list[DocClaim], list[str]]:
        """Extract facts/claims from all files in parallel using ProcessPoolExecutor.

        Uses ProcessPoolExecutor for Python files (CPU-bound extraction) and
        ThreadPoolExecutor for Markdown/config/JS files. Falls back to serial
        processing if parallel execution fails.
        """
        errors: list[str] = []
        all_facts: list[CodeFact] = []
        all_claims: list[DocClaim] = []

        # Determine worker count: use self.jobs if set, else cpu_count
        if self.jobs is not None and self.jobs > 1:
            max_workers = min(self.jobs, os.cpu_count() or 1)
        else:
            max_workers = os.cpu_count() or 1

        try:
            # ProcessPoolExecutor for Python files (can be CPU-intensive)
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                py_futures = {
                    executor.submit(
                        _extract_py_worker,
                        f,
                        self._extractors_enabled,
                        self._extractors_disabled,
                        self.strict,
                    ): f
                    for f in py_files
                }

                # ThreadPoolExecutor for Markdown/config/JS (I/O-bound, lightweight)
                thread_max_workers = min(32, (os.cpu_count() or 1) + 4)
                with ThreadPoolExecutor(max_workers=thread_max_workers) as thread_executor:
                    md_futures = {
                        thread_executor.submit(self._extract_md, f): f for f in md_files
                    }
                    cfg_futures = {
                        thread_executor.submit(self._extract_config, f): f
                        for f in config_files
                    }
                    js_futures = {
                        thread_executor.submit(self._extract_js, f): f for f in js_files
                    }

                    all_futures: dict[Any, Path] = {
                        **py_futures,
                        **md_futures,
                        **cfg_futures,
                        **js_futures,
                    }

                    for future in as_completed(all_futures):
                        file = all_futures[future]
                        try:
                            result = future.result()
                        except Exception as e:
                            err = f"[{file}] parallel extraction failed: {e}"
                            if self.strict:
                                raise
                            errors.append(err)
                            continue

                        if isinstance(result, tuple) and len(result) == 4:
                            # Python file result: (facts, claims, errors, file)
                            facts, claims, errs, _ = result
                            all_facts.extend(facts)
                            all_claims.extend(claims)
                            errors.extend(errs)
                        elif isinstance(result, list):
                            # Markdown or JS result: list of claims
                            all_claims.extend(result)
                        elif isinstance(result, tuple) and len(result) == 2:
                            # Config result: (facts, file)
                            cfg_facts, _ = result
                            all_facts.extend(cfg_facts)
                        else:
                            # Unexpected result
                            errors.append(
                                f"[{file}] unexpected result type from parallel extraction"
                            )

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
