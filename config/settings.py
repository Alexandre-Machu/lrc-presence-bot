import os
from dotenv import load_dotenv
import pytz

load_dotenv()

# Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
TIMEZONE = pytz.timezone('Europe/Paris')
GOOGLE_SPREADSHEET_ID = "1ecdJx1pxESoC55OmImhTw3fTgfM6zUhc0GSHiucUEmk"

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