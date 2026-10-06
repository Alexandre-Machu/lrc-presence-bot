"""Guide des commandes (/lrcinfo)."""
import re

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import GUILD_ID

VERSION = "V1.8.0"

# Une seule source de vérité : le guide ET le test qui vérifie que chaque commande existe
GUIDE_SECTIONS = [
    ("📋 Présence", [
        "Le message du jour (8h00) a 3 menus : **présence**, **heure d'arrivée**, **jeux**.",
        "🕒 **Heure exacte** (bouton) : tape ton heure précise, ex `21:40`.",
        "Si tu es ❓ *Ne sait pas*, l'heure choisie devient « pas avant ».",
    ]),
    ("📅 Absences", [
        "📅 **Mes absences** (bouton sous le message) ou `/lrcabsence` : calendrier cliquable.",
        "`/lrcabsence 12/10 18/10` : une période d'un coup.",
        "`/lrcabsences` : tes absences (`tous: True` pour celles de tout le monde).",
        "`/lrcremoveabsence` : annule une absence.",
    ]),
    ("🎂 Anniversaires", [
        "`/lrcbirthday` : enregistre le tien (un formulaire s'ouvre), ou `/lrcbirthday 25/12`.",
        "`/lrcremovebirthday` : supprime le tien.",
        "`/lrcbirthdays` : anniversaires des 30 prochains jours.",
    ]),
    ("🛠️ Admin", [
        "`/lrcreset` : nouveau message de présence (remet tout à zéro).",
        "`/lrcbirthday ... user:@membre` et `/lrcremovebirthday user:@membre` : pour un autre membre.",
    ]),
    ("⏰ Automatique (heure de Paris)", [
        "8h00 : message de présence · 8h05 : vœux d'anniversaire.",
    ]),
]


def guide_command_names():
    """Noms de commandes cités dans le guide (utilisé par les tests)."""
    text = "\n".join(line for _, lines in GUIDE_SECTIONS for line in lines)
    return set(re.findall(r"`/(lrc\w+)", text)) | {"lrcinfo"}


def build_guide_embed():
    embed = discord.Embed(title=f"🤖 Bot LRC — guide {VERSION}", color=discord.Color.blue())
    for title, lines in GUIDE_SECTIONS:
        embed.add_field(name=title, value="\n".join(f"• {line}" for line in lines), inline=False)
    embed.set_footer(text="Astuce : tape / dans le salon pour voir toutes les commandes.")
    return embed


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="lrcinfo", description="Guide des commandes du bot")
    async def lrcinfo(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_guide_embed(), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Info(bot), guild=discord.Object(id=GUILD_ID))
