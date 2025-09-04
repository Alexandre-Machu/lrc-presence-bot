# LRC Presence Bot V3

Bot Discord pour la gestion des présences du LRC.

## Fonctionnalités

### Système de Présence
- Interface intuitive avec menu déroulant
- 3 états possibles : Présent ✅, Absent ❌, Ne sait pas ❓
- Sélection d'heure d'arrivée personnalisée
- Affichage en temps réel des présences
- Message quotidien automatique à 8h00

### Heures d'arrivée
- Pour les présents : choix entre 20h30 et 21h30 (par palier de 15min)
- Pour les "Ne sait pas" : estimation à partir de 21h30
- Option "Plus tard" disponible

### Commandes
- `/lrcshowpresence [date]` : Affiche la liste des présences
- `/lrcsendpresencemessage` : Envoie un nouveau message de présence (admin)
- `/lrcpush [date]` : Envoie les données vers Google Sheets (admin)
- `/lrcreset` : Réinitialise le message de présence (admin)
- `/lrcinfo` : Affiche l'aide et les informations du bot

### Automatisation
- Message de présence quotidien à 8h00
- Push automatique des données vers Google Sheets à 23h30
- Mise à jour en temps réel du message de présence

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