"""The few data types every layer passes around."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Status(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    NOT_LISTED = "not_listed"
    COULD_NOT_CHECK = "could_not_check"


class Decision(str, Enum):
    """The result of comparing one thing."""

    MATCH = "match"
    MISMATCH = "mismatch"
    UNCLEAR = "unclear"


class Page(BaseModel):
    url: str
    status: int
    html: str
    complete: bool = True   # False when the content we waited for never appeared


class RawProduct(BaseModel):
    """What a source reader lifts off the page, before any interpretation."""

    platform: str
    url: str
    title: str
    brand: str | None = None
    category_path: list[str] = Field(default_factory=list)
    specs: dict[str, str] = Field(default_factory=dict)


class Listing(BaseModel):
    """A product as one site shows it: the source product or a candidate."""

    platform: str
    url: str
    title: str
    brand: str | None = None
    model: str | None = None            # cleaned model name
    model_code: str | None = None       # model number or style code
    specs: dict[str, str] = Field(default_factory=dict)       # raw text from the page
    attributes: dict[str, Any] = Field(default_factory=dict)  # parsed match fields
    in_stock: bool | None = None        # known once the product page is read


class Fingerprint(BaseModel):
    category: str
    category_label: str = ""
    platforms: dict[str, str] = Field(default_factory=dict)   # name -> label, to be checked
    source: Listing
    search_queries: list[str]
    matched_on: list[str] = Field(default_factory=list)   # "RAM 12 GB", "Storage 256 GB"
    matching: str = "Basic"                                # which matching was used
    notes: list[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    decision: Decision
    score: float | None = None
    reasons: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)   # must-match fields not found yet
    # Which check rejected it: "brand", "attribute", "model_number" or "model_name".
    # Only a "model_name" rejection can be overturned by the AI check.
    failed_on: str | None = None


class Verdict(BaseModel):
    """A tie-breaker's answer about one candidate."""

    decision: Decision
    reason: str = ""


class PlatformResult(BaseModel):
    platform: str
    label: str
    status: Status
    url: str | None = None
    matched_title: str | None = None
    reasons: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    error: str | None = None            # the reason shown in the pop-up
