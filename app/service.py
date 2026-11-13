"""Orchestration: read the source product, then check every platform side by side."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Mapping, Sequence

from app.categories import CATEGORY_RULES, CategoryRule, find_rule
from app.errors import LookupFailure, UnsupportedLink
from app.matching.describer import Describer
from app.matching.engine import MatchEngine
from app.matching.normalise import brand_matches, codes_close, codes_equal
from app.models import Decision, Fingerprint, Listing, MatchResult, PlatformResult, Status
from app.platforms.base import PlatformAdapter
from app.sources.base import SourceReader
from app.tiebreak.base import TieBreaker


class PlatformChecker:
    """Finds the source product on one platform and reads its stock."""

    def __init__(self, adapter: PlatformAdapter, engine: MatchEngine, describer: Describer,
                 tiebreaker: TieBreaker, max_candidates: int = 40,
                 max_detail_reads: int = 5, max_stock_reads: int = 3,
                 near_misses: bool = False, near_miss_from: float = 40.0,
                 max_judged: int = 8) -> None:
        self._adapter = adapter
        self._engine = engine
        self._describer = describer
        self._tiebreaker = tiebreaker
        # With the AI check on, names the code rejected but that are close enough
        # are sent to it as well. Brand, attribute and number-word rejections never are.
        self._near_misses = near_misses
        self._near_miss_from = near_miss_from
        self._max_judged = max_judged
        self._ai_notes: list[str] = []
        self._max_candidates = max_candidates      # comparing a search result is free
        self._max_detail_reads = max_detail_reads  # opening a product page is not
        self._max_stock_reads = max_stock_reads

    async def check(self, rule: CategoryRule, fingerprint: Fingerprint) -> PlatformResult:
        try:
            return await self._check(rule, fingerprint)
        except LookupFailure as failure:   # blocked, timed out or unreadable
            return self._result(Status.COULD_NOT_CHECK, error=failure.message)

    async def _check(self, rule: CategoryRule, fingerprint: Fingerprint) -> PlatformResult:
        source = fingerprint.source
        pages: dict[str, Listing] = {}            # product pages read during this check
        seen: set[str] = set()
        matches: list[tuple[Listing, MatchResult]] = []

        unread: LookupFailure | None = None       # a candidate page that failed to load
        for query in fingerprint.search_queries:
            examined: list[list] = []              # [candidate, result] pairs
            for candidate in await self._new_candidates(query, rule, source, seen):
                result = self._engine.compare(rule, source, candidate)
                if (result.missing and self._could_match(result)
                        and len(pages) < self._max_detail_reads):
                    # A must-match field is not in the search result: read the product page.
                    try:
                        await self._add_page_details(candidate, rule, source, pages)
                    except LookupFailure as failure:
                        unread = unread or failure
                        continue
                    result = self._engine.compare(rule, source, candidate)
                examined.append([candidate, result])

            if source.model_code and not any(r.decision is Decision.MATCH for _, r in examined):
                unread = await self._look_up_model_numbers(rule, source, examined, pages) or unread

            to_judge: list[tuple[Listing, MatchResult]] = []
            for candidate, result in examined:
                if result.decision is Decision.MATCH:
                    matches.append((candidate, result))
                elif not result.missing and self._could_match(result):
                    to_judge.append((candidate, result))

            if not matches and to_judge:          # an exact match makes the AI check unneeded
                matches.extend(await self._judge(rule, source, to_judge))
            if matches:
                break                              # a later, broader query is not needed

        if not matches and unread:
            # A candidate could not be checked, so "not listed" would be a guess.
            raise unread

        if not matches:
            return self._result(Status.NOT_LISTED)

        # Identical model number first, then one differing only by a suffix, then the closest match (for example the same
        # colour), then the site's own order.
        matches.sort(key=lambda m: (not codes_equal(source.model_code, m[0].model_code),
                                    not codes_close(source.model_code, m[0].model_code),
                                    -self._engine.preference(rule, source, m[0])))
        return await self._read_stock(source, matches, pages)

    async def _look_up_model_numbers(self, rule: CategoryRule, source: Listing,
                                     examined: list[list], pages: dict[str, Listing]
                                     ) -> LookupFailure | None:
        """Names did not settle it, but the source has a model number: read candidates'
        product pages for theirs. Shops often name the same TV differently ("BRAVIA
        2M2" on Amazon, "BRAVIA 2 II" on Croma), and several listings can share one
        name with different model numbers, so the number is the reliable test."""
        failure = None
        waiting = sorted((e for e in examined if self._needs_model_number(e[0], e[1], pages)),
                         key=lambda e: -(e[1].score or 0))
        for entry in waiting:
            if len(pages) >= self._max_detail_reads:
                break
            try:
                await self._add_page_details(entry[0], rule, source, pages)
            except LookupFailure as exc:
                failure = failure or exc
                continue
            entry[1] = self._engine.compare(rule, source, entry[0])
        return failure

    @staticmethod
    def _needs_model_number(candidate: Listing, result: MatchResult,
                            pages: dict[str, Listing]) -> bool:
        return (result.decision is not Decision.MATCH and not result.missing
                and result.failed_on not in ("brand", "attribute", "model_number")
                and not candidate.model_code and candidate.url not in pages)

    def _could_match(self, result: MatchResult) -> bool:
        """Unclear, or (with the AI check on) rejected only because the name differs a bit.

        Brand, required-field and number-word rejections are final either way.
        """
        if result.decision is Decision.UNCLEAR:
            return True
        return (self._near_misses and result.decision is Decision.MISMATCH
                and result.failed_on == "model_name"
                and (result.score or 0) >= self._near_miss_from)

    async def _judge(self, rule: CategoryRule, source: Listing,
                     to_judge: list[tuple[Listing, MatchResult]]
                     ) -> list[tuple[Listing, MatchResult]]:
        to_judge = sorted(to_judge, key=lambda item: -(item[1].score or 0))[: self._max_judged]
        try:
            verdicts = await self._tiebreaker.judge(rule, source, [c for c, _ in to_judge])
        except Exception as exc:   # the AI check is optional: never fail the lookup over it
            self._ai_notes.append(f"AI check failed ({type(exc).__name__}); "
                                  "basic matching was used")
            return []
        confirmed = []
        for (candidate, result), verdict in zip(to_judge, verdicts):
            if verdict.decision is Decision.MATCH:
                result.decision = Decision.MATCH
                result.reasons = [r for r in result.reasons
                                  if not r.startswith(("model differs", "product name"))]
                result.reasons.append(f"AI check: {verdict.reason or 'same product'}")
                result.notes.append("Matched by the AI check: the names are not identical")
                confirmed.append((candidate, result))
        return confirmed

    async def _new_candidates(self, query: str, rule: CategoryRule, source: Listing,
                              seen: set[str]) -> list[Listing]:
        fresh = []
        for listing in await self._adapter.search(query):
            if listing.url in seen or not brand_matches(source.brand, listing):
                continue
            seen.add(listing.url)
            fresh.append(self._describer.fill(listing, rule, brand=source.brand))
            if len(seen) >= self._max_candidates:
                break
        return fresh

    async def _product(self, url: str, pages: dict[str, Listing]) -> Listing:
        if url not in pages:
            pages[url] = await self._adapter.read_product(url)
        return pages[url]

    async def _add_page_details(self, candidate: Listing, rule: CategoryRule,
                                source: Listing, pages: dict[str, Listing]) -> None:
        page = await self._product(candidate.url, pages)
        candidate.specs = {**candidate.specs, **page.specs,
                           "highlights": " | ".join(filter(None, [
                               candidate.specs.get("highlights"), page.title,
                               page.specs.get("highlights")]))}
        candidate.brand = candidate.brand or page.brand
        candidate.model_code = candidate.model_code or page.model_code
        self._describer.fill(candidate, rule, brand=source.brand)

    async def _read_stock(self, source: Listing, matches: list[tuple[Listing, MatchResult]],
                          pages: dict[str, Listing]) -> PlatformResult:
        out_of_stock: tuple[Listing, MatchResult] | None = None
        failure: LookupFailure | None = None
        for candidate, result in matches[: self._max_stock_reads]:
            try:
                page = await self._product(candidate.url, pages)
            except LookupFailure as exc:
                failure = failure or exc
                continue
            if not candidate.model_code and page.model_code:
                # The search result had no model number; the product page does.
                candidate.model_code = page.model_code
                note = self._engine.model_number_note(source, candidate)
                if note and note not in result.notes:
                    result.notes.append(note)
            if page.in_stock:
                return self._result(Status.IN_STOCK, candidate, result)
            out_of_stock = out_of_stock or (candidate, result)
        if out_of_stock:
            return self._result(Status.OUT_OF_STOCK, *out_of_stock)
        raise failure   # a match exists but no product page could be read

    def _result(self, status: Status, candidate: Listing | None = None,
                match: MatchResult | None = None, error: str | None = None) -> PlatformResult:
        notes = (list(match.notes) if match else []) + self._ai_notes
        stock_note = getattr(self._adapter, "stock_note", None)
        if stock_note and status in (Status.IN_STOCK, Status.OUT_OF_STOCK):
            notes.append(stock_note)
        return PlatformResult(
            platform=self._adapter.name, label=self._adapter.label, status=status,
            url=candidate.url if candidate else None,
            matched_title=candidate.title if candidate else None,
            reasons=match.reasons if match else [], notes=notes, error=error)


class LookupService:
    def __init__(self, readers: Sequence[SourceReader],
                 platforms: Mapping[str, PlatformAdapter], engine: MatchEngine,
                 describer: Describer, tiebreaker: TieBreaker,
                 rules: tuple[CategoryRule, ...] = CATEGORY_RULES,
                 max_candidates: int = 40, max_detail_reads: int = 5,
                 max_stock_reads: int = 3, ai_tiebreaker: TieBreaker | None = None) -> None:
        self._readers = readers
        self._platforms = platforms
        self._engine = engine
        self._describer = describer
        self._tiebreaker = tiebreaker              # used when the AI check is off
        self._ai_tiebreaker = ai_tiebreaker        # None when no API key is set
        self._rules = rules
        self._limits = (max_candidates, max_detail_reads, max_stock_reads)

    @property
    def ai_available(self) -> bool:
        return self._ai_tiebreaker is not None

    @property
    def ai_label(self) -> str | None:
        return self._ai_tiebreaker.label if self._ai_tiebreaker else None

    async def identify(self, url: str) -> tuple[CategoryRule, Fingerprint]:
        reader = next((r for r in self._readers if r.can_read(url)), None)
        if reader is None:
            raise UnsupportedLink("This is not an Amazon.in product link")
        raw = await reader.read(url)
        rule = find_rule(raw.category_path, self._rules)
        if rule is None:
            raise UnsupportedLink("This product's category is not supported")
        fingerprint = self._describer.fingerprint(raw, rule)
        fingerprint.category_label = rule.label
        fingerprint.platforms = {name: self._label(name) for name in rule.platforms}
        return rule, fingerprint

    def _label(self, name: str) -> str:
        adapter = self._platforms.get(name)
        return adapter.label if adapter else name.title()

    async def check(self, url: str, use_ai: bool = False
                    ) -> AsyncIterator[Fingerprint | PlatformResult]:
        """Yields the fingerprint first, then one result per platform as each finishes.

        `use_ai` asks for the AI check. It is ignored, with a note on the
        fingerprint, when no API key is set.
        """
        rule, fingerprint = await self.identify(url)
        ai = use_ai and self.ai_available
        tiebreaker = self._ai_tiebreaker if ai else self._tiebreaker
        fingerprint.matching = tiebreaker.label
        if use_ai and not ai:
            fingerprint.notes.append("The AI check is not set up (no API key), "
                                     "so basic matching was used")
        yield fingerprint
        tasks = [asyncio.create_task(self._check_platform(name, rule, fingerprint,
                                                          tiebreaker, ai))
                 for name in rule.platforms]
        for finished in asyncio.as_completed(tasks):
            yield await finished

    async def _check_platform(self, name: str, rule: CategoryRule, fingerprint: Fingerprint,
                              tiebreaker: TieBreaker, ai: bool) -> PlatformResult:
        adapter = self._platforms.get(name)
        if adapter is None:
            return PlatformResult(platform=name, label=self._label(name),
                                  status=Status.COULD_NOT_CHECK,
                                  error=f"{self._label(name)} is not set up yet")
        checker = PlatformChecker(adapter, self._engine, self._describer,
                                  tiebreaker, *self._limits, near_misses=ai)
        return await checker.check(rule, fingerprint)
