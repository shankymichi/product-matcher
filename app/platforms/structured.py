"""Reads the schema.org product data many shops embed in their pages."""

from __future__ import annotations

import json
from typing import Any, Iterator

from selectolax.lexbor import LexborHTMLParser


def _walk(node: Any) -> Iterator[dict]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def product_data(tree: LexborHTMLParser) -> dict | None:
    """The first schema.org Product on the page that carries an offer."""
    for script in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text())
        except ValueError:
            continue
        for item in _walk(data):
            if item.get("@type") == "Product" or ("offers" in item and "name" in item):
                return item
    return None


def availability(product: dict) -> bool | None:
    """True for InStock, False for any other stated availability, None if unstated."""
    offers = product.get("offers")
    offers = offers[0] if isinstance(offers, list) and offers else offers
    stated = (offers or {}).get("availability") if isinstance(offers, dict) else None
    if not stated:
        return None
    return str(stated).rstrip("/").split("/")[-1].lower() == "instock"


def brand_name(product: dict) -> str | None:
    brand = product.get("brand")
    return brand.get("name") if isinstance(brand, dict) else brand
