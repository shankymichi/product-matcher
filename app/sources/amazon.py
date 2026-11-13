"""Reads an Amazon.in product page: title, brand, category path and spec tables."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from selectolax.lexbor import LexborHTMLParser

from app.errors import PageNotReadable
from app.fetch.base import PageFetcher
from app.models import RawProduct

_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)")
_MARKS = re.compile(r"[‎‏]")
_BYLINE = re.compile(r"^(?:Visit the (.+?) Store|Brand:\s*(.+))$", re.IGNORECASE)

# Spec rows that hold the maker's model number or style code, most specific first.
_MODEL_CODE_KEYS = ("model number", "item model number", "style number",
                    "manufacturer part number")


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", _MARKS.sub("", text or "")).strip()


def asin_of(url: str) -> str | None:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower().removeprefix("www.")
    match = _ASIN.search(parsed.path)
    return match.group(1) if host == "amazon.in" and match else None


class AmazonReader:
    def __init__(self, fetcher: PageFetcher) -> None:
        self._fetcher = fetcher

    def can_read(self, url: str) -> bool:
        return asin_of(url) is not None

    async def read(self, url: str) -> RawProduct:
        # Tracking parameters are dropped: only the product id is sent.
        clean_url = f"https://www.amazon.in/dp/{asin_of(url)}"
        page = await self._fetcher.fetch(clean_url, wait_for="#productTitle")
        return parse_product(page.html, clean_url)


def parse_product(html: str, url: str) -> RawProduct:
    tree = LexborHTMLParser(html)
    heading = tree.css_first("#productTitle")
    title = _clean(heading.text()) if heading else ""
    if not title:
        raise PageNotReadable("Amazon's product page could not be read")

    specs: dict[str, str] = {}
    for row in tree.css("#productOverview_feature_div tr, table.prodDetTable tr, #poExpander tr"):
        cells = row.css("th, td")
        if len(cells) >= 2:
            specs.setdefault(_clean(cells[0].text()), _clean(cells[1].text()))
    for item in tree.css("#detailBullets_feature_div li"):      # clothing and shoes
        key, _, value = _clean(item.text()).partition(":")
        if value:
            specs.setdefault(_clean(key), _clean(value))
    for fact in tree.css(".product-facts-detail"):
        key, value = fact.css_first(".a-col-left"), fact.css_first(".a-col-right")
        if key and value:
            specs.setdefault(_clean(key.text()), _clean(value.text()))

    lowered = {key.lower(): value for key, value in specs.items()}
    code = next((lowered[key] for key in _MODEL_CODE_KEYS if lowered.get(key)), None)
    if code:
        specs["model_code"] = code

    return RawProduct(
        platform="amazon", url=url, title=title,
        brand=lowered.get("brand") or lowered.get("brand name") or _byline_brand(tree),
        category_path=[_clean(a.text()) for a in
                       tree.css("#wayfinding-breadcrumbs_feature_div li a")],
        specs=specs)


def _byline_brand(tree: LexborHTMLParser) -> str | None:
    byline = tree.css_first("#bylineInfo")
    match = _BYLINE.match(_clean(byline.text())) if byline else None
    return (match.group(1) or match.group(2)) if match else None
