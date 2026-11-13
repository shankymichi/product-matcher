"""Re-checks must re-check: the page cache never hides a fresh search."""

from types import SimpleNamespace

from app.fetch.cached import CachedFetcher
from app.models import Decision, Listing, Page
from app.tiebreak.llm import AnthropicBackend, LlmTieBreaker
from tests.conftest import RULES


class CountingFetcher:
    def __init__(self, complete: bool = True) -> None:
        self.calls, self.complete = 0, complete

    async def fetch(self, url, wait_for=None):
        self.calls += 1
        return Page(url=url, status=200, html=f"<p>{self.calls}</p>", complete=self.complete)

    async def close(self):
        return None


async def test_default_is_no_cache_so_every_lookup_reads_the_shop():
    inner = CountingFetcher()
    fetcher = CachedFetcher(inner)                 # default: 0 minutes
    await fetcher.fetch("https://shop/search?q=x")
    await fetcher.fetch("https://shop/search?q=x")
    assert inner.calls == 2


async def test_cache_reuses_complete_pages_when_turned_on():
    inner = CountingFetcher()
    fetcher = CachedFetcher(inner, minutes=30)
    await fetcher.fetch("u"); await fetcher.fetch("u")
    assert inner.calls == 1


async def test_half_loaded_page_is_never_cached():
    """A search page whose results never appeared (slow site) must not be reused,
    or every re-check for the next half hour would say "not listed"."""
    inner = CountingFetcher(complete=False)
    fetcher = CachedFetcher(inner, minutes=30)
    await fetcher.fetch("u"); await fetcher.fetch("u")
    assert inner.calls == 2


class OneAnswerMessages:
    """Answers only candidate 1, as an AI sometimes does."""

    def __init__(self):
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        block = SimpleNamespace(type="tool_use", input={"verdicts": [
            {"candidate": 1, "verdict": "same", "reason": "ok"}]})
        return SimpleNamespace(content=[block])


async def test_ai_skipped_candidate_is_asked_again_next_time():
    messages = OneAnswerMessages()
    llm = LlmTieBreaker(AnthropicBackend(SimpleNamespace(messages=messages), "m"))
    source = Listing(platform="amazon", url="s", title="Puma Smashic")
    one, two = Listing(platform="f", url="a", title="one"), Listing(platform="f", url="b", title="two")

    first = await llm.judge(RULES["sneaker"], source, [one, two])
    assert [v.decision for v in first] == [Decision.MATCH, Decision.UNCLEAR]
    await llm.judge(RULES["sneaker"], source, [one, two])
    assert messages.calls == 2          # "two" was asked again; "one" came from the cache
