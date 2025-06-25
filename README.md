# LRC Presence Bot

Bot Discord pour gérer les présences du LRC

## Installation locale

### Prérequis
- Python 3.12+
- Git
- Un compte Discord avec accès au Developer Portal

### Configuration

1. Cloner le repository :
```powershell
git clone https://github.com/Alexandre-Machu/lrc-presence-bot.git
cd lrc-presence-bot
```

2. Créer un environnement virtuel :
```powershell
python -m venv venv
.\venv\Scripts\activate
```

3. Installer les dépendances :
```powershell
pip install -r requirements.txt
```

4. Configurer les fichiers d'environnement :
- Créer un fichier `.env` avec :
```ini
DISCORD_TOKEN=votre_token_discord
CHANNEL_ID=id_du_canal
GOOGLE_SPREADSHEET_ID=id_de_la_feuille
TIMEZONE=Europe/Paris
```
- Placer le fichier `google_credentials.json` dans le dossier `config/`

### Lancement du bot

1. Activer l'environnement virtuel :
```powershell
.\venv\Scripts\activate
```

2. Lancer le bot :
```powershell
python src/bot.py
```

## Commandes disponibles

- `/lrcshowpresence` : Affiche la liste des personnes présentes
- `/lrcshowstats` : Affiche les statistiques de présence

## Déploiement

Pour le déploiement sur Oracle Cloud, voir [DEPLOY.md](DEPLOY.md)