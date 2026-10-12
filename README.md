# LRC Presence Bot V1.9.0

Bot Discord pour la gestion des présences du LRC.

## Fonctionnalités principales

- Indique ta présence et ton heure d’arrivée
- Sélectionne les jeux pour lesquels tu es dispo (avec emojis)
- Affiche le nombre de joueurs par jeu chaque soir
- Gestion des anniversaires (ajout, suppression, notification)
- Export des présences vers Google Sheets

## Commandes

Absences (calendrier) :

- Bouton **📅 Mes absences** sous le message du jour, ou `/lrcabsence` : calendrier cliquable (un clic sur un jour = absent, flèches pour changer de semaine)
- Dans le calendrier, menu **🔁 Absent chaque semaine le…** : absences récurrentes (ex : chaque jeudi)
- `/lrcabsence debut [fin]` : ou planifie une absence à l'avance (`JJ/MM` ou `JJ/MM/AAAA`). Le jour J, le bot te marque ❌ automatiquement
- `/lrcabsences [tous]` : liste les absences planifiées (les tiennes, ou celles de tout le monde)
- `/lrcremoveabsence` : annule une de tes absences

Anniversaires :

- `/lrcbirthday` : enregistre **ton** anniversaire (un formulaire s'ouvre, ou `/lrcbirthday 25/12`)
- `/lrcremovebirthday` : supprime ton anniversaire
- `/lrcbirthdays` : anniversaires des 30 prochains jours
- `/lrcinfo sujet:Anniversaires` : le guide détaillé (aussi pour Absences et Présence)

Stats : `/lrcstats [periode]` : les plus présents, les jeux les plus demandés, la soirée record. Chaque journée est enregistrée dans `data/history.json`.

Présence : menu d'heure d'arrivée de 19h30 à 23h00 (par 30 min), ou **✏️ Entrer manuellement** pour taper la tienne (`21:40`, `21h40`).

Administrateurs : `/lrcreset` (nouveau message de présence), et `/lrcbirthday`/`/lrcremovebirthday` avec `user:` pour un autre membre.

## Automatisation (heure de Paris)

- 8h00 : nouveau message de présence (état remis à zéro)
- 8h05 : notification des anniversaires
- 23h30 : push des présences vers Google Sheets (uniquement si `config/google_credentials.json` existe)

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

## Structure

```
src/bot.py            point d'entrée, charge les cogs
src/cogs/             presence, birthdays, absences, stats, info
utils/                logique pure (dates, stockage JSON, Sheets)
config/games.json     liste des jeux du menu (nom + emoji, 25 max)
tests/                pytest -q  (pip install -r requirements-dev.txt)
```

## Contribution

Les pull requests sont les bienvenues. Pour les changements majeurs, merci d'ouvrir une issue d'abord.