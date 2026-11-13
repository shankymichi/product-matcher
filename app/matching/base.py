"""A ModelMatcher decides whether two listings name the same model."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models import Listing, MatchResult


@runtime_checkable
class ModelMatcher(Protocol):
    name: str

    def compare(self, source: Listing, candidate: Listing) -> MatchResult: ...


_MATCHERS: dict[str, ModelMatcher] = {}


def register(matcher: ModelMatcher) -> ModelMatcher:
    _MATCHERS[matcher.name] = matcher
    return matcher


def all_matchers() -> dict[str, ModelMatcher]:
    return dict(_MATCHERS)
