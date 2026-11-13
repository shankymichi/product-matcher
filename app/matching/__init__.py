"""Importing this package registers every built-in model matcher."""

from app.matching import exact_words, name_score  # noqa: F401  (registers on import)
from app.matching.base import ModelMatcher, all_matchers, register
from app.matching.describer import Describer
from app.matching.engine import MatchEngine

__all__ = ["Describer", "MatchEngine", "ModelMatcher", "all_matchers", "register"]
