"""A TieBreaker settles the candidates the code could not decide on its own."""

from __future__ import annotations

from typing import Protocol

from app.categories import CategoryRule
from app.models import Listing, Verdict


class TieBreaker(Protocol):
    label: str   # shown on the page, e.g. "Basic" or "Basic + AI check"

    async def judge(self, rule: CategoryRule, source: Listing,
                    candidates: list[Listing]) -> list[Verdict]:
        """One verdict per candidate, in the same order.

        May raise any exception; the caller then falls back to basic matching.
        """
