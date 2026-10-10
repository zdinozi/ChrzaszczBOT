import asyncio
import datetime as dt
import unittest
from unittest.mock import AsyncMock, patch

import main
from epic_games import EpicGamesError
from free_games import FreeGame, GamesCache
from prime_games import PrimeGamesError


class CacheTest(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_requests_and_expired_offers(self):
        now = dt.datetime.now(dt.timezone.utc)
        valid = FreeGame("Active", "https://example.com", now + dt.timedelta(days=1))
        expired = FreeGame("Expired", "https://example.com", now - dt.timedelta(seconds=1))
        fetch = AsyncMock(return_value=[valid, expired])
        cache = GamesCache()
        results = await asyncio.gather(cache.get(fetch), cache.get(fetch))
        self.assertEqual(results, [[valid], [valid]])
        fetch.assert_awaited_once()
        cache._expires = 0
        await cache.get(fetch)
        self.assertEqual(fetch.await_count, 2)

    async def test_failure_retried(self):
        fetch = AsyncMock(side_effect=[PrimeGamesError(), []])
        cache = GamesCache()
        with self.assertRaises(PrimeGamesError):
            await cache.get(fetch)
        self.assertEqual(await cache.get(fetch), [])
        self.assertEqual(fetch.await_count, 2)


class CommandTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.channel = AsyncMock()
        self.patches = [patch.object(main, "epic_cache", GamesCache()),
                        patch.object(main, "prime_cache", GamesCache())]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    async def test_batches_and_subscription_label(self):
        games = [FreeGame("X" * 300, "https://example.com", None,
                          "Amazon Prime", "GOG" * 200, True) for _ in range(16)]
        with patch.object(main, "fetch_free_games", AsyncMock(return_value=[])), \
                patch.object(main, "fetch_prime_games", AsyncMock(return_value=games)):
            await main.publish_free_games(self.channel)
        batches = [c.kwargs["embeds"] for c in self.channel.send.call_args_list if "embeds" in c.kwargs]
        self.assertEqual([len(b) for b in batches], [5, 5, 5, 1])
        for batch in batches:
            self.assertLessEqual(sum(len(e) for e in batch), 6000)
            for embed in batch:
                self.assertLessEqual(len(embed.title), 256)
                self.assertIn("Wymaga Amazon Prime", embed.description)
                self.assertIn("Termin odbioru niepodany", embed.description)

    async def test_each_provider_can_fail_independently(self):
        game = FreeGame("Game", "https://example.com", None)
        for failed in ("epic", "prime", "both"):
            with self.subTest(failed=failed), \
                    patch.object(main, "epic_cache", GamesCache()), \
                    patch.object(main, "prime_cache", GamesCache()), \
                    patch.object(main, "fetch_free_games", AsyncMock(
                        side_effect=EpicGamesError() if failed in ("epic", "both") else None,
                        return_value=[game])), \
                    patch.object(main, "fetch_prime_games", AsyncMock(
                        side_effect=PrimeGamesError() if failed in ("prime", "both") else None,
                        return_value=[game])), self.assertLogs(main.logger, level="ERROR"):
                self.channel.reset_mock()
                await main.publish_free_games(self.channel)
                calls = self.channel.send.call_args_list
                self.assertEqual(len(calls), 2)
                self.assertEqual(sum("embeds" in c.kwargs for c in calls), 0 if failed == "both" else 1)

    async def test_command_defers_before_fetch(self):
        interaction = AsyncMock()
        with patch.object(main, "publish_free_games", AsyncMock()) as publish:
            await main.free_games_command.callback(interaction)
        interaction.response.defer.assert_awaited_once_with(thinking=True)
        publish.assert_awaited_once_with(interaction.followup)
