import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.info import VERSION
from config.settings import CHANNEL_ID, DISCORD_TOKEN, GUILD_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lrc-bot")

EXTENSIONS = ["cogs.presence", "cogs.birthdays", "cogs.absences", "cogs.info"]

# Tout passe par les slash commands : seul l'intent members est nécessaire (cache des membres)
intents = discord.Intents.default()
intents.members = True


class LRCBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        # Exécuté une seule fois (contrairement à on_ready, rappelé à chaque reconnexion)
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        try:
            synced = await self.tree.sync(guild=discord.Object(id=GUILD_ID))
            log.info("Commandes slash synchronisées (%d)", len(synced))
            # Toutes nos commandes sont propres au serveur : l'arbre global est vide, donc cette
            # synchro supprime d'anciennes commandes globales fantômes (doublons dans le menu « / »)
            removed = await self.tree.sync()
            log.info("Commandes globales restantes après nettoyage : %d", len(removed))
        except discord.HTTPException as e:
            log.error("Erreur sync commandes : %s", e)

    async def on_ready(self):
        log.info("%s est connecté !", self.user)
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.playing, name=f"/lrcinfo | {VERSION}"
        ))


bot = LRCBot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "Cette commande est réservée aux administrateurs."
    elif isinstance(error, app_commands.CommandNotFound):
        msg = "Cette commande n'existe plus. Recharge Discord (Ctrl+R) pour mettre à jour la liste."
    else:
        log.exception("Erreur de commande", exc_info=error)
        msg = "Une erreur est survenue."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    if not DISCORD_TOKEN or not CHANNEL_ID:
        sys.exit("DISCORD_TOKEN et CHANNEL_ID doivent être définis dans .env")
    bot.run(DISCORD_TOKEN)
