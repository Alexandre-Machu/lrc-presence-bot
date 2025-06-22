# LRC Presence Bot

Un bot Discord qui gère le suivi des présences des membres de l'équipe en utilisant les réactions Discord et l'intégration avec Google Sheets.

## Fonctionnalités

- Suivi quotidien des présences via les réactions
- Intégration avec Google Sheets pour la persistence des données
- Plusieurs commandes pour gérer les données de présence
- Compatible avec le fuseau horaire (Europe/Paris)
- Commandes administrateur pour la gestion des données

## Prérequis

- Python 3.11+
- Token de Bot Discord
- Identifiants API Google Sheets
- Serveur Discord avec les permissions appropriées

## Installation

1. Cloner le dépôt
```sh
git clone https://github.com/votrenomdutilisateur/lrc-presence-bot.git
cd lrc-presence-bot
```

2. Installer les dépendances
```sh
pip install -r requirements.txt
```

3. Configurer les variables d'environnement
Créer un fichier `.env` avec :
```sh
DISCORD_TOKEN=votre_token_discord_ici
CHANNEL_ID=votre_id_de_canal_ici
```

4. Configurer les identifiants Google Sheets
- Placer votre fichier `google_credentials.json` dans le dossier `config`
- Mettre à jour le `GOOGLE_SPREADSHEET_ID` dans `config/settings.py`

## Utilisation

### Démarrer le Bot
```sh
python src/bot.py
```

### Commandes Disponibles

- `/lrcshowpresence [date]` - Afficher la liste des présences pour une date donnée
- `/lrcinfo` - Afficher les informations sur les commandes du bot, lien du Google Sheets et du dépôt GitHub
- `/lrcsendpresencemessage` - Envoyer manuellement un message de présence (Admin uniquement)
- `/lrcreset` - Réinitialiser les données de présence du jour (Admin uniquement)
- `/lrcpush [date]` - Envoyer les données de présence vers Google Sheets (Admin uniquement)

### Réactions

- ✅ Présent
- ❌ Absent
- ❓ Incertain

## Structure du Projet

```
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── google_credentials.json
│   └── settings.py
├── src/
│   └── bot.py
└── utils/
    ├── __init__.py
    └── sheets_handler.py
```

## Configuration

Le bot peut être configuré via `config/settings.py` :
- Paramètres de fuseau horaire
- ID du canal Discord
- Intégration Google Sheets
- Configuration des émojis
- Mapping des statuts de présence

## Contribution

1. Forker le dépôt
2. Créer une branche pour votre fonctionnalité
3. Commiter vos changements
4. Pousser vers la branche
5. Créer une Pull Request

## Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.