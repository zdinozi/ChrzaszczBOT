"""Persistent delivery history; manual commands never touch this state."""
from __future__ import annotations

import asyncio
import datetime as dt
import sqlite3
from collections.abc import Awaitable, Callable
from pathlib import Path

from free_games import FreeGame


class GameNotifications:
    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()

    async def publish_new(
        self, channel_id: int, games: list[FreeGame],
        send: Callable[[list[FreeGame]], Awaitable[None]],
        *, successful_sources: set[str] | None = None, now: dt.datetime | None = None,
    ) -> int:
        # One bot process owns this database. Serialize overlapping checks.
        async with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path)
            try:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS sent_games (
                        channel_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        offer_id TEXT NOT NULL,
                        sent_at TEXT NOT NULL,
                        PRIMARY KEY (channel_id, source, offer_id)
                    )
                """)
                # Upgrade existing history without losing delivery records.
                columns = {row[1] for row in connection.execute("PRAGMA table_info(sent_games)")}
                for column in ("ends_at", "missing_since"):
                    if column not in columns:
                        connection.execute(f"ALTER TABLE sent_games ADD COLUMN {column} TEXT")
                connection.commit()
                now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
                stamp = now.isoformat()
                sources = successful_sources if successful_sources is not None else {g.source for g in games}
                # Start absence only on a successful catalog read. Active entries
                # below clear it again before retention runs.
                for source in sources:
                    connection.execute(
                        "UPDATE sent_games SET missing_since = COALESCE(missing_since, ?) "
                        "WHERE channel_id = ? AND source = ?",
                        (stamp, str(channel_id), source),
                    )
                seen = set()
                new = []
                for game in games:
                    if not game.offer_id:
                        raise ValueError("Brak stabilnego identyfikatora oferty")
                    key = (game.source, game.offer_id)
                    if key in seen or (game.ends_at is not None and game.ends_at <= now):
                        continue
                    seen.add(key)
                    if game.source not in sources:
                        raise ValueError("Oferta ze źródła bez poprawnego pobrania")
                    if connection.execute(
                        "UPDATE sent_games SET ends_at = ?, missing_since = NULL "
                        "WHERE channel_id = ? AND source = ? AND offer_id = ?",
                        (game.ends_at.astimezone(dt.timezone.utc).isoformat() if game.ends_at else None,
                         str(channel_id), *key),
                    ).rowcount:
                        continue
                    new.append(game)
                for source in sources:
                    connection.execute(
                        "DELETE FROM sent_games WHERE channel_id = ? AND source = ? "
                        "AND missing_since IS NOT NULL AND ("
                        "(ends_at IS NOT NULL AND ends_at <= ?) OR "
                        "(ends_at IS NULL AND missing_since <= ?))",
                        (str(channel_id), source, (now - dt.timedelta(days=30)).isoformat(),
                         (now - dt.timedelta(days=90)).isoformat()),
                    )
                # Persist observed metadata even when there is nothing to send.
                connection.commit()
                if not new:
                    return 0
                # Confirm Discord delivery before recording it. On failure retry
                # at the next scheduled check; never silently lose notifications.
                await send(new)
                connection.executemany(
                    "INSERT INTO sent_games (channel_id, source, offer_id, sent_at, ends_at) VALUES (?, ?, ?, ?, ?)",
                    [(str(channel_id), g.source, g.offer_id, stamp,
                      g.ends_at.astimezone(dt.timezone.utc).isoformat() if g.ends_at else None) for g in new],
                )
                connection.commit()
                return len(new)
            finally:
                connection.close()
