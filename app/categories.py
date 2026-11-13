"""One table decides, per category, where to search and what must match.

To change the match fields, edit `must_match`. To add a category, add a row.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryRule:
    key: str
    label: str
    amazon_paths: tuple[str, ...]     # words found in Amazon's category path
    platforms: tuple[str, ...]        # PlatformAdapter names
    must_match: tuple[str, ...]       # AttributeSpec names
    model_matcher: str                # ModelMatcher name
    prefer: tuple[str, ...] = ()      # tie-break between matches; never rejects one
    stop_words: tuple[str, ...] = ()  # words in titles that are not part of the model name
    search_noun: str = ""             # product type for the broad search, e.g. "tv"


_YEARS = tuple(str(year) for year in range(2018, 2031))
_PEOPLE = ("men", "mens", "man", "women", "womens", "woman", "wmn", "unisex", "adult",
           "boys", "girls", "kids")

CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule("smartphone", "Smartphone", ("smartphones",),
                 ("flipkart", "croma"), ("ram_gb", "storage_gb"), "exact_words",
                 prefer=("colour",), search_noun="smartphone",
                 stop_words=("smartphone", "smartphones", "mobile", "phone")),
    CategoryRule("television", "Television", ("televisions",),
                 ("flipkart", "croma"), ("screen_inches",), "exact_words", search_noun="tv",
                 stop_words=("smart", "tv", "television", "led", "lcd", "uhd", "ultra", "hd", "4k",
                             "8k", "full", "ready", "tizen", "google", "android", "webos",
                             "edition", "model", "series", "star", *_YEARS)),
    CategoryRule("sneaker", "Sneakers", ("sneakers",),
                 ("flipkart", "myntra"), ("colour",), "name_score", search_noun="sneakers",
                 stop_words=("sneakers", "sneaker", "shoes", "shoe", "casual", "lace", "up",
                             "ups", "round", "toe", *_PEOPLE)),
    CategoryRule("top", "T-shirt, polo or jersey", ("t-shirts", "polos", "jerseys"),
                 ("flipkart", "myntra"), ("colour",), "name_score", search_noun="t-shirt",
                 stop_words=("t", "tee", "shirt", "shirts", "tshirt", "tshirts", "neck",
                             "collar", "pure", "cotton", "half", "sleeve", "sleeves",
                             *_PEOPLE)),
)


def find_rule(category_path: list[str],
              rules: tuple[CategoryRule, ...] = CATEGORY_RULES) -> CategoryRule | None:
    """Pick the rule whose path word appears in the product's deepest category.

    Only the last path element counts: "Shirts" under "T-shirts, Polos & Shirts"
    must not be taken for a T-shirt because of its parent's name.
    """
    if not category_path:
        return None
    deepest = category_path[-1].lower()
    for rule in rules:
        if any(word in deepest for word in rule.amazon_paths):
            return rule
    return None
