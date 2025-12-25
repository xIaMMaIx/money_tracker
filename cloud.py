# cloud.py
import os
from utils import HAS_GSPREAD

if HAS_GSPREAD:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

class CloudManager:
    def __init__(self):
        self.scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    
    def connect(self, key_path, sheet_name):
        if not HAS_GSPREAD: raise Exception("Library Missing")
        if not os.path.exists(key_path): raise Exception("Key file not found")
        creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, self.scope)
        client = gspread.authorize(creds)
        try:
            return client.open(sheet_name)
        except gspread.SpreadsheetNotFound:
            raise Exception(f"Sheet '{sheet_name}' not found.")