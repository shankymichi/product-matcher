"""The AI check: which candidates reach it, how answers are used, and failure handling."""

from types import SimpleNamespace

from app.attributes import all_attributes
from app.fetch import FakeFetcher
from app.matching import Describer, MatchEngine, all_matchers
from app.models import Decision, Fingerprint, PlatformResult, RawProduct, Status, Verdict
from app.platforms.flipkart import FlipkartAdapter
from app.service import LookupService
from app.tiebreak import NoTieBreaker
from app.tiebreak.llm import AnthropicBackend, GeminiBackend, LlmTieBreaker, build_prompt
from tests.conftest import FIXTURES, RULES, S25_ULTRA
from tests.test_service import FakeAmazon

SAMSUNG_TV = RawProduct(
    platform="amazon", url="https://www.amazon.in/dp/B0GYRRLP87", brand="Samsung",
    title=("Samsung 55 inch (138cm) Crystal UHD 4K Vision AI 2026 Smart TV | 30W Speakers | "
           "4K Upscaling | HDR10+ | UA55UE85AHULXL"),
    category_path=["Electronics", "Home Theater, TV & Video", "Televisions", "Smart Televisions"],
    specs={"Screen Size": "55 Inches", "model_code": "UA55UE85AHULXL"})

PUMA_SMASHIC = RawProduct(
    platform="amazon", url="https://www.amazon.in/dp/B0BSLKJPXV", brand="PUMA",
    title="Puma | Smashic Comfort Casual Sneakers",
    category_path=["Shoes & Handbags", "Shoes", "Men's Shoes", "Casual Shoes", "Sneakers"],
    specs={"Colour": "White-Matte Silver", "model_code": "39437102"})


class RecordingTieBreaker:
    """Says "same" for titles containing `accept`, and remembers what it was asked."""

    label = "Basic + AI check"

    def __init__(self, accept: str = "", fail: bool = False) -> None:
        self.accept, self.fail, self.asked = accept, fail, []

    async def judge(self, rule, source, candidates):
        self.asked.append([c.title for c in candidates])
        if self.fail:
            raise TimeoutError("no answer")
        return [Verdict(decision=Decision.MATCH if self.accept and self.accept in c.title
                        else Decision.MISMATCH, reason="same series")
                for c in candidates]


def service(product, pages, ai=None):
    return LookupService(
        readers=[FakeAmazon(product)], platforms={"flipkart": FlipkartAdapter(FakeFetcher(pages))},
        engine=MatchEngine(all_attributes(), all_matchers()),
        describer=Describer(all_attributes()), tiebreaker=NoTieBreaker(), ai_tiebreaker=ai)


async def run(svc, use_ai):
    events = [e async for e in svc.check("https://www.amazon.in/dp/X", use_ai=use_ai)]
    assert isinstance(events[0], Fingerprint)
    results = [e for e in events[1:] if isinstance(e, PlatformResult) and e.platform == "flipkart"]
    return events[0], results[0]


TV_PAGES = {"flipkart.com/search": FIXTURES / "flipkart_search_tv.html",
            "/p/": FIXTURES / "flipkart_product_s25.html"}          # any in-stock page
# Every Flipkart shoe page is served the real Smashic page: white, in stock.
SNEAKER_PAGES = {"flipkart.com/search": FIXTURES / "flipkart_search_sneaker.html",
                 "/p/": FIXTURES / "flipkart_product_smashic.html"}


async def test_exact_match_never_calls_the_ai():
    ai = RecordingTieBreaker(accept="Samsung")
    _, result = await run(service(S25_ULTRA, {
        "flipkart.com/search": FIXTURES / "flipkart_search_s25.html",
        "itm09d676ceb930d": FIXTURES / "flipkart_product_s25.html"}, ai), use_ai=True)
    assert result.status is Status.IN_STOCK and ai.asked == []


async def test_sneaker_with_a_shorter_name_is_found_only_with_the_ai_check():
    # Basic: "Smashic Sneakers For Men" is not word-for-word "Smashic Comfort", so not listed.
    _, basic = await run(service(PUMA_SMASHIC, SNEAKER_PAGES, RecordingTieBreaker()), use_ai=False)
    assert basic.status is Status.NOT_LISTED

    ai = RecordingTieBreaker(accept="Smashic Sneakers For Men")
    fingerprint, result = await run(service(PUMA_SMASHIC, SNEAKER_PAGES, ai), use_ai=True)
    assert fingerprint.matching == "Basic + AI check"
    assert result.status is Status.IN_STOCK
    assert result.matched_title == "PUMA Smashic Sneakers For Men"
    assert "AI check: same series" in result.reasons
    assert any("AI check" in n for n in result.notes)
    asked = ai.asked[0]
    assert "PUMA Smash Comfort Sneakers For Men" in asked        # 93% alike: the AI decides
    assert len(asked) <= 8


async def test_tv_exact_series_matches_in_code_and_notes_the_model_number():
    ai = RecordingTieBreaker()
    _, result = await run(service(SAMSUNG_TV, TV_PAGES, ai), use_ai=True)
    assert ai.asked == []                       # "Crystal 4K Vision AI" 55 inch: exact in code
    assert result.status is Status.IN_STOCK
    assert result.matched_title.startswith("Samsung Crystal 4K Vision AI 138 cm (55 inch)")
    assert any("UA55UE85AHULXL" in n and "UA55UE83AHULXL" in n for n in result.notes)


async def test_tv_near_misses_reach_the_ai_but_other_sizes_never_do():
    # No Flipkart listing is called "Crystal 4K Vision Plus", so code finds no exact match.
    vision_plus = RawProduct(**{**SAMSUNG_TV.model_dump(),
                                "title": "Samsung 138 cm (55 inches) Crystal 4K Vision Plus Smart TV",
                                "specs": {"Screen Size": "55 Inches"}})
    ai = RecordingTieBreaker()          # answers "different" to everything
    _, result = await run(service(vision_plus, TV_PAGES, ai), use_ai=True)
    asked = [title for call in ai.asked for title in call]
    assert any("Crystal 4K Vision AI 138 cm (55 inch)" in t for t in asked)   # close name
    assert not any("(43 inch)" in t for t in asked)                         # wrong size
    assert not any(t.startswith(("XIAOMI", "VZY")) for t in asked)           # wrong brand
    assert result.status is Status.NOT_LISTED


async def test_ai_failure_falls_back_to_basic_with_a_note():
    ai = RecordingTieBreaker(fail=True)
    _, result = await run(service(PUMA_SMASHIC, SNEAKER_PAGES, ai), use_ai=True)
    assert result.status is Status.NOT_LISTED
    assert any("AI check failed (TimeoutError)" in n for n in result.notes)


async def test_toggle_without_a_key_uses_basic_and_says_so():
    fingerprint, result = await run(service(PUMA_SMASHIC, SNEAKER_PAGES, ai=None), use_ai=True)
    assert fingerprint.matching == "Basic"
    assert "not set up" in fingerprint.notes[0]
    assert result.status is Status.NOT_LISTED


# --- the Anthropic client wrapper, with a stand-in client ---------------------

class FakeMessages:
    def __init__(self, verdicts):
        self.verdicts, self.calls = verdicts, []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="tool_use", input={"verdicts": self.verdicts})
        return SimpleNamespace(content=[block])


def listing(title, url):
    from app.models import Listing
    return Listing(platform="flipkart", url=url, title=title)


async def test_llm_tiebreaker_maps_answers_and_caches_them():
    messages = FakeMessages([
        {"candidate": 1, "verdict": "same", "reason": "same Smashic shoe"},
        {"candidate": 2, "verdict": "different", "reason": "Smash Comfort is another line"},
        {"candidate": 3, "verdict": "unsure", "reason": "too little detail"}])
    llm = LlmTieBreaker(AnthropicBackend(SimpleNamespace(messages=messages), "test-model"))
    source = Describer(all_attributes()).fingerprint(PUMA_SMASHIC, RULES["sneaker"]).source
    cands = [listing("PUMA Smashic Sneakers For Men", "a"),
             listing("PUMA Smash Comfort Sneakers For Men", "b"),
             listing("PUMA Smashic Sneakers For Women", "c")]

    verdicts = await llm.judge(RULES["sneaker"], source, cands)
    assert [v.decision for v in verdicts] == [Decision.MATCH, Decision.MISMATCH, Decision.UNCLEAR]
    assert verdicts[0].reason == "same Smashic shoe"

    call = messages.calls[0]
    assert call["model"] == "test-model"
    assert set(call) <= {"model", "max_tokens", "system", "tools", "tool_choice", "messages"}
    assert call["tool_choice"] == {"type": "tool", "name": "record_verdicts"}

    await llm.judge(RULES["sneaker"], source, cands)       # same question again
    assert len(messages.calls) == 1                         # answered from the cache


async def test_llm_tiebreaker_treats_a_missing_answer_as_unsure():
    messages = FakeMessages([{"candidate": 1, "verdict": "same", "reason": "ok"}])
    llm = LlmTieBreaker(AnthropicBackend(SimpleNamespace(messages=messages), "m"))
    source = Describer(all_attributes()).fingerprint(PUMA_SMASHIC, RULES["sneaker"]).source
    verdicts = await llm.judge(RULES["sneaker"], source,
                               [listing("one", "a"), listing("two", "b")])
    assert [v.decision for v in verdicts] == [Decision.MATCH, Decision.UNCLEAR]


def test_prompt_says_what_code_already_checked():
    source = Describer(all_attributes()).fingerprint(SAMSUNG_TV, RULES["television"]).source
    prompt = build_prompt(RULES["television"], source, [listing("Samsung Crystal 4K Vision", "a")])
    assert '"already_checked_by_code"' in prompt and "screen_inches" in prompt
    assert "UA55UE85AHULXL" in prompt and '"candidate": 1' in prompt


class FakeGeminiModels:
    def __init__(self, text):
        self.text, self.calls = text, []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text)


async def test_gemini_backend_asks_for_json_and_reads_it():
    import json
    models = FakeGeminiModels(json.dumps({"verdicts": [
        {"candidate": 1, "verdict": "same", "reason": "same Smashic shoe"},
        {"candidate": 2, "verdict": "different", "reason": "another line"}]}))
    llm = LlmTieBreaker(GeminiBackend(SimpleNamespace(aio=SimpleNamespace(models=models)),
                                      "gemini-test"))
    assert llm.label == "Basic + AI check (Gemini)"
    source = Describer(all_attributes()).fingerprint(PUMA_SMASHIC, RULES["sneaker"]).source
    verdicts = await llm.judge(RULES["sneaker"], source,
                               [listing("PUMA Smashic Sneakers For Men", "a"),
                                listing("PUMA Smash Comfort Sneakers For Men", "b")])
    assert [v.decision for v in verdicts] == [Decision.MATCH, Decision.MISMATCH]
    call = models.calls[0]
    assert call["model"] == "gemini-test"
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["temperature"] == 0 and "verdicts" in str(call["config"]["response_json_schema"])


async def test_gemini_empty_answer_is_an_error_so_basic_matching_is_used():
    import pytest
    llm = LlmTieBreaker(GeminiBackend(
        SimpleNamespace(aio=SimpleNamespace(models=FakeGeminiModels(""))), "g"))
    with pytest.raises(ValueError):
        await llm.judge(RULES["sneaker"], listing("x", "s"), [listing("y", "a")])


def test_provider_choice():
    from app.config import choose_provider
    assert choose_provider(None, "g-key", None) == "gemini"
    assert choose_provider(None, None, "a-key") == "anthropic"
    assert choose_provider(None, "g-key", "a-key") == "gemini"
    assert choose_provider("anthropic", "g-key", "a-key") == "anthropic"
    assert choose_provider("anthropic", "g-key", None) is None      # asked for, no key
    assert choose_provider(None, None, None) is None


def test_settings_read_a_gemini_key(monkeypatch):
    from app import config
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "AI_PROVIDER", "AI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "load_env_file", lambda: None)   # ignore any real .env
    monkeypatch.setenv("GEMINI_API_KEY", "abc123")
    settings = config.Settings.from_env()
    assert settings.ai_provider == "gemini" and settings.ai_api_key == "abc123"
    assert settings.ai_model == "gemini-3.5-flash"


def test_env_file_is_read(tmp_path, monkeypatch):
    from app.config import load_env_file
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("# comment\nGEMINI_API_KEY = \"from-file\"\n")
    load_env_file(env)
    import os
    assert os.environ["GEMINI_API_KEY"] == "from-file"
