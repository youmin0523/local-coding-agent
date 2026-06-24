"""Shared test helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


async def drain(agen: AsyncIterator[Any]) -> list[Any]:
    """Collect all items from an async generator into a list."""
    return [item async for item in agen]


def events_of(events: list[Any], type_name: str) -> list[Any]:
    """Filter agent events by their discriminator ``type``."""
    return [e for e in events if getattr(e, "type", None) == type_name]


def first_of(events: list[Any], type_name: str) -> Any | None:
    matches = events_of(events, type_name)
    return matches[0] if matches else None
