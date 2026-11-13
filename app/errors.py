"""Typed failures. Each one becomes a "could not check" pop-up, never "not listed"."""

from __future__ import annotations


class LookupFailure(Exception):
    """Base class: `message` is safe to show to the user."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class FetchBlocked(LookupFailure):
    """The site refused the request (access denied, bot check, dropped connection)."""


class FetchTimeout(LookupFailure):
    """The site did not answer in time."""


class PageNotReadable(LookupFailure):
    """The page loaded but did not contain what the adapter expects."""


class UnsupportedLink(LookupFailure):
    """The link is not a supported product page or category."""
