from __future__ import annotations

import asyncio
import datetime as dt
import json
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener

from free_games import FreeGame


PRIME_HOME = "https://luna.amazon.com/claims/"
PRIME_API = "https://luna.amazon.com/graphql"
PAGE_SIZE = 100
# Public website API, not a supported Amazon developer API. No account login.
QUERY = """
query FreeGames {
  games: items(collectionType: FREE_GAMES, pageSize: 100) {
    items {
      id isFGWP isTeaserCard category
      assets { title redemptionPlatforms }
      offers { startTime endTime }
    }
  }
}
"""


class PrimeGamesError(RuntimeError):
    pass


class _CsrfParser(HTMLParser):
    token: str | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "csrf-key":
            self.token = attrs.get("value")


def _date(value: str) -> dt.datetime:
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("missing timezone")
    return result


def parse_prime_games(payload: dict, now: dt.datetime | None = None) -> list[FreeGame]:
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        items = payload["data"]["games"]["items"]
        if payload.get("errors") or not isinstance(items, list) or len(items) >= PAGE_SIZE:
            raise ValueError("invalid or potentially truncated catalog")
        games = []
        seen = set()
        for item in items:
            if (item["isFGWP"] is not True or item["category"] != "FULL_GAME"
                    or item["isTeaserCard"] is not False):
                continue
            ends = []
            for offer in item["offers"]:
                start = _date(offer["startTime"])
                end = _date(offer["endTime"]) if offer["endTime"] else None
                if start <= now and (end is None or now < end):
                    ends.append(end)
            if not ends:
                continue
            item_id = item["id"]
            title = item["assets"]["title"]
            if not isinstance(item_id, str) or not item_id or not isinstance(title, str) or not title.strip():
                raise ValueError("invalid game identity")
            if item_id in seen:
                continue
            platforms = item["assets"].get("redemptionPlatforms") or []
            if not isinstance(platforms, list) or any(not isinstance(p, str) for p in platforms):
                raise ValueError("invalid platforms")
            games.append(FreeGame(
                title=title.strip(), url=PRIME_HOME + "dp/" + quote(item_id, safe=""),
                ends_at=None if None in ends else max(ends),
                source="Amazon Prime", platform=", ".join(platforms) or None,
                requires_prime=True,
            ))
            seen.add(item_id)
        return sorted(games, key=lambda g: (
            g.ends_at or dt.datetime.max.replace(tzinfo=dt.timezone.utc), g.title.casefold(),
        ))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise PrimeGamesError("Nieprawidłowa odpowiedź katalogu Amazon Prime") from error


def _download_games() -> dict:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    headers = {"User-Agent": "ChrzaszczBOT/1.0"}
    try:
        with opener.open(Request(PRIME_HOME, headers=headers), timeout=20) as response:
            parser = _CsrfParser()
            parser.feed(response.read().decode("utf-8"))
        if not parser.token:
            raise PrimeGamesError("Brak anonimowej sesji katalogu Amazon Prime")
        request = Request(PRIME_API, data=json.dumps({
            "operationName": "FreeGames", "query": QUERY,
        }).encode("utf-8"), headers={
            **headers, "Content-Type": "application/json", "Accept": "application/json",
            "Client-Id": "CarboniteApp", "csrf-token": parser.token,
            "prime-gaming-language": "pl-PL",
        })
        with opener.open(request, timeout=20) as response:
            return json.load(response)
    except (URLError, OSError, ValueError) as error:
        raise PrimeGamesError("Nie udało się pobrać katalogu Amazon Prime") from error


async def fetch_prime_games() -> list[FreeGame]:
    return parse_prime_games(await asyncio.to_thread(_download_games))
