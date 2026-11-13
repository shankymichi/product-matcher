"""Serves saved pages, so adapters and the service are tested without the network."""

from __future__ import annotations

from pathlib import Path

from app.errors import LookupFailure, PageNotReadable
from app.models import Page


class FakeFetcher:
    def __init__(self, pages: dict[str, Path | LookupFailure]) -> None:
        """`pages` maps a URL fragment to a saved HTML file, or to an error to raise."""
        self._pages = pages
        self.requested: list[str] = []

    async def fetch(self, url: str, wait_for: str | None = None) -> Page:
        self.requested.append(url)
        for fragment, answer in self._pages.items():
            if fragment in url:
                if isinstance(answer, LookupFailure):
                    raise answer
                return Page(url=url, status=200, html=Path(answer).read_text(encoding="utf-8"))
        raise PageNotReadable(f"no saved page for {url}")

    async def close(self) -> None:
        return None
