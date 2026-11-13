"""Croma: search results and product pages."""

from __future__ import annotations

import re
from urllib.parse import quote

from selectolax.lexbor import LexborHTMLParser

from app.errors import PageNotReadable
from app.fetch.base import PageFetcher
from app.models import Listing
from app.platforms.base import register_platform

BASE = "https://www.croma.com"
_UNAVAILABLE = re.compile(
    r"not available (?:for|at) (?:your )?pincode|out of stock|sold out|notify me"
    r"|currently unavailable|coming soon", re.I)
_BUYABLE = re.compile(r"^(?:buy now|add to cart)$", re.I)


class CromaAdapter:
    name = "croma"
    label = "Croma"
    stock_note = "Croma's stock depends on the pincode; this is what the site shows by default"

    def __init__(self, fetcher: PageFetcher) -> None:
        self._fetcher = fetcher

    async def search(self, query: str) -> list[Listing]:
        encoded = quote(query)
        page = await self._fetcher.fetch(
            f"{BASE}/searchB?q={encoded}%3Arelevance&text={encoded}",
            wait_for="li.product-item")
        return parse_search(page.html)

    async def read_product(self, url: str) -> Listing:
        page = await self._fetcher.fetch(url, wait_for="h1")
        return parse_product(page.html, url)


def parse_search(html: str) -> list[Listing]:
    tree = LexborHTMLParser(html)
    listings: dict[str, Listing] = {}
    for item in tree.css("li.product-item"):
        heading, link = item.css_first("h3"), item.css_first('a[href*="/p/"]')
        if not heading or not link:
            continue
        path = (link.attributes.get("href") or "").split("?")[0]
        text = item.text(separator=" | ")
        listings.setdefault(path, Listing(
            platform="croma", url=f"{BASE}{path}", title=heading.text(strip=True),
            in_stock=False if _UNAVAILABLE.search(text) else None))
    return list(listings.values())


def parse_product(html: str, url: str) -> Listing:
    tree = LexborHTMLParser(html)
    heading = tree.css_first("h1")
    title = heading.text(strip=True) if heading else ""
    if not title:
        raise PageNotReadable("Croma's product page could not be read")
    body = tree.body.text(separator=" ") if tree.body else ""
    buttons = [button.text(strip=True) for button in tree.css("button")]
    specs = spec_table(tree)
    return Listing(platform="croma", url=url, title=title, brand=specs.get("Brand"),
                   model_code=specs.get("Model Number"), specs=specs,
                   in_stock=stock_from(body, buttons))


def spec_table(tree: LexborHTMLParser) -> dict[str, str]:
    """Croma lists specs as a label <li> followed by its value <li>."""
    specs: dict[str, str] = {}
    for label in tree.css("li.cp-specification-spec-title"):
        value = label.next
        while value is not None and value.tag == "-text":
            value = value.next
        if value is not None and "cp-specification-spec-details" in (value.attributes.get("class") or ""):
            key, text = label.text(strip=True), value.text(strip=True)
            if key and text:
                specs.setdefault(key, text)
    return specs


def stock_from(body_text: str, button_labels: list[str]) -> bool:
    """Croma keeps its buy buttons even when a product cannot be delivered,
    so an unavailable notice always wins over the buttons."""
    if _UNAVAILABLE.search(body_text):
        return False
    return any(_BUYABLE.match(label) for label in button_labels)


@register_platform("croma")
def _build(fetcher: PageFetcher) -> CromaAdapter:
    return CromaAdapter(fetcher)
