"""Baseline management — snapshot and compare drift state."""

import json
from datetime import datetime, timezone
from pathlib import Path

from drift.models import CodeFact, DocClaim, DriftItem, DriftReport


BASELINE_FILENAME = Path(".drift") / "baseline.json"


def _serialize_items(report: DriftReport) -> list[dict]:
    """Serialize drift items to JSON-compatible dicts."""
    items = []
    for item in report.drift_items:
        items.append({
            "fact": item.fact.to_dict() if item.fact else None,
            "claim": item.claim.to_dict() if item.claim else None,
            "severity": item.severity.value,
            "category": item.category,
            "message": item.message,
            "suggestion": item.suggestion,
            "metadata": item.metadata,
        })
    return items


def save_baseline(report: DriftReport, base_path: Path | None = None) -> Path:
    """Save a baseline snapshot of the current drift state.

    Returns the path to the saved baseline file.
    """
    baseline_path = base_path / BASELINE_FILENAME if base_path else Path(BASELINE_FILENAME)
    baseline_path = baseline_path.resolve()

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": _serialize_items(report),
    }

    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, indent=2))
    return baseline_path


def load_baseline(base_path: Path | None = None) -> tuple[str, list[dict]] | None:
    """Load a baseline snapshot.

    Returns (created_at, items) if found, or None if no baseline exists.
    """
    baseline_path = base_path / BASELINE_FILENAME if base_path else Path(BASELINE_FILENAME)
    baseline_path = baseline_path.resolve()

    if not baseline_path.exists():
        return None

    try:
        data = json.loads(baseline_path.read_text())
        return data["created_at"], data["items"]
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def filter_new_drift(
    current_items: list[DriftItem],
    baseline_items: list[dict],
) -> list[DriftItem]:
    """Return only items that are NOT present in the baseline.

    Comparison is done by (fact.name, claim.name, category) tuple to identify
    unique drift items across scans.
    """
    # Build a set of baseline item signatures
    baseline_sigs: set[tuple[str | None, str | None, str]] = set()
    for item in baseline_items:
        fact = item.get("fact")
        claim = item.get("claim")
        fact_name = fact.get("name") if fact else None
        claim_name = claim.get("name") if claim else None
        category = item.get("category", "")
        baseline_sigs.add((fact_name, claim_name, category))

    # Filter current items: keep only those not in baseline
    new_items = []
    for item in current_items:
        fact_name = item.fact.name if item.fact else None
        claim_name = item.claim.name if item.claim else None
        sig = (fact_name, claim_name, item.category)
        if sig not in baseline_sigs:
            new_items.append(item)

    return new_items
