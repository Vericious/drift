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


class ClaimKind(Enum):
    FUNCTION_SIGNATURE = "function_signature"
    CODE_EXAMPLE = "code_example"
    PARAMETER_DESCRIPTION = "parameter_description"
    RETURN_DESCRIPTION = "return_description"
    CLI_USAGE = "cli_usage"
    CLI_FLAG_REF = "cli_flag_ref"
    CONFIG_REF = "config_ref"


class Severity(Enum):
    ERROR = "error"       # signature mismatch, renamed/removed
    WARNING = "warning"   # possibly stale
    INFO = "info"        # minor drift


class DriftCategory(Enum):
    """Categories of drift between code and docs."""
    MISSING_PARAM = "missing_param"
    EXTRA_PARAM = "extra_param"
    WRONG_DEFAULT = "wrong_default"
    WRONG_TYPE = "wrong_type"
    WRONG_RETURN_TYPE = "wrong_return_type"
    RENAMED = "renamed"
    DOCUMENTED_BUT_MISSING = "documented_but_missing"
    UNDOCUMENTED = "undocumented"
    SIGNATURE_MISMATCH = "signature_mismatch"


@dataclass
class Parameter:
    """A single function/method parameter."""
    name: str
    type_annotation: str | None = None
    default: str | None = None
    kind: str = "positional"  # "positional", "keyword", "varargs", "varkw"


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
            p.name + (f": {p.type_annotation}" if p.type_annotation else "")
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
    raw_text: str                    # the raw claim text from docs
    kind: ClaimKind
    doc_file: Path
    line_number: int
    name: str | None = None          # extracted function/class name
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
                }
                for p in self.parameters
            ],
            "return_type": self.return_type,
            "metadata": self.metadata,
        }


@dataclass
class DriftItem:
    """A specific mismatch between a CodeFact and a DocClaim."""
    fact: CodeFact | None = None
    claim: DocClaim | None = None
    severity: Severity = Severity.WARNING
    category: str = ""              # DriftCategory value
    message: str = ""               # human-readable description
    suggestion: str | None = None   # what the doc should probably say
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DriftReport:
    """The full result of a drift scan."""
    scanned_path: Path
    facts: list[CodeFact] = field(default_factory=list)
    claims: list[DocClaim] = field(default_factory=list)
    drift_items: list[DriftItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

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
