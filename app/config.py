"""Settings read once at startup. Everything has a default, so no setup is required."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Read KEY=value lines from .env. Values already set in the environment win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


DEFAULT_MODELS = {"gemini": "gemini-3.5-flash", "anthropic": "claude-haiku-5-5"}


def choose_provider(requested: str | None, gemini_key: str | None,
                    anthropic_key: str | None) -> str | None:
    """AI_PROVIDER wins when its key is set; otherwise whichever key exists, Gemini first."""
    keys = {"gemini": gemini_key, "anthropic": anthropic_key}
    wanted = (requested or "").strip().lower()
    if wanted in keys:
        return wanted if keys[wanted] else None
    return next((name for name, key in keys.items() if key), None)


@dataclass(frozen=True)
class Settings:
    ai_provider: str | None = None          # "gemini", "anthropic" or None (AI check off)
    ai_api_key: str | None = None
    ai_model: str | None = None
    fetch_timeout_s: int = 20
    cache_minutes: int = 0       # 0: every lookup reads the shops afresh
    headless: bool = False              # Croma and Myntra reject a headless browser
    browser_channel: str | None = "chrome"   # the installed Google Chrome
    max_candidates: int = 40     # search results compared per platform
    max_detail_reads: int = 5    # product pages opened to find a missing field
    max_stock_reads: int = 3     # matched product pages opened to read stock

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None
        anthropic_key = os.getenv("ANTHROPIC_API_KEY") or None
        provider = choose_provider(os.getenv("AI_PROVIDER"), gemini_key, anthropic_key)
        return cls(
            ai_provider=provider,
            ai_api_key={"gemini": gemini_key, "anthropic": anthropic_key}.get(provider or ""),
            ai_model=(os.getenv("AI_MODEL") or DEFAULT_MODELS.get(provider or "")) if provider
            else None,
            fetch_timeout_s=int(os.getenv("FETCH_TIMEOUT_S", "20")),
            cache_minutes=int(os.getenv("CACHE_MINUTES", "0")),
            headless=_flag("HEADLESS", default=False),
            browser_channel=os.getenv("BROWSER_CHANNEL", "chrome") or None,
        )
