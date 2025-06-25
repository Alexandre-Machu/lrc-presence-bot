import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord.ext import commands
from discord.ui import Select, View
from datetime import datetime, timedelta
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

@bot.event
async def on_ready():
    print(f'{bot.user} est connecté!')
    
    try:
        # Synchronise les nouvelles commandes
        commands = await bot.tree.sync()
        print(f"Les commandes ont été resynchronisées avec succès! ({len(commands)} commandes)")
    except Exception as e:
        print(f"Erreur lors de la synchronisation des commandes: {e}")

async def send_presence_message(channel):
    today = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
    
    # Create the base message
    embed = discord.Embed(
        title=f"Qui sera présent aujourd'hui ? ({today})",
        description=(
            f"{EMOJI_PRESENT} : Présent\n"
            f"{EMOJI_ABSENT} : Absent\n"
            f"{EMOJI_MAYBE} : Ne sait pas"
        ),
        color=discord.Color.blue()
    )
    
    message = await channel.send(embed=embed)
    
    for emoji in [EMOJI_PRESENT, EMOJI_ABSENT, EMOJI_MAYBE]:
        await message.add_reaction(emoji)
    
    return message

@bot.tree.command(
    name="lrcshowpresence", 
    description="Affiche la liste des personnes présentes pour une date donnée"
)
async def lrcshowpresence(
    interaction: discord.Interaction, 
    date: str = None
):
    await interaction.response.defer(ephemeral=False)
    
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if date is None:
            target_date = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
        else:
            # Valider le format de la date
            try:
                datetime.strptime(date, "%d/%m/%Y")
                target_date = date
            except ValueError:
                await interaction.followup.send("Format de date invalide. Utilisez le format DD/MM/YYYY")
                return

        # Trouve le message pour la date donnée
        presence_message = None
        async for message in channel.history(limit=100):
            if message.author == bot.user and target_date in message.content:
                presence_message = message
                break

        if not presence_message:
            await interaction.followup.send(f"Aucun message de présence trouvé pour le {target_date}")
            return

        # Initialise les listes pour chaque catégorie
        presents = set()
        maybe = set()
        
        # Récupère les membres du serveur
        guild = interaction.guild
        
        # Traite les réactions du message
        for reaction in presence_message.reactions:
            if str(reaction.emoji) == EMOJI_PRESENT:
                async for user in reaction.users():
                    if not user.bot:
                        member = guild.get_member(user.id)
                        presents.add(member.mention)
            elif str(reaction.emoji) == EMOJI_MAYBE:
                async for user in reaction.users():
                    if not user.bot:
                        member = guild.get_member(user.id)
                        maybe.add(member.mention)
        
        # Construit le message
        message_parts = []
        
        if presents:
            present_list = []
            for mention in sorted(presents):
                arrival_time = sheets_handler.get_arrival_time(mention)
                time_str = f" ({arrival_time})" if arrival_time else ""
                present_list.append(f"- {mention}{time_str}")
            message_parts.append(f"**Personnes présentes ce soir :**\n{'\n'.join(present_list)}")
        
        if maybe:
            maybe_list = "\n- ".join(sorted(maybe))
            message_parts.append(f"\n\n**Personnes pas sûres :**\n- {maybe_list}")
        
        if not presents and not maybe:
            await interaction.followup.send("**Personne n'est encore présent pour aujourd'hui** 😢\nUtilisez `/lrcpresent` ou réagissez avec ✅ pour indiquer votre présence!")
            return
            
        final_message = "\n".join(message_parts)
        await interaction.followup.send(final_message)
        
    except Exception as e:
        await interaction.followup.send(f"Une erreur est survenue : {str(e)}")

@bot.tree.command(name="lrcshowstats", description="Affiche les statistiques de présence")
async def lrcshowstats(interaction: discord.Interaction):
    try:
        df = sheets_handler.get_stats()
        # Ajouter ici la logique pour afficher les stats depuis Google Sheets
        await interaction.response.send_message("Fonctionnalité en cours de développement")
    except Exception as e:
        await interaction.response.send_message("Une erreur est survenue lors de la récupération des statistiques.")

@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user:
        return

    if reaction.message.author == bot.user:
        presence = PRESENCE_STATUS.get(str(reaction.emoji))
        if presence == "Présent":
            # Create time selector
            view = View()
            time_select = ArrivalTimeSelect(user.id)
            view.add_item(time_select)
            await reaction.message.channel.send(
                f"{user.mention}, à quelle heure pensez-vous arriver?",
                view=view,
                delete_after=60
            )

@bot.event
async def on_reaction_remove(reaction, user):
    if user == bot.user:
        return

    if reaction.message.author == bot.user:
        today = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
        if today in reaction.message.content:
            # Si on retire une réaction "présent", on met à jour l'Excel
            if str(reaction.emoji) == EMOJI_PRESENT:
                df = sheets_handler.load_or_create()
                today_date = datetime.now(TIMEZONE).date()
                # Supprime l'entrée pour aujourd'hui
                df = df[~((df['Date'].dt.date == today_date) & (df['Personne'] == user.name))]
                df.to_excel(EXCEL_FILE, index=False)

@bot.tree.command(name="lrcsendpresencemessage", description="Envoie manuellement un message de présence pour aujourd'hui")
async def lrcsendpresencemessage(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Vous n'avez pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await interaction.response.send_message("Le canal configuré est introuvable.", ephemeral=True)
        return

    # Vérifier si un message existe déjà pour aujourd'hui
    today = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
    async for message in channel.history(limit=50):
        if message.author == bot.user and today in message.content:
            await interaction.response.send_message("Un message de présence existe déjà pour aujourd'hui.", ephemeral=True)
            return

    await interaction.response.defer(ephemeral=True)
    await send_presence_message(channel)
    await interaction.followup.send("Message de présence envoyé avec succès!", ephemeral=True)

@bot.tree.command(name="lrcinfo", description="Affiche les informations sur les commandes du bot")
async def lrcinfo(interaction: discord.Interaction):
    info_message = f"""
**🤖 Bot LRC - Guide des commandes**

**Liens utiles :**
• Google Sheets : https://docs.google.com/spreadsheets/d/{GOOGLE_SPREADSHEET_ID}
• GitHub : https://github.com/Alexandre-Machu/lrc-presence-bot

**Commandes d'information :**
• `/lrcshowpresence [date]` - Affiche la liste des présences
  - Sans date : affiche les présences du jour
  - Avec date : affiche les présences pour la date spécifiée (format: DD/MM/YYYY)

**Commandes administrateur :**
• `/lrcsendpresencemessage` - Envoie un nouveau message de présence
• `/lrcpush [date]` - Envoie les données vers Google Sheets
  - Sans date : envoie les données du jour
  - Avec date : envoie les données pour la date spécifiée (format: DD/MM/YYYY)

**Réactions disponibles :**
✅ : Présent
❌ : Absent
❓ : Ne sait pas
"""
    await interaction.response.send_message(info_message, ephemeral=True)

@bot.tree.command(name="lrcreset", description="Réinitialise les données de présence pour aujourd'hui (admin only)")
async def lrcreset(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Vous n'avez pas la permission d'utiliser cette commande.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    
    try:
        channel = bot.get_channel(CHANNEL_ID)
        today = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
        
        # Supprime l'ancien message
        async for message in channel.history(limit=50):
            if message.author == bot.user and today in message.content:
                await message.delete()
                break
        
        # Crée un nouveau message
        await send_presence_message(channel)
        await interaction.followup.send("Les données de présence ont été réinitialisées.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Une erreur est survenue : {str(e)}", ephemeral=True)

@bot.tree.command(
    name="lrcpush", 
    description="Envoie les données de présence vers Google Sheets pour une date donnée"
)
async def lrcpush(
    interaction: discord.Interaction,
    date: str = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Vous n'avez pas les permissions nécessaires.", ephemeral=True)
        return

    # Defer the response immediately
    await interaction.response.defer(ephemeral=True)

    try:
        channel = bot.get_channel(CHANNEL_ID)
        if date is None:
            target_date = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
        else:
            try:
                # Convertir la date fournie en objet datetime
                target_datetime = datetime.strptime(date, "%d/%m/%Y")
                target_date = date
            except ValueError:
                await interaction.followup.send("Format de date invalide. Utilisez le format DD/MM/YYYY")
                return

        presence_message = None
        async for message in channel.history(limit=100):
            if message.author == bot.user and target_date in message.content:
                presence_message = message
                break

        if not presence_message:
            await interaction.followup.send(f"Aucun message de présence trouvé pour le {target_date}!")
            return

        count = 0
        for reaction in presence_message.reactions:
            if str(reaction.emoji) in PRESENCE_STATUS:
                async for user in reaction.users():
                    if not user.bot:
                        presence = PRESENCE_STATUS[str(reaction.emoji)]
                        # Utiliser la date fournie pour l'ajout d'entrée
                        if date:
                            sheets_handler.add_entry(user.name, presence, TIMEZONE, target_datetime)
                        else:
                            sheets_handler.add_entry(user.name, presence, TIMEZONE)
                        count += 1

        await interaction.followup.send(f"Les données du {target_date} ont été envoyées vers Google Sheets! ({count} entrées)")

    except Exception as e:
        await interaction.followup.send(f"Une erreur est survenue : {str(e)}")

class ArrivalTimeSelect(Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        options = [
            discord.SelectOption(label=f"{hour}h00", value=f"{hour:02d}:00") 
            for hour in range(18, 24)
        ]
        options.append(discord.SelectOption(label="Plus tard", value="later"))
        
        super().__init__(
            placeholder="Sélectionnez votre heure d'arrivée",
            options=options,
            custom_id=f"arrival_time_{user_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce n'est pas votre sélecteur d'heure!", ephemeral=True)
            return

        time = self.values[0]
        sheets_handler.update_arrival_time(interaction.user.name, time)
        await interaction.response.send_message(f"Heure d'arrivée mise à jour: {time}", ephemeral=True)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)