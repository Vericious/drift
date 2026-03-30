"""Tests for multi-path scanning."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.cli import main, _merge_reports
from drift.models import ClaimKind, CodeFact, DocClaim, DriftItem, DriftReport, FactKind, Parameter, Severity


@pytest.fixture
def cli_runner():
    """Return a Click CLI test runner."""
    return CliRunner()


def test_multiple_paths(cli_runner, tmp_path):
    """`drift scan path1 path2` scans both paths and merges results."""
    # Create two separate directories with different content
    dir1 = tmp_path / "project1"
    dir2 = tmp_path / "project2"
    dir1.mkdir()
    dir2.mkdir()

    (dir1 / "mod1.py").write_text(
        "def func_alpha():\n"
        "    '''Function alpha.'''\n"
        "    pass\n"
    )
    (dir2 / "mod2.py").write_text(
        "def func_beta():\n"
        "    '''Function beta.'''\n"
        "    pass\n"
    )

    result = cli_runner.invoke(main, ["scan", str(dir1), str(dir2)])
    assert result.exit_code == 0
    # Both functions should be found
    assert "func_alpha" in result.output or "2 facts" in result.output
    assert "func_beta" in result.output or "2 facts" in result.output


def test_no_path_defaults_cwd(cli_runner, tmp_path):
    """`drift scan` with no paths defaults to scanning current directory."""
    # Use a temp directory as cwd
    with cli_runner.isolated_filesystem(temp_dir=tmp_path):
        # Create a file with documented function
        (Path.cwd() / "sample.py").write_text(
            "def hello(name: str) -> str:\n"
            "    '''Say hello.'''\n"
            "    return f'Hello, {name}'\n"
        )
        result = cli_runner.invoke(main, ["scan"])
        assert result.exit_code == 0
        assert "1 fact" in result.output or "facts" in result.output


def test_overlapping_paths_dedup(cli_runner, tmp_path):
    """When paths overlap, drift items are deduplicated."""
    # Create dir with one function (no doc claim needed)
    shared = tmp_path / "shared"
    shared.mkdir()

    (shared / "mod.py").write_text(
        "def shared_func(x: int) -> int:\n"
        "    '''Shared function.'''\n"
        "    return x * 2\n"
    )

    # Scan the same directory twice via two paths (one parent, one explicit)
    # The scanner should deduplicate and still produce a clean result
    result = cli_runner.invoke(main, ["scan", str(shared), str(shared / "mod.py")])
    assert result.exit_code == 0
    # Should show 1 fact (not 2 from double-scanning)
    assert "1 fact" in result.output


# =============================================================================
# DRIFT-175: Multi-path deduplication tests for _merge_reports()
# =============================================================================


def _make_drift_item(
    category: str,
    fact_name: str = "func",
    claim_name: str = "func",
    fact_file: str = "src/code.py",
    claim_file: str = "docs/api.md",
    severity: Severity = Severity.ERROR,
) -> DriftItem:
    """Helper to create a DriftItem for deduplication testing."""
    fact = CodeFact(
        name=fact_name,
        kind=FactKind.FUNCTION,
        source_file=Path(fact_file),
        line_number=10,
        parameters=[],
    )
    claim = DocClaim(
        raw_text=f"def {claim_name}()",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=Path(claim_file),
        line_number=5,
        name=claim_name,
        parameters=[],
    )
    return DriftItem(
        fact=fact,
        claim=claim,
        severity=severity,
        category=category,
        message=f"{category}: {fact_name}",
    )


def test_no_duplicates_same_file_two_paths():
    """Same file scanned via two paths produces no duplicate drift items."""
    # Create two reports with the same drift item (same source file, fact name, claim name, category)
    item = _make_drift_item(
        category="undocumented",
        fact_name="my_func",
        claim_name="my_func",
        fact_file="src/my_func.py",
    )

    report1 = DriftReport(scanned_path=Path("project1"), drift_items=[item])
    report2 = DriftReport(scanned_path=Path("project2"), drift_items=[item])

    merged = _merge_reports([report1, report2])

    # Should have only 1 drift item (deduplicated), not 2
    assert len(merged.drift_items) == 1
    assert merged.drift_items[0].fact.name == "my_func"


def test_no_duplicates_ts_and_md_overlap():
    """Same item documented in both .ts and .md files is deduplicated."""
    # Two reports with same item but different doc sources
    # (TypeScript interface and Markdown both document the same function)
    item = _make_drift_item(
        category="documented_but_missing",
        fact_name="UserService",
        claim_name="UserService",
        fact_file="src/user_service.ts",
        claim_file="docs/user_service.md",
    )

    report_ts = DriftReport(
        scanned_path=Path("src"),
        drift_items=[
            _make_drift_item(
                category="documented_but_missing",
                fact_name="UserService",
                claim_name="UserService",
                fact_file="src/user_service.ts",
                claim_file="src/user_service.ts",  # TS doc claim
            )
        ],
    )
    report_md = DriftReport(
        scanned_path=Path("docs"),
        drift_items=[
            _make_drift_item(
                category="documented_but_missing",
                fact_name="UserService",
                claim_name="UserService",
                fact_file="src/user_service.ts",
                claim_file="docs/user_service.md",  # MD doc claim
            )
        ],
    )

    merged = _merge_reports([report_ts, report_md])

    # Both have the same (source_file, fact.name, claim.name, category) key
    # Should be deduplicated to 1 item
    assert len(merged.drift_items) == 1


def test_merge_preserves_unique_items():
    """Items with different (source_file, fact.name, claim.name, category) are preserved."""
    item1 = _make_drift_item(
        category="undocumented",
        fact_name="func_a",
        claim_name="func_a",
        fact_file="src/a.py",
    )
    item2 = _make_drift_item(
        category="fuzzy_renamed",
        fact_name="old_b",
        claim_name="new_b",  # Different claim name
        fact_file="src/b.py",
    )
    item3 = _make_drift_item(
        category="undocumented",
        fact_name="func_c",
        claim_name="func_c",
        fact_file="src/c.py",
    )

    report1 = DriftReport(scanned_path=Path("proj1"), drift_items=[item1])
    report2 = DriftReport(scanned_path=Path("proj2"), drift_items=[item2, item3])

    merged = _merge_reports([report1, report2])

    # All 3 unique items should be preserved
    assert len(merged.drift_items) == 3
    names = {item.fact.name for item in merged.drift_items}
    assert names == {"func_a", "old_b", "func_c"}
