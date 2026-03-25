"""
Signature Matcher — compares CodeFact objects against DocClaim objects to produce DriftItem objects.
"""
from pathlib import Path

from drift.models import (
    CodeFact,
    DocClaim,
    DriftItem,
    DriftReport,
    Parameter,
    Severity,
)


class SignatureMatcher:
    """Match code facts against doc claims and produce drift items."""

    def _same_signature_structure(self, fact: CodeFact, claim: DocClaim) -> bool:
        """Return True if fact and claim have the same parameter names."""
        fact_param_names = {p.name for p in fact.parameters}
        claim_param_names = {p.name for p in claim.parameters}
        return fact_param_names == claim_param_names

    def match(self, facts: list[CodeFact], claims: list[DocClaim]) -> list[DriftItem]:
        """Match facts against claims and return drift items."""
        drift_items: list[DriftItem] = []

        # Build lookup maps for facts
        facts_by_qualified: dict[str, CodeFact] = {f.name: f for f in facts}
        facts_by_unqualified: dict[str, list[CodeFact]] = {}
        for f in facts:
            unqual = f.name.split(".")[-1]
            facts_by_unqualified.setdefault(unqual, []).append(f)

        # Track which facts have been matched
        matched_fact_names: set[str] = set()

        for claim in claims:
            if claim.name is None:
                continue

            # Try exact qualified name match first
            fact = facts_by_qualified.get(claim.name)

            # Fallback: try unqualified name
            if fact is None:
                unqual = claim.name.split(".")[-1]
                candidates = facts_by_unqualified.get(unqual, [])
                if len(candidates) == 1:
                    fact = candidates[0]

            if fact is None:
                # Try to find by signature similarity (might be renamed)
                renamed_fact = None
                for f in facts:
                    if f.name not in matched_fact_names:
                        if self._same_signature_structure(f, claim):
                            renamed_fact = f
                            break

                if renamed_fact:
                    matched_fact_names.add(renamed_fact.name)
                    drift_items.append(
                        DriftItem(
                            fact=renamed_fact,
                            claim=claim,
                            severity=Severity.ERROR,
                            category="renamed",
                            message=f"'{claim.name}' (docs) may have been renamed to '{renamed_fact.name}'",
                            suggestion=f"Update docs to reference '{renamed_fact.name}'",
                        )
                    )
                    # Skip further comparison for renamed — names differ, params matched
                    continue

                # Documented but missing
                drift_items.append(
                    DriftItem(
                        fact=None,
                        claim=claim,
                        severity=Severity.ERROR,
                        category="documented_but_missing",
                        message=f"'{claim.name}' is documented but not found in code",
                        suggestion=f"Add implementation for '{claim.name}' or update docs",
                    )
                )
                continue

            matched_fact_names.add(fact.name)

            # Compare parameters
            fact_params = {p.name: p for p in fact.parameters}
            claim_params = {p.name: p for p in claim.parameters}

            all_param_names = set(fact_params.keys()) | set(claim_params.keys())

            for param_name in all_param_names:
                f_param = fact_params.get(param_name)
                c_param = claim_params.get(param_name)

                if c_param is None:
                    # Missing param in docs — fact has it, claim doesn't
                    drift_items.append(
                        DriftItem(
                            fact=fact,
                            claim=claim,
                            severity=Severity.ERROR,
                            category="missing_param",
                            message=f"Parameter '{param_name}' in {fact.name} is not documented",
                            suggestion=f"Add '{param_name}' to docs for {fact.name}",
                        )
                    )
                elif f_param is None:
                    # Extra param in docs — claim has it but fact doesn't
                    drift_items.append(
                        DriftItem(
                            fact=fact,
                            claim=claim,
                            severity=Severity.ERROR,
                            category="extra_param",
                            message=f"Parameter '{param_name}' is documented for {fact.name} but not in code",
                            suggestion=f"Remove '{param_name}' from docs or update implementation",
                        )
                    )
                else:
                    # Both have the param — check defaults and types
                    if f_param.default != c_param.default:
                        drift_items.append(
                            DriftItem(
                                fact=fact,
                                claim=claim,
                                severity=Severity.WARNING,
                                category="wrong_default",
                                message=f"Parameter '{param_name}' default differs: {c_param.default!r} (docs) vs {f_param.default!r} (code)",
                                suggestion=f"Update docs for '{param_name}' to default={f_param.default!r}",
                            )
                        )
                    if f_param.type_annotation != c_param.type_annotation:
                        drift_items.append(
                            DriftItem(
                                fact=fact,
                                claim=claim,
                                severity=Severity.WARNING,
                                category="wrong_type",
                                message=f"Parameter '{param_name}' type differs: {c_param.type_annotation!r} (docs) vs {f_param.type_annotation!r} (code)",
                                suggestion=f"Update docs for '{param_name}' type to {f_param.type_annotation!r}",
                            )
                        )

            # Check return type
            if fact.return_type != claim.return_type:
                drift_items.append(
                    DriftItem(
                        fact=fact,
                        claim=claim,
                        severity=Severity.WARNING,
                        category="wrong_return_type",
                        message=f"Return type differs: {claim.return_type!r} (docs) vs {fact.return_type!r} (code)",
                        suggestion=f"Update return type to {fact.return_type!r}",
                    )
                )



        # Undocumented — fact exists but no matching claim
        for fact in facts:
            if fact.name not in matched_fact_names:
                drift_items.append(
                    DriftItem(
                        fact=fact,
                        claim=None,
                        severity=Severity.WARNING,
                        category="undocumented",
                        message=f"'{fact.name}' exists in code but is not documented",
                        suggestion=f"Add documentation for {fact.name}",
                    )
                )

        return drift_items


def build_report(facts: list[CodeFact], claims: list[DocClaim], scanned_path: str = ".") -> DriftReport:
    """Build a complete DriftReport from facts and claims."""
    matcher = SignatureMatcher()
    drift_items = matcher.match(facts, claims)
    return DriftReport(
        scanned_path=scanned_path if isinstance(scanned_path, Path) else Path(scanned_path),
        facts=facts,
        claims=claims,
        drift_items=drift_items,
        errors=[],
    )
