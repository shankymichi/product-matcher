"""A PlatformAdapter knows one shopping site's search and product pages."""

from __future__ import annotations

from typing import Callable, Protocol

from app.fetch.base import PageFetcher
from app.models import Listing


class PlatformAdapter(Protocol):
    name: str    # used in CategoryRule.platforms
    label: str   # shown on the result card
    # Optional: `stock_note`, a caveat about this site's stock shown on the card.

    async def search(self, query: str) -> list[Listing]:
        """Search results as listings, in the site's order."""

    async def read_product(self, url: str) -> Listing:
        """The product page as a listing, with `in_stock` set."""


AdapterFactory = Callable[[PageFetcher], PlatformAdapter]
_FACTORIES: dict[str, AdapterFactory] = {}


def register_platform(name: str) -> Callable[[AdapterFactory], AdapterFactory]:
    def decorator(factory: AdapterFactory) -> AdapterFactory:
        _FACTORIES[name] = factory
        return factory
    return decorator


def build_platforms(fetcher: PageFetcher) -> dict[str, PlatformAdapter]:
    return {name: factory(fetcher) for name, factory in _FACTORIES.items()}
