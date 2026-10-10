from __future__ import annotations

import asyncio
import datetime as dt
import json
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from free_games import FreeGame


EPIC_URL = (
    "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    "?locale=pl&country=PL&allowCountries=PL"
)


class EpicGamesError(RuntimeError):
    pass


def parse_free_games(payload: dict, now: dt.datetime | None = None) -> list[FreeGame]:
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        elements = payload["data"]["Catalog"]["searchStore"]["elements"]
        if not isinstance(elements, list) or payload.get("errors"):
            raise ValueError("invalid catalog")
        games = []
        seen = set()
        for item in elements:
            price = (item.get("price") or {}).get("totalPrice") or {}
            if price.get("discountPrice") != 0 or price.get("originalPrice", 0) <= 0:
                continue
            if item.get("offerType") not in {"BASE_GAME", "BUNDLE"}:
                continue
            ends = []
            for group in (item.get("promotions") or {}).get("promotionalOffers", []):
                for offer in group.get("promotionalOffers", []):
                    start = dt.datetime.fromisoformat(offer["startDate"].replace("Z", "+00:00"))
                    end = dt.datetime.fromisoformat(offer["endDate"].replace("Z", "+00:00"))
                    discount = offer.get("discountSetting") or {}
                    if (start <= now < end and discount.get("discountType") == "PERCENTAGE"
                            and discount.get("discountPercentage") == 0):
                        ends.append(end)
            key = (item["namespace"], item["id"])
            if not ends or key in seen:
                continue
            mappings = (item.get("offerMappings") or []) + ((item.get("catalogNs") or {}).get("mappings") or [])
            slug = next((m["pageSlug"] for m in mappings if m.get("pageSlug") and m.get("pageType") == "productHome"), None)
            slug = slug or item.get("productSlug")
            if slug:
                slug = slug.removesuffix("/home")
                url = "https://store.epicgames.com/pl/p/" + quote(slug, safe="/-")
            else:
                url = "https://store.epicgames.com/pl/free-games"
            games.append(FreeGame(item["title"], url, max(ends)))
            seen.add(key)
        return sorted(games, key=lambda game: (game.ends_at, game.title.casefold()))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise EpicGamesError("Nieprawidłowa odpowiedź katalogu Epic Games") from error


def _download_games() -> dict:
    request = Request(EPIC_URL, headers={"User-Agent": "ChrzaszczBOT/1.0", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except (URLError, OSError, ValueError) as error:
        raise EpicGamesError("Nie udało się pobrać katalogu Epic Games") from error


async def fetch_free_games() -> list[FreeGame]:
    return parse_free_games(await asyncio.to_thread(_download_games))
