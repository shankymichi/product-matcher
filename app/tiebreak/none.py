"""Basic matching: no AI, so a candidate the code could not decide is not a match."""

from __future__ import annotations

from app.categories import CategoryRule
from app.models import Decision, Listing, Verdict


class NoTieBreaker:
    label = "Basic"

    async def judge(self, rule: CategoryRule, source: Listing,
                    candidates: list[Listing]) -> list[Verdict]:
        return [Verdict(decision=Decision.MISMATCH) for _ in candidates]
