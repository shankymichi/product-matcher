"""A SourceReader reads the product the user pasted."""

from __future__ import annotations

from typing import Protocol

from app.models import RawProduct


class SourceReader(Protocol):
    def can_read(self, url: str) -> bool: ...

    async def read(self, url: str) -> RawProduct: ...
