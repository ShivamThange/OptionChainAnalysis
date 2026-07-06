"""Provider interface. Both Kite (real-time push) and NSE (poll) conform.

A provider's job is narrow: keep the LiveStore's underlying states populated
with fresh quotes. How it does so (websocket vs polling) is its own concern.
The provider does NOT compute metrics — that's the engine's job.
"""
from __future__ import annotations

import abc

from ..state import LiveStore


class MarketDataProvider(abc.ABC):
    name: str = "base"

    def __init__(self, store: LiveStore):
        self.store = store

    @abc.abstractmethod
    async def start(self, underlyings: list[str]) -> None:
        """Begin populating the store for these underlyings. Non-blocking:
        launches background tasks / websocket threads and returns."""

    @abc.abstractmethod
    async def stop(self) -> None:
        ...

    @abc.abstractmethod
    async def healthy(self) -> bool:
        """True if the provider currently has a live, non-stale connection."""
