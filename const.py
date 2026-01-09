# const.py

# --- THEME COLORS ---
COLOR_BG = "#121212"
COLOR_SURFACE = "#1E1E1E"
COLOR_PRIMARY = "#64B5F6"
COLOR_INCOME = "#81C784"
COLOR_EXPENSE = "#E57373"
COLOR_BTN_INCOME = "#2E7D32" # สีเขียวเข้ม (ใช้ในปุ่ม)
COLOR_BTN_EXPENSE = "#C62828" # สีแดงเข้ม (ใช้ในปุ่ม)
COLOR_TEXT = "#FFFFFF"
COLOR_HIGHLIGHT = "#2C2C2C"
COLOR_BUTTON_GREY = "#424242"
COLOR_WARNING = "#FFA726"
COLOR_ALERT = "#D32F2F"

# --- CONFIG CONSTANTS ---
CONFIG_FILE = "tracker_config.json"
DEFAULT_DB_NAME = "modern_money.db"

# --- TRANSLATIONS ---
TRANSLATIONS = {
    "en": {
        "app_title": "Money Tracker",
        "income": "Income", "expense": "Expense", "balance": "Balance",
        "recent_trans": "Recent Transactions", "recurring": "Recurring", "budget": "Monthly Budget Status",
        "settings": "Settings", "categories": "Categories", "general": "General", "cloud": "Cloud Sync",
        "appearance": "Appearance",
        "language": "Language", "db_file": "Database File", "select_file": "Select File...",
        "save": "Save", "close": "Close", "cancel": "Cancel", "delete": "Delete", "edit": "Edit",
        "confirm_delete": "Confirm Delete", "msg_delete": "Delete this item?", 
        "listening": "Listening...", "confirm_trans": "Confirm Transaction", 
        "item": "Item", "amount": "Amount", "category": "Category", 
        "paid": "Paid", "pay": "Pay", "add_rec": "Add Recurring", 
        "day": "Day", "top_chart": "Top 10 Chart", "push_cloud": "Push to cloud",
        "voice_opts": "Voice / Auto Save", 
        "enable_auto_save": "Auto Save",
        "auto_save_delay": "Delay (sec)",
        "reset_filter": "Reset Filter", "no_items": "No items",
        "app_section": "Application", "data_section": "Budget & Data",
        "font_family": "Font Family", "font_size": "Font Size (Base)", "font_weight": "Font Weight",
        "add_category": "Add Category", "edit_category": "Edit Category", 
        "cat_name": "Category Name", "keywords": "Keywords (comma separated)", "back": "Back",
        "msg_delete_cat": "Delete category",
        "cloud_config": "Cloud Configuration", "json_key": "JSON Key File", "sheet_name": "Sheet Name",
        "sync_actions": "Sync Actions", "status": "Status", "btn_check": "Check Connection",
        "btn_compare": "Compare Data", "btn_pull": "Pull from Cloud (Overwrite Local)", "btn_push": "Push to Cloud (Overwrite Cloud)",
        "msg_lib_missing": "Libraries 'gspread' or 'oauth2client' missing!",
        "msg_success": "Success", "msg_error": "Error", "msg_processing": "Processing...",
        "confirm_action": "Confirm Action", "confirm_push": "Overwrite Cloud data with Local data?", "confirm_pull": "Overwrite Local data with Cloud data?",
        "compare_result": "Comparison Result", "local_recs": "Local Records", "cloud_recs": "Cloud Records", "yes": "Yes",
        "select_date": "Select Date",
        "overview": "Overview",
        "payment_method": "Payment Method",
        "credit_cards": "Credit Cards",
        "startup_mode": "Startup Mode",
        "simple_mode": "Simple",
        "full_mode": "Full Dashboard",
        "no_trans_today": "No transactions today",
        "press_mic": "Press buttons below to record"
    },
    "th": {
        "app_title": "Money Tracker",
        "income": "รายรับ", "expense": "รายจ่าย", "balance": "ยอดคงเหลือ",
        "recent_trans": "รายการล่าสุด", "recurring": "รายจ่ายประจำ", "budget": "สถานะงบประมาณรายเดือน",
        "settings": "ตั้งค่า", "categories": "หมวดหมู่", "general": "ทั่วไป", "cloud": "ออนไลน์ / Cloud",
        "appearance": "การแสดงผล",
        "language": "ภาษา / Language", "db_file": "ไฟล์ฐานข้อมูล", "select_file": "เลือกไฟล์...",
        "save": "บันทึก", "close": "ปิด", "cancel": "ยกเลิก", "delete": "ลบ", "edit": "แก้ไข",
        "confirm_delete": "ยืนยันการลบ", "msg_delete": "คุณแน่ใจหรือไม่ที่จะลบรายการนี้?", 
        "listening": "กำลังฟัง...", "confirm_trans": "ตรวจสอบข้อมูล", 
        "item": "รายการ", "amount": "จำนวนเงิน", 
        "category": "หมวดหมู่", "paid": "จ่ายแล้ว", "pay": "จ่าย", "add_rec": "เพิ่มรายจ่าย", 
        "day": "วันที่", "top_chart": "10 อันดับสูงสุด", "push_cloud": "ส่งข้อมูลไป cloud",
        "voice_opts": "เสียงและบันทึกอัตโนมัติ", 
        "enable_auto_save": "บันทึกอัตโนมัติ",
        "auto_save_delay": "หน่วงเวลา (วินาที)",
        "reset_filter": "รีเซ็ตตัวกรอง", "no_items": "ไม่มีรายการ",
        "app_section": "แอปพลิเคชัน", "data_section": "งบประมาณและข้อมูล",
        "font_family": "แบบอักษร (Font)", "font_size": "ขนาดตัวอักษร", "font_weight": "ความหนาตัวอักษร",
        "add_category": "+ เพิ่มหมวดหมู่", "edit_category": "แก้ไขหมวดหมู่",
        "cat_name": "ชื่อหมวดหมู่", "keywords": "คำค้นหา (คั่นด้วยลูกน้ำ)", "back": "ย้อนกลับ",
        "msg_delete_cat": "ต้องการลบหมวดหมู่นี้หรือไม่?",
        "cloud_config": "ตั้งค่าการเชื่อมต่อ ", "json_key": "ไฟล์กุญแจ (JSON Key)",
        "sync_actions": "คำสั่งการเชื่อมต่อ", "status": "สถานะ", "btn_check": "ตรวจสอบการเชื่อมต่อ",
        "btn_compare": "เปรียบเทียบข้อมูล", "btn_pull": "ดึงจาก Cloud ลงเครื่อง (ทับข้อมูลเก่า)", "btn_push": "ส่งจากเครื่องขึ้น Cloud (ทับข้อมูลบน Cloud)",
        "msg_lib_missing": "ไม่พบไลบรารี gspread หรือ oauth2client",
        "msg_success": "สำเร็จ", "msg_error": "เกิดข้อผิดพลาด", "msg_processing": "กำลังดำเนินการ...",
        "confirm_action": "ยืนยันการทำรายการ", "confirm_push": "คุณต้องการส่งข้อมูลขึ้น Cloud (ทับข้อมูลบน Cloud) ใช่หรือไม่?", "confirm_pull": "คุณต้องการดึงข้อมูลจาก Cloud (ทับข้อมูลในเครื่อง) ใช่หรือไม่?",
        "compare_result": "ผลการเปรียบเทียบ", "local_recs": "รายการในเครื่อง", "cloud_recs": "รายการบน Cloud", "yes": "ใช่",
        "select_date": "เลือกเดือนและปี",
        "overview": "ภาพรวม",
        "payment_method": "วิธีการชำระเงิน",
        "credit_cards": "บัตรเครดิต",
        "startup_mode": "โหมดเริ่มต้น",
        "simple_mode": "Simple (จดไว)",
        "full_mode": "Full Dashboard",
        "no_trans_today": "ยังไม่มีรายการวันนี้",
        "press_mic": "กดปุ่มด้านล่างเพื่อเริ่มบันทึก"
    }
}