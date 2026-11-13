"""Compares a candidate with the source. Names no category, platform or field."""

from __future__ import annotations

from typing import Mapping

from app.attributes.base import AttributeSpec
from app.categories import CategoryRule
from app.matching.base import ModelMatcher
from app.matching.normalise import brand_matches, codes_close, codes_differ, codes_equal
from app.models import Decision, Listing, MatchResult


class MatchEngine:
    def __init__(self, attributes: Mapping[str, AttributeSpec],
                 matchers: Mapping[str, ModelMatcher]) -> None:
        self._attributes = attributes
        self._matchers = matchers

    def compare(self, rule: CategoryRule, source: Listing, candidate: Listing) -> MatchResult:
        if not brand_matches(source.brand, candidate):
            return MatchResult(decision=Decision.MISMATCH, reasons=["brand differs"],
                               failed_on="brand")

        reasons, missing = ["brand"], []
        for name in rule.must_match:                      # driven by config
            spec = self._attributes[name]
            wanted, found = source.attributes.get(name), candidate.attributes.get(name)
            verdict = spec.compare(wanted, found)
            if verdict is Decision.MISMATCH:
                return MatchResult(
                    decision=Decision.MISMATCH, failed_on="attribute",
                    reasons=[f"{spec.label} differs: {spec.describe(wanted)} "
                             f"vs {spec.describe(found)}"])
            if verdict is Decision.UNCLEAR:
                missing.append(name)
            else:
                reasons.append(f"{spec.label} {spec.describe(wanted)}")

        if codes_equal(source.model_code, candidate.model_code):
            result = MatchResult(decision=Decision.MATCH, score=100.0,
                                 reasons=["model number equal"])
        else:
            result = self._matchers[rule.model_matcher].compare(source, candidate)

        if result.decision is Decision.MATCH and missing:
            result.decision = Decision.UNCLEAR            # model agrees, a field is unknown
        if result.decision is Decision.MATCH:
            note = self.model_number_note(source, candidate)
            if note:
                result.notes.append(note)
        result.reasons = reasons + result.reasons
        result.missing = missing
        return result

    @staticmethod
    def model_number_note(source: Listing, candidate: Listing) -> str | None:
        """A note for a match whose model number is not identical, or None."""
        if not codes_differ(source.model_code, candidate.model_code):
            return None
        if codes_close(source.model_code, candidate.model_code):
            return (f"Model number differs only by a suffix: {source.model_code} on Amazon, "
                    f"{candidate.model_code} here (usually colour or region)")
        return f"Model number differs: {source.model_code} on Amazon, {candidate.model_code} here"

    def preference(self, rule: CategoryRule, source: Listing, candidate: Listing) -> int:
        """How many of the rule's 'prefer' fields agree. Only orders matches."""
        return sum(
            self._attributes[name].compare(source.attributes.get(name),
                                           candidate.attributes.get(name)) is Decision.MATCH
            for name in rule.prefer)
