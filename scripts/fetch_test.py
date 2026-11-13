"""Fetch test: can an automated browser load the pages the product matcher needs?

Loads one search page and one product page on each site with Playwright, checks
that the expected content is present, and reports any block (CAPTCHA, access
denied, empty page). Saves every page's HTML and a screenshot so the site
adapters can be built and unit-tested against real pages.

Setup (once):
    pip install playwright
    playwright install chromium

Run:
    python fetch_test.py              # headless Chromium
    python fetch_test.py --headed     # visible browser window
    python fetch_test.py --channel chrome   # use the installed Google Chrome
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from playwright.async_api import Browser, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeout

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# Text that marks a block page rather than real content.
BLOCK_PATTERNS = [
    r"enter the characters you see below",
    r"sorry, we just need to make sure you're not a robot",
    r"click the button below to continue shopping",
    r"access denied",
    r"you don't have permission to access",
    r"unusual traffic",
    r"are you a human",
    r"verify you are human",
    r"request blocked",
    r"pardon our interruption",
    r"site maintenance",
]


@dataclass(frozen=True)
class Target:
    site: str
    page: str  # "search" or "product"
    url: str
    selector: str  # an element that only real content has
    min_count: int = 1


TARGETS = [
    Target("amazon", "product", "https://www.amazon.in/dp/B0DSKNQW8F", "#productTitle"),
    Target(
        "flipkart",
        "search",
        "https://www.flipkart.com/search?q=samsung+galaxy+s25+ultra+5g+256+gb",
        'a[href*="/p/"]',
        5,
    ),
    Target(
        "flipkart",
        "product",
        "https://www.flipkart.com/samsung-galaxy-s25-ultra-5g-titanium-black-256-gb"
        "/p/itm09d676ceb930d?pid=MOBH8K8UVNGVNGKN",
        "h1",
    ),
    Target(
        "croma",
        "search",
        "https://www.croma.com/searchB?q=samsung%20galaxy%20s25%20ultra%3Arelevance"
        "&text=samsung%20galaxy%20s25%20ultra",
        'a[href*="/p/"]',
        3,
    ),
    Target(
        "croma",
        "product",
        "https://www.croma.com/samsung-galaxy-s25-ultra-5g-12gb-ram-256gb-titanium-silverblue-/p/313330",
        "h1",
    ),
    Target(
        "myntra",
        "search",
        "https://www.myntra.com/puma-smash-pop-sneakers?rawQuery=puma%20smash%20pop%20sneakers",
        "li.product-base",
        3,
    ),
    Target(
        "myntra",
        "product",
        "https://www.myntra.com/casual-shoes/puma/puma-smash-pop-men-round-toe-sneakers/30103226/buy",
        ".pdp-name",
    ),
]


@dataclass
class Outcome:
    site: str
    page: str
    result: str  # "ok", "blocked", "empty", "timeout", "error"
    http_status: int | None
    found: int
    seconds: float
    title: str
    detail: str


async def check(browser: Browser, target: Target, out_dir: Path, timeout_ms: int) -> Outcome:
    context = await browser.new_context(
        user_agent=USER_AGENT,
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        viewport={"width": 1366, "height": 900},
    )
    page = await context.new_page()
    started = time.monotonic()
    status: int | None = None
    found = 0
    title = ""
    result, detail = "error", ""
    try:
        response = await page.goto(target.url, wait_until="domcontentloaded", timeout=timeout_ms)
        status = response.status if response else None
        try:
            await page.wait_for_selector(target.selector, timeout=timeout_ms, state="attached")
        except PlaywrightTimeout:
            pass  # judged below from what the page actually holds
        found = await page.locator(target.selector).count()
        title = (await page.title())[:80]
        text = (await page.inner_text("body"))[:20000].lower()
        blocked = next((p for p in BLOCK_PATTERNS if re.search(p, text)), None)

        if blocked or status in (403, 429, 503):
            result, detail = "blocked", blocked or f"HTTP {status}"
        elif found >= target.min_count:
            result, detail = "ok", f"{found} x {target.selector}"
        else:
            result, detail = "empty", f"expected {target.selector}, found {found}"

        stem = f"{target.site}_{target.page}"
        (out_dir / f"{stem}.html").write_text(await page.content(), encoding="utf-8")
        await page.screenshot(path=str(out_dir / f"{stem}.png"))
    except PlaywrightTimeout:
        result, detail = "timeout", f"no response in {timeout_ms // 1000}s"
    except Exception as exc:  # report, do not crash the whole run
        result, detail = "error", str(exc).splitlines()[0][:120]
    finally:
        await context.close()
    return Outcome(
        target.site, target.page, result, status, found,
        round(time.monotonic() - started, 1), title, detail,
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument("--channel", default=None, help='browser channel, e.g. "chrome"')
    parser.add_argument("--timeout", type=int, default=20, help="seconds per page")
    parser.add_argument("--out", default="fetch_test_output", help="folder for saved pages")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not args.headed, channel=args.channel)
        outcomes = []
        for target in TARGETS:  # one at a time: a gentle request rate
            outcome = await check(browser, target, out_dir, args.timeout * 1000)
            outcomes.append(outcome)
            print(
                f"{outcome.site:<9}{outcome.page:<9}{outcome.result.upper():<9}"
                f"http={outcome.http_status!s:<5}{outcome.seconds:>5}s  {outcome.detail}"
            )
        await browser.close()

    (out_dir / "report.json").write_text(
        json.dumps([asdict(o) for o in outcomes], indent=2), encoding="utf-8"
    )
    passed = sum(o.result == "ok" for o in outcomes)
    print(f"\n{passed} of {len(outcomes)} pages loaded. Saved pages and report in {out_dir}/")
    return 0 if passed == len(outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
