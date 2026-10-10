import copy
import datetime as dt
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from prime_games import PrimeGamesError, _download_games, parse_prime_games


NOW = dt.datetime(2026, 10, 10, tzinfo=dt.timezone.utc)
FIXTURE = json.loads((Path(__file__).parent / "tests/fixtures/prime_games.json").read_text())


def payload(item):
    return {"data": {"games": {"items": [item]}}}


class PrimeGamesTest(unittest.TestCase):
    def setUp(self):
        self.item = copy.deepcopy(FIXTURE["data"]["games"]["items"][0])

    def test_real_catalog(self):
        games = parse_prime_games(FIXTURE, NOW)
        self.assertEqual(len(games), 16)
        self.assertTrue(all(g.requires_prime and g.source == "Amazon Prime" for g in games))
        self.assertTrue(all(g.url.startswith("https://luna.amazon.com/claims/dp/") for g in games))
        self.assertEqual(games[0].title, "Botany Manor")

    def test_excludes_ineligible_offers(self):
        for kind in ("future", "expired", "teaser", "loot", "streaming", "no_offers"):
            with self.subTest(kind=kind):
                item = copy.deepcopy(self.item)
                if kind == "future":
                    item["offers"][0]["startTime"] = "2026-10-11T00:00:00Z"
                elif kind == "expired":
                    item["offers"][0]["endTime"] = NOW.isoformat()
                elif kind == "teaser":
                    item["isTeaserCard"] = True
                elif kind == "loot":
                    item["category"] = "LOOT"
                elif kind == "streaming":
                    item["isFGWP"] = False
                else:
                    item["offers"] = []
                self.assertEqual(parse_prime_games(payload(item), NOW), [])

    def test_missing_end_platform_and_duplicates(self):
        self.item["offers"][0].update(startTime=NOW.isoformat(), endTime=None)
        self.item["assets"]["redemptionPlatforms"] = ["GOG"]
        data = payload(self.item)
        data["data"]["games"]["items"].append(copy.deepcopy(self.item))
        games = parse_prime_games(data, NOW)
        self.assertEqual(len(games), 1)
        self.assertIsNone(games[0].ends_at)
        self.assertEqual(games[0].platform, "GOG")

    def test_invalid_catalog_is_not_empty_success(self):
        self.item["offers"][0]["startTime"] = "2026-10-01T00:00:00"
        for data in ({}, {"data": None}, payload(None), payload(self.item),
                     {**FIXTURE, "errors": [{"message": "failed"}]}):
            with self.subTest(data=data), self.assertRaises(PrimeGamesError):
                parse_prime_games(data, NOW)
        self.assertEqual(parse_prime_games({"data": {"games": {"items": []}}}, NOW), [])

    def test_anonymous_session_and_post(self):
        opener = MagicMock()
        home, response = MagicMock(), MagicMock()
        home.read.return_value = b'<input value="anonymous-token" name="csrf-key">'
        response.read.return_value = json.dumps(FIXTURE).encode()
        opener.open.return_value.__enter__.side_effect = [home, response]
        with patch("prime_games.build_opener", return_value=opener):
            self.assertEqual(_download_games(), FIXTURE)
        request = opener.open.call_args_list[1].args[0]
        self.assertEqual(request.get_header("Csrf-token"), "anonymous-token")
        self.assertEqual(request.get_method(), "POST")

    def test_network_failure_and_missing_session(self):
        opener = MagicMock()
        opener.open.side_effect = URLError("offline")
        with patch("prime_games.build_opener", return_value=opener), self.assertRaises(PrimeGamesError):
            _download_games()
        opener.open.side_effect = None
        opener.open.return_value.__enter__.return_value.read.return_value = b"<html>unavailable</html>"
        with patch("prime_games.build_opener", return_value=opener), self.assertRaises(PrimeGamesError):
            _download_games()
