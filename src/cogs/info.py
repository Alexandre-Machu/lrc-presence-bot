"""Commande d'aide."""
import discord
from discord import app_commands
from discord.ext import commands

from config.settings import GUILD_ID

VERSION = "V1.7.0"

INFO_MESSAGE = f"""
🤖 **Bot LRC - Guide des commandes {VERSION}**

━━━━━━━━━ **Commandes** ━━━━━━━━━

**Absences**
• 📅 Bouton **Mes absences** (sous le message du jour) ou `/lrcabsence` - Calendrier cliquable
• `/lrcabsence debut [fin]` - Ou une période en JJ/MM ou JJ/MM/AAAA
• `/lrcabsences [tous]` - Liste des absences planifiées
• `/lrcremoveabsence` - Annule une de tes absences

**Anniversaires**
• `/lrcaddbirthday JJ/MM` - Enregistre **ton** anniversaire
• `/lrcremovebirthday` - Supprime ton anniversaire
• `/lrcbirthdays` - Anniversaires des 30 prochains jours

**Administrateur**
• `/lrcreset` - Réinitialisation et nouveau message de présence
• `/lrcaddbirthday JJ/MM @user` et `/lrcremovebirthday @user` - Pour un autre membre

━━━━━━━━ **Paramètres** ━━━━━━━━

**États de présence**
• ✅ Présent  • ❌ Absent  • ❓ Ne sait pas (l'heure choisie devient « pas avant »)
• Les absences planifiées te marquent ❌ automatiquement le jour J

**Automatisation (heure de Paris)**
• Message quotidien → 8h00
• Notification anniversaire → 8h05
"""


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="lrcinfo", description="Affiche les informations sur les commandes du bot")
    async def lrcinfo(self, interaction: discord.Interaction):
        await interaction.response.send_message(INFO_MESSAGE, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Info(bot), guild=discord.Object(id=GUILD_ID))
