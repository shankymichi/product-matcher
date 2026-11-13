"""An AttributeSpec knows one match field: how to find it and how to compare it."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from app.models import Decision


@runtime_checkable
class AttributeSpec(Protocol):
    name: str    # key in Listing.attributes and in CategoryRule.must_match
    label: str   # shown on the result card

    def extract(self, title: str, specs: Mapping[str, str]) -> Any | None:
        """Return the parsed value, or None when the listing does not state it."""

    def compare(self, source: Any, candidate: Any) -> Decision: ...

    def describe(self, value: Any) -> str:
        """Human-readable value for the result card: "256 GB"."""

    def search_text(self, value: Any) -> str:
        """The value as a shopper would type it into a search box: "12 GB RAM"."""


def compare_exact(source: Any, candidate: Any) -> Decision:
    if source is None or candidate is None:
        return Decision.UNCLEAR
    return Decision.MATCH if source == candidate else Decision.MISMATCH


def spec_value(specs: Mapping[str, str], include: tuple[str, ...],
               exclude: tuple[str, ...] = ()) -> str | None:
    """First spec whose key contains one of `include` and none of `exclude`."""
    for key, value in specs.items():
        low = key.lower()
        if any(word in low for word in include) and not any(word in low for word in exclude):
            return value
    return None


def free_text(title: str, specs: Mapping[str, str]) -> str:
    """Title plus the short highlight line some search results carry."""
    return f"{title} {specs.get('highlights', '')}"
