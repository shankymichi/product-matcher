"""AI check: asks a language model whether near-miss candidates are the same product.

Only candidates the code has already accepted on brand and on every must-match
field reach this, so the model judges the product name alone. It is told that a
different variant or generation is a different product.

The question, the rules and the reading of answers are shared. Each provider
(Claude, Gemini) is a small backend that only sends the question and returns
the raw verdicts, so adding a provider never touches the matching logic.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from app.categories import CategoryRule
from app.models import Decision, Listing, Verdict

SYSTEM = """You decide whether shop listings are the same product as a reference product.

Rules:
- The brand and the required attributes have already been checked by code and agree.
  Judge only whether the product names refer to the same model.
- Treat as the SAME model: different word order, abbreviations, marketing words,
  the shop adding or dropping generic words such as "Smart", "LED", "Casual",
  "Sneakers", "For Men", "Ultra HD", or a series name written slightly differently.
- Treat as a DIFFERENT model: a different variant or tier (Pro, Plus, Ultra, Lite,
  Max, FE, Mini, Neo, Prime), a different generation or version (V1 vs V2, 2024 vs
  2025 when the model changed), a different series or line name, or a different
  product type.
- Answer "unsure" when the listing does not give enough to tell. Never guess "same".
- Keep each reason under 15 words."""

VERDICTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate": {"type": "integer", "description": "The candidate's number"},
                    "verdict": {"type": "string", "enum": ["same", "different", "unsure"]},
                    "reason": {"type": "string"},
                },
                "required": ["candidate", "verdict", "reason"],
            },
        },
    },
    "required": ["verdicts"],
}

_DECISIONS = {"same": Decision.MATCH, "different": Decision.MISMATCH,
              "unsure": Decision.UNCLEAR}


class LlmBackend(Protocol):
    """Sends one question to one provider and returns its raw verdict objects."""

    name: str   # shown on the page: "Claude" or "Gemini"

    async def verdicts(self, system: str, prompt: str) -> list[dict]: ...


# --- the shared question and answer handling ---------------------------------

def _describe(listing: Listing) -> dict[str, Any]:
    details: dict[str, Any] = {"title": listing.title}
    if listing.model_code:
        details["model_number"] = listing.model_code
    if listing.attributes:
        details["attributes"] = listing.attributes
    highlights = listing.specs.get("highlights")
    if highlights and highlights.strip() != listing.title:
        details["listing_text"] = " ".join(highlights.split())[:300]
    return details


def build_prompt(rule: CategoryRule, source: Listing, candidates: list[Listing]) -> str:
    payload = {
        "category": rule.label,
        "already_checked_by_code": ["brand", *rule.must_match],
        "reference_product": {"brand": source.brand, **_describe(source)},
        "candidates": [{"candidate": number, **_describe(listing)}
                       for number, listing in enumerate(candidates, start=1)],
    }
    return ("Is each candidate the same product as the reference product?\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=1))


def parse_verdicts(items: list[dict]) -> dict[int, Verdict]:
    answers: dict[int, Verdict] = {}
    for item in items:
        decision = _DECISIONS.get(str(item.get("verdict", "")).lower())
        number = item.get("candidate")
        if decision is not None and isinstance(number, int):
            answers[number] = Verdict(decision=decision, reason=str(item.get("reason", ""))[:200])
    return answers


class LlmTieBreaker:
    def __init__(self, backend: LlmBackend) -> None:
        self._backend = backend
        self._cache: dict[tuple[str, str], Verdict] = {}
        self.label = f"Basic + AI check ({backend.name})"

    async def judge(self, rule: CategoryRule, source: Listing,
                    candidates: list[Listing]) -> list[Verdict]:
        todo = [c for c in candidates if (source.url, c.url) not in self._cache]
        fresh: dict[str, Verdict] = {}
        if todo:
            items = await self._backend.verdicts(SYSTEM, build_prompt(rule, source, todo))
            answers = parse_verdicts(items)
            for number, listing in enumerate(todo, start=1):
                if number in answers:
                    # Same question, same answer: reused to save quota and time.
                    self._cache[(source.url, listing.url)] = answers[number]
                else:
                    # Skipped by the AI: not remembered, so it is asked again next time.
                    fresh[listing.url] = Verdict(decision=Decision.UNCLEAR, reason="no answer")
        return [self._cache.get((source.url, c.url)) or fresh[c.url] for c in candidates]


# --- providers ----------------------------------------------------------------

class AnthropicBackend:
    name = "Claude"
    _TOOL = {"name": "record_verdicts",
             "description": "Record one verdict for every candidate listing.",
             "input_schema": VERDICTS_SCHEMA}

    def __init__(self, client: Any, model: str, max_tokens: int = 1024) -> None:
        """`client` is an anthropic.AsyncAnthropic, or a stand-in in tests."""
        self._client, self._model, self._max_tokens = client, model, max_tokens

    async def verdicts(self, system: str, prompt: str) -> list[dict]:
        response = await self._client.messages.create(
            model=self._model, max_tokens=self._max_tokens, system=system,
            tools=[self._TOOL], tool_choice={"type": "tool", "name": self._TOOL["name"]},
            messages=[{"role": "user", "content": prompt}])
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"),
                     None)
        if block is None:
            raise ValueError("Claude returned no verdicts")
        return list(block.input.get("verdicts", []))


class GeminiBackend:
    name = "Gemini"

    def __init__(self, client: Any, model: str) -> None:
        """`client` is a google.genai.Client, or a stand-in in tests."""
        self._client, self._model = client, model

    async def verdicts(self, system: str, prompt: str) -> list[dict]:
        response = await self._client.aio.models.generate_content(
            model=self._model, contents=prompt,
            config={"system_instruction": system, "temperature": 0,
                    "response_mime_type": "application/json",
                    "response_json_schema": VERDICTS_SCHEMA})
        if not response.text:
            raise ValueError("Gemini returned no verdicts")
        return list(json.loads(response.text).get("verdicts", []))


def build_anthropic(api_key: str, model: str) -> LlmTieBreaker:
    from anthropic import AsyncAnthropic   # imported here so basic mode needs no SDK
    client = AsyncAnthropic(api_key=api_key, max_retries=2, timeout=30.0)
    return LlmTieBreaker(AnthropicBackend(client, model))


def build_gemini(api_key: str, model: str) -> LlmTieBreaker:
    from google import genai               # imported here so basic mode needs no SDK
    client = genai.Client(api_key=api_key, http_options={"timeout": 30_000})   # milliseconds
    return LlmTieBreaker(GeminiBackend(client, model))
