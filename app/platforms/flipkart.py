"""Flipkart: search results and product pages."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, quote_plus, urlparse

from selectolax.lexbor import LexborHTMLParser

from app.errors import PageNotReadable
from app.fetch.base import PageFetcher
from app.models import Listing
from app.platforms.base import register_platform
from app.platforms.structured import availability, brand_name, product_data

BASE = "https://www.flipkart.com"
_UNAVAILABLE = re.compile(r"currently unavailable|sold out|coming soon|notify me", re.I)
_BUYABLE = re.compile(r"buy now|add to cart", re.I)
_MODEL_ID = re.compile(r"Model ID:\s*([A-Za-z0-9\-/]+)")


class FlipkartAdapter:
    name = "flipkart"
    label = "Flipkart"

    def __init__(self, fetcher: PageFetcher) -> None:
        self._fetcher = fetcher

    async def search(self, query: str) -> list[Listing]:
        page = await self._fetcher.fetch(f"{BASE}/search?q={quote_plus(query)}",
                                         wait_for='a[href*="/p/"]')
        return parse_search(page.html)

    async def read_product(self, url: str) -> Listing:
        page = await self._fetcher.fetch(url, wait_for="h1")
        return parse_product(page.html, url)


def parse_search(html: str) -> list[Listing]:
    """Flipkart has two result layouts.

    Electronics: one link per product whose image alt text is the full title.
    Fashion: the link's `title` attribute is the product name, and the brand is
    the first line of the surrounding card.
    """
    tree = LexborHTMLParser(html)
    listings: dict[str, Listing] = {}
    for anchor in tree.css('a[href*="/p/"]'):
        parsed = urlparse(anchor.attributes.get("href") or "")
        product_id = parse_qs(parsed.query).get("pid", [None])[0]
        if not product_id or product_id in listings:
            continue
        alt = next((img.attributes.get("alt") for img in anchor.css("img")
                    if img.attributes.get("alt")), None)
        name = anchor.attributes.get("title")
        brand = None
        if alt:
            title, text = alt.strip(), anchor.text(separator=" | ")
        elif name and anchor.parent is not None:
            text = anchor.parent.text(separator=" | ")
            brand = text.split("|")[0].strip() or None
            title = f"{brand} {name.strip()}" if brand else name.strip()
        else:
            continue
        model_id = _MODEL_ID.search(text)
        listings[product_id] = Listing(
            platform="flipkart",
            url=f"{BASE}{parsed.path}?pid={product_id}",
            title=title, brand=brand,
            model_code=model_id.group(1) if model_id else None,
            specs={"highlights": text},
            in_stock=False if _UNAVAILABLE.search(text) else None)
    return list(listings.values())


def parse_product(html: str, url: str) -> Listing:
    tree = LexborHTMLParser(html)
    heading = tree.css_first("h1")
    product = product_data(tree) or {}
    title = (heading.text(strip=True) if heading else "") or product.get("name", "")
    if not title:
        raise PageNotReadable("Flipkart's product page could not be read")

    in_stock = availability(product)
    if in_stock is None:   # no structured data: fall back to the buy button
        body = tree.body.text(separator=" ") if tree.body else ""
        in_stock = False if _UNAVAILABLE.search(body) else bool(_BUYABLE.search(body))

    specs = {"highlights": str(product.get("description", ""))}
    if product.get("color"):
        specs["colour"] = str(product["color"])
    return Listing(platform="flipkart", url=url, title=title, brand=brand_name(product),
                   specs=specs, in_stock=in_stock)


@register_platform("flipkart")
def _build(fetcher: PageFetcher) -> FlipkartAdapter:
    return FlipkartAdapter(fetcher)
