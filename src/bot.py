import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord.ext import commands, tasks
from discord.ui import Select, View
from datetime import datetime, timedelta, time  # Ajout de time
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

# Au début du fichier, modifions les variables globales
arrival_times = {}  # Pour stocker les heures des présents {user_id: time}
maybe_times = {}    # Pour stocker les heures des "Ne sait pas" {user_id: time}
presence_states = {}  # Pour stocker les états de présence {user_id: state}

@bot.event
async def on_ready():
    print(f'{bot.user} est connecté!')
    
    # Synchronise les nouvelles commandes
    try:
        commands = await bot.tree.sync()
        print(f"Les commandes ont été resynchronisées avec succès! ({len(commands)} commandes)")
    except Exception as e:
        print(f"Erreur lors de la synchronisation des commandes: {e}")

    # Définir l'activité du bot
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name="/lrcinfo | V1.3.4"
    )
    await bot.change_presence(activity=activity)

    # Démarrer les tâches planifiées
    daily_push.start()
    daily_presence_message.start()
    # daily_showpresence.start()  # Suppression de la tâche d'affichage quotidien à 20h15

async def clear_old_presence_messages(channel):
    """Nettoie les anciens messages de présence du bot"""
    try:
        async for message in channel.history(limit=100):
            if message.author == bot.user:
                await message.delete()
    except Exception as e:
        print(f"Erreur lors du nettoyage des messages : {e}")

async def send_presence_message(channel):
    """Envoie un nouveau message de présence après avoir nettoyé les anciens"""
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
        print(f"Erreur lors de l'envoi du message de présence : {e}")
        return None

@bot.tree.command(
    name="lrcshowpresence", 
    description="Affiche la liste des personnes présentes pour une date donnée"
)
async def lrcshowpresence(interaction: discord.Interaction, date: str = None):
    await interaction.response.defer(ephemeral=False)
    
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if date is None:
            target_date = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
            # Pour aujourd'hui, utiliser les états stockés
            presents = [k for k, v in presence_states.items() if v == "Présent"]
            absents = [k for k, v in presence_states.items() if v == "Absent"]
            maybe = [k for k, v in presence_states.items() if v == "Ne sait pas"]
        else:
            # Pour les autres dates, chercher dans l'historique
            try:
                datetime.strptime(date, "%d/%m/%Y")
                target_date = date
            except ValueError:
                await interaction.followup.send("Format de date invalide. Utilisez le format DD/MM/YYYY")
                return

            # Trouve le message pour la date donnée
            presence_message = None
            async for message in channel.history(limit=100):
                if message.author == bot.user and hasattr(message, 'embeds'):
                    for embed in message.embeds:
                        if embed.title and target_date in embed.title:
                            presence_message = message
                            break
                if presence_message:
                    break

            if not presence_message:
                await interaction.followup.send(f"Aucun message de présence trouvé pour le {target_date}")
                return

            # Initialise les listes pour chaque catégorie
            presents = set()
            maybe = set()
            absents = set()  # Nouvelle liste pour les absents

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
                elif str(reaction.emoji) == EMOJI_ABSENT:  # Ajout du traitement des absents
                    async for user in reaction.users():
                        if not user.bot:
                            member = guild.get_member(user.id)
                            absents.add(member.mention)

        message_parts = []
        guild = interaction.guild

        if presents:
            present_list = []
            for user_id in presents:
                user = guild.get_member(int(user_id))
                if user:
                    time = arrival_times.get(user_id, "")
                    time_str = f" ({time})" if time else ""
                    present_list.append(f"- {user.mention}{time_str}")
            if present_list:
                message_parts.append(f"**Personnes présentes :**\n{chr(10).join(present_list)}")

        if maybe:
            maybe_list = []
            for user_id in maybe:
                user = guild.get_member(int(user_id))
                if user:
                    time = maybe_times.get(user_id, "")
                    time_str = f" (pas avant {time})" if time else ""
                    maybe_list.append(f"- {user.mention}{time_str}")
            if maybe_list:
                message_parts.append(f"\n\n**Personnes pas sûres :**\n{chr(10).join(maybe_list)}")
        
        if absents:  # Ajout de la section des absents
            absent_list = []
            for user_id in absents:
                user = guild.get_member(int(user_id))
                if user:
                    absent_list.append(f"- {user.mention}")
            if absent_list:
                message_parts.append(f"\n\n**Personnes absentes :**\n{chr(10).join(absent_list)}")

        if not message_parts:
            await interaction.followup.send("Personne n'a encore répondu pour cette date.")
            return

        await interaction.followup.send("\n\n".join(message_parts))
        
    except Exception as e:
        print(f"Error in lrcshowpresence: {e}")
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
        if today in reaction.message.content and str(reaction.emoji) == EMOJI_PRESENT:
            # Supprimer toute la partie Excel/Sheets
            pass

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
        if message.author == bot.user and hasattr(message, 'embeds') and len(message.embeds) > 0:
            if today in message.embeds[0].title:
                await interaction.response.send_message("Un message de présence existe déjà pour aujourd'hui.", ephemeral=True)
                return

    await interaction.response.defer(ephemeral=True)
    await send_presence_message(channel)
    await interaction.followup.send("Message de présence envoyé avec succès!", ephemeral=True)

@bot.tree.command(name="lrcinfo", description="Affiche les informations sur les commandes du bot")
async def lrcinfo(interaction: discord.Interaction):
    info_message = """
🤖 **Bot LRC - Guide des commandes V1.3.4**

━━━━━━━━━ **Commandes** ━━━━━━━━━

**Utilisateur**
• `/lrcshowpresence [date]` - Liste des présences
  › Sans date : présences du jour
  › Avec date : historique (DD/MM/YYYY)

**Administrateur**
• `/lrcsendpresencemessage` - Nouveau message de présence
• `/lrcpush [date]` - Export vers Google Sheets
• `/lrcreset` - Réinitialisation du message

━━━━━━━━ **Paramètres** ━━━━━━━━

**États de présence**
• ✅ Présent
• ❌ Absent
• ❓ Ne sait pas

**Horaires disponibles**
• Présent : 20h30 → 21h30 (par palier de 15min)
• Ne sait pas : à partir de 21h30

**Automatisation**
• Message quotidien → 8h00
• Push des données → 23h30
"""
    await interaction.response.send_message(info_message, ephemeral=True)

@bot.tree.command(name="lrcreset", description="Réinitialise le message de présence")
async def lrcreset(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        
        # Toujours utiliser le canal configuré
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            await interaction.followup.send("Le canal configuré est introuvable.", ephemeral=True)
            return
            
        message = await send_presence_message(channel)
        
        if message:
            await interaction.followup.send("Les données de présence ont été réinitialisées.")
        else:
            await interaction.followup.send("Une erreur est survenue lors de la réinitialisation.")
        
    except Exception as e:
        print(f"Error in lrcreset: {e}")
        await interaction.followup.send(f"Une erreur est survenue : {str(e)}")

@bot.tree.command(
    name="lrcpush", 
    description="Envoie les données vers Google Sheets"
)
async def lrcpush(interaction: discord.Interaction, date: str = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Vous n'avez pas les permissions nécessaires.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        # Initialize target_datetime
        target_datetime = None
        
        if date is None:
            target_date = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
            target_datetime = datetime.now(TIMEZONE)
        else:
            try:
                target_datetime = datetime.strptime(date, "%d/%m/%Y")
                target_date = date
            except ValueError:
                await interaction.followup.send("Format de date invalide. Utilisez le format DD/MM/YYYY")
                return

        # Récupération des présences depuis les dictionnaires
        count = 0
        for user_id, presence_state in presence_states.items():
            try:
                user = await interaction.guild.fetch_member(int(user_id))
                if user and not user.bot:
                    # Utiliser le bon dictionnaire d'heures selon l'état
                    arrival_time = None
                    if presence_state == "Présent":
                        arrival_time = arrival_times.get(user_id)
                    elif presence_state == "Ne sait pas":
                        arrival_time = maybe_times.get(user_id)
                    
                    sheets_handler.add_entry(user.name, presence_state, TIMEZONE, target_datetime, arrival_time)
                    count += 1
            except discord.NotFound:
                continue

        # Vider les dictionnaires après le push
        if not date:
            arrival_times.clear()
            maybe_times.clear()
            presence_states.clear()
        
        await interaction.followup.send(f"Les données du {target_date} ont été envoyées vers Google Sheets! ({count} entrées)")

    except Exception as e:
        print(f"Error in lrcpush: {e}")
        await interaction.followup.send(f"Une erreur est survenue : {str(e)}")

class ArrivalTimeSelect(Select):
    def __init__(self, user_id: int = None, is_maybe: bool = False):
        self.is_maybe = is_maybe  # Garder en mémoire le type d'heure
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
            # Pour "Ne sait pas", plages de 15 minutes à partir de 21h30
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
            
            # Stocker l'heure dans le bon dictionnaire
            if self.is_maybe:
                maybe_times[user_id] = time
                # Nettoyer l'autre dictionnaire
                arrival_times.pop(user_id, None)
            else:
                arrival_times[user_id] = time
                # Nettoyer l'autre dictionnaire
                maybe_times.pop(user_id, None)
            
            # Mettre à jour le message
            channel = interaction.channel
            await interaction.response.defer()
            
            async for message in channel.history(limit=10):
                if (message.author == interaction.client.user and 
                    hasattr(message, 'embeds') and 
                    len(message.embeds) > 0 and
                    "Qui sera présent aujourd'hui ?" in message.embeds[0].title):
                    
                    view = PresenceButtons()
                    await view.update_presence_message(message)
                    break
                    
        except Exception as e:
            print(f"Error in ArrivalTimeSelect callback: {e}")
            pass

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
                # Créer le sélecteur d'heure pour "Présent"
                time_view = View()
                time_select = ArrivalTimeSelect(interaction.user.id, is_maybe=False)
                time_view.add_item(time_select)
                await interaction.response.send_message(
                    "À quelle heure pensez-vous arriver ?",
                    view=time_view,
                    ephemeral=True
                )
            elif choice == "absent":
                presence_states[user_id] = "Absent"
                arrival_times.pop(user_id, None)
                maybe_times.pop(user_id, None)
                await interaction.response.defer()
            else:  # maybe
                presence_states[user_id] = "Ne sait pas"
                arrival_times.pop(user_id, None)
                # Créer le sélecteur d'heure pour "Ne sait pas"
                time_view = View()
                time_select = ArrivalTimeSelect(interaction.user.id, is_maybe=True)
                time_view.add_item(time_select)
                await interaction.response.send_message(
                    "Si vous venez, ce ne sera pas avant quelle heure ?",
                    view=time_view,
                    ephemeral=True
                )

            await self.view.update_presence_message(interaction.message)

        except Exception as e:
            print(f"Error in PresenceSelect callback: {e}")
            await interaction.response.defer()

class PresenceButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PresenceSelect())

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
                    content += f"- {user.mention}{time_str}\n"

        if maybe:
            content += "\n**Personnes pas sûres :**\n"  # Un seul \n au début
            for user_id in maybe:
                user = message.guild.get_member(int(user_id))
                if user:
                    time = maybe_times.get(user_id, "")
                    time_str = f" (pas avant {time})" if time else ""
                    content += f"- {user.mention}{time_str}\n"

        if absents:
            content += "\n**Personnes absentes :**\n"  # Un seul \n au début
            for user_id in absents:
                user = message.guild.get_member(int(user_id))
                if user:
                    content += f"- {user.mention}\n"

        embed = message.embeds[0]
        embed.description = content
        await message.edit(embed=embed, view=self)

class PresenceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PresenceSelect())
        self.add_item(ArrivalTimeSelect())

    # Méthode pour mettre à jour l'état du message
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
                time = arrival_times.get(user_id, "")
                time_str = f" ({time})" if time else ""
                content += f"- {user.mention}{time_str}\n"

        if absents:
            content += "\n**Absents :**\n"
            for user_id in absents:
                user = message.guild.get_member(int(user_id))
                content += f"- {user.mention}\n"

        if maybe:
            content += "\n**Ne sait pas :**\n"
            for user_id in maybe:
                user = message.guild.get_member(int(user_id))
                content += f"- {user.mention}\n"

        embed = message.embeds[0]
        embed.description = content
        await message.edit(embed=embed, view=self)

@tasks.loop(time=time(hour=21, minute=30))  # 23h30 UTC+2
async def daily_push():
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            print("Erreur: Canal introuvable pour le push quotidien")
            return

        today = datetime.now(TIMEZONE)  # Date du jour
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

@tasks.loop(time=time(hour=8, minute=0))  # 10h00 UTC+2
async def daily_presence_message():
    try:
        # Reset AVANT d'envoyer le nouveau message
        arrival_times.clear()
        maybe_times.clear()
        presence_states.clear()
        
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await clear_old_presence_messages(channel)  # Nettoie les anciens messages
            await send_presence_message(channel)
            print("Message de présence quotidien envoyé")
        else:
            print("Erreur: Canal introuvable pour le message quotidien")
    except Exception as e:
        print(f"Erreur lors de l'envoi du message quotidien : {str(e)}")


## Tâche daily_showpresence supprimée : plus d'envoi automatique du récapitulatif à 20h15

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)