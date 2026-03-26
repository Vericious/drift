"""Python code extractor using AST."""

import ast
from pathlib import Path

from drift.models import CodeFact, FactKind, Parameter


class PythonExtractor:
    """Extract CodeFact objects from Python source files using AST."""

    def can_handle(self, path: Path) -> bool:
        """Return True if this extractor handles Python files."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract all CodeFact objects from a Python file."""
        source = path.read_text()
        tree = ast.parse(source)

        facts: list[CodeFact] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                # Extract class as a CodeFact
                facts.append(self._extract_class(node, path))
                # Extract methods from the class
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        facts.append(self._extract_method(item, node.name, path))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private functions at module level
                if not node.name.startswith("_"):
                    facts.append(self._extract_function(node, path, module=""))

        return facts

    def _extract_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, path: Path, module: str
    ) -> CodeFact:
        """Extract a top-level function."""
        qualified_name = node.name
        if module:
            qualified_name = f"{module}.{qualified_name}"
        return self._build_func_codefact(node, qualified_name, FactKind.FUNCTION, path)

    def _extract_method(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, class_name: str, path: Path
    ) -> CodeFact:
        """Extract a method from a class."""
        qualified_name = f"{class_name}.{node.name}"
        return self._build_func_codefact(node, qualified_name, FactKind.METHOD, path)

    def _extract_class(self, node: ast.ClassDef, path: Path) -> CodeFact:
        """Extract a class definition."""
        qualified_name = node.name

        # Extract decorators
        decorators = []
        for dec in getattr(node, "decorator_list", []):
            try:
                decorators.append(ast.unparse(dec))
            except Exception:
                pass

        # Derive module path
        module_path = self._derive_module(path)

        return CodeFact(
            name=qualified_name,
            kind=FactKind.CLASS,
            source_file=path,
            line_number=node.lineno,
            parameters=[],  # Classes don't have parameters
            return_type=None,
            decorators=decorators,
            module=module_path,
        )

    def _build_func_codefact(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        qualified_name: str,
        kind: FactKind,
        path: Path,
    ) -> CodeFact:
        """Build a CodeFact from a function/method AST node."""
        # Extract decorators
        decorators = []
        for dec in node.decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except Exception:
                pass

        # Derive module path
        module_path = self._derive_module(path)

        # Extract parameters
        parameters = self._extract_parameters(node)

        # Extract return type
        return_type = None
        if node.returns is not None:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                pass

        return CodeFact(
            name=qualified_name,
            kind=kind,
            source_file=path,
            line_number=node.lineno,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            module=module_path,
        )

    def _extract_parameters(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[Parameter]:
        """Extract parameters from a function or method node."""
        parameters: list[Parameter] = []
        args = node.args

        # Number of positional args that have no defaults
        num_defaults = len(args.defaults)
        num_args = len(args.args)
        num_no_default = num_args - num_defaults

        # Regular positional args
        for i, arg in enumerate(args.args):
            default = None
            if i >= num_no_default:
                default_idx = i - num_no_default
                try:
                    default = ast.unparse(args.defaults[default_idx])
                except Exception:
                    pass

            annotation = None
            if arg.annotation:
                try:
                    annotation = ast.unparse(arg.annotation)
                except Exception:
                    pass

            parameters.append(
                Parameter(
                    name=arg.arg,
                    type_annotation=annotation,
                    default=default,
                    kind="positional",
                )
            )

        # *args
        if args.vararg:
            annotation = None
            if args.vararg.annotation:
                try:
                    annotation = ast.unparse(args.vararg.annotation)
                except Exception:
                    pass
            parameters.append(
                Parameter(
                    name=args.vararg.arg, type_annotation=annotation, kind="varargs"
                )
            )

        # Keyword-only args
        for i, arg in enumerate(args.kwonlyargs):
            default = None
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                try:
                    default = ast.unparse(args.kw_defaults[i])  # type: ignore[arg-type]
                except Exception:
                    pass

            annotation = None
            if arg.annotation:
                try:
                    annotation = ast.unparse(arg.annotation)
                except Exception:
                    pass

            parameters.append(
                Parameter(
                    name=arg.arg,
                    type_annotation=annotation,
                    default=default,
                    kind="keyword",
                )
            )

        # **kwargs
        if args.kwarg:
            annotation = None
            if args.kwarg.annotation:
                try:
                    annotation = ast.unparse(args.kwarg.annotation)
                except Exception:
                    pass
            parameters.append(
                Parameter(name=args.kwarg.arg, type_annotation=annotation, kind="varkw")
            )

        return parameters

    def _derive_module(self, path: Path) -> str:
        """Derive the module path from a file path.

        e.g. src/foo/bar.py -> foo.bar
        """
        parts = path.parts
        if len(parts) >= 2:
            module_parts = list(parts[:-1])  # Remove filename
            # Find common base like 'src' or the project root
            for i, part in enumerate(module_parts):
                if part in ("src", "tests", "drift"):
                    module_parts = module_parts[i + 1 :]
                    break
            # Remove __init__ marker if present
            if module_parts and module_parts[-1] == "__init__":
                module_parts = module_parts[:-1]
            return ".".join(module_parts)
        return ""
