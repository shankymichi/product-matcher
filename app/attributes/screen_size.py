"""Screen size in whole inches."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.attributes.base import compare_exact, free_text, spec_value
from app.attributes.registry import register
from app.models import Decision

_INCHES = re.compile(r"(\d+(?:\.\d+)?)\s*-?\s*(?:inch(?:es)?\b|\")", re.IGNORECASE)
_CM = re.compile(r"(\d+(?:\.\d+)?)\s*cm\b", re.IGNORECASE)


def inches(text: str) -> int | None:
    match = _INCHES.search(text)
    if match:
        return round(float(match.group(1)))
    match = _CM.search(text)
    return round(float(match.group(1)) / 2.54) if match else None


class ScreenSizeSpec:
    name = "screen_inches"
    label = "Screen size"

    def extract(self, title: str, specs: Mapping[str, str]) -> Any | None:
        stated = spec_value(specs, ("screen size", "display size"))
        if stated and inches(stated) is not None:
            return inches(stated)
        return inches(free_text(title, specs))

    def compare(self, source: Any, candidate: Any) -> Decision:
        return compare_exact(source, candidate)

    def describe(self, value: Any) -> str:
        return f"{value} inch"


    def search_text(self, value: Any) -> str:
        return self.describe(value)


register(ScreenSizeSpec())
