"""Calendrier d'absences : on prévient à l'avance, le bot marque « Absent » le jour J."""
import logging
from datetime import date, datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import GUILD_ID, TIMEZONE
from utils.absences import (
    AbsenceError, add_absence, load_absences, parse_date, purge_past, remove_absence, save_absences,
)

log = logging.getLogger(__name__)


def fmt(day: date):
    return day.strftime("%d/%m/%Y")


def fmt_range(entry):
    start, end = date.fromisoformat(entry["start"]), date.fromisoformat(entry["end"])
    return fmt(start) if start == end else f"{fmt(start)} → {fmt(end)}"


class Absences(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="lrcabsence", description="Planifie une absence à l'avance (vacances, voyage…)")
    @app_commands.describe(
        debut="Premier jour d'absence : JJ/MM ou JJ/MM/AAAA",
        fin="Dernier jour (inclus), même format. Vide = un seul jour",
    )
    async def lrcabsence(self, interaction: discord.Interaction, debut: str, fin: Optional[str] = None):
        today = datetime.now(TIMEZONE).date()
        try:
            start = parse_date(debut, today)
            end = parse_date(fin, today, not_before=start) if fin else start
            data = load_absences()
            purge_past(data, today)
            add_absence(data, interaction.user.id, start, end)
        except AbsenceError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        except ValueError:
            await interaction.response.send_message(
                "Date invalide. Utilise JJ/MM ou JJ/MM/AAAA (ex : 14/07 ou 14/07/2027).", ephemeral=True)
            return
        if end < today:
            await interaction.response.send_message("Cette période est déjà passée.", ephemeral=True)
            return
        save_absences(data)
        text = f"Absence enregistrée : **{fmt_range({'start': start.isoformat(), 'end': end.isoformat()})}**."
        if start <= today <= end:
            presence = self.bot.get_cog("Presence")
            if presence:
                presence.mark_absent_today(interaction.user.id)
                await presence.update_message()
            text += " Tu es marqué absent pour aujourd'hui."
        else:
            text += " Tu seras marqué absent automatiquement chaque matin (tu peux toujours changer d'avis dans le menu)."
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(name="lrcabsences", description="Affiche les absences planifiées")
    @app_commands.describe(tous="Afficher celles de tout le monde (sinon seulement les tiennes)")
    async def lrcabsences(self, interaction: discord.Interaction, tous: bool = False):
        today = datetime.now(TIMEZONE).date()
        data = load_absences()
        if purge_past(data, today):
            save_absences(data)
        rows = []
        for uid, entries in data.items():
            if not tous and uid != str(interaction.user.id):
                continue
            for entry in entries:
                rows.append((entry["start"], uid, entry))
        if not rows:
            await interaction.response.send_message("Aucune absence planifiée.", ephemeral=True)
            return
        lines = [f"- <@{uid}> : {fmt_range(e)}" for _, uid, e in sorted(rows)]
        await interaction.response.send_message(
            "**Absences planifiées :**\n" + "\n".join(lines),
            ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="lrcremoveabsence", description="Annule une de tes absences planifiées")
    @app_commands.describe(absence="L'absence à annuler")
    async def lrcremoveabsence(self, interaction: discord.Interaction, absence: str):
        data = load_absences()
        if remove_absence(data, interaction.user.id, absence):
            save_absences(data)
            await interaction.response.send_message("Absence annulée.", ephemeral=True)
        else:
            await interaction.response.send_message("Absence introuvable.", ephemeral=True)

    @lrcremoveabsence.autocomplete("absence")
    async def absence_autocomplete(self, interaction: discord.Interaction, current: str):
        entries = load_absences().get(str(interaction.user.id), [])
        return [
            app_commands.Choice(name=fmt_range(e), value=e["start"])
            for e in entries if current.lower() in fmt_range(e).lower()
        ][:25]


async def setup(bot):
    await bot.add_cog(Absences(bot), guild=discord.Object(id=GUILD_ID))
