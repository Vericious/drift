"""
Signature Matcher — compares CodeFact objects against DocClaim objects to produce DriftItem objects.
"""

import difflib
from pathlib import Path

from drift.models import (
    ClaimKind,
    CodeFact,
    ConfidenceSignals,
    DocClaim,
    DriftItem,
    DriftReport,
    FactKind,
    Severity,
)


class SignatureMatcher:
    """Match code facts against doc claims and produce drift items."""

    def _fuzzy_name_match(
        self, name1: str, name2: str, threshold: float = 0.7
    ) -> tuple[bool, float]:
        """Return (matched, confidence) using difflib.SequenceMatcher.

        Compares normalized names (split on underscores/camelCase).
        """

        # Normalize: split on underscores and camelCase boundaries
        def normalize(s: str) -> str:
            s = s.replace("_", " ").replace("-", " ")
            # Split camelCase
            result = ""
            for c in s:
                if c.isupper() and result:
                    result += " " + c.lower()
                else:
                    result += c.lower()
            return result.strip()

        n1 = normalize(name1)
        n2 = normalize(name2)
        ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
        return (ratio >= threshold, round(ratio * 100, 1))

    def _same_signature_structure(self, fact: CodeFact, claim: DocClaim) -> bool:
        """Return True if fact and claim have the same parameter names."""
        fact_param_names = {p.name for p in fact.parameters}
        claim_param_names = {p.name for p in claim.parameters}
        return fact_param_names == claim_param_names

    def _cli_flag_matches(self, fact: CodeFact, claim: DocClaim) -> bool:
        """Return True if a CLI_FLAG fact matches a CLI_FLAG_REF claim.

        CLI flags match by exact name (e.g., '--verbose' matches '--verbose')
        or by short flag (e.g., claim '-f' matches fact '--format' with short_flag='-f').
        No parameter comparison needed — the flag's type/default are in the fact's
        metadata, not in its parameter list.
        """
        if fact.kind != FactKind.CLI_FLAG or claim.kind != ClaimKind.CLI_FLAG_REF:
            return False
        # Exact name match
        if fact.name == claim.name:
            return True
        # Short flag match: claim name is the fact's short flag
        if (
            claim.name is not None
            and claim.name.startswith("-")
            and fact.metadata.get("short_flag") == claim.name
        ):
            return True
        return False

    def _jaccard(self, set1: set, set2: set) -> float:
        """Compute Jaccard similarity between two sets."""
        if not set1 and not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _compute_type_match_fraction(
        self, fact: CodeFact, claim: DocClaim
    ) -> float:
        """Compute fraction of parameters where types match."""
        fact_params = {p.name: p for p in fact.parameters}
        claim_params = {p.name: p for p in claim.parameters}
        common_names = set(fact_params.keys()) & set(claim_params.keys())
        if not common_names:
            return 0.0
        matches = sum(
            1
            for name in common_names
            if fact_params[name].type_annotation == claim_params[name].type_annotation
        )
        return matches / len(common_names)

    def _same_directory(self, fact: CodeFact, claim: DocClaim) -> bool:
        """Return True if fact and claim are in the same directory."""
        fact_dir = fact.source_file.parent
        claim_dir = claim.doc_file.parent
        return fact_dir == claim_dir

    def _compute_fuzzy_signals(
        self, fact: CodeFact, claim: DocClaim
    ) -> ConfidenceSignals:
        """Compute signals for a fuzzy_renamed match."""
        # name_similarity: SequenceMatcher.ratio on normalized names
        name_sim = difflib.SequenceMatcher(None, fact.name, claim.name).ratio()

        # param_overlap: Jaccard of param names
        fact_param_names = {p.name for p in fact.parameters}
        claim_param_names = {p.name for p in claim.parameters}
        param_overlap = self._jaccard(fact_param_names, claim_param_names)

        # type_match: fraction of params where types match
        type_match = self._compute_type_match_fraction(fact, claim)

        # location_proximity: 1.0 if same directory, else 0.5
        location_prox = 1.0 if self._same_directory(fact, claim) else 0.5

        signals = ConfidenceSignals(
            name_similarity=round(name_sim, 3),
            param_overlap=round(param_overlap, 3),
            type_match=round(type_match, 3),
            location_proximity=location_prox,
            context_match=0.0,
        )
        return signals

    def _compute_exact_drift_signals(
        self, fact: CodeFact, claim: DocClaim
    ) -> ConfidenceSignals:
        """Compute signals for an exact-with-drift match (name matches, params differ).

        For exact name matches with minor drift, set high signals to reflect
        the strong match confidence (confidence=1.0 for same directory).
        """
        # Location proximity: 1.0 if same directory, 0.5 otherwise
        location_prox = 1.0 if self._same_directory(fact, claim) else 0.5

        signals = ConfidenceSignals(
            name_similarity=1.0,
            param_overlap=1.0,
            type_match=1.0,
            location_proximity=location_prox,
            context_match=1.0,
        )
        return signals

    def _compute_missing_signals(self) -> ConfidenceSignals:
        """Compute signals for documented_but_missing (all zeros)."""
        return ConfidenceSignals(
            name_similarity=0.0,
            param_overlap=0.0,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.0,
        )

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

            # Skip suppressed claims (via <!-- drift:ignore --> in markdown)
            if claim.metadata.get("suppressed"):
                continue

            # Special case: CONFIG_KEY facts match CONFIG_REF claims by exact name
            if claim.kind == ClaimKind.CONFIG_REF:
                config_fact = facts_by_qualified.get(claim.name)
                if config_fact is not None and config_fact.kind == FactKind.CONFIG_KEY:
                    matched_fact_names.add(config_fact.name)
                    continue

            # Special case: CLI_FLAG facts match CLI_FLAG_REF claims by exact name
            # (no parameter comparison needed for CLI flags).
            # Also handle short flag lookup: if claim is `-f` and fact is `--format`
            # with short_flag='-f', treat as a match.
            if claim.kind == ClaimKind.CLI_FLAG_REF:
                cli_fact = facts_by_qualified.get(claim.name)
                if cli_fact is None and claim.name.startswith("-"):
                    # Try short flag lookup: find a CLI_FLAG fact whose short_flag matches
                    for f in facts:
                        if (
                            f.kind == FactKind.CLI_FLAG
                            and f.metadata.get("short_flag") == claim.name
                        ):
                            cli_fact = f
                            break
                if cli_fact is not None and self._cli_flag_matches(cli_fact, claim):
                    matched_fact_names.add(cli_fact.name)
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
                # Step 1: Try fuzzy name matching — highest confidence wins
                # This runs BEFORE renamed to ensure fuzzy_renamed takes precedence
                fuzzy_match: tuple[CodeFact, float] | None = None
                if claim.kind not in (ClaimKind.CLI_FLAG_REF, ClaimKind.CLI_USAGE):
                    for f in facts:
                        if f.name in matched_fact_names or f.kind == FactKind.CLI_FLAG:
                            continue
                        is_match, confidence = self._fuzzy_name_match(
                            f.name, claim.name
                        )
                        if is_match and self._same_signature_structure(f, claim):
                            if fuzzy_match is None or confidence > fuzzy_match[1]:
                                fuzzy_match = (f, confidence)

                if fuzzy_match:
                    fuzzy_fact, confidence = fuzzy_match
                    matched_fact_names.add(fuzzy_fact.name)
                    signals = self._compute_fuzzy_signals(fuzzy_fact, claim)
                    drift_items.append(
                        DriftItem(
                            fact=fuzzy_fact,
                            claim=claim,
                            severity=Severity.WARNING,
                            category="fuzzy_renamed",
                            message=(
                            f"'{claim.name}' (docs) may match "
                            f"'{fuzzy_fact.name}' (code) — {confidence}% confidence"
                        ),
                            suggestion=f"Consider renaming '{fuzzy_fact.name}' to '{claim.name}' or update docs",
                            confidence=signals.score(),
                            signals=signals,
                            metadata={
                                "match_method": "fuzzy",
                                "confidence": confidence,
                            },
                        )
                    )
                    continue

                # Step 2: Fallback — renamed when names are completely different
                # but signatures match (only for single candidate to avoid ambiguity).
                # If fuzzy name matching was attempted but found nothing (names too
                # different even for renamed), fall through to documented_but_missing.
                if claim.kind not in (
                    ClaimKind.CLI_FLAG_REF,
                    ClaimKind.CONFIG_REF,
                    ClaimKind.CLI_USAGE,
                ):
                    # Check whether any fact name shares meaningful character overlap
                    # with the claim name — if not, skip renamed and go to documented_but_missing.
                    MIN_NAME_OVERLAP_RATIO = 0.35  # noqa: N806
                    renamed_candidate: CodeFact | None = None
                    sig_matches = [
                        f
                        for f in facts
                        if f.name not in matched_fact_names
                        and f.kind != FactKind.CLI_FLAG
                        and self._same_signature_structure(f, claim)
                    ]
                    if len(sig_matches) == 1:
                        candidate = sig_matches[0]
                        name_ratio = difflib.SequenceMatcher(
                            None, candidate.name, claim.name
                        ).ratio()
                        if name_ratio >= MIN_NAME_OVERLAP_RATIO:
                            renamed_candidate = candidate

                    if renamed_candidate:
                        matched_fact_names.add(renamed_candidate.name)
                        drift_items.append(
                            DriftItem(
                                fact=renamed_candidate,
                                claim=claim,
                                severity=Severity.ERROR,
                                category="renamed",
                                message=f"'{claim.name}' (docs) may have been renamed to '{renamed_candidate.name}'",
                                suggestion=f"Update docs to reference '{renamed_candidate.name}'",
                                confidence=name_ratio,
                            )
                        )
                        continue

                # Step 3: Documented but missing
                # CLI_USAGE claims document CLI invocations (e.g., `$ mycli --flag`)
                # which may be implemented via argparse without a named function.
                # Also skip --help and --version for CLI_FLAG_REF claims since these
                # are implicit in argparse and not explicitly defined in add_argument().
                if claim.kind == ClaimKind.CLI_FLAG_REF and claim.name in (
                    "--help",
                    "--version",
                ):
                    # Skip — implicit argparse flags that aren't explicitly defined
                    continue
                if claim.kind != ClaimKind.CLI_USAGE:
                    signals = self._compute_missing_signals()
                    drift_items.append(
                        DriftItem(
                            fact=None,
                            claim=claim,
                            severity=Severity.ERROR,
                            category="documented_but_missing",
                            message=f"'{claim.name}' is documented but not found in code",
                            suggestion=f"Add implementation for '{claim.name}' or update docs",
                            confidence=signals.score(),
                            signals=signals,
                        )
                    )
                continue

            matched_fact_names.add(fact.name)

            # Special case: CLI_FLAG facts vs CLI_FLAG_REF claims — no parameter comparison needed.
            # The flag is documented, that's what matters. Skip the function-signature comparison.
            if fact.kind == FactKind.CLI_FLAG and claim.kind == ClaimKind.CLI_FLAG_REF:
                continue

            # Special case: CONFIG_KEY facts vs CONFIG_REF claims — no parameter comparison needed.
            # Config keys are documented by name; no signature comparison needed.
            if fact.kind == FactKind.CONFIG_KEY and claim.kind == ClaimKind.CONFIG_REF:
                continue

            # Compute signals for exact-with-drift (name matches exactly, params differ)
            signals = self._compute_exact_drift_signals(fact, claim)

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
                            confidence=signals.score(),
                            signals=signals,
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
                            confidence=signals.score(),
                            signals=signals,
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
                                message=(
                                f"Parameter '{param_name}' default differs: "
                                f"{c_param.default!r} (docs) vs {f_param.default!r} (code)"
                            ),
                                suggestion=f"Update docs for '{param_name}' to default={f_param.default!r}",
                                confidence=signals.score(),
                                signals=signals,
                            )
                        )
                    if f_param.type_annotation != c_param.type_annotation:
                        drift_items.append(
                            DriftItem(
                                fact=fact,
                                claim=claim,
                                severity=Severity.WARNING,
                                category="wrong_type",
                                message=(
                                f"Parameter '{param_name}' type differs: "
                                f"{c_param.type_annotation!r} (docs) vs {f_param.type_annotation!r} (code)"
                            ),
                                suggestion=f"Update docs for '{param_name}' type to {f_param.type_annotation!r}",
                                confidence=signals.score(),
                                signals=signals,
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
                        confidence=signals.score(),
                        signals=signals,
                    )
                )

        # Undocumented — fact exists but no matching claim
        for fact in facts:
            if fact.name not in matched_fact_names:
                # CLI flags are more serious: undocumented flags are errors, not warnings
                severity = (
                    Severity.ERROR
                    if fact.kind == FactKind.CLI_FLAG
                    else Severity.WARNING
                )
                drift_items.append(
                    DriftItem(
                        fact=fact,
                        claim=None,
                        severity=severity,
                        category="undocumented",
                        message=f"'{fact.name}' exists in code but is not documented",
                        suggestion=f"Add documentation for {fact.name}",
                        confidence=0.0,
                    )
                )

        return drift_items


def build_report(
    facts: list[CodeFact], claims: list[DocClaim], scanned_path: str = "."
) -> DriftReport:
    """Build a complete DriftReport from facts and claims."""
    matcher = SignatureMatcher()
    drift_items = matcher.match(facts, claims)
    return DriftReport(
        scanned_path=scanned_path
        if isinstance(scanned_path, Path)
        else Path(scanned_path),
        facts=facts,
        claims=claims,
        drift_items=drift_items,
        errors=[],
    )
