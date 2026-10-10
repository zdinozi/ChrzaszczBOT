from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import tasks

from pepper_scraper import Deal, PepperScraperError, fetch_hottest_deals
from epic_games import fetch_free_games
from free_games import FreeGame, GamesCache
from prime_games import fetch_prime_games


CHANNEL_NAME = os.getenv("DISCORD_CHANNEL", "promocje")
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


epic_cache = GamesCache()
prime_cache = GamesCache()


def build_game_embed(game: FreeGame) -> discord.Embed:
    details = [
        f"Do odebrania do <t:{int(game.ends_at.timestamp())}:F>"
        if game.ends_at else "Termin odbioru niepodany przez źródło."
    ]
    if game.platform:
        details.append(f"Platforma aktywacji: {discord.utils.escape_markdown(game.platform[:200])}")
    if game.requires_prime:
        details.append("Wymaga Amazon Prime.")
    embed = discord.Embed(
        title=game.title[:256], url=game.url, description="\n".join(details),
        colour=discord.Colour.purple() if game.requires_prime else discord.Colour.blue(),
    )
    embed.set_footer(text=game.source if game.requires_prime else "Epic Games Store • Polska")
    return embed


class FreeGamesView(discord.ui.View):
    def __init__(self, pages: list[tuple[str, list[discord.Embed]]], notices: list[str]):
        super().__init__(timeout=300)
        self.pages = pages
        self.notices = notices
        self.page = 0
        self.message = None
        self.lock = asyncio.Lock()
        self.expired = False
        self.update_buttons()

    def update_buttons(self) -> None:
        self.previous.disabled = self.expired or self.page == 0
        self.next.disabled = self.expired or self.page == len(self.pages) - 1

    def message_content(self) -> str:
        heading, _ = self.pages[self.page]
        hint = "Nawigacja wygasła — wywołaj ponownie /darmowegry." if self.expired else ""
        return "\n".join(text for text in (
            heading, f"**Strona {self.page + 1}/{len(self.pages)}**", *self.notices, hint,
        ) if text)

    async def move(self, interaction: discord.Interaction, offset: int) -> None:
        async with self.lock:
            if not self.expired:
                self.page = max(0, min(len(self.pages) - 1, self.page + offset))
            self.update_buttons()
            await interaction.response.edit_message(
                content=self.message_content(), embeds=self.pages[self.page][1], view=self,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @discord.ui.button(label="Poprzednia", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.move(interaction, -1)

    @discord.ui.button(label="Następna", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.move(interaction, 1)

    async def on_timeout(self) -> None:
        async with self.lock:
            self.expired = True
            self.update_buttons()
            if self.message is not None:
                try:
                    await self.message.edit(content=self.message_content(), view=self)
                except discord.HTTPException:
                    logger.warning("Nie udało się wyłączyć nawigacji gier po wygaśnięciu")


async def publish_free_games(channel: discord.Webhook) -> None:
    results = await asyncio.gather(
        epic_cache.get(fetch_free_games), prime_cache.get(fetch_prime_games),
        return_exceptions=True,
    )
    providers = (
        ("Epic Games Store", "🎮 **Gry do odebrania za darmo w Epic Games Store**"),
        ("Amazon Prime", "🎁 **Gry do odebrania w ramach Amazon Prime**\n"
         "Wymagana aktywna subskrypcja. Dostępność dla konta i regionu sprawdzisz na stronie oferty."),
    )
    pages = []
    notices = []
    for (source, heading), result in zip(providers, results):
        if isinstance(result, Exception):
            logger.error("Nie udało się pobrać gier: %s", source,
                         exc_info=(type(result), result, result.__traceback__))
            notices.append(f"⚠️ Nie udało się pobrać gier z {source}. Spróbuj ponownie później.")
            continue
        if not result:
            notices.append(f"Obecnie brak aktywnych ofert do odebrania w {source}.")
            continue
        # Five bounded cards fit both the 10-embed and 6000-character limits.
        for offset in range(0, len(result), 5):
            pages.append((heading, [build_game_embed(game) for game in result[offset:offset + 5]]))
    if not pages:
        await channel.send("\n".join(notices))
        return
    if len(pages) == 1:
        await channel.send(content="\n".join([pages[0][0], *notices]), embeds=pages[0][1],
                           allowed_mentions=discord.AllowedMentions.none())
        return
    view = FreeGamesView(pages, notices)
    view.message = await channel.send(
        content=view.message_content(), embeds=pages[0][1], view=view, wait=True,
        allowed_mentions=discord.AllowedMentions.none(),
    )


@command_tree.command(name="darmowegry", description="Pokaż gry do odebrania w Epic Games i z subskrypcją Amazon Prime")
async def free_games_command(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    await publish_free_games(interaction.followup)


if __name__ == "__main__":
    client.run(get_token())
