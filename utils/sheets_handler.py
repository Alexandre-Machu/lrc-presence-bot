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

    def add_entry(self, user, presence, timezone):
        try:
            print(f"Ajout d'une entrée : {user} - {presence}")
            today = datetime.now(timezone).strftime("%d/%m/%Y")
            
            # Récupère les données existantes
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Présences!A:C'
            ).execute()
            values = result.get('values', [])
            
            # Vérifie si l'entrée existe déjà
            row_index = None
            for i, row in enumerate(values):
                if row[0] == today and row[1] == user:
                    row_index = i + 1
                    break
            
            # Met à jour ou ajoute l'entrée
            if row_index:
                range_name = f'Présences!C{row_index}'
                self.sheet.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body={'values': [[presence]]}
                ).execute()
            else:
                self.sheet.values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range='Présences!A:C',
                    valueInputOption='RAW',
                    body={'values': [[today, user, presence]]}
                ).execute()
            print("Entrée ajoutée avec succès")
        except Exception as e:
            print(f"Erreur lors de l'ajout de l'entrée : {e}")

    def get_stats(self):
        result = self.sheet.values().get(
            spreadsheetId=self.spreadsheet_id,
            range='Présences!A:C'
        ).execute()
        values = result.get('values', [])
        
        # Convertit en DataFrame pour faciliter l'analyse
        df = pd.DataFrame(values[1:], columns=values[0])
        return df