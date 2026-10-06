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
