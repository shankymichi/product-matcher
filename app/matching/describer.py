"""Fills in a listing's model name and match fields, the same way for every site."""

from __future__ import annotations

from typing import Mapping

from app.attributes.base import AttributeSpec
from app.categories import CategoryRule
from app.matching.normalise import model_name, without_code
from app.models import Fingerprint, Listing, RawProduct


class Describer:
    def __init__(self, attributes: Mapping[str, AttributeSpec]) -> None:
        self._attributes = attributes

    def fill(self, listing: Listing, rule: CategoryRule, brand: str | None = None) -> Listing:
        """Set the model name and every field the rule compares or prefers."""
        if not listing.model:
            listing.model = without_code(
                model_name(listing.title, listing.brand or brand, rule.stop_words),
                listing.model_code)
        for name in (*rule.must_match, *rule.prefer):
            if listing.attributes.get(name) is None:
                value = self._attributes[name].extract(listing.title, listing.specs)
                if value is not None:
                    listing.attributes[name] = value
        return listing

    def fingerprint(self, raw: RawProduct, rule: CategoryRule) -> Fingerprint:
        source = self.fill(
            Listing(platform=raw.platform, url=raw.url, title=raw.title, brand=raw.brand,
                    model_code=raw.specs.get("model_code"), specs=raw.specs), rule)
        fields = [(self._attributes[n], source.attributes.get(n)) for n in rule.must_match]
        stated = [spec.search_text(value) for spec, value in fields if value is not None]
        base = f"{raw.brand or ''} {source.model}".strip().lower()
        brand = (raw.brand or "").lower()
        queries = [
            f"{base} {' '.join(stated)}".strip().lower(),           # model + required fields
            base,                                                  # model only
            # Broad: brand + required fields + product type. Shop searches sometimes
            # miss a model name entirely (Croma finds no Sony TV for "sony bravia 3"),
            # so this lets the model check decide among the brand's listings.
            f"{brand} {' '.join(stated)} {rule.search_noun}".strip().lower(),
        ]
        return Fingerprint(
            category=rule.key, source=source,
            search_queries=list(dict.fromkeys(queries)),
            matched_on=[f"{spec.label} {spec.describe(value)}"
                        for spec, value in fields if value is not None])
