# LRC Presence Bot V1.5.0

Bot Discord pour la gestion des présences du LRC.

## Fonctionnalités principales

- Indique ta présence et ton heure d’arrivée
- Sélectionne les jeux pour lesquels tu es dispo (avec emojis)
- Affiche le nombre de joueurs par jeu chaque soir
- Gestion des anniversaires (ajout, suppression, notification)
- Export des présences vers Google Sheets

## Commandes

- `/lrcbirthdays` : Affiche les anniversaires des 30 prochains jours
- `/lrcinfo` : Affiche le guide des commandes

Réservées aux administrateurs :

- `/lrcreset` : Réinitialise et renvoie le message de présence
- `/lrcaddbirthday @user JJ/MM` : Ajoute ou modifie l'anniversaire d'un membre
- `/lrcremovebirthday @user` : Supprime l'anniversaire d'un membre

## Automatisation (heure de Paris)

- 8h00 : nouveau message de présence (état remis à zéro)
- 8h05 : notification des anniversaires
- 23h30 : push des présences vers Google Sheets

L'état du jour est sauvegardé dans `data/state.json` : un redémarrage du bot ne
perd ni les réponses ni le fonctionnement des menus.

## Installation

1. Cloner le repository
2. Installer les dépendances : `pip install -r requirements.txt`
3. Configurer les variables d'environnement dans un fichier `.env`
4. Lancer le bot : `python src/bot.py`

## Configuration

Fichier `.env` requis avec les variables suivantes :
```
DISCORD_TOKEN=your_discord_token
GOOGLE_SPREADSHEET_ID=your_spreadsheet_id   # optionnel
CHANNEL_ID=your_channel_id
GUILD_ID=your_guild_id                       # optionnel
```

Le compte de service Google va dans `config/google_credentials.json` (non versionné).

## Contribution

Les pull requests sont les bienvenues. Pour les changements majeurs, merci d'ouvrir une issue d'abord.