"""OpenAPI/Swagger route claim extractor for Drift.

Parses openapi.yaml / swagger.yaml files. Extracts API_ENDPOINT facts
from OpenAPI 3.x and Swagger 2.0 specifications.
"""

from pathlib import Path
from typing import Any

import yaml

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind

# HTTP methods tracked in OpenAPI specs
HTTP_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
)


def _extract_parameters(
    params: list[dict[str, Any]], source: str
) -> list[dict[str, Any]]:
    """Extract a clean list of parameter descriptors from a parameters list.

    Args:
        params: Raw parameters list from OpenAPI spec.
        source: 'path' | 'query' | 'header' | 'cookie' — only 'path' is
            required for route matching, but all are stored for completeness.

    Returns:
        List of dicts with at least: name, in, description (if present).
    """
    result = []
    for p in params:
        if not isinstance(p, dict):
            continue
        result.append(
            {
                "name": p.get("name", ""),
                "in": p.get("in", ""),
                "description": p.get("description", ""),
                "required": p.get("required", False),
                "schema": p.get("schema", {}),
            }
        )
    return result


def _extract_path_params(path: str) -> list[str]:
    """Extract parameter names from an OpenAPI path template.

    E.g., "/users/{user_id}/posts/{post_id}" -> ["user_id", "post_id"]
    """
    import re

    return re.findall(r"\{([^}]+)\}", path)


@register
class OpenAPIExtractor(Extractor):
    """Extract API_ENDPOINT facts from OpenAPI 3.x and Swagger 2.0 specs.

    Handles:
      - OpenAPI 3.0.x / 3.1.x: paths.{path}.{method}
      - Swagger 2.0: paths.{path}.{method}

    Servers/basePath are prepended when present to build fully-qualified paths.

    Fact name format: "METHOD /path" (e.g., "GET /users")
    """

    def can_handle(self, file_path: Path) -> bool:
        """Return True for .yaml and .yml files."""
        return file_path.suffix.lower() in (".yaml", ".yml")

    def extract(self, file_path: Path) -> list[CodeFact]:
        """Extract API_ENDPOINT CodeFacts from an OpenAPI/Swagger spec file."""
        facts: list[CodeFact] = []

        try:
            content = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            spec = yaml.safe_load(content)
        except yaml.YAMLError:
            return facts

        if not isinstance(spec, dict):
            return facts

        # Determine spec version
        openapi_version = str(spec.get("openapi", ""))
        is_swagger2 = "swagger" in spec and "2" in spec.get("swagger", "")

        # Build base URL components
        servers = spec.get("servers", [])
        base_url = ""
        if servers and isinstance(servers, list) and isinstance(servers[0], dict):
            base_url = servers[0].get("url", "")
        elif isinstance(servers, list) and servers and isinstance(servers[0], str):
            base_url = servers[0]

        # Swagger 2.0 uses basePath instead of servers
        base_path = spec.get("basePath", "") if is_swagger2 else ""

        paths = spec.get("paths", {})
        if not isinstance(paths, dict):
            return facts

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Resolve path parameters from the path template itself
            path_param_names = _extract_path_params(path)

            for method in HTTP_METHODS:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue

                # Skip x- extensions and non-operation objects
                if method.startswith("x-"):
                    continue

                operation_id = operation.get("operationId")
                summary = operation.get("summary", "")
                description = operation.get("description", "")

                # Collect parameters: operation-level + path-level (path-level win)
                all_params: list[dict[str, Any]] = []

                # Path-level parameters (apply to all methods on this path)
                path_params = path_item.get("parameters", [])
                if isinstance(path_params, list):
                    all_params.extend(_extract_parameters(path_params, "path"))

                # Operation-level parameters
                op_params = operation.get("parameters", [])
                if isinstance(op_params, list):
                    all_params.extend(_extract_parameters(op_params, "query"))

                # Build fully-qualified path
                full_path = path
                if base_path:
                    base_path = base_path.rstrip("/")
                    full_path = f"{base_path}/{path.lstrip('/')}"
                if base_url:
                    base_url = base_url.rstrip("/")
                    full_path = f"{base_url}/{full_path.lstrip('/')}"

                fact_name = f"{method.upper()} {full_path}"

                metadata: dict[str, Any] = {
                    "method": method.upper(),
                    "path": full_path,
                    "operation_id": operation_id,
                    "summary": summary,
                    "description": description,
                    "parameters": all_params,
                    "path_param_names": path_param_names,
                    "openapi_version": openapi_version or spec.get("swagger", ""),
                }

                facts.append(
                    CodeFact(
                        name=fact_name,
                        kind=FactKind.API_ENDPOINT,
                        source_file=file_path,
                        line_number=1,
                        metadata=metadata,
                    )
                )

        return facts
