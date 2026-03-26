"""Click CLI extractor for Drift.

Detects CLI flags and arguments defined via click decorators in Python source code.
"""
from drift.extractors.registry import register
import ast
from pathlib import Path
from typing import Any, Optional, cast

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
    """Extract value from an ast.Constant or ast.Str node."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    return None


def _parse_click_decorator(decorator: ast.expr) -> Optional[tuple[str, dict[str, Any], list[Any]]]:
    """Parse a click decorator and return (decorator_type, kwargs_dict, args_list).

    Handles:
      @click.option('--flag', ...)
      @click.argument('name', ...)
      @click.command()
      @click.group()
    """
    if not isinstance(decorator, ast.Call):
        return None

    func = decorator.func
    func_name = _get_func_name(func)
    if not func_name or not func_name.startswith("click."):
        return None

    # Extract decorator type (option, argument, command, group)
    parts = func_name.split(".")
    dec_type = parts[-1]

    # Extract keyword arguments from the decorator call
    kwargs: dict[str, Any] = {}
    for kw in decorator.keywords:
        if kw.arg is not None:
            kwargs[kw.arg] = kw.value

    # Extract positional args
    args = [_get_constant_value(a) for a in decorator.args]

    return dec_type, kwargs, args


def _extract_option_info(dec_type: str, kwargs: dict[str, Any], args: list[Any]) -> Optional[dict[str, Any]]:
    """Extract option/argument metadata from a click decorator's parsed info."""
    if dec_type not in ("option", "argument"):
        return None

    result: dict[str, Any] = {
        "name": None,
        "short_flag": None,
        "type": None,
        "default": None,
        "help": None,
        "required": False,
        "is_flag": False,
        "multiple": False,
        "choices": None,
    }

    if dec_type == "option":
        # Positional args: first is the flag string, second (if string starting with -) is short
        if args:
            flag_str = str(args[0])
            result["name"] = flag_str
            if len(args) > 1 and isinstance(args[1], str) and args[1].startswith("-"):
                result["short_flag"] = str(args[1])

        # '--flag' / '-f' can also come as keyword args
        if "name" in kwargs:
            nv = _get_constant_value(kwargs["name"])
            if nv:
                result["name"] = str(nv)
        if "short" in kwargs:
            sv = _get_constant_value(kwargs["short"])
            if sv:
                result["short_flag"] = str(sv)

        # is_flag: is_flag=True or action=store_true/False
        is_flag = isinstance(kwargs.get("is_flag"), ast.Constant) and kwargs["is_flag"].value is True
        action = kwargs.get("action")
        if isinstance(action, ast.Constant) and action.value in ("store_true", "store_false"):
            is_flag = True

        result["is_flag"] = is_flag or (
            result["name"] and result["name"].startswith("-") and not result["name"].startswith("--")
        )

        # type
        type_node = kwargs.get("type")
        if isinstance(type_node, ast.Name):
            result["type"] = type_node.id
        elif isinstance(type_node, ast.Attribute):
            result["type"] = _get_func_name(type_node)
        elif isinstance(type_node, ast.Call):
            func_n = _get_func_name(type_node.func)
            result["type"] = func_n
            if func_n and "Choice" in func_n:
                # Choices list: click.Choice(['json', 'console'])
                choices = []
                for arg in type_node.args:
                    if isinstance(arg, ast.List):
                        for elt in arg.elts:
                            v = _get_constant_value(elt)
                            if v is not None:
                                choices.append(v)
                    else:
                        v = _get_constant_value(arg)
                        if v is not None:
                            choices.append(v)
                result["choices"] = choices

        # default
        default_node = kwargs.get("default")
        if default_node is not None:
            if isinstance(default_node, ast.Constant):
                result["default"] = repr(default_node.value)
            elif isinstance(default_node, ast.Name):
                result["default"] = default_node.id

        # help
        help_node = kwargs.get("help")
        if isinstance(help_node, ast.Constant):
            result["help"] = help_node.value

        # required (options are optional by default, but can be required=True)
        required_node = kwargs.get("required")
        if isinstance(required_node, ast.Constant):
            result["required"] = bool(required_node.value)

        # multiple
        multiple_node = kwargs.get("multiple")
        if isinstance(multiple_node, ast.Constant):
            result["multiple"] = multiple_node.value

    elif dec_type == "argument":
        # @click.argument('name', ...)
        if args:
            result["name"] = str(args[0])
        elif "name" in kwargs:
            nv = _get_constant_value(kwargs["name"])
            if nv:
                result["name"] = str(nv)

        type_node = kwargs.get("type")
        if isinstance(type_node, ast.Name):
            result["type"] = type_node.id
        elif isinstance(type_node, ast.Attribute):
            result["type"] = _get_func_name(type_node)
        elif isinstance(type_node, ast.Call):
            func_n = _get_func_name(type_node.func)
            result["type"] = func_n

        default_node = kwargs.get("default")
        if default_node is not None:
            if isinstance(default_node, ast.Constant):
                result["default"] = repr(default_node.value)
            elif isinstance(default_node, ast.Name):
                result["default"] = default_node.id

        help_node = kwargs.get("help")
        if isinstance(help_node, ast.Constant):
            result["help"] = help_node.value

    return result


@register
class ClickExtractor(Extractor):
    """Extract CLI flags and arguments from click-using Python files.

    Finds click decorators (@click.option, @click.argument, @click.command)
    and produces CodeFact objects with kind="cli_flag".
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CLI flag CodeFacts from a Python file using click."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        # Walk to find FunctionDef nodes with click decorators
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for decorator in node.decorator_list:
                parsed = _parse_click_decorator(decorator)
                if not parsed:
                    continue

                dec_type, kwargs, args = parsed
                info = _extract_option_info(dec_type, kwargs, args)

                if info and info.get("name"):
                    fact = self._build_codefact(info, path, decorator.lineno or node.lineno)
                    facts.append(fact)

        return facts

    def _build_codefact(self, info: dict[str, Any], source_file: Path, line_number: int) -> CodeFact:
        """Build a CodeFact from extracted option/argument metadata."""
        name = info["name"]

        params = []
        if info.get("type"):
            params.append(Parameter(
                name=name,
                type_annotation=info["type"],
                default=info.get("default"),
                kind="keyword",
            ))

        return CodeFact(
            name=name,
            kind=FactKind.CLI_FLAG,
            source_file=source_file,
            line_number=line_number,
            parameters=params,
            metadata={
                "short_flag": info.get("short_flag"),
                "is_flag": info.get("is_flag", False),
                "choices": info.get("choices"),
                "required": info.get("required", False),
                "help_text": info.get("help"),
                "multiple": info.get("multiple", False),
            },
        )
