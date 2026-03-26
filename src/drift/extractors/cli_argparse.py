"""Argparse CLI extractor for Drift.

Detects CLI flags and arguments defined via argparse in Python source code.
"""
from drift.extractors.registry import register
import ast
from pathlib import Path
from typing import Optional

from drift.extractors.base import Extractor
from drift.models import CodeFact, FactKind, Parameter


def _get_func_name(node: ast.expr) -> Optional[str]:
    """Get the dotted name from an Attribute or Name node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _get_func_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def _get_constant_value(node: ast.expr):
    """Extract value from an ast.Constant or ast.Str node."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Str):  # Python < 3.8
        return node.s
    return None


def _is_flag_name(name: str) -> bool:
    """Return True if name looks like a CLI flag (starts with - or --)."""
    return isinstance(name, str) and name.startswith("-")


@register
class ArgparseExtractor(Extractor):
    """Extract CLI flags and arguments from argparse-using Python files.

    Finds ArgumentParser instantiation and add_argument() calls,
    producing CodeFact objects with kind="cli_flag".
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list:
        """Extract CLI flag CodeFacts from a Python file using argparse."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        # Walk once to find add_argument calls
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func_name = _get_func_name(node.func)
            if not func_name or "add_argument" not in func_name:
                continue

            arg_info = self._extract_arg_info(node)
            if not arg_info or not arg_info.get("name"):
                continue

            name = arg_info["name"]
            is_flag = _is_flag_name(name) or _is_flag_name(arg_info.get("short_flag", ""))
            if arg_info.get("action") in ("store_true", "store_false", "count"):
                is_flag = True

            fact = self._build_codefact(name, arg_info, path, node.lineno, is_flag)
            facts.append(fact)

        return facts

    def _extract_arg_info(self, call: ast.Call) -> Optional[dict]:
        """Extract all argument metadata from an add_argument() call.

        Handles:
          parser.add_argument('name', help='...')
          parser.add_argument('--name', '-n', help='...')
          parser.add_argument('--name', type=int, required=True)
          subparser.add_argument('pos', ...)
        """
        result = {
            "name": None,
            "short_flag": None,
            "type": None,
            "default": None,
            "help": None,
            "required": False,
            "action": None,
            "choices": None,
            "nargs": None,
        }

        args = list(call.args)
        kwargs = {kw.arg for kw in call.keywords}

        # Positional args: first is name/flag, second (if dash) is short flag
        if args:
            first_val = _get_constant_value(args[0])
            if first_val is not None:
                result["name"] = str(first_val)

        if len(args) > 1:
            second_val = _get_constant_value(args[1])
            if second_val is not None and isinstance(second_val, str) and second_val.startswith("-"):
                result["short_flag"] = str(second_val)

        # Keyword args
        for kw in call.keywords:
            key = kw.arg
            val = kw.value

            if key == "type":
                if isinstance(val, ast.Name):
                    result["type"] = val.id
                elif isinstance(val, ast.Attribute):
                    result["type"] = _get_func_name(val)
                elif isinstance(val, ast.Constant):
                    result["type"] = type(val.value).__name__

            elif key == "default":
                result["default"] = repr(_get_constant_value(val)) if _get_constant_value(val) is not None else val.id if isinstance(val, ast.Name) else None

            elif key == "help":
                result["help"] = _get_constant_value(val) if isinstance(val, ast.Constant) else None

            elif key == "required":
                if isinstance(val, ast.Constant):
                    result["required"] = bool(val.value)

            elif key == "action":
                if isinstance(val, ast.Constant):
                    result["action"] = val.value

            elif key == "choices":
                if isinstance(val, ast.List):
                    choices = []
                    for elt in val.elts:
                        v = _get_constant_value(elt)
                        if v is not None:
                            choices.append(v)
                    result["choices"] = choices

            elif key == "nargs":
                result["nargs"] = _get_constant_value(val)

        return result

    def _build_codefact(self, name: str, metadata: dict, source_file: Path, line_number: int, is_flag: bool) -> CodeFact:
        """Build a CodeFact from extracted argument metadata."""
        # Normalize: use long flag name if available
        display_name = name
        if metadata.get("short_flag") and name.startswith("-"):
            display_name = name  # keep the flag form as-is

        params = []
        if metadata.get("type"):
            params.append(Parameter(
                name=name,
                type_annotation=metadata["type"],
                default=metadata.get("default"),
                kind="keyword" if is_flag else "positional",
            ))

        return CodeFact(
            name=display_name,
            kind=FactKind.CLI_FLAG,
            source_file=source_file,
            line_number=line_number,
            parameters=params,
            metadata={
                "short_flag": metadata.get("short_flag"),
                "action": metadata.get("action"),
                "choices": metadata.get("choices"),
                "required": metadata.get("required", False),
                "help_text": metadata.get("help"),
                "is_flag": is_flag,
                "nargs": metadata.get("nargs"),
            },
        )
