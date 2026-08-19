from __future__ import annotations

import asyncio
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PEPPER_URL = "https://www.pepper.pl/najgoretsze"
USER_AGENT = "Mozilla/5.0 (compatible; ChrzaszczBOT/1.0; +https://github.com/zdinozi/ChrzaszczBOT)"


class PepperScraperError(RuntimeError):
    pass


@dataclass(frozen=True)
class Deal:
    title: str
    url: str
    temperature: str = ""
    price: str = ""
    image_url: str = ""


class _DealsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.deals: list[Deal] = []
        self._deal: dict[str, str] | None = None
        self._capture: str | None = None

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs_list)
        classes = set((attrs.get("class") or "").split())

        if attrs.get("data-t") == "thread":
            self._finish_deal()
            self._deal = {}
            return
        if self._deal is None:
            return
        if tag == "a" and attrs.get("data-t") == "threadLink":
            self._deal["title"] = (attrs.get("title") or "").strip()
            self._deal["url"] = (attrs.get("href") or "").strip()
        elif tag == "img" and "thread-image" in classes:
            srcset = (attrs.get("srcset") or "").strip()
            largest_src = srcset.split(",")[-1].strip().split(" ")[0] if srcset else ""
            self._deal["image_url"] = largest_src or (attrs.get("src") or "").strip()
        elif "cept-vote-temp" in classes:
            self._capture = "temperature"
        elif "thread-price" in classes:
            self._capture = "price"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"button", "span", "div"}:
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._deal is not None and self._capture and data.strip():
            self._deal[self._capture] = data.strip()

    def close(self) -> None:
        super().close()
        self._finish_deal()

    def _finish_deal(self) -> None:
        if self._deal and self._deal.get("title") and self._deal.get("url"):
            self.deals.append(Deal(**self._deal))
        self._deal = None
        self._capture = None


def parse_deals(html: str, limit: int = 10) -> list[Deal]:
    parser = _DealsParser()
    parser.feed(html)
    parser.close()
    return parser.deals[:limit]


def _download_page(timeout: int = 20) -> str:
    request = Request(
        PEPPER_URL,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "pl-PL,pl;q=0.9"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError) as error:
        raise PepperScraperError(f"błąd pobierania strony: {error}") from error


async def fetch_hottest_deals(limit: int = 10) -> list[Deal]:
    html = await asyncio.to_thread(_download_page)
    deals = parse_deals(html, limit)
    if len(deals) < limit:
        raise PepperScraperError(f"znaleziono tylko {len(deals)} z {limit} ofert")
    return deals
