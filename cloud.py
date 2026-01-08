# cloud.py
import os
import json
from utils import HAS_GSPREAD

if HAS_GSPREAD:
    import gspread

class CloudManager:
    def __init__(self):
        self.client = None
    
    def connect(self, key_path, sheet_name):
        if not HAS_GSPREAD: 
            raise Exception("Library 'gspread' missing.")
        
        if not os.path.exists(key_path): 
            raise Exception(f"ไม่พบไฟล์ Key: {key_path}")
        
        try:
            # เพิ่มการตรวจสอบไฟล์ JSON ว่าถูกต้องไหมก่อนส่งให้ gspread
            with open(key_path, 'r') as f:
                json.load(f) # ลองโหลดดู ถ้าพังจะเด้ง Error ตรงนี้ก่อน
            
            # เชื่อมต่อ
            if self.client is None:
                self.client = gspread.service_account(filename=key_path)
            
            return self.client.open(sheet_name)
        
        except json.JSONDecodeError:
            raise Exception("ไฟล์ JSON Key ไม่ถูกต้อง (Corrupted)")
        except gspread.SpreadsheetNotFound:
            raise Exception(f"ไม่พบ Google Sheet ชื่อ: '{sheet_name}'\n(กรุณาแชร์ Sheet ให้กับอีเมลในไฟล์ JSON Key)")
        except Exception as e:
            # ดัก Error แปลกๆ ทั้งหมด
            raise Exception(f"Connection Failed: {str(e)}")