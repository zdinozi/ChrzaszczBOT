from __future__ import annotations

import datetime as dt
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
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
client = discord.Client(intents=intents)
command_tree = app_commands.CommandTree(client)
commands_synced = False


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


def build_embeds(deals: list[Deal]) -> list[discord.Embed]:
    embeds = []
    for position, deal in enumerate(deals, start=1):
        title = deal.title
        if len(title) > 245:
            title = title[:242] + "..."
        details = " · ".join(value for value in (deal.price, deal.temperature) if value)
        embed = discord.Embed(
            title=f"{position}. {title}",
            url=deal.url,
            description=details or None,
            colour=discord.Colour.orange(),
        )
        if deal.image_url:
            embed.set_image(url=deal.image_url)
        embed.set_footer(text="Pepper.pl • ranking Najgorętsze")
        embeds.append(embed)
    return embeds


async def publish_deals(channel: discord.abc.Messageable) -> None:
    try:
        deals = await fetch_hottest_deals(limit=10)
        today = dt.datetime.now(WARSAW).strftime("%d.%m.%Y")
        await channel.send(
            content=f"🔥 **10 najgorętszych okazji — {today}**",
            embeds=build_embeds(deals),
        )
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
    global commands_synced
    logger.info("Zalogowano jako %s; codzienna publikacja o 18:00 Europe/Warsaw", client.user)
    if not commands_synced:
        total_synced = 0
        for guild in client.guilds:
            guild_target = discord.Object(id=guild.id)
            command_tree.copy_global_to(guild=guild_target)
            synced = await command_tree.sync(guild=guild_target)
            total_synced += len(synced)
            logger.info("Zarejestrowano komendy na serwerze %s (%s)", guild.name, guild.id)
        commands_synced = True
        logger.info("Zarejestrowano łącznie %d komend aplikacji", total_synced)
    if not daily_deals.is_running():
        daily_deals.start()


@command_tree.command(name="promocje", description="Pokaż 10 najgorętszych okazji z Pepper.pl")
async def promotions_command(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    await publish_deals(interaction.followup)


if __name__ == "__main__":
    client.run(get_token())
