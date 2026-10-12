"""Stats des soirées (/lrcstats), calculées sur l'historique enregistré chaque jour."""
from datetime import date, datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import GAMES, GUILD_ID, TIMEZONE
from utils.history import compute_stats, load_history

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


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
