"""Myntra: search results and product pages, read from the data Myntra embeds in the page."""

from __future__ import annotations

import json
import re
from urllib.parse import quote

from selectolax.lexbor import LexborHTMLParser

from app.errors import PageNotReadable
from app.fetch.base import PageFetcher
from app.models import Listing
from app.platforms.base import register_platform
from app.platforms.structured import availability, product_data

BASE = "https://www.myntra.com"
_PAGE_DATA = re.compile(r"window\.__myx\s*=\s*(\{.*\})\s*;?\s*$", re.S)


class MyntraAdapter:
    name = "myntra"
    label = "Myntra"

    def __init__(self, fetcher: PageFetcher) -> None:
        self._fetcher = fetcher

    async def search(self, query: str) -> list[Listing]:
        slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        page = await self._fetcher.fetch(f"{BASE}/{slug}?rawQuery={quote(query)}",
                                         wait_for="li.product-base")
        return parse_search(page.html)

    async def read_product(self, url: str) -> Listing:
        page = await self._fetcher.fetch(url, wait_for=".pdp-name")
        return parse_product(page.html, url)


def _page_data(tree: LexborHTMLParser) -> dict:
    for script in tree.css("script"):
        text = (script.text() or "").strip()
        if text.startswith("window.__myx"):
            match = _PAGE_DATA.match(text)
            if match:
                try:
                    return json.loads(match.group(1))
                except ValueError:
                    return {}
    return {}


def parse_search(html: str) -> list[Listing]:
    products = (_page_data(LexborHTMLParser(html)).get("searchData", {})
                .get("results", {}).get("products", []))
    listings = []
    for product in products:
        name, path = product.get("productName"), product.get("landingPageUrl")
        if not name or not path:
            continue
        sizes = product.get("inventoryInfo") or []
        listings.append(Listing(
            platform="myntra", url=f"{BASE}/{path.lstrip('/')}", title=name,
            brand=product.get("brand"),
            specs={"colour": product.get("primaryColour") or ""},
            in_stock=any(size.get("available") for size in sizes) if sizes else None))
    return listings


def parse_product(html: str, url: str) -> Listing:
    tree = LexborHTMLParser(html)
    data = _page_data(tree).get("pdpData")
    if data:
        sizes = data.get("sizes") or []
        sold_out = bool((data.get("flags") or {}).get("outOfStock"))
        # In stock when at least one size can be bought.
        in_stock = not sold_out and any(size.get("available") for size in sizes)
        return Listing(platform="myntra", url=url, title=data.get("name", ""),
                       brand=(data.get("brand") or {}).get("name"),
                       specs={"colour": data.get("baseColour") or ""}, in_stock=in_stock)

    product = product_data(tree)      # fallback: the schema.org block
    if not product or not product.get("name"):
        raise PageNotReadable("Myntra's product page could not be read")
    brand = product.get("brand")
    return Listing(platform="myntra", url=url, title=product["name"],
                   brand=brand.get("name") if isinstance(brand, dict) else brand,
                   in_stock=bool(availability(product)))


@register_platform("myntra")
def _build(fetcher: PageFetcher) -> MyntraAdapter:
    return MyntraAdapter(fetcher)
