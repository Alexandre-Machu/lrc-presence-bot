"""Message de présence quotidien, menus, push Google Sheets."""
import logging
import os
from datetime import datetime, time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.settings import (
    CHANNEL_ID, GAMES, GOOGLE_CREDENTIALS_FILE, GOOGLE_SPREADSHEET_ID, GUILD_ID, TIMEZONE,
)
from utils.absences import absent_on, load_absences, purge_past, save_absences
from utils.storage import PresenceState
from utils.times import parse_arrival_time

log = logging.getLogger(__name__)

PRESENCE_TITLE = "Qui sera présent aujourd'hui ?"
GAME_EMOJIS = {g["name"]: g["emoji"] for g in GAMES}
ST_PRESENT, ST_ABSENT, ST_MAYBE = "Présent", "Absent", "Ne sait pas"


def fmt_time(value):
    """'20:30' -> '20h30', 'later' -> 'plus tard'."""
    if not value:
        return ""
    if value == "later":
        return "plus tard"
    return value.replace(":", "h")


# 18h00-20h00 toutes les 30 min, puis toutes les 15 min jusqu'à 23h30
ARRIVAL_SLOTS = (
    ["18:00", "18:30", "19:00", "19:30", "20:00"]
    + [f"{m // 60:02d}:{m % 60:02d}" for m in range(20 * 60 + 15, 23 * 60 + 31, 15)]
)


# ---------------------------------------------------------------- Menus

class PresenceSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Indiquez votre présence",
            custom_id="presence_select",
            options=[
                discord.SelectOption(label="Présent", emoji="✅", value="present", description="Je serai présent"),
                discord.SelectOption(label="Absent", emoji="❌", value="absent", description="Je serai absent"),
                discord.SelectOption(label="Ne sait pas", emoji="❓", value="maybe", description="Je ne sais pas encore"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        state = self.view.cog.state
        state.ensure_today()
        uid = str(interaction.user.id)
        choice = self.values[0]
        if choice == "present":
            state.presence[uid] = ST_PRESENT
            state.maybe.pop(uid, None)
        elif choice == "absent":
            state.presence[uid] = ST_ABSENT
            state.arrival.pop(uid, None)
            state.maybe.pop(uid, None)
        else:
            state.presence[uid] = ST_MAYBE
            state.arrival.pop(uid, None)
        state.save()
        await self.view.cog.refresh(interaction)


class ArrivalTimeSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Heure d'arrivée (ou « pas avant » si pas sûr)",
            custom_id="arrival_time_select",
            options=[discord.SelectOption(label=fmt_time(t), value=t) for t in ARRIVAL_SLOTS]
            + [discord.SelectOption(label="Plus tard", value="later")],
        )

    async def callback(self, interaction: discord.Interaction):
        cog = self.view.cog
        known = cog.set_arrival(interaction.user.id, self.values[0])
        await cog.refresh(interaction)
        if not known:
            await cog.hint_presence_needed(interaction)


class GameSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Sélectionne tes jeux dispo",
            custom_id="game_select",
            min_values=0,
            max_values=len(GAMES),
            options=[
                discord.SelectOption(label=g["name"], value=g["name"], emoji=g["emoji"])
                for g in GAMES
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        cog = self.view.cog
        state = cog.state
        state.ensure_today()
        uid = str(interaction.user.id)
        known = uid in state.presence
        state.games[uid] = list(self.values)
        state.save()
        await cog.refresh(interaction)
        if not known:
            await cog.hint_presence_needed(interaction)


class ExactTimeModal(discord.ui.Modal, title="Heure d'arrivée exacte"):
    heure = discord.ui.TextInput(
        label="Ton heure (ex : 21:40 ou 21h40)",
        placeholder="21:40", min_length=1, max_length=5,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = parse_arrival_time(self.heure.value)
        except ValueError:
            await interaction.response.send_message(
                "Heure invalide. Écris par exemple `21:40` ou `21h40`.", ephemeral=True)
            return
        known = self.cog.set_arrival(interaction.user.id, value)
        await self.cog.refresh(interaction)
        if not known:
            await self.cog.hint_presence_needed(interaction)


class ExactTimeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Heure exacte", emoji="🕒", style=discord.ButtonStyle.secondary,
            custom_id="exact_time", row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ExactTimeModal(self.view.cog))


class AbsencePanelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Mes absences", emoji="📅", style=discord.ButtonStyle.secondary,
            custom_id="absence_panel", row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.client.get_cog("Absences").open_panel(interaction)


class PresenceView(discord.ui.View):
    """Vue persistante : custom_id fixes, ré-enregistrée au chargement du cog."""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(PresenceSelect())
        self.add_item(ArrivalTimeSelect())
        self.add_item(GameSelect())
        self.add_item(ExactTimeButton())
        self.add_item(AbsencePanelButton())


# ---------------------------------------------------------------- Cog

class Presence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.state = PresenceState()
        self.sheets = None
        if os.path.exists(GOOGLE_CREDENTIALS_FILE):
            from utils.sheets_handler import SheetsHandler
            self.sheets = SheetsHandler(GOOGLE_SPREADSHEET_ID)
        else:
            log.info("Pas de config/google_credentials.json : push Google Sheets désactivé")

    async def cog_load(self):
        self.state.load()
        self.bot.add_view(PresenceView(self))  # rend les menus des anciens messages fonctionnels
        self.daily_presence_message.start()
        self.daily_push.start()

    async def cog_unload(self):
        self.daily_presence_message.cancel()
        self.daily_push.cancel()

    # ---- affichage

    def games_emojis(self, uid):
        chosen = self.state.games.get(uid, [])
        return " ".join(emoji for name, emoji in GAME_EMOJIS.items() if name in chosen)

    def build_embed(self):
        state = self.state
        today = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
        presents = [u for u, s in state.presence.items() if s == ST_PRESENT]
        maybe = [u for u, s in state.presence.items() if s == ST_MAYBE]
        absents = [u for u, s in state.presence.items() if s == ST_ABSENT]

        content = f"**Présences pour le {today} :**\n\n"
        if presents:
            content += "**Présents :**\n"
            for uid in presents:
                t = fmt_time(state.arrival.get(uid))
                content += f"- <@{uid}>{f' ({t})' if t else ''} {self.games_emojis(uid)}\n"
        if maybe:
            content += "\n**Personnes pas sûres :**\n"
            for uid in maybe:
                t = fmt_time(state.maybe.get(uid))
                content += f"- <@{uid}>{f' (pas avant {t})' if t else ''} {self.games_emojis(uid)}\n"
        if absents:
            content += "\n**Personnes absentes :**\n"
            for uid in absents:
                content += f"- <@{uid}>\n"

        counts = {g["name"]: 0 for g in GAMES}
        for uid in presents + maybe:
            for jeu in state.games.get(uid, []):
                if jeu in counts:
                    counts[jeu] += 1
        content += "\n**Jeux ce soir :**\n"
        for g in GAMES:
            if counts[g["name"]]:
                content += f"{g['emoji']} {g['name']} : {counts[g['name']]}\n"

        return discord.Embed(
            title=f"{PRESENCE_TITLE} ({today})",
            description=content[:4096],
            color=discord.Color.blue(),
        )

    async def refresh(self, interaction: discord.Interaction):
        """Répond à l'interaction en éditant directement le message qui porte le menu."""
        await interaction.response.edit_message(embed=self.build_embed(), view=PresenceView(self))

    async def hint_presence_needed(self, interaction: discord.Interaction):
        await interaction.followup.send(
            "Indique d'abord ta présence (menu du haut) pour apparaître dans la liste.",
            ephemeral=True,
        )

    async def update_message(self):
        """Met à jour le message du jour depuis le code (ex. absence planifiée)."""
        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel or not self.state.message_id:
            return
        try:
            message = await channel.fetch_message(self.state.message_id)
            await message.edit(embed=self.build_embed(), view=PresenceView(self))
        except discord.NotFound:
            pass

    # ---- messages

    def is_presence_message(self, message: discord.Message):
        return (
            message.author == self.bot.user
            and message.embeds
            and (message.embeds[0].title or "").startswith(PRESENCE_TITLE)
        )

    async def clear_old_presence_messages(self, channel):
        """Supprime uniquement les anciens messages de présence (pas les anniversaires)."""
        try:
            async for message in channel.history(limit=50):
                if self.is_presence_message(message):
                    await message.delete()
        except discord.HTTPException as e:
            log.error("Erreur nettoyage messages : %s", e)

    def apply_planned_absences(self):
        """Pré-remplit « Absent » pour ceux qui ont planifié une absence aujourd'hui."""
        today = datetime.now(TIMEZONE).date()
        absences = load_absences()
        if purge_past(absences, today):
            save_absences(absences)
        for uid in absent_on(absences, today):
            self.state.presence[uid] = ST_ABSENT

    async def send_presence_message(self, channel):
        """Repart d'un état vierge et poste un nouveau message de présence."""
        await self.clear_old_presence_messages(channel)
        self.state.reset(save=False)
        self.apply_planned_absences()
        message = await channel.send(embed=self.build_embed(), view=PresenceView(self))
        self.state.message_id = message.id
        self.state.save()
        return message

    def mark_absent_today(self, uid):
        self.state.ensure_today()
        uid = str(uid)
        self.state.presence[uid] = ST_ABSENT
        self.state.arrival.pop(uid, None)
        self.state.maybe.pop(uid, None)
        self.state.save()

    def set_arrival(self, uid, value):
        """Enregistre l'heure (« pas avant » si le membre n'est pas sûr). Retourne si sa présence était déjà connue."""
        self.state.ensure_today()
        uid = str(uid)
        known = uid in self.state.presence
        if self.state.presence.get(uid) == ST_MAYBE:
            self.state.maybe[uid] = value
        else:
            self.state.arrival[uid] = value
        self.state.save()
        return known

    def set_absent_today(self, uid, absent: bool):
        """Absence ajoutée/retirée pour aujourd'hui depuis le calendrier."""
        if absent:
            self.mark_absent_today(uid)
        elif self.state.presence.get(str(uid)) == ST_ABSENT:
            self.state.ensure_today()
            self.state.presence.pop(str(uid), None)
            self.state.save()

    # ---- commandes

    @app_commands.command(name="lrcreset", description="Réinitialise le message de présence")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def lrcreset(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.send_presence_message(interaction.channel)
        await interaction.followup.send("Message de présence réinitialisé !", ephemeral=True)

    # ---- tâches planifiées (heure de Paris)

    @tasks.loop(time=time(hour=8, minute=0, tzinfo=TIMEZONE))
    async def daily_presence_message(self):
        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            log.error("Canal introuvable pour le message quotidien")
            return
        await self.send_presence_message(channel)
        log.info("Message de présence quotidien envoyé")

    @daily_presence_message.before_loop
    async def before_daily_presence_message(self):
        await self.bot.wait_until_ready()
        # Rattrapage : bot (re)démarré après 8h sans message du jour
        if datetime.now(TIMEZONE).hour >= 8 and self.state.message_id is None:
            channel = self.bot.get_channel(CHANNEL_ID)
            if channel:
                await self.send_presence_message(channel)
                log.info("Message de présence envoyé au démarrage (rattrapage)")

    @daily_presence_message.error
    async def daily_presence_message_error(self, error):
        log.exception("Erreur lors de l'envoi du message quotidien", exc_info=error)

    @tasks.loop(time=time(hour=23, minute=30, tzinfo=TIMEZONE))
    async def daily_push(self):
        if not self.sheets:
            return
        now = datetime.now(TIMEZONE)
        if self.state.date != now.strftime("%d/%m/%Y") or not self.state.presence:
            log.info("Push quotidien : rien à envoyer")
            return
        rows = []
        for uid, presence_state in self.state.presence.items():
            try:
                user = self.bot.get_user(int(uid)) or await self.bot.fetch_user(int(uid))
            except discord.NotFound:
                continue
            if user.bot:
                continue
            if presence_state == ST_PRESENT:
                arrival = self.state.arrival.get(uid)
            elif presence_state == ST_MAYBE:
                arrival = self.state.maybe.get(uid)
            else:
                arrival = None
            rows.append((user.name, presence_state, arrival))
        await self.sheets.add_entries_async(rows, now)
        log.info("Push automatique effectué (%d entrées)", len(rows))

    @daily_push.before_loop
    async def before_daily_push(self):
        await self.bot.wait_until_ready()

    @daily_push.error
    async def daily_push_error(self, error):
        log.exception("Erreur lors du push quotidien", exc_info=error)


async def setup(bot):
    await bot.add_cog(Presence(bot), guild=discord.Object(id=GUILD_ID))
