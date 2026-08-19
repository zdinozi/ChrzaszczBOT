from __future__ import annotations

import datetime as dt
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord.ext import tasks

from pepper_scraper import Deal, PepperScraperError, fetch_hottest_deals


CHANNEL_NAME = os.getenv("DISCORD_CHANNEL", "main")
WARSAW = ZoneInfo("Europe/Warsaw")
POST_TIME = dt.time(hour=18, minute=0, tzinfo=WARSAW)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("chrzaszczbot")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def get_token() -> str:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        token_file = Path(__file__).with_name("token.txt")
        if token_file.exists():
            token = token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("Ustaw DISCORD_TOKEN albo wpisz token do pliku token.txt")
    return token


def find_channel() -> discord.TextChannel | None:
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if channel_id and channel_id.isdigit():
        channel = client.get_channel(int(channel_id))
        if isinstance(channel, discord.TextChannel):
            return channel

    return discord.utils.find(
        lambda item: isinstance(item, discord.TextChannel)
        and item.name.casefold() == CHANNEL_NAME.casefold(),
        client.get_all_channels(),
    )


def build_embed(deals: list[Deal]) -> discord.Embed:
    today = dt.datetime.now(WARSAW).strftime("%d.%m.%Y")
    embed = discord.Embed(
        title=f"🔥 10 najgorętszych okazji — {today}",
        url="https://www.pepper.pl/najgoretsze",
        colour=discord.Colour.orange(),
    )
    for position, deal in enumerate(deals, start=1):
        title = deal.title.replace("[", "(").replace("]", ")")
        if len(title) > 220:
            title = title[:217] + "..."
        details = " · ".join(value for value in (deal.price, deal.temperature) if value)
        value = f"{details}\n[Zobacz okazję]({deal.url})" if details else f"[Zobacz okazję]({deal.url})"
        embed.add_field(name=f"{position}. {title}", value=value, inline=False)
    embed.set_footer(text="Źródło: Pepper.pl • ranking Najgorętsze")
    return embed


async def publish_deals(channel: discord.abc.Messageable) -> None:
    try:
        deals = await fetch_hottest_deals(limit=10)
        await channel.send(embed=build_embed(deals))
        logger.info("Opublikowano %d okazji", len(deals))
    except PepperScraperError as error:
        logger.exception("Nie udało się pobrać okazji")
        await channel.send(f"⚠️ Nie udało się pobrać okazji z Pepper.pl: {error}")
    except discord.HTTPException:
        logger.exception("Nie udało się wysłać wiadomości na Discord")


@tasks.loop(time=POST_TIME)
async def daily_deals() -> None:
    channel = find_channel()
    if channel is None:
        logger.error("Nie znaleziono kanału tekstowego #%s", CHANNEL_NAME)
        return
    await publish_deals(channel)


@daily_deals.before_loop
async def before_daily_deals() -> None:
    await client.wait_until_ready()


@client.event
async def on_ready() -> None:
    logger.info("Zalogowano jako %s; codzienna publikacja o 18:00 Europe/Warsaw", client.user)
    if not daily_deals.is_running():
        daily_deals.start()


@client.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return
    if message.content.strip().casefold() == "$deale":
        await publish_deals(message.channel)


if __name__ == "__main__":
    client.run(get_token())
