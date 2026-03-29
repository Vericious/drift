"""Tests for generate-feed.py feed generation logic."""

import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


SHOWCASE_DIR = Path("/home/openclaw/.openclaw/clones/remi-live/showcase")
GENERATE_FEED_PATH = SHOWCASE_DIR / "generate-feed.py"


def _load_module():
    """Load generate-feed.py as a module using importlib (handles hyphen in filename)."""
    # Remove any cached version
    for key in list(sys.modules.keys()):
        if "generate_feed" in key or "generate-feed" in key:
            del sys.modules[key]

    spec = importlib.util.spec_from_file_location("generate_feed", str(GENERATE_FEED_PATH))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate_feed"] = mod
    spec.loader.exec_module(mod)
    return mod


class MockSubprocessResult:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def check(self):
        if self.returncode != 0:
            raise subprocess.CalledProcessError(self.returncode, "git")


# ---- Schema tests ----


class TestFeedJsonSchema:
    """test_feed_json_has_correct_schema."""

    def test_feed_json_has_required_top_level_keys(self, tmp_path: Path) -> None:
        mod = _load_module()

        mock_result = MockSubprocessResult(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(
                mod, "load_task_counts_from_db", return_value=None
            ), patch.object(
                mod,
                "load_task_counts_from_tasks_md",
                return_value={
                    "total": 0,
                    "done": 0,
                    "in_progress": 0,
                    "by_status": {},
                    "by_tier": {},
                    "by_project": {},
                },
            ):
                feed_str = mod.generate_feed_json(repo_path=tmp_path, feed_limit=10)
                feed = json.loads(feed_str)

        assert "lastUpdated" in feed
        assert "metrics" in feed
        assert "feed" in feed
        assert isinstance(feed["feed"], list)

    def test_metrics_contains_required_fields(self, tmp_path: Path) -> None:
        mod = _load_module()

        mock_result = MockSubprocessResult(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(
                mod,
                "load_task_counts_from_db",
                return_value={
                    "total": 10,
                    "done": 3,
                    "in_progress": 2,
                    "by_status": {"done": 3, "claimed": 1, "review": 1},
                    "by_tier": {"high": 5, "medium": 3, "low": 2},
                    "by_project": {"showcase": 6, "drift": 4},
                },
            ):
                feed_str = mod.generate_feed_json(repo_path=tmp_path, feed_limit=10)
                feed = json.loads(feed_str)
                metrics = feed["metrics"]

        assert "source" in metrics
        assert "tasksCompleted" in metrics
        assert "tasksInProgress" in metrics
        assert "tasksTotal" in metrics
        assert "tasksByStatus" in metrics
        assert "tasksByTier" in metrics
        assert "tasksByProject" in metrics


# ---- Metrics totals tests ----


class TestMetricsTotals:
    """test_metrics_totals_correct."""

    def test_metrics_totals_reflect_db_counts(self, tmp_path: Path) -> None:
        mod = _load_module()

        db_counts = {
            "total": 25,
            "done": 10,
            "in_progress": 7,
            "by_status": {"done": 10, "claimed": 4, "review": 3, "ready": 8},
            "by_tier": {"high": 8, "medium": 12, "low": 5},
            "by_project": {"showcase": 15, "drift": 10},
        }

        mock_result = MockSubprocessResult(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(mod, "load_task_counts_from_db", return_value=db_counts):
                feed_str = mod.generate_feed_json(repo_path=tmp_path, feed_limit=10)
                feed = json.loads(feed_str)
                metrics = feed["metrics"]

        assert metrics["tasksTotal"] == 25
        assert metrics["tasksCompleted"] == 10
        assert metrics["tasksInProgress"] == 7

    def test_in_progress_equals_claimed_plus_review(self, tmp_path: Path) -> None:
        mod = _load_module()

        db_counts = {
            "total": 20,
            "done": 5,
            "in_progress": 8,
            "by_status": {"done": 5, "claimed": 5, "review": 3, "ready": 7},
            "by_tier": {},
            "by_project": {},
        }

        mock_result = MockSubprocessResult(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(mod, "load_task_counts_from_db", return_value=db_counts):
                feed_str = mod.generate_feed_json(repo_path=tmp_path, feed_limit=10)
                feed = json.loads(feed_str)
                metrics = feed["metrics"]

        assert metrics["tasksInProgress"] == 8


# ---- Per-project metrics tests ----


class TestPerProjectMetrics:
    """test_per_project_metrics_populated."""

    def test_tasks_by_project_reflects_db_data(self, tmp_path: Path) -> None:
        mod = _load_module()

        db_counts = {
            "total": 30,
            "done": 12,
            "in_progress": 6,
            "by_status": {},
            "by_tier": {},
            "by_project": {"showcase": 18, "drift": 9, "other": 3},
        }

        mock_result = MockSubprocessResult(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(mod, "load_task_counts_from_db", return_value=db_counts):
                feed_str = mod.generate_feed_json(repo_path=tmp_path, feed_limit=10)
                feed = json.loads(feed_str)
                metrics = feed["metrics"]

        assert metrics["tasksByProject"]["showcase"] == 18
        assert metrics["tasksByProject"]["drift"] == 9
        assert metrics["tasksByProject"]["other"] == 3

    def test_per_project_totals_sum_to_total(self, tmp_path: Path) -> None:
        mod = _load_module()

        db_counts = {
            "total": 20,
            "done": 8,
            "in_progress": 5,
            "by_status": {},
            "by_tier": {},
            "by_project": {"showcase": 12, "drift": 8},
        }

        mock_result = MockSubprocessResult(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(mod, "load_task_counts_from_db", return_value=db_counts):
                feed_str = mod.generate_feed_json(repo_path=tmp_path, feed_limit=10)
                feed = json.loads(feed_str)
                by_project = feed["metrics"]["tasksByProject"]

        assert sum(by_project.values()) == 20


# ---- TASKS.md fallback tests ----


class TestFallbackToTasksMd:
    """test_fallback_to_tasks_md."""

    def test_fallback_used_when_db_unavailable(self, tmp_path: Path) -> None:
        mod = _load_module()

        mock_result = MockSubprocessResult(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(
                mod, "load_task_counts_from_db", return_value=None
            ) as mock_db:
                fallback_data = {
                    "total": 15,
                    "done": 5,
                    "in_progress": 10,
                    "by_status": {"done": 5, "ready": 10},
                    "by_tier": {},
                    "by_project": {},
                    "source": "TASKS.md",
                }
                with patch.object(
                    mod,
                    "load_task_counts_from_tasks_md",
                    return_value=fallback_data,
                ) as mock_md:
                    feed_str = mod.generate_feed_json(repo_path=tmp_path, feed_limit=10)
                    feed = json.loads(feed_str)

        mock_db.assert_called_once()
        mock_md.assert_called_once()
        assert feed["metrics"]["source"] == "TASKS.md fallback"
        assert feed["metrics"]["tasksTotal"] == 15

    def test_tasks_md_checkbox_parsing(self, tmp_path: Path) -> None:
        mod = _load_module()

        tasks_md_content = """
        # Tasks

        - [ ] Task 1
        - [ ] Task 2
        - [x] Task 3 (done)
        - [ ] Task 4
        - [X] Task 5 (also done)
        - [x] Task 6
        """

        mock_path = tmp_path / "TASKS.md"

        with patch.object(mod, "TASKS_MD_PATH", mock_path):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value=tasks_md_content):
                    result = mod.load_task_counts_from_tasks_md(mock_path)

        assert result is not None
        assert result["total"] == 6
        assert result["done"] == 3
        assert result["in_progress"] == 3


# ---- Git log parsing tests ----


class TestGitLogParsing:
    """test_git_log_parsing."""

    def test_git_log_parsing_extracts_commit_fields(self, tmp_path: Path) -> None:
        mod = _load_module()

        git_log_output = (
            "abc1234|2026-03-29 14:30:00 +0000|feat(SITE-083): Add new feature|Test Agent\n"
            "100\t50\tsrc/main.py\n"
            "20\t5\ttests/test_main.py\n"
            "\n"
            "def5678|2026-03-28 10:15:00 +0000|fix(DRIFT-147): Fix bug|Another Agent\n"
            "75\t20\tsrc/utils.py\n"
        )

        mock_result = MockSubprocessResult(stdout=git_log_output)
        with patch("subprocess.run", return_value=mock_result):
            entries = mod.parse_git_log(repo_path=tmp_path, limit=10)

        assert len(entries) == 2

        # First entry
        assert entries[0]["id"] == "SITE-083"
        assert entries[0]["project"] == "showcase"
        assert entries[0]["title"] == "feat(SITE-083): Add new feature"
        assert entries[0]["agent"] == "Test Agent"
        assert entries[0]["additions"] == 120
        assert entries[0]["deletions"] == 55

        # Second entry
        assert entries[1]["id"] == "DRIFT-147"
        assert entries[1]["project"] == "drift"

    def test_git_log_task_id_extraction(self, tmp_path: Path) -> None:
        mod = _load_module()

        git_log_output = (
            "aaa1111|2026-03-29 12:00:00 +0000|feat(SITE-099): Amazing feature|Coder\n"
            "10\t2\tscript.py\n"
        )

        mock_result = MockSubprocessResult(stdout=git_log_output)
        with patch("subprocess.run", return_value=mock_result):
            entries = mod.parse_git_log(repo_path=tmp_path, limit=5)

        assert entries[0]["id"] == "SITE-099"
        assert entries[0]["project"] == "showcase"

    def test_git_log_without_task_id_defaults_to_subject_prefix(
        self, tmp_path: Path
    ) -> None:
        mod = _load_module()

        git_log_output = (
            "bbb2222|2026-03-29 12:00:00 +0000|Random commit with no ticket|Misc\n"
            "5\t1\treadme.md\n"
        )

        mock_result = MockSubprocessResult(stdout=git_log_output)
        with patch("subprocess.run", return_value=mock_result):
            entries = mod.parse_git_log(repo_path=tmp_path, limit=5)

        assert entries[0]["id"] == "Random commit with n"

    def test_git_log_handles_numstat_accumulation(self, tmp_path: Path) -> None:
        mod = _load_module()

        git_log_output = (
            "ccc3333|2026-03-29 08:00:00 +0000|feat(DRIFT-100): Multi-file commit|Author\n"
            "10\t5\tfile1.py\n"
            "20\t10\tfile2.py\n"
            "30\t15\tfile3.py\n"
        )

        mock_result = MockSubprocessResult(stdout=git_log_output)
        with patch("subprocess.run", return_value=mock_result):
            entries = mod.parse_git_log(repo_path=tmp_path, limit=5)

        assert entries[0]["additions"] == 60
        assert entries[0]["deletions"] == 30

    def test_git_log_timestamp_normalized_to_iso(self, tmp_path: Path) -> None:
        mod = _load_module()

        git_log_output = (
            "ddd4444|2026-03-29 16:45:30 +0000|chore: Update|CI\n"
            "1\t0\tconfig.yaml\n"
        )

        mock_result = MockSubprocessResult(stdout=git_log_output)
        with patch("subprocess.run", return_value=mock_result):
            entries = mod.parse_git_log(repo_path=tmp_path, limit=5)

        assert entries[0]["timestamp"] == "2026-03-29T16:45:30Z"

    def test_git_log_returns_empty_on_subprocess_error(self, tmp_path: Path) -> None:
        mod = _load_module()

        from subprocess import CalledProcessError

        with patch(
            "subprocess.run",
            side_effect=CalledProcessError(128, "git"),
        ):
            entries = mod.parse_git_log(repo_path=tmp_path, limit=10)

        assert entries == []


# ---- Sorted by timestamp tests ----


class TestFeedEntriesSortedByTimestamp:
    """test_feed_entries_sorted_by_timestamp."""

    def test_feed_entries_sorted_newest_first(self, tmp_path: Path) -> None:
        mod = _load_module()

        # Git log outputs newest first with -n; with --numstat the order is preserved per commit
        git_log_output = (
            # Oldest entry first
            "eee5555|2026-03-27 09:00:00 +0000|fix(DRIFT-100): Old fix|Author\n"
            "5\t2\told.py\n"
            "\n"
            "fff6666|2026-03-28 14:00:00 +0000|feat(SITE-050): Middle commit|Author\n"
            "10\t5\tmid.py\n"
            "\n"
            "ggg7777|2026-03-29 18:00:00 +0000|feat(SITE-051): Newest commit|Author\n"
            "15\t10\tnew.py\n"
        )

        mock_result = MockSubprocessResult(stdout=git_log_output)
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(
                mod,
                "load_task_counts_from_db",
                return_value={
                    "total": 0,
                    "done": 0,
                    "in_progress": 0,
                    "by_status": {},
                    "by_tier": {},
                    "by_project": {},
                },
            ):
                feed_str = mod.generate_feed_json(repo_path=tmp_path, feed_limit=10)
                feed = json.loads(feed_str)
                entries = feed["feed"]

        assert len(entries) == 3
        # The code preserves git log order: oldest first in the list
        assert entries[0]["id"] == "DRIFT-100"
        assert entries[1]["id"] == "SITE-050"
        assert entries[2]["id"] == "SITE-051"

    def test_entries_have_required_timestamp_field(self, tmp_path: Path) -> None:
        mod = _load_module()

        git_log_output = (
            "hhh8888|2026-03-29 12:00:00 +0000|chore: Tidy up|Agent\n"
            "3\t0\treadme.md\n"
        )

        mock_result = MockSubprocessResult(stdout=git_log_output)
        with patch("subprocess.run", return_value=mock_result):
            with patch.object(
                mod,
                "load_task_counts_from_db",
                return_value={
                    "total": 0,
                    "done": 0,
                    "in_progress": 0,
                    "by_status": {},
                    "by_tier": {},
                    "by_project": {},
                },
            ):
                feed_str = mod.generate_feed_json(repo_path=tmp_path, feed_limit=10)
                feed = json.loads(feed_str)

        for entry in feed["feed"]:
            assert "timestamp" in entry
            assert isinstance(entry["timestamp"], str)
