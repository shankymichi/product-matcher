"""Run one lookup from the terminal:  python -m app.cli [--ai] <amazon link>"""

from __future__ import annotations

import asyncio
import sys

from app.config import Settings
from app.container import build
from app.errors import LookupFailure
from app.models import Fingerprint

WORDS = {"in_stock": "IN STOCK", "out_of_stock": "OUT OF STOCK",
         "not_listed": "NOT LISTED", "could_not_check": "COULD NOT CHECK"}


async def main(url: str, use_ai: bool) -> int:
    service, fetcher = build(Settings.from_env())
    try:
        async for event in service.check(url, use_ai=use_ai):
            if isinstance(event, Fingerprint):
                print(f"Product : {event.source.title}")
                print(f"Category: {event.category_label}")
                print(f"Looking : {event.source.brand} | {event.source.model} | "
                      f"{', '.join(event.matched_on)}")
                print(f"Matching: {event.matching}")
                for note in event.notes:
                    print(f"Note    : {note}")
                print()
                continue
            print(f"{event.label:<10}{WORDS[event.status.value]}")
            if event.url:
                print(f"          {event.matched_title}\n          {event.url}")
            if event.reasons:
                print(f"          matched on: {', '.join(event.reasons)}")
            for note in event.notes:
                print(f"          note: {note}")
            if event.error:
                print(f"          reason: {event.error}")
        return 0
    except LookupFailure as failure:
        print(f"Could not check: {failure.message}")
        return 1
    finally:
        await fetcher.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    use_ai = "--ai" in args
    links = [a for a in args if a != "--ai"]
    if len(links) != 1:
        raise SystemExit("usage: python -m app.cli [--ai] <amazon.in product link>")
    raise SystemExit(asyncio.run(main(links[0], use_ai)))
