"""A PageFetcher turns a URL into page content, or raises a clear error."""

from __future__ import annotations

from typing import Protocol

from app.models import Page


class PageFetcher(Protocol):
    async def fetch(self, url: str, wait_for: str | None = None) -> Page:
        """Load the page. `wait_for` is a CSS selector that real content has.

        Raises FetchBlocked or FetchTimeout.
        """

    async def close(self) -> None: ...
