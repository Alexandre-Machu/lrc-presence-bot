"""Anniversaires : enregistrement libre-service, liste et vœux quotidiens."""
import logging
from datetime import datetime, time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.settings import CHANNEL_ID, GUILD_ID, TIMEZONE
from utils.birthdays import birthday_on, days_until, format_birthday, parse_birthday
from utils.storage import (
    get_last_birthday_notice, load_birthdays, save_birthdays, set_last_birthday_notice,
)

log = logging.getLogger(__name__)


async def find_member(guild: discord.Guild, user_id: int):
    """Membre du serveur, même s'il n'est pas dans le cache ; None s'il est parti."""
    member = guild.get_member(user_id)
    if member:
        return member
    try:
        return await guild.fetch_member(user_id)
    except discord.NotFound:
        return None


def can_manage(interaction: discord.Interaction, target: discord.Member):
    """Chacun gère son propre anniversaire ; les admins gèrent celui des autres."""
    return target.id == interaction.user.id or interaction.user.guild_permissions.administrator


def save_birthday(user_id, date_text):
    """Valide et enregistre. Retourne la date normalisée ; ValueError si invalide."""
    day, month = parse_birthday(date_text)
    normalized = format_birthday(day, month)
    birthdays = load_birthdays()
    birthdays[str(user_id)] = normalized
    save_birthdays(birthdays)
    return normalized


class BirthdayModal(discord.ui.Modal, title="Ton anniversaire"):
    date = discord.ui.TextInput(label="Date (jour/mois, ex : 25/12)", placeholder="25/12", min_length=3, max_length=5)

    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        try:
            normalized = save_birthday(self.target.id, self.date.value)
        except ValueError:
            await interaction.response.send_message("Date invalide. Écris par exemple `25/12`.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Anniversaire de {self.target.mention} enregistré pour le {normalized} 🎂", ephemeral=True)


class Birthdays(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.birthday_notifier.start()

    async def cog_unload(self):
        self.birthday_notifier.cancel()

    async def announce_birthdays(self, channel):
        """Souhaite les anniversaires du jour. Retourne le nombre de messages envoyés."""
        today = datetime.now(TIMEZONE).date()
        sent = 0
        for user_id, date_str in load_birthdays().items():
            try:
                day, month = parse_birthday(date_str)
            except ValueError:
                log.warning("Date d'anniversaire invalide ignorée : %s=%s", user_id, date_str)
                continue
            if birthday_on(today.year, day, month) != today:
                continue
            member = await find_member(channel.guild, int(user_id))
            if member and not member.bot:
                await channel.send(f"🎉 **Joyeux anniversaire {member.mention} !** 🎂")
                sent += 1
        set_last_birthday_notice(today.isoformat())
        log.info("Anniversaires du jour : %d message(s)", sent)
        return sent

    @app_commands.command(
        name="lrcbirthday",
        description="Enregistre ton anniversaire (un formulaire s'ouvre si tu ne donnes pas la date)",
    )
    @app_commands.describe(date="(Optionnel) JJ/MM, ex : 25/12", user="Membre (admin uniquement)")
    async def lrcbirthday(self, interaction: discord.Interaction, date: Optional[str] = None, user: Optional[discord.Member] = None):
        target = user or interaction.user
        if not can_manage(interaction, target):
            await interaction.response.send_message(
                "Seuls les administrateurs peuvent modifier l'anniversaire d'un autre membre.", ephemeral=True)
            return
        if date is None:
            await interaction.response.send_modal(BirthdayModal(target))
            return
        try:
            normalized = save_birthday(target.id, date)
        except ValueError:
            await interaction.response.send_message("Format de date invalide. Utilise JJ/MM (ex : 25/12).", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Anniversaire de {target.mention} enregistré pour le {normalized} 🎂", ephemeral=True)

    @app_commands.command(name="lrcremovebirthday", description="Supprime ton anniversaire (ou celui d'un membre si tu es admin)")
    @app_commands.describe(user="Membre (admin uniquement)")
    async def lrcremovebirthday(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        if not can_manage(interaction, target):
            await interaction.response.send_message(
                "Seuls les administrateurs peuvent modifier l'anniversaire d'un autre membre.", ephemeral=True)
            return
        birthdays = load_birthdays()
        if birthdays.pop(str(target.id), None) is not None:
            save_birthdays(birthdays)
            await interaction.response.send_message(f"Anniversaire de {target.mention} supprimé.", ephemeral=True)
        else:
            await interaction.response.send_message("Aucun anniversaire enregistré pour ce membre.", ephemeral=True)

    @app_commands.command(name="lrcbirthdays", description="Affiche les anniversaires à venir")
    async def lrcbirthdays(self, interaction: discord.Interaction):
        await interaction.response.defer()
        today = datetime.now(TIMEZONE).date()
        upcoming = []
        for user_id, date_str in load_birthdays().items():
            try:
                delta = days_until(date_str, today)
            except ValueError:
                continue
            if delta > 30:
                continue
            member = await find_member(interaction.guild, int(user_id))
            if member:
                when = "aujourd'hui 🎂" if delta == 0 else f"dans {delta} j"
                upcoming.append((delta, f"- {member.mention} : {date_str} ({when})"))
        if upcoming:
            msg = "**Anniversaires à venir (30 jours) :**\n" + "\n".join(line for _, line in sorted(upcoming))
        else:
            msg = "Aucun anniversaire à venir dans les 30 jours."
        await interaction.followup.send(msg)

    @tasks.loop(time=time(hour=8, minute=5, tzinfo=TIMEZONE))
    async def birthday_notifier(self):
        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            log.error("Canal introuvable pour les anniversaires")
            return
        await self.announce_birthdays(channel)

    @birthday_notifier.before_loop
    async def before_birthday_notifier(self):
        await self.bot.wait_until_ready()
        # Rattrapage : bot indisponible à 8h05 (redémarrage, panne)
        now = datetime.now(TIMEZONE)
        if (now.hour, now.minute) >= (8, 5) and get_last_birthday_notice() != now.date().isoformat():
            channel = self.bot.get_channel(CHANNEL_ID)
            if channel:
                await self.announce_birthdays(channel)

    @birthday_notifier.error
    async def birthday_notifier_error(self, error):
        log.exception("Erreur dans birthday_notifier", exc_info=error)


async def setup(bot):
    await bot.add_cog(Birthdays(bot), guild=discord.Object(id=GUILD_ID))
