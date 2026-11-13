"""Wraps any fetcher and reuses pages for a while.

Off by default (CACHE_MINUTES=0), so every lookup reads the shops afresh: stock
changes, and a re-check is expected to re-check. Only pages whose content fully
appeared are ever kept, so a slow, half-loaded page is never reused.
"""

from __future__ import annotations

import time

from app.fetch.base import PageFetcher
from app.models import Page


class CachedFetcher:
    def __init__(self, inner: PageFetcher, minutes: int = 0) -> None:
        self._inner = inner
        self._ttl = minutes * 60
        self._pages: dict[str, tuple[float, Page]] = {}

    async def fetch(self, url: str, wait_for: str | None = None) -> Page:
        if self._ttl <= 0:
            return await self._inner.fetch(url, wait_for)
        hit = self._pages.get(url)
        if hit and time.monotonic() - hit[0] < self._ttl:
            return hit[1]
        page = await self._inner.fetch(url, wait_for)
        if page.complete:                       # errors and half-loaded pages are not kept
            self._pages[url] = (time.monotonic(), page)
        return page

    async def close(self) -> None:
        await self._inner.close()
