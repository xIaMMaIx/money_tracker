# utils.py
import sys
import json
import os
import re
from types import ModuleType

# ==============================================================================
# [FIX] Android Workaround: สร้าง wsgiref ปลอม (ทำงานเฉพาะตอนหาไม่เจอ)
# ==============================================================================
try:
    import wsgiref
except ImportError:
    # ถ้า import ไม่ได้ (Android) ให้สร้างของปลอม
    mock_wsgiref = ModuleType("wsgiref")
    sys.modules["wsgiref"] = mock_wsgiref
    
    mock_util = ModuleType("wsgiref.util")
    sys.modules["wsgiref.util"] = mock_util
    mock_wsgiref.util = mock_util
    
    mock_server = ModuleType("wsgiref.simple_server")
    sys.modules["wsgiref.simple_server"] = mock_server
    mock_wsgiref.simple_server = mock_server
    
    class MockHandler: pass
    def mock_make_server(*args, **kwargs): return None

    mock_server.WSGIRequestHandler = MockHandler
    mock_server.make_server = mock_make_server
# ==============================================================================

from datetime import datetime
from const import CONFIG_FILE, DEFAULT_DB_NAME

# [SECTION: LIBRARIES]
HAS_PYTHAINLP = False
try:
    from pythainlp.util import text_to_num
    HAS_PYTHAINLP = True
except ImportError:
    pass

# [UPDATED] ตรวจสอบ PyAudio แบบยืดหยุ่น (ใช้ได้ทั้ง PC และ Android)
HAS_PYAUDIO = False
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    # บน Android ไม่มี Library นี้ มันจะเข้า case นี้และทำงานต่อได้โดยไม่มีเสียง
    pass

HAS_GSPREAD = False
GSPREAD_ERROR = ""
try:
    import gspread
    HAS_GSPREAD = True
except Exception as e:
    GSPREAD_ERROR = str(e)
    pass

# [SECTION: FORMATTERS]
def format_currency(amount):
    try:
        val = float(amount)
        if val.is_integer():
            return f"{int(val):,}" 
        return f"{val:,.2f}"
    except:
        return str(amount)

def hex_with_opacity(hex_color, opacity):
    hex_color = hex_color.replace("#", "")
    if len(hex_color) == 6:
        alpha = int(opacity * 255)
        return f"#{hex_color}{alpha:02x}"
    return f"#{hex_color}"

def get_heavier_weight(weight_str):
    try:
        val = int(weight_str.replace("w", ""))
        new_val = min(val + 100, 900)
        return f"w{new_val}"
    except:
        return "bold"

def parse_db_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            return datetime.fromisoformat(date_str)
        except:
            return datetime.now()

# -------------------------------------------------------------
# [LOGIC] Thai Money Parser (Robust "Saen-Ha" & Cleanup)
# -------------------------------------------------------------
def parse_thai_money(text):
    original_text = text
    
    # 1. Basic Cleaning
    text = text.replace(",", "")
    text = text.replace("กับ", "")
    text = text.replace("และ", "")

    # 2. Define Values & Units
    thai_vals = {
        'ศูนย์': 0, 'หนึ่ง': 1, 'เอ็ด': 1, 'สอง': 2, 'ยี่': 2, 
        'สาม': 3, 'สี่': 4, 'ห้า': 5, 'หก': 6, 'เจ็ด': 7, 'แปด': 8, 'เก้า': 9,
        'ครึ่ง': 0.5
    }
    
    unit_map = {
        'สิบ': 10, 'ร้อย': 100, 'พัน': 1000, 'หมื่น': 10000, 
        'แสน': 100000, 'ล้าน': 1000000,
        10: 10, 100: 100, 1000: 1000, 10000: 10000, 100000: 100000, 1000000: 1000000
    }

    # 3. Tokenizing
    raw_tokens = []
    if HAS_PYTHAINLP:
        try:
            raw_tokens = text_to_num(text)
        except:
            raw_tokens = re.findall(r"(\d+(?:\.\d+)?|\w+)", text)
    else:
        all_keywords = list(thai_vals.keys()) + list(unit_map.keys())
        str_keywords = [k for k in all_keywords if isinstance(k, str)]
        str_keywords.sort(key=len, reverse=True)
        pattern = r"(\d+(?:\.\d+)?|" + "|".join(str_keywords) + r")"
        raw_tokens = re.findall(pattern, text)

    # 4. Filter Tokens
    tokens = []
    for t in raw_tokens:
        if isinstance(t, str):
            clean_t = t.strip()
            if clean_t: tokens.append(clean_t)
        else:
            tokens.append(t)

    # --- Helper Functions ---
    def get_token_val(t):
        if isinstance(t, (int, float)): return float(t)
        if isinstance(t, str):
            if re.match(r"^\d+(?:\.\d+)?$", t): return float(t)
            if t in thai_vals: return float(thai_vals[t])
            if t in unit_map: return float(unit_map[t])
        return None

    def is_unit_token(t):
        if isinstance(t, (int, float)) and t in unit_map: return True
        if isinstance(t, str) and t in unit_map: return True
        val = get_token_val(t)
        if val in [10, 100, 1000, 10000, 100000, 1000000]: return True
        return False

    # --- Calculation Loop ---
    total_amount = 0.0
    current_val = 0.0
    
    i = 0
    while i < len(tokens):
        token = tokens[i]
        val = get_token_val(token)
        is_unit = is_unit_token(token)
        
        # Special check: number acting as unit
        if val is not None and not is_unit and current_val > 0 and val in [10, 100, 1000, 10000, 100000, 1000000]:
            is_unit = True

        if is_unit:
            unit_val = val
            if current_val == 0: current_val = 1
            
            if unit_val == 1000000:
                total_amount = (total_amount + current_val) * unit_val
                current_val = 0
            else:
                total_amount += (current_val * unit_val)
                current_val = 0
            
            # [COLLOQUIAL LOGIC]: "แสนห้า", "หมื่นแปด"
            if unit_val >= 1000 and (i + 1 < len(tokens)):
                next_token = tokens[i+1]
                next_val = get_token_val(next_token)
                
                if next_val is not None and 1 <= next_val <= 9:
                    is_next_unit = False
                    if i + 2 < len(tokens):
                        next_next_token = tokens[i+2]
                        if is_unit_token(next_next_token):
                            is_next_unit = True
                    
                    if not is_next_unit:
                        colloquial_amt = next_val * (unit_val / 10)
                        total_amount += colloquial_amt
                        i += 1 
                        
        elif val is not None:
            if current_val > 0: total_amount += current_val
            current_val = val
        
        i += 1

    total_amount += current_val

    # Extraction
    item_text = original_text.replace(",", "")
    remove_list = list(thai_vals.keys()) + [k for k in unit_map.keys() if isinstance(k, str)] + [
        "บาท", "สตางค์", "เท่าไหร่", "กี่บาท", "ราคา", "จ่าย", "ซื้อ", "ค่า", "กับ", "และ"
    ]
    for w in remove_list: item_text = item_text.replace(w, "")
    item_text = re.sub(r"[-+]?\d*\.\d+|\d+", "", item_text)
    item_text = item_text.strip()
    if not item_text: item_text = "Unknown"

    return total_amount, item_text

def load_config():
    default = {
        "db_path": DEFAULT_DB_NAME, "width": 400, "height": 700, "lang": "th", 
        "font_family": "Prompt", "font_size": 14, "font_weight": 400,
        "cloud_key": "", "cloud_sheet": "", "startup_mode": "simple"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                if "font_weight" in saved:
                    fw = saved["font_weight"]
                    if isinstance(fw, str):
                        if fw.startswith("w"): saved["font_weight"] = int(fw[1:])
                        elif fw == "bold": saved["font_weight"] = 700
                        elif fw == "normal": saved["font_weight"] = 400
                        else: saved["font_weight"] = 600
                default.update(saved)
        except: pass
    return default

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f)