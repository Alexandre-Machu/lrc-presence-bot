# LRC Presence Bot V1.4.0

Bot Discord pour la gestion des présences du LRC.

## Fonctionnalités principales

- Indique ta présence et ton heure d’arrivée
- Sélectionne les jeux pour lesquels tu es dispo (avec emojis)
- Affiche le nombre de joueurs par jeu chaque soir
- Gestion des anniversaires (ajout, suppression, notification)
- Export des présences vers Google Sheets

## Commandes

- `/lrcshowpresence [date]` : Liste des présences (et jeux associés)
- `/lrcsendpresencemessage` : Envoie manuellement le message de présence
- `/lrcpush [date]` : Export vers Google Sheets
- `/lrcreset` : Réinitialise le message de présence
- `/lrcaddbirthday @user JJ/MM` : Ajoute ou modifie l'anniversaire d'un membre
- `/lrcremovebirthday @user` : Supprime l'anniversaire d'un membre
- `/lrcbirthdays` : Affiche les anniversaires à venir
- `/lrcinfo` : Affiche le guide des commandes

## Automatisation

- Message de présence quotidien à 8h00
- Push automatique des données vers Google Sheets à 23h30
- Notification anniversaire à 8h05

**Note :** Le bot n'envoie plus de récapitulatif automatique des présences à 20h15.

## Installation

1. Cloner le repository
2. Installer les dépendances : `pip install -r requirements.txt`
3. Configurer les variables d'environnement dans un fichier `.env`
4. Lancer le bot : `python src/bot.py`

## Configuration

Fichier `.env` requis avec les variables suivantes :
```
DISCORD_TOKEN=your_discord_token
GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
CHANNEL_ID=your_channel_id
```

## Contribution

Les pull requests sont les bienvenues. Pour les changements majeurs, merci d'ouvrir une issue d'abord.