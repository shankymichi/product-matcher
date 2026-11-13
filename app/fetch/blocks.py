"""Recognises pages a site sends instead of content. They are reported, never bypassed."""

from __future__ import annotations

import re

BLOCK_STATUSES = {403, 429, 503}

_BLOCK_TEXT = re.compile(
    "|".join([
        r"enter the characters you see below",
        r"make sure you're not a robot",
        r"click the button below to continue shopping",
        r"access denied",
        r"you don't have permission to access",
        r"unusual traffic",
        r"verify you are human",
        r"pardon our interruption",
        r"request blocked",
    ]),
    re.IGNORECASE)


def block_reason(status: int, visible_text: str) -> str | None:
    """Why this response counts as blocked, or None when it looks like content."""
    if status in BLOCK_STATUSES:
        return f"the site answered HTTP {status}"
    match = _BLOCK_TEXT.search(visible_text[:5000])
    return f'the site showed a check page ("{match.group(0).lower()}")' if match else None
