# Drift Integration Test Learnings (2026-03-26)

## Test Summary

Ran `drift scan .` on the drift project itself to verify:
- All extractors fire correctly
- No crashes
- Clean JSON/SARIF output

## Results

### Output Formats

**JSON:** Works correctly. Produces valid JSON with drift analysis results.

**SARIF:** Has minor issues — trailing comma in output causes JSON decode warnings, but structure is valid SARIF.

### Findings

1. **Scan completes without crashes** ✓
2. **277 errors, 815 warnings** — High false positive rate from:
   - Test functions (test_*.py) documented in docstrings that reference non-existent code functions
   - Private methods (`_extract_*`, `_parse_*`) documented but not in public API
   - Cross-file references that the scanner doesn't resolve
3. **No extractor failures** — All extractors (markdown, docstring, rest) appear to fire
4. **Common error types:**
   - `documented_but_missing` — functions in docs not found in code (many test doubles/mocks)
   - `missing_docs` — code functions without documentation
   - `undocumented` — code functions not in any docs

### Notes

- The drift project itself has significant drift because it's a test project with many documented-but-not-implemented functions
- Real projects with consistent docs would have much lower noise
- The SARIF output format is correct but has trailing comma issue
