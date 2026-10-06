"""Guide des commandes (/lrcinfo)."""
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import GUILD_ID

VERSION = "V1.8.1"

# Une seule source de vérité : le guide ET le test qui vérifie que chaque commande existe
GUIDE_SECTIONS = [
    ("📋 Présence", [
        "Le message du jour (8h00) a 3 menus : **présence**, **heure d'arrivée**, **jeux**.",
        "Heure d'arrivée : choisis un créneau (19h30 → 23h00) ou **✏️ Entrer manuellement** pour taper ton heure, ex `21:40`.",
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
        "Tu veux les détails ? `/lrcinfo sujet:Anniversaires`.",
    ]),
    ("🛠️ Admin", [
        "`/lrcreset` : nouveau message de présence (remet tout à zéro).",
        "`/lrcbirthday ... user:@membre` et `/lrcremovebirthday user:@membre` : pour un autre membre.",
    ]),
    ("⏰ Automatique (heure de Paris)", [
        "8h00 : message de présence · 8h05 : vœux d'anniversaire.",
    ]),
]

# Détail par thème : /lrcinfo sujet:Anniversaires
TOPICS = {
    "anniversaires": ("🎂 Comment marchent les anniversaires", [
        ("Le principe",
         "Tu enregistres **ton jour et ton mois** (pas l'année). Chaque année, le jour J à **8h05**, "
         "le bot te souhaite ton anniversaire dans le salon de présence."),
        ("1. Enregistrer le tien",
         "`/lrcbirthday` : un petit formulaire s'ouvre, tape par exemple `25/12`.\n"
         "Ou en une ligne : `/lrcbirthday 25/12`.\n"
         "Tu t'es trompé ? Refais la commande, la nouvelle date remplace l'ancienne."),
        ("2. Voir les prochains",
         "`/lrcbirthdays` : les anniversaires des 30 prochains jours, avec le nombre de jours restants."),
        ("3. Supprimer le tien",
         "`/lrcremovebirthday`."),
        ("Formats acceptés",
         "`25/12`, `5/3`, `05/03`. Le `29/02` est accepté : les années non bissextiles, "
         "les vœux sont envoyés le 28/02."),
        ("Pour les admins",
         "Ajoute `user:@membre` pour gérer l'anniversaire de quelqu'un d'autre : "
         "`/lrcbirthday 14/07 user:@membre` ou `/lrcremovebirthday user:@membre`."),
        ("Bon à savoir",
         "Si le bot était éteint à 8h05, il envoie les vœux dès son redémarrage (une seule fois par jour). "
         "Un membre qui a quitté le serveur n'est pas souhaité."),
    ]),
    "absences": ("📅 Comment marchent les absences", [
        ("Le principe",
         "Tu préviens à l'avance : chaque matin à 8h, tu es déjà marqué ❌ dans le message de présence "
         "pour les jours concernés. Tu peux toujours changer d'avis avec le menu."),
        ("Calendrier cliquable",
         "Bouton **📅 Mes absences** sous le message du jour, ou `/lrcabsence`. "
         "Clique sur un jour pour l'ajouter ou le retirer, **🏖️ Toute la semaine** pour les vacances, "
         "◀ ▶ pour changer de semaine."),
        ("Une période d'un coup",
         "`/lrcabsence 12/10 18/10` (début et fin inclus), ou `/lrcabsence 25/12/2026`."),
        ("Voir et annuler",
         "`/lrcabsences` (les tiennes, `tous: True` pour tout le monde) et `/lrcremoveabsence`."),
    ]),
    "presence": ("📋 Comment marche la présence", [
        ("Le message du jour",
         "Posté à **8h00** dans le salon : un menu pour ta présence, un pour l'heure d'arrivée, un pour tes jeux."),
        ("Heure d'arrivée",
         "Choisis un créneau (19h30 → 23h00) ou **✏️ Entrer manuellement** pour taper ton heure, ex `21:40`. "
         "Si tu es ❓ *Ne sait pas*, elle devient « pas avant »."),
        ("Jeux",
         "Choisis ceux qui te tentent : le message affiche le nombre de joueurs par jeu."),
        ("Admin",
         "`/lrcreset` renvoie un message tout neuf et remet tout à zéro."),
    ]),
}


def guide_command_names():
    """Noms de commandes cités dans le guide (utilisé par les tests)."""
    texts = [line for _, lines in GUIDE_SECTIONS for line in lines]
    texts += [body for fields in (f for _, f in TOPICS.values()) for _, body in fields]
    return set(re.findall(r"`/(lrc\w+)", "\n".join(texts))) | {"lrcinfo"}


def build_guide_embed():
    embed = discord.Embed(title=f"🤖 Bot LRC — guide {VERSION}", color=discord.Color.blue())
    for title, lines in GUIDE_SECTIONS:
        embed.add_field(name=title, value="\n".join(f"• {line}" for line in lines), inline=False)
    embed.set_footer(text="Détails : /lrcinfo sujet:Anniversaires (ou Absences, Présence).")
    return embed


def build_topic_embed(key):
    title, fields = TOPICS[key]
    embed = discord.Embed(title=title, color=discord.Color.blue())
    for name, body in fields:
        embed.add_field(name=name, value=body, inline=False)
    return embed


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="lrcinfo", description="Guide des commandes du bot")
    @app_commands.describe(sujet="(Optionnel) Détail d'un thème")
    @app_commands.choices(sujet=[
        app_commands.Choice(name="Anniversaires", value="anniversaires"),
        app_commands.Choice(name="Absences", value="absences"),
        app_commands.Choice(name="Présence", value="presence"),
    ])
    async def lrcinfo(self, interaction: discord.Interaction, sujet: Optional[app_commands.Choice[str]] = None):
        embed = build_topic_embed(sujet.value) if sujet else build_guide_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Info(bot), guild=discord.Object(id=GUILD_ID))
