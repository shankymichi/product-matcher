"""Attribute specs by name. Config refers to them as strings such as "colour"."""

from __future__ import annotations

from app.attributes.base import AttributeSpec

_ATTRIBUTES: dict[str, AttributeSpec] = {}


def register(spec: AttributeSpec) -> AttributeSpec:
    _ATTRIBUTES[spec.name] = spec
    return spec


def all_attributes() -> dict[str, AttributeSpec]:
    return dict(_ATTRIBUTES)
