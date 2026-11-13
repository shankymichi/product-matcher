"""The one place that names concrete classes and wires them together."""

from __future__ import annotations

import app.attributes  # noqa: F401  (registers the attribute specs)
import app.matching    # noqa: F401  (registers the model matchers)
import app.platforms   # noqa: F401  (registers the platform adapters)
from app.attributes import all_attributes
from app.config import Settings
from app.fetch import CachedFetcher, PageFetcher
from app.fetch.playwright_fetcher import PlaywrightFetcher
from app.matching import Describer, MatchEngine, all_matchers
from app.platforms import build_platforms
from app.service import LookupService
from app.sources.amazon import AmazonReader
from app.tiebreak import NoTieBreaker, TieBreaker


def build_ai_tiebreaker(settings: Settings) -> TieBreaker | None:
    """The AI check, or None when no API key is set (the page then greys out the toggle)."""
    if not settings.ai_provider or not settings.ai_api_key or not settings.ai_model:
        return None
    from app.tiebreak import llm
    builders = {"gemini": llm.build_gemini, "anthropic": llm.build_anthropic}
    return builders[settings.ai_provider](settings.ai_api_key, settings.ai_model)


def build(settings: Settings) -> tuple[LookupService, PageFetcher]:
    fetcher = CachedFetcher(
        PlaywrightFetcher(timeout_s=settings.fetch_timeout_s, headless=settings.headless,
                          channel=settings.browser_channel),
        minutes=settings.cache_minutes)
    attributes = all_attributes()
    service = LookupService(
        readers=[AmazonReader(fetcher)],
        platforms=build_platforms(fetcher),
        engine=MatchEngine(attributes, all_matchers()),
        describer=Describer(attributes),
        tiebreaker=NoTieBreaker(),
        ai_tiebreaker=build_ai_tiebreaker(settings),
        max_candidates=settings.max_candidates,
        max_detail_reads=settings.max_detail_reads,
        max_stock_reads=settings.max_stock_reads)
    return service, fetcher
