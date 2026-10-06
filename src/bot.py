import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import date, datetime, time, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config.settings import (
    CHANNEL_ID, DISCORD_TOKEN, GOOGLE_SPREADSHEET_ID, GUILD_ID, TIMEZONE,
)
from utils.sheets_handler import SheetsHandler
from utils.storage import (
    PresenceState, get_last_birthday_notice, load_birthdays, save_birthdays,
    set_last_birthday_notice,
)

VERSION = "V1.5.0"
PRESENCE_TITLE = "Qui sera présent aujourd'hui ?"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lrc-bot")

# Bot setup (plus besoin de message_content ni presences : tout passe par les slash commands)
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)
sheets_handler = SheetsHandler(GOOGLE_SPREADSHEET_ID)
GUILD = discord.Object(id=GUILD_ID)

state = PresenceState()

GAMES = [
    {"name": "CS2", "emoji": "<:cs2:1413650875255099494>"},
    {"name": "League Of Legends", "emoji": "<:LoLIcon:1413650879315443814>"},
    {"name": "R.E.P.O", "emoji": "<:Repolicon:1413650886252695763>"},
    {"name": "Monster Hunter", "emoji": "<:MHIcon:1413650881865322546>"},
    {"name": "Jeux du soir", "emoji": "✨"},
    {"name": "Valorant", "emoji": "<:Valolicon:1413650888391659520>"},
    {"name": "VGMQ", "emoji": "<:VGMQLogo:1413650890061250743>"},
    {"name": "D&D", "emoji": "<:DDIcon:1413652803351613470>"},
    {"name": "AMQ", "emoji": "<:AMQIcon:1413650873267130562>"},
    {"name": "Minecraft", "emoji": "<:MinecraftIcon:1413650884184899594>"},
    {"name": "DBD", "emoji": "<:DBDIcon:1413652799610163220>"},
    {"name": "OW", "emoji": "<:OWIcon:1413652805755076809>"},
    {"name": "Among Us", "emoji": "<:AmongUsIcon:1413653484963627170>"},
    {"name": "Jeux de golf", "emoji": "⛳"},
]
GAME_EMOJIS = {g["name"]: g["emoji"] for g in GAMES}

ST_PRESENT, ST_ABSENT, ST_MAYBE = "Présent", "Absent", "Ne sait pas"


# ---------------------------------------------------------------- Affichage

def fmt_time(value):
    """'20:30' -> '20h30', 'later' -> 'plus tard'."""
    if not value:
        return ""
    if value == "later":
        return "plus tard"
    return value.replace(":", "h")


def games_emojis(user_id):
    chosen = state.games.get(user_id, [])
    return " ".join(GAME_EMOJIS[name] for name in GAME_EMOJIS if name in chosen)


def build_embed():
    today = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
    presents = [u for u, s in state.presence.items() if s == ST_PRESENT]
    maybe = [u for u, s in state.presence.items() if s == ST_MAYBE]
    absents = [u for u, s in state.presence.items() if s == ST_ABSENT]

    content = f"**Présences pour le {today} :**\n\n"
    if presents:
        content += "**Présents :**\n"
        for uid in presents:
            t = fmt_time(state.arrival.get(uid))
            content += f"- <@{uid}>{f' ({t})' if t else ''} {games_emojis(uid)}\n"
    if maybe:
        content += "\n**Personnes pas sûres :**\n"
        for uid in maybe:
            t = fmt_time(state.maybe.get(uid))
            content += f"- <@{uid}>{f' (pas avant {t})' if t else ''} {games_emojis(uid)}\n"
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


async def refresh(interaction: discord.Interaction):
    """Répond à l'interaction en éditant directement le message qui porte le menu."""
    await interaction.response.edit_message(embed=build_embed(), view=PresenceView())


async def hint_presence_needed(interaction: discord.Interaction):
    await interaction.followup.send(
        "Indique d'abord ta présence (menu du haut) pour apparaître dans la liste.",
        ephemeral=True,
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
        await refresh(interaction)


class ArrivalTimeSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Heure d'arrivée (ou « pas avant » si pas sûr)",
            custom_id="arrival_time_select",
            options=[
                discord.SelectOption(label="20h30", value="20:30"),
                discord.SelectOption(label="20h45", value="20:45"),
                discord.SelectOption(label="21h00", value="21:00"),
                discord.SelectOption(label="21h15", value="21:15"),
                discord.SelectOption(label="21h30", value="21:30"),
                discord.SelectOption(label="Plus tard", value="later"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        state.ensure_today()
        uid = str(interaction.user.id)
        value = self.values[0]
        known = uid in state.presence
        if state.presence.get(uid) == ST_MAYBE:
            state.maybe[uid] = value
        else:
            state.arrival[uid] = value
        state.save()
        await refresh(interaction)
        if not known:
            await hint_presence_needed(interaction)


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
        state.ensure_today()
        uid = str(interaction.user.id)
        known = uid in state.presence
        state.games[uid] = list(self.values)
        state.save()
        await refresh(interaction)
        if not known:
            await hint_presence_needed(interaction)


class PresenceView(discord.ui.View):
    """Vue persistante : custom_id fixes, ré-enregistrée au démarrage (setup_hook)."""

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PresenceSelect())
        self.add_item(ArrivalTimeSelect())
        self.add_item(GameSelect())


# ---------------------------------------------------------------- Messages

def is_presence_message(message: discord.Message):
    return (
        message.author == bot.user
        and message.embeds
        and (message.embeds[0].title or "").startswith(PRESENCE_TITLE)
    )


async def clear_old_presence_messages(channel):
    """Supprime uniquement les anciens messages de présence (pas les anniversaires)."""
    try:
        async for message in channel.history(limit=50):
            if is_presence_message(message):
                await message.delete()
    except discord.HTTPException as e:
        log.error("Erreur nettoyage messages : %s", e)


async def send_presence_message(channel):
    """Repart d'un état vierge et poste un nouveau message de présence."""
    await clear_old_presence_messages(channel)
    state.reset(save=False)
    message = await channel.send(embed=build_embed(), view=PresenceView())
    state.message_id = message.id
    state.save()
    return message


# ---------------------------------------------------------------- Anniversaires

def parse_birthday(date_str):
    """'JJ/MM' -> (jour, mois). Lève ValueError si invalide (29/02 accepté)."""
    d = datetime.strptime(f"{date_str}/2000", "%d/%m/%Y")
    return d.day, d.month


def birthday_on(year, day, month):
    try:
        return date(year, month, day)
    except ValueError:  # 29/02 les années non bissextiles
        return date(year, 2, 28)


def days_until(date_str, today: date):
    day, month = parse_birthday(date_str)
    nxt = birthday_on(today.year, day, month)
    if nxt < today:
        nxt = birthday_on(today.year + 1, day, month)
    return (nxt - today).days


async def find_member(guild: discord.Guild, user_id: int):
    """Membre du serveur, même s'il n'est pas dans le cache ; None s'il est parti."""
    member = guild.get_member(user_id)
    if member:
        return member
    try:
        return await guild.fetch_member(user_id)
    except discord.NotFound:
        return None


async def announce_birthdays(channel):
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


# ---------------------------------------------------------------- Permissions

admin_only = app_commands.default_permissions(administrator=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "Cette commande est réservée aux administrateurs."
    else:
        log.exception("Erreur de commande", exc_info=error)
        msg = "Une erreur est survenue."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


# ---------------------------------------------------------------- Commandes

@bot.tree.command(name="lrcinfo", description="Affiche les informations sur les commandes du bot", guild=GUILD)
async def lrcinfo(interaction: discord.Interaction):
    info_message = f"""
🤖 **Bot LRC - Guide des commandes {VERSION}**

━━━━━━━━━ **Commandes** ━━━━━━━━━

**Utilisateur**
• `/lrcbirthdays` - Affiche les anniversaires à venir (30 jours)

**Administrateur**
• `/lrcreset` - Réinitialisation et nouveau message de présence
• `/lrcaddbirthday @user JJ/MM` - Ajoute ou modifie l'anniversaire d'un membre
• `/lrcremovebirthday @user` - Supprime l'anniversaire d'un membre

━━━━━━━━ **Paramètres** ━━━━━━━━

**États de présence**
• ✅ Présent
• ❌ Absent
• ❓ Ne sait pas (l'heure choisie devient « pas avant »)

**Horaires disponibles**
• 20h30 → 21h30 (par palier de 15min), ou plus tard

**Jeux disponibles**
• Sélectionne tes jeux via le menu (emojis personnalisés)
• Le message affiche le nombre de joueurs par jeu

**Automatisation (heure de Paris)**
• Message quotidien → 8h00
• Notification anniversaire → 8h05
• Push Google Sheets → 23h30
"""
    await interaction.response.send_message(info_message, ephemeral=True)


@bot.tree.command(name="lrcaddbirthday", description="Ajoute ou modifie la date d'anniversaire d'un membre", guild=GUILD)
@admin_only
@app_commands.checks.has_permissions(administrator=True)
async def lrcaddbirthday(interaction: discord.Interaction, user: discord.Member, date: str):
    try:
        day, month = parse_birthday(date)
    except ValueError:
        await interaction.response.send_message("Format de date invalide. Utilisez JJ/MM.", ephemeral=True)
        return
    normalized = f"{day:02d}/{month:02d}"
    birthdays = load_birthdays()
    birthdays[str(user.id)] = normalized
    save_birthdays(birthdays)
    await interaction.response.send_message(
        f"Anniversaire de {user.mention} enregistré pour le {normalized} !", ephemeral=True
    )


@bot.tree.command(name="lrcbirthdays", description="Affiche les anniversaires à venir", guild=GUILD)
async def lrcbirthdays(interaction: discord.Interaction):
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


@bot.tree.command(name="lrcremovebirthday", description="Supprime l'anniversaire d'un membre", guild=GUILD)
@admin_only
@app_commands.checks.has_permissions(administrator=True)
async def lrcremovebirthday(interaction: discord.Interaction, user: discord.Member):
    birthdays = load_birthdays()
    if birthdays.pop(str(user.id), None) is not None:
        save_birthdays(birthdays)
        await interaction.response.send_message(f"Anniversaire de {user.mention} supprimé.", ephemeral=True)
    else:
        await interaction.response.send_message("Aucun anniversaire enregistré pour ce membre.", ephemeral=True)


@bot.tree.command(name="lrcreset", description="Réinitialise le message de présence", guild=GUILD)
@admin_only
@app_commands.checks.has_permissions(administrator=True)
async def lrcreset(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await send_presence_message(interaction.channel)
    await interaction.followup.send("Message de présence réinitialisé !", ephemeral=True)


# ---------------------------------------------------------------- Tâches planifiées (heure de Paris)

@tasks.loop(time=time(hour=23, minute=30, tzinfo=TIMEZONE))
async def daily_push():
    if state.date != datetime.now(TIMEZONE).strftime("%d/%m/%Y") or not state.presence:
        log.info("Push quotidien : rien à envoyer")
        return
    rows = []
    for uid, presence_state in state.presence.items():
        try:
            user = bot.get_user(int(uid)) or await bot.fetch_user(int(uid))
        except discord.NotFound:
            continue
        if user.bot:
            continue
        if presence_state == ST_PRESENT:
            arrival = state.arrival.get(uid)
        elif presence_state == ST_MAYBE:
            arrival = state.maybe.get(uid)
        else:
            arrival = None
        rows.append((user.name, presence_state, arrival))
    await sheets_handler.add_entries_async(rows, datetime.now(TIMEZONE))
    log.info("Push automatique effectué (%d entrées)", len(rows))


@daily_push.error
async def daily_push_error(error):
    log.exception("Erreur lors du push quotidien", exc_info=error)


@tasks.loop(time=time(hour=8, minute=0, tzinfo=TIMEZONE))
async def daily_presence_message():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        log.error("Canal introuvable pour le message quotidien")
        return
    await send_presence_message(channel)
    log.info("Message de présence quotidien envoyé")


@daily_presence_message.before_loop
async def before_daily_presence_message():
    await bot.wait_until_ready()
    # Rattrapage : bot (re)démarré après 8h sans message du jour
    now = datetime.now(TIMEZONE)
    if now.hour >= 8 and state.message_id is None:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await send_presence_message(channel)
            log.info("Message de présence envoyé au démarrage (rattrapage)")


@daily_presence_message.error
async def daily_presence_message_error(error):
    log.exception("Erreur lors de l'envoi du message quotidien", exc_info=error)


@tasks.loop(time=time(hour=8, minute=5, tzinfo=TIMEZONE))
async def birthday_notifier():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        log.error("Canal introuvable pour les anniversaires")
        return
    await announce_birthdays(channel)


@birthday_notifier.before_loop
async def before_birthday_notifier():
    await bot.wait_until_ready()
    # Rattrapage : bot indisponible à 8h05 (redémarrage, panne)
    now = datetime.now(TIMEZONE)
    if (now.hour, now.minute) >= (8, 5) and get_last_birthday_notice() != now.date().isoformat():
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await announce_birthdays(channel)


@birthday_notifier.error
async def birthday_notifier_error(error):
    log.exception("Erreur dans birthday_notifier", exc_info=error)


@daily_push.before_loop
async def before_daily_push():
    await bot.wait_until_ready()


# ---------------------------------------------------------------- Cycle de vie

@bot.event
async def setup_hook():
    # Exécuté une seule fois (contrairement à on_ready, rappelé à chaque reconnexion)
    state.load()
    bot.add_view(PresenceView())  # rend les menus des anciens messages fonctionnels
    try:
        synced = await bot.tree.sync(guild=GUILD)
        log.info("Commandes slash synchronisées (%d)", len(synced))
    except discord.HTTPException as e:
        log.error("Erreur sync commandes : %s", e)
    daily_push.start()
    daily_presence_message.start()
    birthday_notifier.start()


@bot.event
async def on_ready():
    log.info("%s est connecté !", bot.user)
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.playing, name=f"/lrcinfo | {VERSION}"
    ))


if __name__ == "__main__":
    if not DISCORD_TOKEN or not CHANNEL_ID:
        sys.exit("DISCORD_TOKEN et CHANNEL_ID doivent être définis dans .env")
    bot.run(DISCORD_TOKEN)
