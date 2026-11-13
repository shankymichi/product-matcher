"""Model names compared word for word. For products with precise model names."""

from __future__ import annotations

from app.matching.base import register
from app.models import Decision, Listing, MatchResult

# Words a seller may leave out without it being a different model.
SOFT_WORDS = {"galaxy"}


def _code_inside(words: set[str], model_number: str | None) -> str | None:
    """A word such as 'ue81a' that appears inside a model number such as UA55UE81AFULXL."""
    number = (model_number or "").lower()
    for word in sorted(words):
        if len(word) >= 5 and any(c.isdigit() for c in word) and any(c.isalpha() for c in word) \
                and word in number:
            return word
    return None


class ExactWordsMatcher:
    name = "exact_words"

    def compare(self, source: Listing, candidate: Listing) -> MatchResult:
        a, b = set((source.model or "").split()), set((candidate.model or "").split())
        short_code = _code_inside(b, source.model_code) or _code_inside(a, candidate.model_code)
        if short_code:
            return MatchResult(decision=Decision.MATCH, score=100.0,
                               reasons=[f"model code {short_code.upper()} is part of the model number"])
        if not a or not b:
            return MatchResult(decision=Decision.UNCLEAR, reasons=["model name missing"])
        score = round(100 * len(a & b) / len(a | b), 1)
        if a == b:
            return MatchResult(decision=Decision.MATCH, score=score, reasons=["model name equal"])
        if (a ^ b) <= SOFT_WORDS:
            return MatchResult(decision=Decision.UNCLEAR, score=score,
                               reasons=["model name differs only by an optional word"])
        return MatchResult(decision=Decision.MISMATCH, score=score, failed_on="model_name",
                           reasons=[f"model differs: '{source.model}' vs '{candidate.model}'"])


register(ExactWordsMatcher())
