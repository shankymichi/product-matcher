"""Importing this package registers every built-in attribute spec."""

from app.attributes import colour, memory, screen_size  # noqa: F401  (registers on import)
from app.attributes.base import AttributeSpec
from app.attributes.registry import all_attributes, register

__all__ = ["AttributeSpec", "all_attributes", "register"]
