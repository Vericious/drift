"""Typer CLI extractor for Drift.

Detects CLI flags and arguments defined via Typer decorators in Python source code.
"""
import ast
from pathlib import Path
from typing import Any, Optional

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


def _get_constant_value(node: ast.expr) -> Any:
    """Extract value from an ast.Constant node."""
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _extract_option_info(call: ast.Call) -> Optional[dict]:
    """Extract metadata from a typer.Option() or typer.Argument() call.

    Handles:
      typer.Option("--name", "-n", default=..., help=..., ...)
      typer.Option(default=..., help=..., ...)
      typer.Argument("name", default=..., help=..., ...)
    """
    func_name = _get_func_name(call.func)
    if not func_name or func_name not in ("typer.Option", "typer.Argument"):
        return None

    result = {
        "name": None,
        "short_flag": None,
        "type": None,
        "default": None,
        "help": None,
        "required": False,
        "is_flag": True,
    }

    if func_name == "typer.Argument":
        result["is_flag"] = False

    # Positional args carry the flag names
    args = list(call.args)
    if args:
        first_val = _get_constant_value(args[0])
        if first_val is not None and isinstance(first_val, str):
            result["name"] = first_val
        if len(args) > 1:
            second_val = _get_constant_value(args[1])
            if second_val is not None and isinstance(second_val, str) and second_val.startswith("-"):
                result["short_flag"] = second_val

    # Keyword args
    for kw in call.keywords:
        key = kw.arg
        val = kw.value

        if key == "default":
            result["default"] = repr(_get_constant_value(val)) if isinstance(val, ast.Constant) else val.id if isinstance(val, ast.Name) else None

        elif key == "help":
            result["help"] = _get_constant_value(val) if isinstance(val, ast.Constant) else None

        elif key == "type":
            if isinstance(val, ast.Name):
                result["type"] = val.id
            elif isinstance(val, ast.Attribute):
                result["type"] = _get_func_name(val)
            elif isinstance(val, ast.Subscript):
                result["type"] = _get_func_name(val)

        elif key == "required":
            if isinstance(val, ast.Constant):
                result["required"] = bool(val.value)

    return result


def _flag_name_from_python_name(name: str) -> str:
    """Convert a Python parameter name to a CLI flag name.

    foo_bar -> --foo-bar
    """
    return "--" + name.replace("_", "-")


def _get_type_from_annotation(annotation: ast.expr) -> Optional[str]:
    """Extract type name from an annotation (possibly Annotated[...] or bare type)."""
    if isinstance(annotation, ast.Subscript):
        if isinstance(annotation.value, ast.Name) and annotation.value.id == "Annotated":
            if isinstance(annotation.slice, ast.Tuple) and len(annotation.slice.elts) >= 1:
                type_node = annotation.slice.elts[0]
                if isinstance(type_node, ast.Name):
                    return type_node.id
                elif isinstance(type_node, ast.Attribute):
                    return _get_func_name(type_node)
        # Fallback: subscript itself
        return _get_func_name(annotation)
    elif isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Attribute):
        return _get_func_name(annotation)
    return None


class TyperExtractor(Extractor):
    """Extract CLI flags and arguments from Typer-using Python files.

    Finds @app.command() decorated functions and typer.Option/Argument
    annotations, producing CodeFact objects with kind="cli_flag".
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list:
        """Extract CLI flag CodeFacts from a Python file using Typer."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        # Walk to find FunctionDef nodes with typer command decorators
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            if not self._is_typer_command(node):
                continue

            # Map parameter defaults: last N args have defaults
            defaults_map = {}
            num_args = len(node.args.args)
            num_defaults = len(node.args.defaults)
            for i, default in enumerate(node.args.defaults):
                arg_idx = num_args - num_defaults + i
                defaults_map[node.args.args[arg_idx].arg] = default

            # Process each argument
            for arg in node.args.args:
                info = self._extract_param_info(arg, defaults_map)
                if info:
                    fact = self._build_codefact(info, path, arg.lineno or node.lineno)
                    facts.append(fact)

        return facts

    def _is_typer_command(self, node: ast.FunctionDef) -> bool:
        """Return True if function has a typer command decorator."""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                func_name = _get_func_name(decorator.func)
                if func_name and ("command" in func_name or ".command" in func_name):
                    return True
        return False

    def _extract_param_info(self, arg: ast.arg, defaults_map: dict) -> Optional[dict]:
        """Extract option/argument info for a function parameter.

        Handles two patterns:
          1. Annotated style: name: Annotated[Type, typer.Option(...)]
          2. Default style:   name: Type = typer.Option(...) or name = typer.Argument(...)
        """
        python_default = defaults_map.get(arg.arg)

        # Check Annotated[...] style annotation
        if isinstance(arg.annotation, ast.Subscript):
            subscript = arg.annotation
            if isinstance(subscript.value, ast.Name) and subscript.value.id == "Annotated":
                if isinstance(subscript.slice, ast.Tuple) and len(subscript.slice.elts) >= 2:
                    typer_call = subscript.slice.elts[-1]
                    if isinstance(typer_call, ast.Call):
                        call_info = _extract_option_info(typer_call)
                        if call_info:
                            # Type from Annotated[Type, ...]
                            call_info["type"] = _get_type_from_annotation(arg.annotation)
                            # Name comes from typer.Option("--flag") positional arg, or derived
                            name = call_info.get("name") or _flag_name_from_python_name(arg.arg)
                            call_info["name"] = name
                            call_info["python_name"] = arg.arg
                            # If there's a plain Python default, use it
                            if python_default is not None and not isinstance(python_default, ast.Call):
                                call_info["default"] = repr(_get_constant_value(python_default)) if isinstance(python_default, ast.Constant) else None
                            return call_info

        # Check default style: name = typer.Option(...) or name = typer.Argument(...)
        if python_default and isinstance(python_default, ast.Call):
            call_info = _extract_option_info(python_default)
            if call_info:
                func_name = _get_func_name(python_default.func)
                is_argument = func_name == "typer.Argument"
                name = call_info.get("name") or _flag_name_from_python_name(arg.arg)
                call_info["name"] = name
                call_info["python_name"] = arg.arg
                call_info["is_flag"] = not is_argument
                # Arguments with no default are required
                if is_argument and call_info.get("default") is None:
                    call_info["required"] = True
                return call_info

        return None

    def _build_codefact(self, info: dict, source_file: Path, line_number: int) -> CodeFact:
        """Build a CodeFact from extracted option/argument metadata."""
        name = info["name"]
        is_flag = info.get("is_flag", True)

        params = []
        if info.get("type") or info.get("default") is not None:
            params.append(Parameter(
                name=name,
                type_annotation=info.get("type"),
                default=info.get("default"),
                kind="keyword" if is_flag else "positional",
            ))

        return CodeFact(
            name=name,
            kind=FactKind.CLI_FLAG,
            source_file=source_file,
            line_number=line_number,
            parameters=params,
            metadata={
                "is_flag": is_flag,
                "help_text": info.get("help"),
                "required": info.get("required", False),
                "python_name": info.get("python_name"),
                "short_flag": info.get("short_flag"),
            },
        )
