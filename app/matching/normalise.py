"""Text clean-up shared by the matchers: brands and model names."""

from __future__ import annotations

import re
from typing import Iterable

from app.attributes.colour import BASE_COLOURS, SYNONYMS
from app.models import Listing

BRAND_ALIASES = {
    "mi": "xiaomi",
    "one plus": "oneplus",
    "adidas originals": "adidas",
    "the indian garage co": "indian garage co",
}

# Filler words that are never part of a model name, in any category.
GENERIC_WORDS = {"ai", "with", "and", "the", "new", "for", "in", "of", "by", "ram", "rom",
                 "storage", "smartchoice"}

_NON_WORD = re.compile(r"[^a-z0-9+]+")
_SPEC_TOKEN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:gb|tb|mah|mp|hz|w|cm|inch|inches)\b")


def norm(text: str | None) -> str:
    """Lowercase, punctuation to spaces, single spaces."""
    return _NON_WORD.sub(" ", (text or "").lower()).strip()


def normalise_brand(brand: str | None) -> str:
    cleaned = norm(brand)
    return BRAND_ALIASES.get(cleaned, cleaned)


def _same_or_prefix(a: str, b: str) -> bool:
    """Equal, or one is the other plus more words: "u s polo assn" / "... denim co"."""
    return a == b or a.startswith(b + " ") or b.startswith(a + " ")


def brand_matches(source_brand: str | None, candidate: Listing) -> bool:
    """True when the candidate is the source's brand.

    When a search result carries no brand field, its title must start with the
    brand. An accessory "for Samsung Galaxy ..." therefore does not pass.
    """
    wanted = normalise_brand(source_brand)
    if not wanted:
        return False
    if candidate.brand:
        return _same_or_prefix(normalise_brand(candidate.brand), wanted)
    title = norm(candidate.title)
    return title == wanted or title.startswith(wanted + " ")


_RATING = re.compile(r"\b\d\s*star\b", re.IGNORECASE)
_PARENS = re.compile(r"\([^)]*\)")
_SEGMENTS = re.compile(r"[,|]|\s-\s|\swith\s", re.IGNORECASE)


def model_name(title: str, brand: str | None, stop_words: Iterable[str] = ()) -> str:
    """The model words of a title.

    'Samsung Galaxy S25 Ultra 5G AI Smartphone (Titanium Black, 12GB RAM), 200MP'
    becomes 'galaxy s25 ultra 5g': brackets, specs, colours, the brand, filler
    words and the category's stop words are dropped, and only the first part of
    the title that still has words left is used.
    """
    brand_words = normalise_brand(brand).split()
    skip = GENERIC_WORDS | set(stop_words) | BASE_COLOURS | set(SYNONYMS)
    title = re.sub(r"['\u2019]s\b", "", title)            # "Men's" -> "Men"
    title = _RATING.sub(" ", title)                          # "2 Star" energy rating
    for segment in _SEGMENTS.split(_PARENS.sub(" ", title)):
        words = norm(_SPEC_TOKEN.sub(" ", segment.lower())).split()
        if brand_words and words[: len(brand_words)] == brand_words:
            words = words[len(brand_words):]
        words = [w for w in words if w not in skip]
        if words:
            return " ".join(words)
    return ""


def without_code(model: str, model_code: str | None) -> str:
    """Drop the model number's own words: 'bravia 2m2 k 43s22bm2' -> 'bravia 2m2'."""
    code_words = set(norm(model_code).split())
    return " ".join(w for w in model.split() if w not in code_words) if code_words else model


def codes_differ(a: str | None, b: str | None) -> bool:
    return bool(a and b) and norm(a).replace(" ", "") != norm(b).replace(" ", "")


def codes_close(a: str | None, b: str | None) -> bool:
    """One model number is the other plus up to two letters: K-55S30B / K-55S30.
    Such suffixes usually mark a colour or region, not a different model."""
    x, y = (norm(a).replace(" ", ""), norm(b).replace(" ", "")) if a and b else ("", "")
    if not x or not y or x == y:
        return False
    short, long_ = sorted((x, y), key=len)
    extra = long_[len(short):]
    return long_.startswith(short) and len(extra) <= 2 and extra.isalpha() and len(short) >= 5


def codes_equal(a: str | None, b: str | None) -> bool:
    return bool(a and b) and norm(a).replace(" ", "") == norm(b).replace(" ", "")
