import json
import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

# Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID', '0'))
GUILD_ID = int(os.getenv('GUILD_ID', '948537493593129011'))
TIMEZONE = ZoneInfo('Europe/Paris')
GOOGLE_SPREADSHEET_ID = os.getenv(
    'GOOGLE_SPREADSHEET_ID',
    '1ecdJx1pxESoC55OmImhTw3fTgfM6zUhc0GSHiucUEmk',
)

# Chemins
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
GOOGLE_CREDENTIALS_FILE = os.path.join(BASE_DIR, 'config', 'google_credentials.json')

# Emoji Configuration
EMOJI_PRESENT = '✅'
EMOJI_ABSENT = '❌'
EMOJI_MAYBE = '❓'

# Presence Status
PRESENCE_STATUS = {
    EMOJI_PRESENT: 'Oui',
    EMOJI_ABSENT: 'Non',
    EMOJI_MAYBE: 'Ne sait pas'
}

# Jeux proposés dans le menu (config/games.json, 25 max : limite Discord)
GAMES_FILE = os.path.join(BASE_DIR, 'config', 'games.json')


def load_games():
    with open(GAMES_FILE, encoding='utf-8') as f:
        games = json.load(f)
    if not 1 <= len(games) <= 25:
        raise ValueError("config/games.json doit contenir entre 1 et 25 jeux")
    return games


GAMES = load_games()
