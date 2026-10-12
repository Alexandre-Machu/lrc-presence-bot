"""Stats des soirées (/lrcstats) et récap automatique du mois, calculés sur l'historique."""
import logging
from datetime import date, datetime, time, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.settings import CHANNEL_ID, GAMES, GUILD_ID, TIMEZONE
from utils.history import MONTHS, compute_stats, load_history, month_recap, previous_month
from utils.storage import get_meta, set_meta

log = logging.getLogger(__name__)
RECAP_HOUR = 10
RECAP_CATCH_UP_DAYS = 3  # bot éteint le 1er : récap rattrapé jusqu'au 3

GAME_EMOJIS = {g["name"]: g["emoji"] for g in GAMES}
MEDALS = ["🥇", "🥈", "🥉"]


def fr(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def build_stats_embed(stats, label):
    embed = discord.Embed(title=f"📊 Stats LRC — {label}", color=discord.Color.gold())
    if not stats["nights"]:
        since = f" (l'historique a démarré le {fr(stats['first_day'])})" if stats["first_day"] else ""
        embed.description = f"Pas encore de soirée avec des présents sur cette période{since}."
        return embed

    record_day, record_n = stats["record"]
    embed.add_field(name="🌙 Soirées", value=(
        f"**{stats['nights']}** soirée(s) avec au moins un présent\n"
        f"**{stats['average']:.1f}** présents en moyenne\n"
        f"Record : **{record_n}** le {fr(record_day)}"
    ), inline=False)

    players = [
        f"{MEDALS[i] if i < 3 else f'{i + 1}.'} <@{uid}> — {n} soirée{'s' if n > 1 else ''}"
        for i, (uid, n) in enumerate(stats["top_players"])
    ]
    embed.add_field(name="🏆 Les plus présents", value="\n".join(players), inline=False)

    if stats["top_games"]:
        games = [f"{GAME_EMOJIS.get(name, '🎮')} {name} — {n}" for name, n in stats["top_games"]]
        embed.add_field(name="🎮 Jeux les plus demandés", value="\n".join(games), inline=False)

    embed.set_footer(text=f"Historique depuis le {fr(stats['first_day'])} · seuls les « Présent » comptent")
    return embed


def build_recap_embed(stats, titles, year, month):
    embed = build_stats_embed(stats, f"récap de {MONTHS[month - 1]} {year}")
    embed.title = f"🗓️ Récap de {MONTHS[month - 1]} {year}"
    if titles:
        embed.add_field(
            name="🏅 Les titres du mois",
            value="\n".join(f"**{title}** : <@{uid}> ({detail})" for title, uid, detail in titles),
            inline=False,
        )
    return embed


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.monthly_recap.start()

    async def cog_unload(self):
        self.monthly_recap.cancel()

    async def post_recap_if_due(self):
        """Poste le récap du mois précédent, une seule fois, entre le 1er (10h) et le 3."""
        now = datetime.now(TIMEZONE)
        if now.day > RECAP_CATCH_UP_DAYS or (now.day == 1 and now.hour < RECAP_HOUR):
            return False
        year, month = previous_month(now.date())
        key = f"{year}-{month:02d}"
        if get_meta("last_monthly_recap") == key:
            return False
        stats, titles = month_recap(load_history(), year, month)
        set_meta("last_monthly_recap", key)
        if not stats["nights"]:
            log.info("Récap %s : aucune soirée, rien à poster", key)
            return False
        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            log.error("Canal introuvable pour le récap du mois")
            return False
        await channel.send(embed=build_recap_embed(stats, titles, year, month),
                           allowed_mentions=discord.AllowedMentions.none())
        log.info("Récap du mois %s posté", key)
        return True

    @tasks.loop(time=time(hour=RECAP_HOUR, minute=0, tzinfo=TIMEZONE))
    async def monthly_recap(self):
        await self.post_recap_if_due()

    @monthly_recap.before_loop
    async def before_monthly_recap(self):
        await self.bot.wait_until_ready()
        await self.post_recap_if_due()

    @monthly_recap.error
    async def monthly_recap_error(self, error):
        log.exception("Erreur lors du récap du mois", exc_info=error)

    @app_commands.command(name="lrcstats", description="Stats des soirées : les plus présents, les jeux les plus joués…")
    @app_commands.describe(periode="Période (30 derniers jours par défaut)")
    @app_commands.choices(periode=[
        app_commands.Choice(name="7 derniers jours", value=7),
        app_commands.Choice(name="30 derniers jours", value=30),
        app_commands.Choice(name="Depuis le début", value=0),
    ])
    async def lrcstats(self, interaction: discord.Interaction, periode: Optional[app_commands.Choice[int]] = None):
        days = periode.value if periode else 30
        today = datetime.now(TIMEZONE).date()
        since = today - timedelta(days=days - 1) if days else None
        label = periode.name if periode else "30 derniers jours"
        embed = build_stats_embed(compute_stats(load_history(), since), label)
        # message visible par tous, mais sans notifier les membres cités
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(Stats(bot), guild=discord.Object(id=GUILD_ID))
