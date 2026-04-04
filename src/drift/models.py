"""
Core data models for Drift.

CodeFact: a ground-truth fact extracted from source code
DocClaim: a claim found in documentation about code
DriftItem: a specific mismatch between a CodeFact and a DocClaim
DriftReport: the full result of a drift scan
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class FactKind(Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    CLI_FLAG = "cli_flag"
    API_ENDPOINT = "api_endpoint"
    CONFIG_KEY = "config_key"
    DECORATOR = "decorator"
    DEPRECATED = "deprecated"
    TABLE_SCHEMA = "table_schema"
    TS_INTERFACE = "ts_interface"
    TS_TYPE = "ts_type"
    TS_ENUM = "ts_enum"


class ClaimKind(Enum):
    FUNCTION_SIGNATURE = "function_signature"
    CODE_EXAMPLE = "code_example"
    PARAMETER_DESCRIPTION = "parameter_description"
    RETURN_DESCRIPTION = "return_description"
    CLI_USAGE = "cli_usage"
    CLI_FLAG_REF = "cli_flag_ref"
    CONFIG_REF = "config_ref"
    FUNCTION_REF = "function_ref"


class Severity(Enum):
    ERROR = "error"  # signature mismatch, renamed/removed
    WARNING = "warning"  # possibly stale
    INFO = "info"  # minor drift


class DriftCategory(Enum):
    """Categories of drift between code and docs."""

    MISSING_PARAM = "missing_param"
    EXTRA_PARAM = "extra_param"
    WRONG_DEFAULT = "wrong_default"
    WRONG_TYPE = "wrong_type"
    WRONG_RETURN_TYPE = "wrong_return_type"
    RENAMED = "renamed"
    FUZZY_RENAMED = "fuzzy_renamed"
    DOCUMENTED_BUT_MISSING = "documented_but_missing"
    UNDOCUMENTED = "undocumented"
    SIGNATURE_MISMATCH = "signature_mismatch"
    TS_PROPERTY_MISSING = "ts_property_missing"
    TS_PROPERTY_EXTRA = "ts_property_extra"
    TS_MEMBER_MISSING = "ts_member_missing"
    TS_MEMBER_EXTRA = "ts_member_extra"


@dataclass
class Parameter:
    """A single function/method parameter."""

    name: str
    type_annotation: str | None = None
    default: str | None = None
    kind: str = "positional"  # "positional", "keyword", "varargs", "varkw"
    is_optional: bool = False  # True for TypeScript optional properties (bar?: type)
    is_readonly: bool = False  # True for TypeScript readonly properties (readonly bar: type)


@dataclass
class CodeFact:
    """A ground-truth fact extracted from source code."""

    name: str
    kind: FactKind
    source_file: Path
    line_number: int
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str | None = None
    decorators: list[str] = field(default_factory=list)
    module: str = ""
    docstring: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def signature_str(self) -> str:
        """Render the signature as a human-readable string."""
        params = ", ".join(
            p.name
            + (f": {p.type_annotation}" if p.type_annotation else "")
            + (f" = {p.default}" if p.default else "")
            for p in self.parameters
        )
        ret = f" -> {self.return_type}" if self.return_type else ""
        return f"{self.name}({params}){ret}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict with Path objects converted to strings."""
        return {
            "name": self.name,
            "kind": self.kind.value,
            "source_file": str(self.source_file),
            "line_number": self.line_number,
            "parameters": [
                {
                    "name": p.name,
                    "type_annotation": p.type_annotation,
                    "default": p.default,
                    "kind": p.kind,
                    "is_optional": p.is_optional,
                    "is_readonly": p.is_readonly,
                }
                for p in self.parameters
            ],
            "return_type": self.return_type,
            "decorators": self.decorators,
            "module": self.module,
            "docstring": self.docstring,
            "metadata": self.metadata,
        }


@dataclass
class DocClaim:
    """A claim found in documentation about code."""

    raw_text: str  # the raw claim text from docs
    kind: ClaimKind
    doc_file: Path
    line_number: int
    name: str | None = None  # extracted function/class name
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict with Path objects converted to strings."""
        return {
            "raw_text": self.raw_text,
            "kind": self.kind.value,
            "doc_file": str(self.doc_file),
            "line_number": self.line_number,
            "name": self.name,
            "parameters": [
                {
                    "name": p.name,
                    "type_annotation": p.type_annotation,
                    "default": p.default,
                    "kind": p.kind,
                    "is_optional": p.is_optional,
                    "is_readonly": p.is_readonly,
                }
                for p in self.parameters
            ],
            "return_type": self.return_type,
            "metadata": self.metadata,
        }


@dataclass
class ConfidenceSignals:
    """Weighted signal fields that contribute to a DriftItem's confidence score."""

    name_similarity: float = 0.0  # 0.0–1.0
    param_overlap: float = 0.0  # 0.0–1.0
    type_match: float = 0.0  # 0.0–1.0
    location_proximity: float = 0.0  # 0.0–1.0
    context_match: float = 0.0  # 0.0–1.0

    def score(self) -> float:
        """Return weighted sum clamped to [0,1], rounded to 3 decimal places."""
        weighted = (
            self.name_similarity * 0.35
            + self.param_overlap * 0.30
            + self.type_match * 0.15
            + self.location_proximity * 0.10
            + self.context_match * 0.10
        )
        return round(max(0.0, min(1.0, weighted)), 3)

    def to_dict(self) -> dict[str, float]:
        """Serialize all 5 signal fields as a dict."""
        return {
            "name_similarity": self.name_similarity,
            "param_overlap": self.param_overlap,
            "type_match": self.type_match,
            "location_proximity": self.location_proximity,
            "context_match": self.context_match,
        }

    def explain(self) -> str:
        """Return a human-readable breakdown of each signal's contribution.

        Format: 'param_overlap: 0.85 (weight=0.3, contribution=0.255)'
        Includes total score on last line.
        """
        weights = {
            "name_similarity": 0.35,
            "param_overlap": 0.30,
            "type_match": 0.15,
            "location_proximity": 0.10,
            "context_match": 0.10,
        }
        lines = []
        for name, raw_value in [
            ("name_similarity", self.name_similarity),
            ("param_overlap", self.param_overlap),
            ("type_match", self.type_match),
            ("location_proximity", self.location_proximity),
            ("context_match", self.context_match),
        ]:
            weight = weights[name]
            contribution = raw_value * weight
            lines.append(f"{name}: {raw_value} (weight={weight}, contribution={contribution:.3f})")
        lines.append(f"total: {self.score()}")
        return "\n".join(lines)


@dataclass
class DriftItem:
    """A specific mismatch between a CodeFact and a DocClaim."""

    fact: CodeFact | None = None
    claim: DocClaim | None = None
    severity: Severity = Severity.WARNING
    category: str = ""  # DriftCategory value
    message: str = ""  # human-readable description
    suggestion: str | None = None  # what the doc should probably say
    confidence: float = 1.0  # 0.0–1.0 confidence that this drift item is real
    signals: ConfidenceSignals | None = None  # detailed signal fields
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanMetrics:
    """Timing metrics for each phase of a drift scan."""

    extract_ms: float = 0.0  # Time spent in extraction phase (ms)
    match_ms: float = 0.0  # Time spent in matching phase (ms)
    filter_ms: float = 0.0  # Time spent in content-aware filtering phase (ms)
    total_ms: float = 0.0  # Total scan time (ms)


@dataclass
class DriftReport:
    """The full result of a drift scan."""

    scanned_path: Path
    facts: list[CodeFact] = field(default_factory=list)
    claims: list[DocClaim] = field(default_factory=list)
    drift_items: list[DriftItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    files_skipped: int = 0
    files_scanned: int = 0  # Total files considered for scanning (before cache/since filters)
    metrics: ScanMetrics | None = None

    @property
    def errors_count(self) -> int:
        """Count items with severity ERROR."""
        return sum(1 for item in self.drift_items if item.severity == Severity.ERROR)

    @property
    def warnings_count(self) -> int:
        """Count WARNING items."""
        return sum(1 for item in self.drift_items if item.severity == Severity.WARNING)

    @property
    def has_drift(self) -> bool:
        """True only if any ERROR-severity items exist (matches plan semantics)."""
        return any(item.severity == Severity.ERROR for item in self.drift_items)

    def summary(self) -> str:
        """Returns 'X facts, Y claims, Z drift items (A errors, B warnings)'."""
        return (
            f"{len(self.facts)} facts, {len(self.claims)} claims, "
            f"{len(self.drift_items)} drift items "
            f"({self.errors_count} errors, {self.warnings_count} warnings)"
        )
