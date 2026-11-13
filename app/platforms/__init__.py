"""Importing this package registers every built-in platform adapter."""

from app.platforms import croma, flipkart, myntra  # noqa: F401  (registers on import)
from app.platforms.base import PlatformAdapter, build_platforms, register_platform

__all__ = ["PlatformAdapter", "build_platforms", "register_platform"]
