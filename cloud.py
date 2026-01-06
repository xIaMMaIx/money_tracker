# cloud.py
import os
from utils import HAS_GSPREAD

if HAS_GSPREAD:
    import gspread
    # ไม่ต้อง import oauth2client แล้ว

class CloudManager:
    def __init__(self):
        # ไม่ต้องกำหนด Scope เองแล้ว gspread จัดการให้
        pass
    
    def connect(self, key_path, sheet_name):
        if not HAS_GSPREAD: raise Exception("Library Missing (gspread)")
        if not os.path.exists(key_path): raise Exception("Key file not found")
        
        try:
            # ใช้คำสั่ง service_account ของ gspread โดยตรง
            # มันจะอ่าน JSON Key และจัดการทุกอย่างให้อัตโนมัติ (และไม่เรียกใช้ wsgiref)
            client = gspread.service_account(filename=key_path)
            
            return client.open(sheet_name)
        except gspread.SpreadsheetNotFound:
            raise Exception(f"Sheet '{sheet_name}' not found.")
        except Exception as e:
            raise Exception(f"Connection Error: {e}")