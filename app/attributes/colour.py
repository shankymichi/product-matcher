"""Colour, reduced to base colours so "Core Black" and "Black" agree."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.attributes.base import free_text, spec_value
from app.attributes.registry import register
from app.models import Decision

BASE_COLOURS = {
    "black", "white", "grey", "silver", "blue", "red", "green", "yellow", "orange",
    "pink", "purple", "brown", "beige", "gold", "teal", "multicolour",
}

SYNONYMS = {
    "gray": "grey", "charcoal": "grey", "graphite": "grey", "slate": "grey", "ash": "grey",
    "navy": "blue", "indigo": "blue", "cobalt": "blue", "aqua": "blue", "cyan": "blue",
    "silverblue": "blue", "icyblue": "blue", "sky": "blue",
    "maroon": "red", "burgundy": "red", "crimson": "red", "wine": "red", "coralred": "red",
    "olive": "green", "mint": "green", "lime": "green", "sage": "green", "emerald": "green",
    "mustard": "yellow", "lemon": "yellow",
    "coral": "orange", "peach": "orange", "rust": "orange",
    "magenta": "pink", "rose": "pink", "fuchsia": "pink",
    "violet": "purple", "lavender": "purple", "lilac": "purple", "mauve": "purple",
    "tan": "brown", "coffee": "brown", "chocolate": "brown", "camel": "brown",
    "cream": "beige", "khaki": "beige", "sand": "beige", "taupe": "beige", "nude": "beige",
    "ivory": "white", "offwhite": "white", "whitesilver": "silver",
    "golden": "gold", "turquoise": "teal",
    "multi": "multicolour", "multicolor": "multicolour", "multicoloured": "multicolour",
}

_WORD = re.compile(r"[a-z]+")


def base_colours(text: str) -> list[str]:
    """Base colours named in the text, in order, without repeats."""
    low = text.lower().replace("off white", "offwhite").replace("off-white", "offwhite")
    found: list[str] = []
    for word in _WORD.findall(low):
        base = word if word in BASE_COLOURS else SYNONYMS.get(word)
        if base and base not in found:
            found.append(base)
    return found


class ColourSpec:
    name = "colour"
    label = "Colour"

    def extract(self, title: str, specs: Mapping[str, str]) -> Any | None:
        stated = spec_value(specs, ("colour", "color"), exclude=("hex", "family"))
        if stated and base_colours(stated):
            return base_colours(stated)
        return base_colours(free_text(title, specs)) or None

    def compare(self, source: Any, candidate: Any) -> Decision:
        if not source or not candidate:
            return Decision.UNCLEAR
        if source[0] == candidate[0]:
            return Decision.MATCH
        # Same colours listed in a different order: not safe to call either way.
        return Decision.UNCLEAR if set(source) & set(candidate) else Decision.MISMATCH

    def describe(self, value: Any) -> str:
        return " / ".join(value)


    def search_text(self, value: Any) -> str:
        return value[0]          # the main colour is enough for a search box


register(ColourSpec())
