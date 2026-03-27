"""Terraform HCL configuration extractor for Drift.

Extracts CONFIG_KEY facts from Terraform .tf files.
Handles: resource definitions, variable declarations, output values.
"""

import ast
from pathlib import Path
from typing import Any

try:
    import hcl2
    HAS_HCL2 = True
except ImportError:
    HAS_HCL2 = False

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """Flatten a nested dict into dot-notation keys."""
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


@register
class TerraformExtractor(Extractor):
    """Extract CONFIG_KEY facts from Terraform HCL files.

    Handles:
      resource "type" "name" { ... }
      variable "name" { ... }
      output "name" { ... }
      data "type" "name" { ... }

    Fact naming:
      resource_type.resource_name.attr for resources
      var.variable_name for variables
      output.output_name for outputs
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Terraform .tf or .tf.json file."""
        suffix = path.suffix.lower()
        return suffix == ".tf" or (suffix == ".json" and path.stem.endswith(".tf"))

    def _extract_resources(self, data: dict) -> list[CodeFact]:
        """Extract resource facts from parsed HCL data."""
        facts: list[CodeFact] = []

        # Handle "resource" blocks
        if "resource" in data:
            for resource_block in data.get("resource", []):
                if not isinstance(resource_block, dict):
                    continue
                for resource_type, resource_configs in resource_block.items():
                    # resource_configs is a dict: { "resource_name": { ... body ... } }
                    if not isinstance(resource_configs, dict):
                        continue
                    for resource_name, resource_body in resource_configs.items():
                        if not isinstance(resource_body, dict):
                            continue
                        # Flatten the resource body
                        flat_attrs = _flatten_dict(resource_body)
                        # First fact is the resource itself
                        fact_name = f"{resource_type}.{resource_name}"
                        metadata = {
                            "resource_type": resource_type,
                            "resource_name": resource_name,
                            "is_resource": True,
                        }
                        facts.append(
                            CodeFact(
                                name=fact_name,
                                kind=FactKind.CONFIG_KEY,
                                source_file=Path("<terraform>"),
                                line_number=0,
                                metadata=metadata,
                            )
                        )
                        # Additional facts for each attribute
                        for attr_name, attr_value in flat_attrs.items():
                            if attr_name.startswith("_"):
                                continue
                            full_name = f"{resource_type}.{resource_name}.{attr_name}"
                            facts.append(
                                CodeFact(
                                    name=full_name,
                                    kind=FactKind.CONFIG_KEY,
                                    source_file=Path("<terraform>"),
                                    line_number=0,
                                    metadata={
                                        "resource_type": resource_type,
                                        "resource_name": resource_name,
                                        "attribute": attr_name,
                                        "value": str(attr_value) if attr_value is not None else None,
                                    },
                                )
                            )

        return facts

    def _extract_variables(self, data: dict) -> list[CodeFact]:
        """Extract variable facts from parsed HCL data."""
        facts: list[CodeFact] = []

        if "variable" in data:
            for var_block in data.get("variable", []):
                if not isinstance(var_block, dict):
                    continue
                for var_name, var_config in var_block.items():
                    if not isinstance(var_config, dict):
                        var_config = {}
                    var_type = var_config.get("type", "any")
                    var_default = var_config.get("default", None)
                    var_description = var_config.get("description", None)

                    fact_name = f"var.{var_name}"
                    facts.append(
                        CodeFact(
                            name=fact_name,
                            kind=FactKind.CONFIG_KEY,
                            source_file=Path("<terraform>"),
                            line_number=0,
                            metadata={
                                "variable_name": var_name,
                                "variable_type": var_type,
                                "default": str(var_default) if var_default is not None else None,
                                "description": var_description,
                                "is_variable": True,
                            },
                        )
                    )

        return facts

    def _extract_outputs(self, data: dict) -> list[CodeFact]:
        """Extract output facts from parsed HCL data."""
        facts: list[CodeFact] = []

        if "output" in data:
            for out_block in data.get("output", []):
                if not isinstance(out_block, dict):
                    continue
                for out_name, out_config in out_block.items():
                    if not isinstance(out_config, dict):
                        out_config = {}
                    out_value = out_config.get("value", None)
                    out_description = out_config.get("description", None)

                    fact_name = f"output.{out_name}"
                    facts.append(
                        CodeFact(
                            name=fact_name,
                            kind=FactKind.CONFIG_KEY,
                            source_file=Path("<terraform>"),
                            line_number=0,
                            metadata={
                                "output_name": out_name,
                                "value": str(out_value) if out_value is not None else None,
                                "description": out_description,
                                "is_output": True,
                            },
                        )
                    )

        return facts

    def _extract_data(self, data: dict) -> list[CodeFact]:
        """Extract data source facts from parsed HCL data."""
        facts: list[CodeFact] = []

        if "data" in data:
            for data_block in data.get("data", []):
                if not isinstance(data_block, dict):
                    continue
                for data_type, data_configs in data_block.items():
                    # data_configs is a dict: { "data_name": { ... body ... } }
                    if not isinstance(data_configs, dict):
                        continue
                    for data_name, data_body in data_configs.items():
                        fact_name = f"data.{data_type}.{data_name}"
                        facts.append(
                            CodeFact(
                                name=fact_name,
                                kind=FactKind.CONFIG_KEY,
                                source_file=Path("<terraform>"),
                                line_number=0,
                                metadata={
                                    "data_type": data_type,
                                    "data_name": data_name,
                                    "is_data": True,
                                },
                            )
                        )

        return facts

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CONFIG_KEY CodeFacts from Terraform HCL files."""
        if not HAS_HCL2:
            return []

        facts: list[CodeFact] = []

        try:
            with open(path, 'r') as f:
                data = hcl2.load(f)
        except (OSError, ValueError, Exception):
            return facts

        facts.extend(self._extract_resources(data))
        facts.extend(self._extract_variables(data))
        facts.extend(self._extract_outputs(data))
        facts.extend(self._extract_data(data))

        return facts
