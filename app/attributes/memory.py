"""RAM and storage, both parsed to whole GB."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.attributes.base import compare_exact, free_text, spec_value
from app.attributes.registry import register
from app.models import Decision

# "12 GB RAM", "256GB", "1 TB"; group 3 is set when the size is labelled as RAM.
_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*(GB|TB)\b(\s*(?:of\s+)?RAM\b)?", re.IGNORECASE)


def sizes(text: str) -> list[tuple[int, bool]]:
    """Every size in the text as (gigabytes, is_labelled_ram)."""
    found = []
    for number, unit, ram in _SIZE.findall(text):
        gb = float(number) * (1024 if unit.lower() == "tb" else 1)
        found.append((int(round(gb)), bool(ram)))
    return found


class RamSpec:
    name = "ram_gb"
    label = "RAM"

    def extract(self, title: str, specs: Mapping[str, str]) -> Any | None:
        stated = spec_value(specs, ("ram",))
        if stated and sizes(stated):
            return sizes(stated)[0][0]
        return next((gb for gb, is_ram in sizes(free_text(title, specs)) if is_ram), None)

    def compare(self, source: Any, candidate: Any) -> Decision:
        return compare_exact(source, candidate)

    def describe(self, value: Any) -> str:
        return f"{value} GB"

    def search_text(self, value: Any) -> str:
        return f"{value} GB RAM"


class StorageSpec:
    name = "storage_gb"
    label = "Storage"

    def extract(self, title: str, specs: Mapping[str, str]) -> Any | None:
        stated = spec_value(specs, ("storage capacity", "internal storage", "rom"),
                            exclude=("ram", "maximum", "expandable"))
        if stated and sizes(stated):
            return sizes(stated)[0][0]
        # In a title the first size not labelled RAM is the storage.
        return next((gb for gb, is_ram in sizes(free_text(title, specs)) if not is_ram), None)

    def compare(self, source: Any, candidate: Any) -> Decision:
        return compare_exact(source, candidate)

    def describe(self, value: Any) -> str:
        return f"{value // 1024} TB" if value >= 1024 and value % 1024 == 0 else f"{value} GB"

    def search_text(self, value: Any) -> str:
        return self.describe(value)


register(RamSpec())
register(StorageSpec())
