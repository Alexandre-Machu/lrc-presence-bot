from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import pandas as pd

class SheetsHandler:
    def __init__(self, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        self.creds = service_account.Credentials.from_service_account_file(
            'config/google_credentials.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=self.creds)
        self.sheet = self.service.spreadsheets()

    def add_entry(self, user, presence, timezone, specific_date=None, arrival_time=None):
        try:
            if specific_date:
                date = specific_date
            else:
                date = datetime.now(timezone)
            today = date.strftime("%d/%m/%Y")
            
            values = [[today, user, presence, arrival_time if arrival_time else '']]
            
            body = {
                'values': values
            }
            
            result = self.sheet.values().append(
                spreadsheetId=self.spreadsheet_id,
                range='Présences!A:D',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            print(f"Ajout d'une entrée : {user} - {presence} - {arrival_time}")
            
        except Exception as e:
            print(f"Erreur lors de l'ajout de l'entrée : {e}")
            raise e

    def get_stats(self):
        result = self.sheet.values().get(
            spreadsheetId=self.spreadsheet_id,
            range='Présences!A:C'
        ).execute()
        values = result.get('values', [])
        
        # Convertit en DataFrame pour faciliter l'analyse
        df = pd.DataFrame(values[1:], columns=values[0])
        return df