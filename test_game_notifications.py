import asyncio
import datetime as dt
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import main
from free_games import FreeGame
from game_notifications import GameNotifications
from prime_games import PrimeGamesError


def game(identity="one", source="Epic Games Store"):
    return FreeGame("Gra", "https://example.com/game", None, source=source,
                    requires_prime=source == "Amazon Prime", offer_id=identity)


class NotificationsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state" / "games.sqlite3"
        self.history = GameNotifications(self.path)
        self.send = AsyncMock()

    async def test_first_run_restart_and_only_new_games(self):
        first = game()
        self.assertEqual(await self.history.publish_new(123, [first, first], self.send), 1)
        self.send.assert_awaited_once_with([first])
        # A restart and changed title/end time must not announce the same ID again.
        history = GameNotifications(self.path)
        changed = replace(first, title="Nowy tytuł", ends_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7))
        self.assertEqual(await history.publish_new(123, [changed], self.send), 0)
        new = game("two")
        self.assertEqual(await history.publish_new(123, [changed, new], self.send), 1)
        self.send.assert_awaited_with([new])
        self.assertEqual(self.send.await_count, 2)

    async def test_empty_or_missing_game_does_not_erase_history(self):
        await self.history.publish_new(123, [game()], self.send)
        await self.history.publish_new(123, [], self.send)
        await self.history.publish_new(123, [game()], self.send)
        self.send.assert_awaited_once()

    async def test_source_and_channel_are_independent(self):
        await self.history.publish_new(123, [game(), game(source="Amazon Prime")], self.send)
        self.assertEqual(len(self.send.call_args.args[0]), 2)
        self.assertEqual(await self.history.publish_new(456, [game()], self.send), 1)

    async def test_failed_delivery_can_be_retried(self):
        self.send.side_effect = RuntimeError("Discord unavailable")
        with self.assertRaises(RuntimeError):
            await self.history.publish_new(123, [game()], self.send)
        self.send.side_effect = None
        self.assertEqual(await GameNotifications(self.path).publish_new(123, [game()], self.send), 1)

    async def test_concurrent_checks_send_once(self):
        counts = await asyncio.gather(*[
            self.history.publish_new(123, [game()], self.send) for _ in range(2)
        ])
        self.assertEqual(counts, [1, 0])
        self.send.assert_awaited_once()

    async def test_expired_game_is_not_sent(self):
        expired = replace(game(), ends_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1))
        self.assertEqual(await self.history.publish_new(123, [expired], self.send), 0)
        self.send.assert_not_awaited()

    async def test_corrupt_history_fails_closed(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b"not a sqlite database")
        with self.assertRaises(sqlite3.DatabaseError):
            await self.history.publish_new(123, [game()], self.send)
        self.send.assert_not_awaited()
        self.assertEqual(self.path.read_bytes(), b"not a sqlite database")

    async def test_daily_fetch_failure_and_recovery(self):
        channel = AsyncMock()
        channel.id = 123
        with patch.object(main, "game_notifications", self.history), \
                patch.object(main, "fetch_free_games", AsyncMock(return_value=[game()])), \
                patch.object(main, "fetch_prime_games", AsyncMock(side_effect=PrimeGamesError())), \
                self.assertLogs(main.logger, level="ERROR"):
            await main.publish_new_games(channel)
        channel.send.assert_awaited_once()
        self.assertNotIn("wait", channel.send.call_args.kwargs)
        with patch.object(main, "game_notifications", GameNotifications(self.path)), \
                patch.object(main, "fetch_free_games", AsyncMock(return_value=[game()])), \
                patch.object(main, "fetch_prime_games", AsyncMock(return_value=[game(source="Amazon Prime")])):
            channel.reset_mock()
            await main.publish_new_games(channel)
            channel.send.assert_awaited_once()
            self.assertIn("Amazon Prime", channel.send.call_args.kwargs["content"])
            channel.reset_mock()
            await main.publish_new_games(channel)
            channel.send.assert_not_awaited()

    async def test_daily_pagination_uses_channel_send(self):
        channel = AsyncMock()
        channel.id = 123
        with patch.object(main, "game_notifications", self.history), \
                patch.object(main, "fetch_free_games", AsyncMock(return_value=[game(str(i)) for i in range(7)])), \
                patch.object(main, "fetch_prime_games", AsyncMock(return_value=[])):
            await main.publish_new_games(channel)
        channel.send.assert_awaited_once()
        self.assertNotIn("wait", channel.send.call_args.kwargs)
        view = channel.send.call_args.kwargs["view"]
        self.addCleanup(view.stop)
        self.assertEqual(len(view.pages), 2)

    async def test_scheduler_survives_failure(self):
        with patch.object(main, "find_games_channel", return_value=AsyncMock()), \
                patch.object(main, "publish_new_games", AsyncMock(side_effect=RuntimeError("failure"))), \
                self.assertLogs(main.logger, level="ERROR"):
            await main.daily_games()
        self.assertEqual(main.daily_games.time, [main.POST_TIME])
        self.assertEqual(main.POST_TIME.hour, 18)
        self.assertEqual(str(main.POST_TIME.tzinfo), "Europe/Warsaw")

    def test_channel_selection_is_separate_from_pepper(self):
        games_channel = MagicMock(spec=discord.TextChannel)
        games_channel.name = "tvgry"
        pepper_channel = MagicMock(spec=discord.TextChannel)
        pepper_channel.name = "promocje"
        with patch.dict("os.environ", {"DISCORD_CHANNEL_ID": "999"}, clear=True), \
                patch.object(main.client, "get_all_channels", return_value=[pepper_channel, games_channel]):
            self.assertIs(main.find_games_channel(), games_channel)
        with patch.dict("os.environ", {"DISCORD_GAMES_CHANNEL_ID": "123"}, clear=True), \
                patch.object(main.client, "get_channel", return_value=games_channel) as lookup:
            self.assertIs(main.find_games_channel(), games_channel)
            lookup.assert_called_once_with(123)
        with patch.dict("os.environ", {}, clear=True), \
                patch.object(main.client, "get_all_channels", return_value=[games_channel, games_channel]):
            self.assertIsNone(main.find_games_channel())

    async def test_retention_expired_and_returning_offer(self):
        now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        item = replace(game(), ends_at=now + dt.timedelta(days=1))
        await self.history.publish_new(123, [item], self.send, now=now)
        async def check(day, sources):
            await self.history.publish_new(123, [], self.send, now=now + dt.timedelta(days=day),
                                           successful_sources=sources)
            with sqlite3.connect(self.path) as db:
                return db.execute('SELECT COUNT(*) FROM sent_games').fetchone()[0]
        self.assertEqual(await check(30, {item.source}), 1)
        self.assertEqual(await check(31, set()), 1)  # Failed fetch cannot prune history.
        self.assertEqual(await check(31, {item.source}), 0)
        returned = replace(item, ends_at=now + dt.timedelta(days=60))
        self.assertEqual(await self.history.publish_new(123, [returned], self.send,
                         now=now + dt.timedelta(days=32)), 1)

    async def test_extension_refreshed_before_cleanup(self):
        now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        item = replace(game(), ends_at=now + dt.timedelta(days=1))
        await self.history.publish_new(123, [item], self.send, now=now)
        extended = replace(item, ends_at=now + dt.timedelta(days=90))
        self.assertEqual(await self.history.publish_new(123, [extended], self.send,
                         now=now + dt.timedelta(days=40)), 0)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT ends_at, missing_since FROM sent_games').fetchone(),
                             (extended.ends_at.isoformat(), None))
        self.send.assert_awaited_once()

    async def test_unknown_end_needs_90_days_absence_and_resets_on_return(self):
        now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        item = game()
        await self.history.publish_new(123, [item], self.send, now=now)
        async def check(day, games, sources):
            await self.history.publish_new(123, games, self.send, now=now + dt.timedelta(days=day),
                                           successful_sources=sources)
            with sqlite3.connect(self.path) as db:
                return db.execute('SELECT COUNT(*) FROM sent_games').fetchone()[0]
        self.assertEqual(await check(100, [], set()), 1)
        self.assertEqual(await check(101, [], {item.source}), 1)  # Absence starts here.
        self.assertEqual(await check(190, [], {item.source}), 1)
        self.assertEqual(await check(191, [item], {item.source}), 1)  # Return cancels cleanup.
        self.assertEqual(await check(192, [], {item.source}), 1)
        self.assertEqual(await check(281, [], {item.source}), 1)
        self.assertEqual(await check(282, [], {item.source}), 0)
        self.send.assert_awaited_once()

    async def test_old_database_migration_preserves_sent_games(self):
        self.path.parent.mkdir()
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE sent_games (channel_id TEXT, source TEXT, offer_id TEXT, '
                       'sent_at TEXT, PRIMARY KEY(channel_id, source, offer_id))')
            db.execute('INSERT INTO sent_games VALUES (?, ?, ?, ?)',
                       ('123', game().source, 'one', '2020-01-01T00:00:00+00:00'))
        self.assertEqual(await self.history.publish_new(123, [game()], self.send), 0)
        self.send.assert_not_awaited()
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT missing_since FROM sent_games').fetchone(), (None,))

    async def test_cleanup_is_scoped_to_channel_and_successful_source(self):
        now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        items = [replace(game(source=s), ends_at=now + dt.timedelta(days=1))
                 for s in ('Epic Games Store', 'Amazon Prime')]
        await self.history.publish_new(123, items, self.send, now=now)
        await self.history.publish_new(456, items, self.send, now=now)
        await self.history.publish_new(123, [], self.send, now=now + dt.timedelta(days=40),
                                       successful_sources={'Epic Games Store'})
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT channel_id, source FROM sent_games ORDER BY channel_id, source').fetchall(),
                             [('123', 'Amazon Prime'), ('456', 'Amazon Prime'), ('456', 'Epic Games Store')])
