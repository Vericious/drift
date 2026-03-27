"""Git utilities for drift scanning."""

import subprocess
from pathlib import Path


def get_changed_files(ref: str, path: Path) -> list[Path] | None:
    """Get list of files changed between ref and current HEAD.

    Returns None if:
    - Not in a git repo
    - ref is invalid or doesn't exist
    - git command fails for any reason
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", ref, "--"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None

        files = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                files.append(Path(line))
        return files
    except (subprocess.TimeoutExpired, OSError):
        return None


def is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, OSError):
        return False


def ref_exists(ref: str, path: Path) -> bool:
    """Check if a git ref (branch, tag, commit) exists."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False
