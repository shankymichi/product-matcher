"""Free-form product names (shoes, clothing) compared by their words."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from app.matching.base import register
from app.models import Decision, Listing, MatchResult

_HAS_DIGIT = re.compile(r"\d")


class NameScoreMatcher:
    """Match only when both names use the same words.

    Character similarity alone is not trusted: "Smash Comfort" and "Smashic
    Comfort" look 93% alike and are different shoes. Similar-but-not-equal
    names are reported as unclear, for the tie-breaker to settle.
    """

    name = "name_score"

    def __init__(self, unclear_from: float = 70.0) -> None:
        self._unclear_from = unclear_from

    def compare(self, source: Listing, candidate: Listing) -> MatchResult:
        a, b = (source.model or "").split(), (candidate.model or "").split()
        if not a or not b:
            return MatchResult(decision=Decision.UNCLEAR, reasons=["product name missing"])

        # Number words carry the model: "Smash v2" is not "Smash v1", "574" is not "530".
        if {w for w in a if _HAS_DIGIT.search(w)} != {w for w in b if _HAS_DIGIT.search(w)}:
            return MatchResult(decision=Decision.MISMATCH, score=0.0, failed_on="model_number",
                               reasons=[f"model numbers differ: '{source.model}' vs "
                                        f"'{candidate.model}'"])

        score = round(fuzz.token_sort_ratio(source.model, candidate.model), 1)
        if set(a) == set(b):
            return MatchResult(decision=Decision.MATCH, score=100.0,
                               reasons=["product name equal"])
        if set(a) <= set(b) or set(b) <= set(a) or score >= self._unclear_from:
            return MatchResult(decision=Decision.UNCLEAR, score=score,
                               reasons=[f"product name similar but not equal: "
                                        f"'{source.model}' vs '{candidate.model}'"])
        return MatchResult(decision=Decision.MISMATCH, score=score, failed_on="model_name",
                           reasons=[f"product name differs: '{source.model}' vs "
                                    f"'{candidate.model}'"])


register(NameScoreMatcher())
