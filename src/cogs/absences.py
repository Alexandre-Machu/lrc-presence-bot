"""Calendrier d'absences : on prévient à l'avance, le bot marque « Absent » le jour J."""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import GUILD_ID, TIMEZONE
from utils.absences import (
    AbsenceError, add_absence, load_absences, parse_date, purge_past, remove_absence, save_absences,
    to_days, toggle_days,
)

log = logging.getLogger(__name__)


def fmt(day: date):
    return day.strftime("%d/%m/%Y")


def fmt_range(entry):
    start, end = date.fromisoformat(entry["start"]), date.fromisoformat(entry["end"])
    return fmt(start) if start == end else f"{fmt(start)} → {fmt(end)}"


DAY_NAMES = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
MAX_WEEKS_AHEAD = 52


def monday_of(day: date):
    return day - timedelta(days=day.weekday())


class DayButton(discord.ui.Button):
    def __init__(self, cog, day: date, absent: bool, past: bool, row: int):
        super().__init__(
            label=f"{DAY_NAMES[day.weekday()]} {day.day}",
            style=discord.ButtonStyle.danger if absent else discord.ButtonStyle.secondary,
            emoji="❌" if absent else None,
            disabled=past,
            row=row,
        )
        self.cog, self.day = cog, day

    async def callback(self, interaction: discord.Interaction):
        await self.cog.toggle(interaction, [self.day], self.view.week_start)


class WeekButton(discord.ui.Button):
    def __init__(self, cog, days, disabled: bool):
        super().__init__(label="Toute la semaine", style=discord.ButtonStyle.primary, emoji="🏖️", row=1, disabled=disabled)
        self.cog, self.days = cog, days

    async def callback(self, interaction: discord.Interaction):
        await self.cog.toggle(interaction, self.days, self.view.week_start)


class NavButton(discord.ui.Button):
    def __init__(self, cog, label: str, delta: int, disabled: bool):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, disabled=disabled, row=2)
        self.cog, self.delta = cog, delta

    async def callback(self, interaction: discord.Interaction):
        week = self.view.week_start + timedelta(weeks=self.delta)
        await interaction.response.edit_message(
            content=self.cog.panel_content(interaction.user.id, week),
            view=self.cog.panel_view(interaction.user.id, week),
        )


class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Terminé", style=discord.ButtonStyle.success, emoji="✅", row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Absences enregistrées ✅", view=None)


class CalendarView(discord.ui.View):
    """Calendrier d'une semaine : un clic sur un jour l'ajoute ou le retire de tes absences."""

    def __init__(self, cog, uid, week_start: date):
        super().__init__(timeout=600)
        self.week_start = week_start
        today = datetime.now(TIMEZONE).date()
        mine = to_days(load_absences().get(str(uid), []))
        days = [week_start + timedelta(days=i) for i in range(7)]
        for i, day in enumerate(days):
            self.add_item(DayButton(cog, day, day in mine, day < today, row=0 if i < 5 else 1))
        self.add_item(WeekButton(cog, [d for d in days if d >= today], disabled=days[-1] < today))
        this_week = monday_of(today)
        self.add_item(NavButton(cog, "◀ Semaine préc.", -1, disabled=week_start <= this_week))
        self.add_item(NavButton(cog, "Semaine suiv. ▶", 1, disabled=week_start >= this_week + timedelta(weeks=MAX_WEEKS_AHEAD)))
        self.add_item(CloseButton())


class Absences(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---- calendrier interactif

    def panel_content(self, uid, week_start: date):
        today = datetime.now(TIMEZONE).date()
        end = week_start + timedelta(days=6)
        text = (
            f"📅 **Mes absences** — semaine du {week_start.strftime('%d/%m')} au {end.strftime('%d/%m/%Y')}\n"
            "Clique sur un jour pour l'ajouter (❌) ou le retirer. "
            "Tu seras marqué absent automatiquement ces jours-là.\n"
        )
        upcoming = [e for e in load_absences().get(str(uid), []) if date.fromisoformat(e["end"]) >= today]
        if upcoming:
            text += "\n**Prévues :** " + " · ".join(fmt_range(e) for e in upcoming[:8])
        return text

    def panel_view(self, uid, week_start: date):
        return CalendarView(self, uid, week_start)

    async def open_panel(self, interaction: discord.Interaction):
        week = monday_of(datetime.now(TIMEZONE).date())
        await interaction.response.send_message(
            self.panel_content(interaction.user.id, week),
            view=self.panel_view(interaction.user.id, week),
            ephemeral=True,
        )

    async def toggle(self, interaction: discord.Interaction, days, week_start: date):
        uid = interaction.user.id
        today = datetime.now(TIMEZONE).date()
        data = load_absences()
        now_absent = toggle_days(data, uid, days)
        purge_past(data, today)
        save_absences(data)
        if today in days:
            presence = self.bot.get_cog("Presence")
            if presence:
                presence.set_absent_today(uid, now_absent)
                await presence.update_message()
        await interaction.response.edit_message(
            content=self.panel_content(uid, week_start),
            view=self.panel_view(uid, week_start),
        )

    # ---- commandes

    @app_commands.command(name="lrcabsence", description="Planifie tes absences : calendrier cliquable, ou une période en JJ/MM")
    @app_commands.describe(
        debut="(Optionnel) Premier jour d'absence : JJ/MM ou JJ/MM/AAAA",
        fin="(Optionnel) Dernier jour inclus. Vide = un seul jour",
    )
    async def lrcabsence(self, interaction: discord.Interaction, debut: Optional[str] = None, fin: Optional[str] = None):
        if debut is None:
            await self.open_panel(interaction)
            return
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
