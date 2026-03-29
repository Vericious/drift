"""Git utilities for drift scanning."""

import re
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


# Regex to parse hunk headers: @@ -old +new @@ optional text
# Regex to parse hunk headers: @@ -old_start[,old_count] +new_start[,new_count] @@
_HUNK_RE = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def get_changed_lines(ref: str, path: Path) -> dict[Path, set[int]] | None:
    """Get per-file set of changed line numbers from a git diff against ref.

    Runs 'git diff --unified=0 ref' and parses @@ hunk headers to extract
    the new-side line range (new_start, new_count). The changed new line numbers
    are new_start through new_start + new_count - 1.

    Returns None if the git command fails (not a repo, invalid ref, etc.).
    Returns a dict mapping each changed file to the set of its changed line numbers.
    Example: {Path('src/api.py'): {42, 43, 44}}

    Note: when new_count is omitted it defaults to 1.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--unified=0", ref, "--"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None

        changed: dict[Path, set[int]] = {}
        current_file: Path | None = None
        file_lines: set[int] = set()

        for line in result.stdout.splitlines():
            if line.startswith("+++ "):
                # Extract file path from +++ b/path
                filename = line[4:].strip()
                if filename.startswith("b/"):
                    filename = filename[2:]
                if filename and filename != "/dev/null":
                    if current_file is not None and file_lines:
                        changed[current_file] = file_lines
                    # Join with resolved absolute path so comparison works
                    current_file = (path.resolve() / filename)
                    file_lines = set()
            elif line.startswith("@@"):
                match = _HUNK_RE.match(line)
                if match:
                    new_start = int(match.group(3))  # group 3 = new_start
                    new_count = int(match.group(4)) if match.group(4) else 1
                    for i in range(new_start, new_start + new_count):
                        if current_file is not None:
                            file_lines.add(i)

        if current_file is not None and file_lines:
            changed[current_file] = file_lines

        return changed
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


def get_merge_base(branch: str, path: Path) -> str | None:
    """Get the merge-base commit between branch and HEAD.

    Returns None if:
    - Not in a git repo
    - branch is invalid or doesn't exist
    - No common ancestor found
    - git command fails for any reason
    """
    try:
        result = subprocess.run(
            ["git", "merge-base", branch, "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return None
