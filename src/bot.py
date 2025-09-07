import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord.ext import commands, tasks
from discord.ui import Select, View
from datetime import datetime, timedelta, time
import json

from config.settings import *
from utils.sheets_handler import SheetsHandler

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
intents.presences = True
intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=intents)
sheets_handler = SheetsHandler(GOOGLE_SPREADSHEET_ID)

GUILD_ID = 948537493593129011  # Ton serveur Discord

# Variables globales
arrival_times = {}      # {user_id: time}
maybe_times = {}        # {user_id: time}
presence_states = {}    # {user_id: state}
user_games = {}         # {user_id: [jeu_name, ...]}

GAMES = [
    {"name": "CS2", "emoji": "<:cs2:1413650875255099494>"},
    {"name": "League Of Legends", "emoji": "<:LoLIcon:1413650879315443814>"},
    {"name": "R.E.P.O", "emoji": "<:Repolicon:1413650886252695763>"},
    {"name": "Monster Hunter", "emoji": "<:MHIcon:1413650881865322546>"},
    {"name": "Jeux du soir", "emoji": "✨"},
    {"name": "Valorant", "emoji": "<:Valolicon:1413650888391659520>"},
    {"name": "VGMQ", "emoji": "<:VGMQLogo:1413650890061250743>"},
    {"name": "Dales & Dawson", "emoji": "<:DDIcon:1413652803351613470>"},
    {"name": "AMQ", "emoji": "<:AMQIcon:1413650873267130562>"},
    {"name": "Minecraft", "emoji": "<:MinecraftIcon:1413650884184899594>"},
    {"name": "DBD", "emoji": "<:DBDIcon:1413652799610163220>"},
    {"name": "OW", "emoji": "<:OWIcon:1413652805755076809>"},
    {"name": "Among Us", "emoji": "<:AmongUsIcon:1413653484963627170>"},
    {"name": "Jeux de golf", "emoji": "⛳"},
]

BIRTHDAYS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "birthdays.json")

def load_birthdays():
    if not os.path.exists(BIRTHDAYS_FILE):
        return {}
    with open(BIRTHDAYS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_birthdays(data):
    with open(BIRTHDAYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@bot.event
async def on_ready():
    print(f'{bot.user} est connecté!')
    try:
        commands_synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Commandes slash synchronisées ({len(commands_synced)})")
    except Exception as e:
        print(f"Erreur sync commandes : {e}")

    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name="/lrcinfo | V1.4.3"  # <-- Upgrade version ici
    )
    await bot.change_presence(activity=activity)
    daily_push.start()
    daily_presence_message.start()
    birthday_notifier.start()

async def clear_old_presence_messages(channel):
    try:
        async for message in channel.history(limit=100):
            if message.author == bot.user:
                await message.delete()
    except Exception as e:
        print(f"Erreur nettoyage messages : {e}")

async def send_presence_message(channel):
    try:
        await clear_old_presence_messages(channel)
        today = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
        embed = discord.Embed(
            title=f"Qui sera présent aujourd'hui ? ({today})",
            description="Utilisez le menu déroulant ci-dessous pour indiquer votre présence",
            color=discord.Color.blue()
        )
        view = PresenceButtons()
        message = await channel.send(embed=embed, view=view)
        return message
    except Exception as e:
        print(f"Erreur envoi message présence : {e}")
        return None

class ArrivalTimeSelect(Select):
    def __init__(self, user_id: int = None, is_maybe: bool = False):
        self.is_maybe = is_maybe
        if not is_maybe:
            options = [
                discord.SelectOption(label="20h30", value="20:30"),
                discord.SelectOption(label="20h45", value="20:45"),
                discord.SelectOption(label="21h00", value="21:00"),
                discord.SelectOption(label="21h15", value="21:15"),
                discord.SelectOption(label="21h30", value="21:30"),
                discord.SelectOption(label="Plus tard", value="later")
            ]
            placeholder = "Sélectionnez votre heure d'arrivée"
        else:
            options = [
                discord.SelectOption(label="21h30", value="21:30+"),
                discord.SelectOption(label="21h45", value="21:45+"),
                discord.SelectOption(label="22h00", value="22:00+"),
                discord.SelectOption(label="22h15", value="22:15+"),
                discord.SelectOption(label="22h30", value="22:30+"),
                discord.SelectOption(label="Plus tard", value="later")
            ]
            placeholder = "Pas avant quelle heure ?"
        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id=f"arrival_time_{user_id if user_id else 'any'}"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            time = self.values[0]
            user_id = str(interaction.user.id)
            if self.is_maybe:
                maybe_times[user_id] = time
                arrival_times.pop(user_id, None)
            else:
                arrival_times[user_id] = time
                maybe_times.pop(user_id, None)
            # Met à jour le message principal
            channel = interaction.channel
            async for message in channel.history(limit=10):
                if (message.author == interaction.client.user and 
                    hasattr(message, 'embeds') and 
                    message.embeds and
                    "Qui sera présent aujourd'hui ?" in message.embeds[0].title):
                    view = PresenceButtons()
                    await interaction.response.defer()
                    await view.update_presence_message(message)
                    break
        except Exception as e:
            print(f"Error in ArrivalTimeSelect callback: {e}")

class GameSelect(discord.ui.Select):
    def __init__(self, user_id):
        options = [
            discord.SelectOption(label=game["name"], value=game["name"], emoji=game["emoji"])
            for game in GAMES
        ]
        super().__init__(
            placeholder="Sélectionne tes jeux dispo",
            options=options,
            min_values=0,
            max_values=len(options),
            custom_id=f"game_select_{user_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            user_id = str(interaction.user.id)
            user_games[user_id] = self.values
            # Met à jour le message principal
            channel = interaction.channel
            async for message in channel.history(limit=10):
                if (message.author == interaction.client.user and 
                    hasattr(message, 'embeds') and 
                    message.embeds and
                    "Qui sera présent aujourd'hui ?" in message.embeds[0].title):
                    view = PresenceButtons()
                    await interaction.response.defer()
                    await view.update_presence_message(message)
                    break
        except Exception as e:
            print(f"Error in GameSelect callback: {e}")

class PresenceSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Présent",
                emoji="✅",
                value="present",
                description="Je serai présent"
            ),
            discord.SelectOption(
                label="Absent",
                emoji="❌",
                value="absent",
                description="Je serai absent"
            ),
            discord.SelectOption(
                label="Ne sait pas",
                emoji="❓",
                value="maybe",
                description="Je ne sais pas encore"
            )
        ]
        super().__init__(
            placeholder="Indiquez votre présence",
            options=options,
            custom_id="presence_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        try:
            choice = self.values[0]
            user_id = str(interaction.user.id)
            if choice == "present":
                presence_states[user_id] = "Présent"
                maybe_times.pop(user_id, None)
            elif choice == "absent":
                presence_states[user_id] = "Absent"
                arrival_times.pop(user_id, None)
                maybe_times.pop(user_id, None)
                user_games.pop(user_id, None)
            else:
                presence_states[user_id] = "Ne sait pas"
                arrival_times.pop(user_id, None)
            # Met à jour le message principal
            channel = interaction.channel
            async for message in channel.history(limit=10):
                if (message.author == interaction.client.user and 
                    hasattr(message, 'embeds') and 
                    message.embeds and
                    "Qui sera présent aujourd'hui ?" in message.embeds[0].title):
                    view = PresenceButtons()
                    await interaction.response.defer()
                    await view.update_presence_message(message)
                    break
        except Exception as e:
            print(f"Error in PresenceSelect callback: {e}")
            await interaction.response.send_message(f"Erreur d'interaction : {e}", ephemeral=True)

class PresenceButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PresenceSelect())
        # Menus pour l'utilisateur courant (affichés à tous, mais chaque user peut interagir)
        self.add_item(ArrivalTimeSelect(None, False))
        self.add_item(GameSelect(None))
        self.add_item(ResendArrivalTimeButton(None, False))
        self.add_item(ResendGameButton(None))

    async def update_presence_message(self, message):
        today = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
        content = f"**Présences pour le {today} :**\n\n"
        presents = [k for k, v in presence_states.items() if v == "Présent"]
        absents = [k for k, v in presence_states.items() if v == "Absent"]
        maybe = [k for k, v in presence_states.items() if v == "Ne sait pas"]

        if presents:
            content += "**Présents :**\n"
            for user_id in presents:
                user = message.guild.get_member(int(user_id))
                if user:
                    time = arrival_times.get(user_id, "")
                    time_str = f" ({time})" if time else ""
                    jeux = user_games.get(user_id, [])
                    jeux_emojis = " ".join([game["emoji"] for game in GAMES if game["name"] in jeux])
                    content += f"- {user.mention}{time_str} {jeux_emojis}\n"

        if maybe:
            content += "\n**Personnes pas sûres :**\n"
            for user_id in maybe:
                user = message.guild.get_member(int(user_id))
                if user:
                    time = maybe_times.get(user_id, "")
                    time_str = f" (pas avant {time})" if time else ""
                    jeux = user_games.get(user_id, [])
                    jeux_emojis = " ".join([game["emoji"] for game in GAMES if game["name"] in jeux])
                    content += f"- {user.mention}{time_str} {jeux_emojis}\n"

        if absents:
            content += "\n**Personnes absentes :**\n"
            for user_id in absents:
                user = message.guild.get_member(int(user_id))
                if user:
                    content += f"- {user.mention}\n"

        # Compteur de jeux EN DESSOUS
        game_counts = {game["name"]: 0 for game in GAMES}
        for user_id in presents + maybe:
            for jeu in user_games.get(user_id, []):
                if jeu in game_counts:
                    game_counts[jeu] += 1

        content += "\n**Jeux ce soir :**\n"
        for game in GAMES:
            count = game_counts[game["name"]]
            if count > 0:
                content += f"{game['emoji']} {game['name']} : {count}\n"

        embed = message.embeds[0]
        embed.description = content
        await message.edit(embed=embed, view=self)

class ResendArrivalTimeView(View):
    def __init__(self, user_id, is_maybe):
        super().__init__(timeout=None)
        self.add_item(ArrivalTimeSelect(user_id, is_maybe))
        self.add_item(ResendArrivalTimeButton(user_id, is_maybe))

class ResendGameView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.add_item(GameSelect(user_id))
        self.add_item(ResendGameButton(user_id))

# Modifie les boutons pour utiliser l'user courant
class ResendArrivalTimeButton(discord.ui.Button):
    def __init__(self, user_id, is_maybe):
        super().__init__(label="Renvoyer le menu heure", style=discord.ButtonStyle.secondary)
        self.user_id = user_id
        self.is_maybe = is_maybe

    async def callback(self, interaction: discord.Interaction):
        view = PresenceButtons()
        await interaction.response.send_message(
            "Sélectionnez à nouveau votre heure d'arrivée.",
            view=view,
            ephemeral=True
        )

class ResendGameButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Renvoyer le menu jeux", style=discord.ButtonStyle.secondary)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        view = PresenceButtons()
        await interaction.response.send_message(
            "Sélectionnez à nouveau vos jeux dispo.",
            view=view,
            ephemeral=True
        )

@bot.tree.command(
    name="lrcinfo",
    description="Affiche les informations sur les commandes du bot",
    guild=discord.Object(id=GUILD_ID)
)
async def lrcinfo(interaction: discord.Interaction):
    info_message = """
🤖 **Bot LRC - Guide des commandes V1.4.3**

━━━━━━━━━ **Commandes** ━━━━━━━━━

**Utilisateur**
• `/lrcshowpresence [date]` - Liste des présences et jeux choisis
  › Sans date : présences du jour
  › Avec date : historique (DD/MM/YYYY)
• `/lrcbirthdays` - Affiche les anniversaires à venir

**Administrateur**
• `/lrcsendpresencemessage` - Nouveau message de présence
• `/lrcpush [date]` - Export vers Google Sheets
• `/lrcreset` - Réinitialisation du message
• `/lrcaddbirthday @user JJ/MM` - Ajoute ou modifie l'anniversaire d'un membre
• `/lrcremovebirthday @user` - Supprime l'anniversaire d'un membre

━━━━━━━━ **Paramètres** ━━━━━━━━

**États de présence**
• ✅ Présent
• ❌ Absent
• ❓ Ne sait pas

**Horaires disponibles**
• Présent : 20h30 → 21h30 (par palier de 15min)
• Ne sait pas : à partir de 21h30

**Jeux disponibles**
• Sélectionne tes jeux via le menu (emojis personnalisés)
• Le message affiche le nombre de joueurs par jeu

**Automatisation**
• Message quotidien → 8h00
• Push des données → 23h30
• Notification anniversaire → 8h05

"""
    await interaction.response.send_message(info_message, ephemeral=True)

@bot.tree.command(
    name="lrcaddbirthday",
    description="Ajoute ou modifie la date d'anniversaire d'un membre",
    guild=discord.Object(id=GUILD_ID)
)
async def lrcaddbirthday(interaction: discord.Interaction, user: discord.Member, date: str):
    try:
        try:
            datetime.strptime(date, "%d/%m")
        except ValueError:
            await interaction.response.send_message("Format de date invalide. Utilisez JJ/MM.", ephemeral=True)
            return
        birthdays = load_birthdays()
        birthdays[str(user.id)] = date
        save_birthdays(birthdays)
        await interaction.response.send_message(f"Anniversaire de {user.mention} enregistré pour le {date} !", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Erreur : {e}", ephemeral=True)

@bot.tree.command(
    name="lrcbirthdays",
    description="Affiche les anniversaires à venir",
    guild=discord.Object(id=GUILD_ID)
)
async def lrcbirthdays(interaction: discord.Interaction):
    try:
        birthdays = load_birthdays()
        today = datetime.now(TIMEZONE)
        upcoming = []
        for user_id, date_str in birthdays.items():
            bday = datetime.strptime(date_str, "%d/%m")
            bday_this_year = bday.replace(year=today.year)
            delta = (bday_this_year - today).days
            if 0 <= delta <= 30:
                member = interaction.guild.get_member(int(user_id))
                if member:
                    upcoming.append(f"- {member.mention} : {date_str}")
        if upcoming:
            msg = "**Anniversaires à venir (30 jours) :**\n" + "\n".join(upcoming)
        else:
            msg = "Aucun anniversaire à venir dans les 30 jours."
        await interaction.response.send_message(msg)
    except Exception as e:
        await interaction.response.send_message(f"Erreur : {e}")

@bot.tree.command(
    name="lrcremovebirthday",
    description="Supprime l'anniversaire d'un membre",
    guild=discord.Object(id=GUILD_ID)
)
async def lrcremovebirthday(interaction: discord.Interaction, user: discord.Member):
    try:
        birthdays = load_birthdays()
        if str(user.id) in birthdays:
            del birthdays[str(user.id)]
            save_birthdays(birthdays)
            await interaction.response.send_message(f"Anniversaire de {user.mention} supprimé.", ephemeral=True)
        else:
            await interaction.response.send_message("Aucun anniversaire enregistré pour ce membre.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Erreur : {e}", ephemeral=True)

@bot.tree.command(
    name="lrcreset",
    description="Réinitialise le message de présence",
    guild=discord.Object(id=GUILD_ID)
)
async def lrcreset(interaction: discord.Interaction):
    arrival_times.clear()
    maybe_times.clear()
    presence_states.clear()
    user_games.clear()
    channel = interaction.channel
    await clear_old_presence_messages(channel)
    await send_presence_message(channel)
    await interaction.response.send_message("Message de présence réinitialisé !", ephemeral=True)

@tasks.loop(time=time(hour=21, minute=30))
async def daily_push():
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print("Erreur: Canal introuvable pour le push quotidien")
            return
        today = datetime.now(TIMEZONE)
        count = 0
        for user_id, presence_state in presence_states.items():
            try:
                user = await bot.fetch_user(int(user_id))
                if user and not user.bot:
                    arrival_time = None
                    if presence_state == "Présent":
                        arrival_time = arrival_times.get(user_id)
                    elif presence_state == "Ne sait pas":
                        arrival_time = maybe_times.get(user_id)
                    sheets_handler.add_entry(user.name, presence_state, TIMEZONE, today, arrival_time)
                    count += 1
            except discord.NotFound:
                continue
        print(f"Push automatique effectué ({count} entrées)")
    except Exception as e:
        print(f"Erreur lors du push quotidien : {str(e)}")

@tasks.loop(time=time(hour=8, minute=0))
async def daily_presence_message():
    try:
        arrival_times.clear()
        maybe_times.clear()
        presence_states.clear()
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await clear_old_presence_messages(channel)
            await send_presence_message(channel)
            print("Message de présence quotidien envoyé")
        else:
            print("Erreur: Canal introuvable pour le message quotidien")
    except Exception as e:
        print(f"Erreur lors de l'envoi du message quotidien : {str(e)}")

@tasks.loop(time=time(hour=8, minute=5))
async def birthday_notifier():
    try:
        birthdays = load_birthdays()
        today = datetime.now(TIMEZONE).strftime("%d/%m")
        channel = bot.get_channel(CHANNEL_ID)
        for user_id, date_str in birthdays.items():
            if date_str == today:
                member = channel.guild.get_member(int(user_id))
                if member:
                    await channel.send(f"🎉 **Joyeux anniversaire {member.mention} !** 🎂")
    except Exception as e:
        print(f"Erreur dans birthday_notifier : {e}")

@bot.command()
async def sync(ctx):
    synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    await ctx.send(f"Commandes slash synchronisées ({len(synced)})")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)