"""Fetches pages with a real browser, because these sites build pages with JavaScript."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Error, Playwright, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeout

from app.errors import FetchBlocked, FetchTimeout
from app.fetch.blocks import block_reason
from app.models import Page


class PlaywrightFetcher:
    def __init__(self, timeout_s: int = 20, headless: bool = False,
                 channel: str | None = "chrome", max_parallel: int = 4) -> None:
        self._timeout_ms = timeout_s * 1000
        self._headless = headless
        self._channel = channel
        self._slots = asyncio.Semaphore(max_parallel)
        self._start_lock = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def _ensure_started(self) -> BrowserContext:
        async with self._start_lock:
            if self._context is None:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=self._headless, channel=self._channel)
                self._context = await self._browser.new_context(
                    locale="en-IN", timezone_id="Asia/Kolkata",
                    viewport={"width": 1366, "height": 900})
        return self._context

    async def fetch(self, url: str, wait_for: str | None = None) -> Page:
        site = urlparse(url).netloc.removeprefix("www.")
        try:
            return await self._fetch_once(url, wait_for, site)
        except FetchTimeout:
            return await self._fetch_once(url, wait_for, site)   # one retry

    async def _fetch_once(self, url: str, wait_for: str | None, site: str) -> Page:
        context = await self._ensure_started()
        async with self._slots:
            page = await context.new_page()
            try:
                response = await page.goto(url, wait_until="domcontentloaded",
                                           timeout=self._timeout_ms)
                status = response.status if response else 0
                complete = True
                if wait_for:
                    try:
                        await page.wait_for_selector(wait_for, state="attached",
                                                     timeout=self._timeout_ms)
                    except PlaywrightTimeout:
                        # May be a genuine "no results" page (the adapter decides), or a
                        # page that was still loading. Either way it must not be cached.
                        complete = False
                text = await page.inner_text("body")
                reason = block_reason(status, text)
                if reason:
                    raise FetchBlocked(f"{site} blocked the request: {reason}")
                return Page(url=page.url, status=status, html=await page.content(),
                            complete=complete)
            except PlaywrightTimeout as exc:
                raise FetchTimeout(
                    f"{site} did not respond in {self._timeout_ms // 1000} seconds") from exc
            except Error as exc:   # e.g. net::ERR_HTTP2_PROTOCOL_ERROR
                raise FetchBlocked(f"{site} refused the connection") from exc
            finally:
                await page.close()

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._context = self._browser = self._playwright = None
