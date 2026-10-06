import asyncio
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config.settings import GOOGLE_CREDENTIALS_FILE


class SheetsHandler:
    def __init__(self, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        self.creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=self.creds)
        self.sheet = self.service.spreadsheets()

    def add_entries(self, rows, date: datetime):
        """Ajoute plusieurs lignes en un seul appel.

        rows : liste de tuples (user, presence, arrival_time).
        """
        if not rows:
            return
        day = date.strftime("%d/%m/%Y")
        values = [[day, user, presence, arrival or ''] for user, presence, arrival in rows]
        self.sheet.values().append(
            spreadsheetId=self.spreadsheet_id,
            range='Présences!A:D',
            valueInputOption='RAW',
            body={'values': values}
        ).execute()

    async def add_entries_async(self, rows, date: datetime):
        """Version non bloquante pour la boucle asyncio."""
        await asyncio.to_thread(self.add_entries, rows, date)
