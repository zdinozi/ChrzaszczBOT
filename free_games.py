from __future__ import annotations

import asyncio
import datetime as dt
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class FreeGame:
    title: str
    url: str
    ends_at: dt.datetime | None
    source: str = "Epic Games Store"
    platform: str | None = None
    requires_prime: bool = False


class GamesCache:
    """Cache one provider; failures are never cached or disguised as empty results."""

    def __init__(self, ttl: float = 900):
        self.ttl = ttl
        self._expires = 0.0
        self._games: list[FreeGame] = []
        self._lock = asyncio.Lock()

    async def get(self, fetch: Callable[[], Awaitable[list[FreeGame]]]) -> list[FreeGame]:
        async with self._lock:
            if time.monotonic() >= self._expires:
                games = await fetch()
                self._games = games
                self._expires = time.monotonic() + self.ttl
            now = dt.datetime.now(dt.timezone.utc)
            return [game for game in self._games if game.ends_at is None or now < game.ends_at]
