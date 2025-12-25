# main.py

# ///////////////////////////////////////////////////////////////
# [SECTION 1] IMPORTS & CONFIG
# ///////////////////////////////////////////////////////////////
import flet as ft
import speech_recognition as sr
import threading
import time
import math
import struct
import os
import re
from datetime import datetime

# Local Imports (Modules)
from const import *
from utils import *
from database import DatabaseManager
from cloud import CloudManager
from ui_components import *
from settings_ui import open_settings_dialog

# ///////////////////////////////////////////////////////////////
# [SECTION 2] GLOBAL VARIABLES
# ///////////////////////////////////////////////////////////////
main_container = None 
splash_icon = None 

# ///////////////////////////////////////////////////////////////
# [SECTION 3] MAIN ENTRY POINT & WINDOW SETUP
# ///////////////////////////////////////////////////////////////
def main(page: ft.Page):
    global main_container, splash_icon
    
    # --- Load Config ---
    config = load_config()
    start_mode = config.get("startup_mode", "simple")
    
    # --- Window Dimensions ---
    if start_mode == "simple":
        target_w, target_h = 400, 600
    else:
        target_w, target_h = 1200, 1000
    
    # --- Initial Window Setup (Hidden) ---
    page.window.visible = False
    page.window.opacity = 0
    page.window.width = target_w
    page.window.height = target_h
    page.window.center()
    
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.title = f"Money Tracker v5.8.1 - {start_mode.upper()}" 
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        font_family=config.get("font_family", "Kanit"),
        scrollbar_theme=ft.ScrollbarTheme(thickness=0, thumb_visibility=False, track_visibility=False)
    )
    
    main_container = ft.Container(
        expand=True,
        opacity=1, 
        animate_opacity=ft.Animation(300, "easeOut"),
        padding=15
    )
    page.add(main_container)

    # --- Dynamic Theme Helpers ---
    def get_font_specs():
        s = config.get("font_size", 14)
        w = config.get("font_weight", 600)
        return s - 14, f"w{w}"

    current_font_delta, current_font_weight_str = get_font_specs()
    
    # --- State Variables ---
    current_db = None
    db_path = config.get("db_path", DEFAULT_DB_NAME)
    current_filter_date = None
    current_lang = config.get("lang", "th")
    current_view_mode = start_mode
    cloud_mgr = CloudManager()

    def T(key): return TRANSLATIONS[current_lang].get(key, key)
    def safe_show_snack(msg, color="green"):
        try: page.open(ft.SnackBar(content=ft.Text(msg), bgcolor=color))
        except: pass
    
    # ///////////////////////////////////////////////////////////////
    # [SECTION 4] UI INITIALIZATION (STATIC WIDGETS)
    # ///////////////////////////////////////////////////////////////
    btn_settings = ft.IconButton("settings", icon_size=20)
    txt_app_title = ft.Text(T("app_title"), color=COLOR_PRIMARY)
    
    card_inc = SummaryCard("income", "+0.00", COLOR_INCOME, "arrow_upward", current_font_delta, current_font_weight_str)
    card_exp = SummaryCard("expense", "-0.00", COLOR_EXPENSE, "arrow_downward", current_font_delta, current_font_weight_str)
    card_bal = SummaryCard("balance", "0.00", COLOR_PRIMARY, "account_balance_wallet", current_font_delta, current_font_weight_str)
    
    txt_summary_header = ft.Text(T("overview"), color="grey")
    
    summary_row = ft.Row([card_inc, card_exp, card_bal], spacing=10)
    summary_section = ft.Container(content=ft.Column([txt_summary_header, summary_row], spacing=10), padding=15, border=ft.border.all(1, "#333333"), border_radius=15, margin=ft.margin.only(bottom=10))
    
    txt_budget_title = ft.Text(T("budget"), color="grey")
    txt_budget_value = ft.Text("- / -", color="white")
    pb_budget = ft.ProgressBar(value=0, color=COLOR_PRIMARY, bgcolor=COLOR_SURFACE, height=8)
    budget_container = ft.Container(content=ft.Column([ft.Row([txt_budget_title, txt_budget_value], alignment="spaceBetween"), pb_budget], spacing=5), padding=ft.padding.symmetric(vertical=10))
    
    txt_heading_recent = ft.Text("Recent")
    txt_heading_rec = ft.Text("Recurring")
    
    btn_reset_filter = ft.OutlinedButton("Reset Filter", icon="refresh")
    
    # [TRANSLATED BUTTONS]
    btn_expense = ft.FloatingActionButton(text=T("expense"), icon="mic", bgcolor=COLOR_BTN_EXPENSE, width=130)
    btn_income = ft.FloatingActionButton(text=T("income"), icon="mic", bgcolor=COLOR_BTN_INCOME, width=130)
    
    trans_list_view = ft.Column(scroll="hidden", expand=True, spacing=5)
    recurring_list_view = ft.Column(spacing=5, scroll="hidden")
    cards_row = ft.ResponsiveRow(spacing=10, run_spacing=10, visible=False)
    simple_list_view = ft.Column(spacing=2, scroll="hidden", expand=True)
    
    # --- Calendar Init ---
    def on_date_change(d): 
        nonlocal current_filter_date
        current_filter_date = d
        refresh_ui()

    cal = CalendarWidget(page, on_date_change, current_font_delta, current_font_weight_str)
    btn_reset_filter.on_click = lambda e: [cal.reset()]

    # [SIMPLE MODE BUTTONS WITH DARKER COLORS]
    btn_simple_exp = ft.Container(content=ft.Row([ft.Icon("mic", size=24, color="white"), ft.Text(T("expense"), size=16, weight="bold", color="white")], alignment="center", spacing=5), bgcolor=COLOR_BTN_EXPENSE, border_radius=15, height=60, expand=True, ink=True, on_click=lambda e: start_listen(e, "expense"))
    btn_simple_inc = ft.Container(content=ft.Row([ft.Icon("mic", size=24, color="white"), ft.Text(T("income"), size=16, weight="bold", color="white")], alignment="center", spacing=5), bgcolor=COLOR_BTN_INCOME, border_radius=15, height=60, expand=True, ink=True, on_click=lambda e: start_listen(e, "income"))
    
    btn_to_full = ft.IconButton(icon="dashboard", icon_color="white24", icon_size=24, on_click=lambda _: switch_view("full"))
    txt_simple_date = ft.Text("Date", size=28, weight="bold", color="white")
    
# ///////////////////////////////////////////////////////////////
    # [SECTION 5] CORE LOGIC (REFRESH & UPDATE)
    # ///////////////////////////////////////////////////////////////
    def update_all_labels():
        nonlocal current_lang, current_font_delta, current_font_weight_str
        current_lang = config.get("lang", "th")
        current_font_delta, current_font_weight_str = get_font_specs()
        
        txt_app_title.value = T("app_title")
        txt_app_title.size = 20 + current_font_delta
        txt_app_title.weight = current_font_weight_str
        btn_settings.icon_size = 20 + current_font_delta
        
        txt_summary_header.size = 14 + current_font_delta
        txt_summary_header.weight = "bold"
        
        txt_budget_title.value = T("budget")
        txt_budget_title.size = 12 + current_font_delta
        txt_budget_value.size = 12 + current_font_delta
        
        txt_heading_recent.size = 20 + current_font_delta
        txt_heading_recent.weight = current_font_weight_str
        
        txt_heading_rec.value = T("recurring")
        txt_heading_rec.size = 14 + current_font_delta
        txt_heading_rec.weight = current_font_weight_str
        
        card_inc.update_style(current_font_delta, current_font_weight_str)
        card_exp.update_style(current_font_delta, current_font_weight_str)
        card_bal.update_style(current_font_delta, current_font_weight_str)
        cal.update_style(current_font_delta, current_font_weight_str)

        if current_filter_date:
            try:
                dt_obj = datetime.strptime(current_filter_date, "%Y-%m-%d"); formatted = dt_obj.strftime("%d %B %Y"); txt_heading_recent.value = formatted
            except: txt_heading_recent.value = current_filter_date
        else: txt_heading_recent.value = T("recent_trans")
        
        txt_simple_date.value = datetime.now().strftime("%d %B %Y")
        
        btn_reset_filter.text = T("reset_filter"); card_inc.txt_title.value = T("income"); card_exp.txt_title.value = T("expense"); card_bal.txt_title.value = T("balance"); 
        
        # [UPDATE BUTTON TEXTS]
        btn_expense.text = T("expense")
        btn_income.text = T("income")
        btn_simple_exp.content.controls[1].value = T("expense")
        btn_simple_inc.content.controls[1].value = T("income")
        btn_simple_exp.tooltip = T("expense"); btn_simple_inc.tooltip = T("income")
        
        page.update()

    # [NEW FUNCTION] แยก Logic Auto Pay ออกมาทำงานก่อนโหลด UI
    def process_auto_pay():
        recs = current_db.get_recurring()
        if not recs: return

        check_month = f"{cal.year}-{cal.month:02d}"
        real_now = datetime.now()
        
        # ทำงานเฉพาะเมื่อดูเดือนปัจจุบันจริงๆ เท่านั้น
        is_real_current_month = (cal.year == real_now.year and cal.month == real_now.month)
        if not is_real_current_month: return
        
        current_day_val = real_now.day
        
        for r in recs:
            try:
                rid, day, item_name, amt, cat, pid, auto = r
            except ValueError:
                rid, day, item_name, amt, cat = r[:5]
                pid, auto = None, 0
            
            # เงื่อนไข Auto Pay: เปิด Auto + ถึงวันกำหนด + ยังไม่จ่าย
            if auto == 1 and day <= current_day_val:
                if not current_db.is_recurring_paid_v2(item_name, amt, cat, check_month, pid):
                    # เรียกจ่ายเงินแบบ suppress_refresh=True (ไม่รีเฟรชซ้ำ)
                    pay_recurring(item_name, amt, cat, day, check_month, pid, is_auto=True, suppress_refresh=True)

    def refresh_ui(new_id=None):
        if not current_db: return
        
        # 1. เช็คและจ่ายเงินอัตโนมัติก่อน (ถ้ามี)
        process_auto_pay()
        
        # 2. อัปเดตหน้าจอตามปกติ (ข้อมูลจะถูกดึงใหม่หลังจ่ายเงินแล้ว)
        update_all_labels()
        
        # [LOGIC] Disable/Enable Buttons
        now = datetime.now()
        is_current_month = (cal.year == now.year and cal.month == now.month)
        is_date_selected = (current_filter_date is not None)
        enable_buttons = is_current_month or is_date_selected
        
        bg_exp = COLOR_BTN_EXPENSE if enable_buttons else "grey"
        bg_inc = COLOR_BTN_INCOME if enable_buttons else "grey"
        
        btn_expense.bgcolor = bg_exp; btn_income.bgcolor = bg_inc
        btn_simple_exp.bgcolor = bg_exp; btn_simple_inc.bgcolor = bg_inc
        # -------------------------------------------------------------

        current_db.check_and_rollover(cal.year, cal.month)
        current_month_str = f"{cal.year}-{cal.month:02d}"
        
        month_name = datetime(cal.year, cal.month, 1).strftime("%B %Y")
        txt_summary_header.value = f"{T('overview')} ({month_name})"
        
        inc, exp, bal = current_db.get_summary(current_month_str)
        card_inc.txt_value.value = f"+{format_currency(inc)}"; card_exp.txt_value.value = f"-{format_currency(exp)}"; card_bal.txt_value.value = f"{format_currency(bal)}"
        
        try: limit = float(current_db.get_setting("budget", "10000"))
        except: limit = 10000.0
        _, mon_exp, _ = current_db.get_summary(current_month_str)
        ratio = mon_exp / limit if limit > 0 else 0; pb_budget.value = min(ratio, 1.0); pb_budget.color = COLOR_PRIMARY if ratio < 0.5 else ("orange" if ratio < 0.8 else COLOR_EXPENSE); txt_budget_value.value = f"{format_currency(mon_exp)} / {format_currency(limit)}"
        
        cards_db = current_db.get_cards(); cards_row.controls.clear()
        if cards_db:
            count = len(cards_db)
            desktop_span = 12 // min(count, 4) 
            sm_span = 6 if count > 1 else 12 
            dynamic_col = {"xs": 12, "sm": sm_span, "md": desktop_span}
            for c in cards_db: 
                usage = current_db.get_card_usage(c[0])
                cards_row.controls.append(MiniCardWidget(c, open_pay_card_dialog, open_card_history_dialog, usage, col=dynamic_col))
            cards_row.visible = True
        else: cards_row.visible = False
        
        if current_view_mode == "simple":
             rows = current_db.get_transactions(None, month_filter=current_month_str)
        else:
             rows = current_db.get_transactions(current_filter_date, month_filter=current_month_str)
        
        d_font_delta, d_font_weight = get_font_specs()

        if current_view_mode == "full":
            trans_list_view.controls.clear(); animated_card = None; current_date_grp = None
            for r in rows:
                dt_obj = parse_db_date(r[5]); date_str = dt_obj.strftime("%d %B %Y")
                if date_str != current_date_grp: current_date_grp = date_str; trans_list_view.controls.append(ft.Container(content=ft.Text(date_str, size=12+d_font_delta, weight="bold", color="grey"), padding=ft.padding.only(top=10, bottom=5)))
                is_new = (r[0] == new_id)
                card = TransactionCard(r, confirm_delete, open_edit_dialog, d_font_delta, d_font_weight, is_new=is_new, minimal=False)
                trans_list_view.controls.append(card)
                if is_new: animated_card = card
            update_recurring_list(); page.update()
            if animated_card: trans_list_view.scroll_to(offset=0, duration=500); animated_card.opacity = 1; animated_card.update()
        
        elif current_view_mode == "simple":
            simple_list_view.controls.clear(); limit_rows = rows[:6]
            if not limit_rows:
                empty_content = ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=ft.Icon(name="note_add", size=48, color=COLOR_PRIMARY),
                            padding=20,
                            bgcolor=hex_with_opacity(COLOR_PRIMARY, 0.1),
                            border_radius=50,
                        ),
                        ft.Text(T("no_trans_today"), size=16, weight="bold", color="white"),
                        ft.Text(T("press_mic"), size=12, color="grey"),
                    ], 
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10
                    ),
                    alignment=ft.alignment.center,
                    expand=True
                )
                simple_list_view.controls.append(empty_content)
            else:
                for r in limit_rows: 
                    card = TransactionCard(r, confirm_delete, open_edit_dialog, d_font_delta, d_font_weight, minimal=True)
                    simple_list_view.controls.append(card)
            page.update()

# [SECTION 5] ในไฟล์ main.py
    # แก้ไขเฉพาะฟังก์ชัน update_recurring_list

    def update_recurring_list():
        d_font_delta, d_font_weight = get_font_specs()
        recurring_list_view.controls.clear()
        
        recs = current_db.get_recurring()
        if not recs: 
            recurring_list_view.controls.append(ft.Text(T("no_items"), color="grey", size=12+d_font_delta))
            return

        # [ADDED] ดึงข้อมูลบัตรทั้งหมดมาสร้าง Map (ID -> {name, color}) เพื่อใช้ดึงสีได้เร็วๆ
        cards_db = current_db.get_cards()
        card_map = {c[0]: {'name': c[1], 'color': c[4]} for c in cards_db}

        recs_data = []
        check_month = f"{cal.year}-{cal.month:02d}"
        now = datetime.now()
        current_day_ref = now.day if cal.year == now.year and cal.month == now.month else (31 if datetime(cal.year, cal.month, 1) < now else 0)

        for r in recs:
            try:
                rid, day, item_name, amt, cat, pid, auto = r
            except ValueError:
                rid, day, item_name, amt, cat = r[:5]
                pid, auto = None, 0
            
            is_paid = current_db.is_recurring_paid_v2(item_name, amt, cat, check_month, pid)
            
            recs_data.append({'data': r, 'is_paid': is_paid, 'day': day, 'auto': auto, 'pid': pid})

        recs_data.sort(key=lambda x: x['is_paid'])

        for item_dict in recs_data:
            r = item_dict['data']
            is_paid = item_dict['is_paid']
            day = item_dict['day']
            auto = item_dict['auto']
            pid = item_dict['pid']
            rid, _, item_name, amt, cat, _, _ = r
            
            is_due_alert = (not is_paid) and (current_day_ref >= day)
            day_bg = COLOR_ALERT if is_due_alert else "transparent"
            day_col = "white" if is_due_alert else "grey"
            
            meta_info = [ft.Text(format_currency(amt), size=12+d_font_delta, color=COLOR_EXPENSE)]
            
            # แสดงชื่อบัตร (ถ้ามี)
            if pid and pid in card_map:
                c_name = card_map[pid]['name']
                meta_info.append(ft.Container(
                    content=ft.Text(f"{c_name}", size=10, weight="bold"),
                    bgcolor="#333333", 
                    padding=ft.padding.symmetric(horizontal=4, vertical=1), 
                    border_radius=3
                ))
            
            if auto == 1:
                meta_info.append(ft.Icon(name="bolt", color="yellow", size=12, tooltip="Auto Pay"))

            day_container = ft.Container(content=ft.Text(f"{day:02d}", color=day_col, size=14+d_font_delta, weight="bold"), bgcolor=day_bg, width=50, alignment=ft.alignment.center, padding=0, margin=0)
            
            # [MODIFIED] Logic ปุ่มกดจ่าย / Auto Badge
            if auto == 1 and pid:
                # กรณี Auto Pay + มีบัตร
                if is_paid:
                    btn = ft.ElevatedButton(T("paid"), disabled=True, height=25)
                else:
                    # [NEW] ดึงสีบัตรมาใช้กับปุ่ม Auto
                    c_color = card_map[pid]['color'] if pid in card_map else "yellow"
                    
                    btn = ft.Container(
                        content=ft.Text("Auto", size=12, color=c_color, weight="bold"),
                        padding=ft.padding.symmetric(horizontal=10, vertical=2),
                        border=ft.border.all(1, c_color),
                        border_radius=5,
                        tooltip="Waiting for auto-pay date"
                    )
            else:
                # กรณีจ่ายเอง
                btn = ft.ElevatedButton(T("paid"), disabled=True, height=25) if is_paid else ft.ElevatedButton(T("pay"), style=ft.ButtonStyle(bgcolor=COLOR_PRIMARY, color="white"), height=25, on_click=lambda e, i=item_name, a=amt, c=cat, d=day, cm=check_month, p=pid: pay_recurring(i,a,c,d,cm,p))
            
            row_content = ft.Row([
                day_container, 
                ft.Container(content=ft.Column([
                    ft.Text(item_name, weight=d_font_weight, size=14+d_font_delta), 
                    ft.Row(meta_info, spacing=5)
                ], spacing=0, alignment="center"), expand=True, padding=ft.padding.only(left=10)), 
                ft.Container(content=btn, padding=ft.padding.only(right=5)), 
                ft.Container(content=ft.IconButton("close", icon_size=12, width=24, height=24, style=ft.ButtonStyle(padding=0), icon_color="grey", on_click=lambda e, id=rid: confirm_delete_rec(id)), padding=ft.padding.only(right=5))
            ], spacing=0, alignment="spaceBetween")
            
            card = ft.Container(content=row_content, bgcolor=COLOR_HIGHLIGHT, border_radius=10, padding=0, height=45, clip_behavior=ft.ClipBehavior.HARD_EDGE)
            recurring_list_view.controls.append(card)
            
    # ///////////////////////////////////////////////////////////////
    # [SECTION 6] DIALOG ACTIONS
    # ///////////////////////////////////////////////////////////////
    def confirm_delete(tid):
        def yes(e): current_db.delete_transaction(tid); dlg.open = False; page.update(); refresh_ui()
        def no(e): dlg.open = False; page.update()
        dlg = ft.AlertDialog(title=ft.Text(T("confirm_delete")), content=ft.Text(T("msg_delete")), actions=[ft.TextButton(T("delete"), on_click=yes), ft.TextButton(T("cancel"), on_click=no)]); page.open(dlg)

    def confirm_delete_rec(rid):
        def yes(e): current_db.delete_recurring(rid); dlg_del_rec.open = False; page.update(); refresh_ui()
        def no(e): dlg_del_rec.open = False; page.update()
        dlg_del_rec = ft.AlertDialog(title=ft.Text(T("confirm_delete")), content=ft.Text(T("msg_delete")), actions=[ft.TextButton(T("delete"), on_click=yes), ft.TextButton(T("cancel"), on_click=no)]); page.open(dlg_del_rec)

    def open_edit_dialog(data):
        tid, ttype, item, amt, cat, _, current_card_name = data
        f_item = ft.TextField(label=T("item"), value=item); 
        
        f_amt = ft.TextField(
            label=T("amount"), 
            value=str(amt), 
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string="")
        )
        
        cats = current_db.get_categories(ttype if ttype != 'repayment' else 'expense'); f_cat = ft.Dropdown(label=T("category"), options=[ft.dropdown.Option(c[1]) for c in cats], value=cat)
        
        cards = current_db.get_cards(); pay_opts = [ft.dropdown.Option("cash", "เงินสด / Cash")]; current_pid_val = "cash"
        if ttype != "income":
            for c in cards:
                pay_opts.append(ft.dropdown.Option(str(c[0]), f"บัตร: {c[1]}"))
                if current_card_name and current_card_name == c[1]: current_pid_val = str(c[0])
        
        f_payment = ft.Dropdown(label=T("payment_method"), options=pay_opts, value=current_pid_val)
        
        def save(e):
            try: pid = int(f_payment.value) if f_payment.value != "cash" else None; current_db.update_transaction(tid, f_item.value, float(f_amt.value), f_cat.value, pid); dlg.open = False; page.update(); refresh_ui()
            except: pass
        def cancel(e): dlg.open = False; page.update()
        dlg = ft.AlertDialog(title=ft.Text(T("edit")), content=ft.Column([f_item, f_amt, f_cat, f_payment], tight=True), actions=[ft.TextButton(T("save"), on_click=save), ft.TextButton(T("cancel"), on_click=cancel)]); page.open(dlg)

    # ฟังก์ชัน 1: สำหรับจ่ายค่าบัตรเครดิต (Payment)
# [SECTION 6] ในไฟล์ main.py
    # แก้ไขเฉพาะฟังก์ชัน open_pay_card_dialog

    def open_pay_card_dialog(card_data):
        cid, name, limit, _, _ = card_data
        current_usage = current_db.get_card_usage(cid)
        
        # -------------------------------------------------------
        # [MODIFIED] Logic: กำหนดวันที่จ่ายเงินตามปฏิทินที่เลือก
        # -------------------------------------------------------
        target_date = datetime.now()
        display_date_str = "Today"
        
        if current_filter_date:
            try:
                # แปลงวันที่ที่เลือกจากปฏิทิน (String) เป็น DateTime Object
                sel_dt = datetime.strptime(current_filter_date, "%Y-%m-%d")
                # รวมกับเวลาปัจจุบัน (เพื่อให้รายการเรียงลำดับได้ถูกต้องตามเวลาที่บันทึก)
                target_date = datetime.combine(sel_dt.date(), datetime.now().time())
                display_date_str = sel_dt.strftime("%d/%m/%Y")
            except:
                pass
        # -------------------------------------------------------

        txt_info = ft.Text(f"Current Debt: {format_currency(current_usage)}")
        txt_date_info = ft.Text(f"Payment Date: {display_date_str}", size=12, color="grey") # แสดงวันที่ให้ user เห็น

        f_amt = ft.TextField(
            label="Payment Amount", 
            value=str(current_usage), 
            keyboard_type=ft.KeyboardType.NUMBER, 
            autofocus=True,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string="")
        )
        
        def save(e):
            try: amt = float(f_amt.value); 
            except: safe_show_snack("Invalid Amount", "red"); return
            
            if amt > 0: 
                # ส่ง target_date เข้าไปบันทึก
                current_db.add_transaction("repayment", f"Pay Card: {name}", amt, "Transfer/Debt", target_date, payment_id=cid)
                
                dlg_pay.open = False
                page.update()
                refresh_ui()
                safe_show_snack(f"Paid {amt} to {name} on {display_date_str}")
        
        dlg_pay = ft.AlertDialog(
            title=ft.Text(f"Pay {name}"), 
            content=ft.Column([txt_info, txt_date_info, f_amt], tight=True), 
            actions=[
                ft.TextButton("Pay", on_click=save), 
                ft.TextButton("Cancel", on_click=lambda _: [setattr(dlg_pay, 'open', False), page.update()])
            ]
        )
        page.open(dlg_pay)
        

    # ฟังก์ชัน 2: สำหรับดูประวัติการใช้บัตร (History)

    def open_card_history_dialog(card_data):
        cid, name, _, _, _ = card_data
        month_str = f"{cal.year}-{cal.month:02d}"
        
        rows = current_db.get_card_transactions(cid, month_str)
        
        # 1. ใช้ ListView หรือ Column แบบ scroll ได้
        lv = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO, expand=True) 
        total_spent = 0.0
        
        # ส่วนหัว (Header)
        header_row = ft.Container(
            content=ft.Row([
                ft.Text(T("day"), size=12, color="grey", width=40),
                ft.Text(T("item"), size=12, color="grey", expand=True),
                ft.Text(T("amount"), size=12, color="grey", width=80, text_align=ft.TextAlign.RIGHT),
            ], alignment="spaceBetween"),
            padding=ft.padding.only(left=10, right=10, bottom=5),
            border=ft.border.only(bottom=ft.BorderSide(1, "#444444"))
        )

        if not rows:
             lv.controls.append(ft.Container(content=ft.Text(T("no_items"), color="grey", italic=True), alignment=ft.alignment.center, padding=20))
        else:
            for i, r in enumerate(rows):
                r_item = r[2]
                r_amt = r[3]
                r_date = parse_db_date(r[5]).strftime("%d/%m")
                total_spent += r_amt
                
                # 2. ปรับ Style ให้เหมือน Top 10 (เป็นกล่องสี่เหลี่ยมมนๆ สีพื้นหลังต่างจาก Dialog นิดหน่อย)
                item_row = ft.Container(
                    content=ft.Row([
                        ft.Text(r_date, size=12, color="white54", width=40),
                        ft.Text(r_item, size=14, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(format_currency(r_amt), size=14, color=COLOR_EXPENSE, weight="bold", width=80, text_align=ft.TextAlign.RIGHT)
                    ], alignment="spaceBetween"),
                    padding=ft.padding.symmetric(horizontal=10, vertical=10),
                    bgcolor=COLOR_SURFACE, # ใช้สีเดียวกับ Item ของ Top 10
                    border_radius=5
                )
                lv.controls.append(item_row)

        txt_total = ft.Text(f"Total: {format_currency(total_spent)}", size=16, weight="bold", color=COLOR_EXPENSE)
        
        def close_dlg(e):
            dlg_hist.open = False
            page.update()

        # จัด Layout ทั้งหมด
        content_col = ft.Column([
            header_row,
            lv, 
            ft.Divider(height=1, color="grey"), 
            ft.Row([txt_total], alignment="end")
        ], spacing=10, expand=True)

        dlg_hist = ft.AlertDialog(
            title=ft.Row([ft.Icon("credit_card", size=24, color=COLOR_PRIMARY), ft.Text(f"{name} ({month_str})")], spacing=10),
            # 3. กำหนดขนาดให้เท่ากับ Top 10 Popup เป๊ะๆ (400x400)
            content=ft.Container(content=content_col, width=400, height=400, padding=0),
            actions=[ft.TextButton(T("close"), on_click=close_dlg)]
        )
        page.open(dlg_hist)

# [SECTION 6] (เฉพาะ 2 ฟังก์ชันนี้)

# [SECTION 6] ในไฟล์ main.py
    # แก้ไขเฉพาะฟังก์ชัน open_add_rec

    def open_add_rec(e):
        f_item = ft.TextField(label=T("item"))
        f_amt = ft.TextField(
            label=T("amount"), 
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string="")
        )
        f_day = ft.Dropdown(label=T("day"), options=[ft.dropdown.Option(str(i)) for i in range(1,32)], value="1")
        f_cat = ft.Dropdown(label=T("category"), options=[ft.dropdown.Option(c[1]) for c in current_db.get_categories("expense")], value="อาหาร")
        
        # Payment Method Selection
        cards = current_db.get_cards()
        pay_opts = [ft.dropdown.Option("cash", "เงินสด / Cash")]
        for c in cards:
            pay_opts.append(ft.dropdown.Option(str(c[0]), f"บัตร: {c[1]}"))
        
        # [MODIFIED] Auto Pay Switch: เริ่มต้นให้ Disable ไว้ก่อน (เพราะ default เป็น cash)
        sw_auto = ft.Switch(label="Auto Pay (ตัดอัตโนมัติเมื่อถึงวัน)", value=False, disabled=True)

        # [ADDED] Logic: เปิด/ปิด Switch ตามการเลือกบัตร
        def on_payment_change(e):
            is_card = (f_payment.value != "cash")
            
            # ถ้าเป็นบัตร ให้กดได้ (disabled = False), ถ้าไม่ใช่บัตร ให้กดไม่ได้ (disabled = True)
            sw_auto.disabled = not is_card
            
            # ถ้าเปลี่ยนกลับมาเป็นเงินสด ให้ยกเลิก Auto Pay ทันที
            if not is_card:
                sw_auto.value = False
            
            sw_auto.update()

        f_payment = ft.Dropdown(
            label=T("payment_method"), 
            options=pay_opts, 
            value="cash",
            on_change=on_payment_change # ผูกฟังก์ชันตรวจสอบที่นี่
        )

        def add(e):
            try:
                pid = int(f_payment.value) if f_payment.value != "cash" else None
                auto_val = 1 if sw_auto.value else 0
                
                current_db.add_recurring(
                    int(f_day.value), 
                    f_item.value, 
                    float(f_amt.value), 
                    f_cat.value, 
                    payment_id=pid, 
                    auto_pay=auto_val
                )
                dlg.open = False
                page.update()
                refresh_ui()
            except Exception as ex:
                safe_show_snack(f"Error: {ex}", "red")

        def cancel(e): dlg.open = False; page.update()
        
        dlg = ft.AlertDialog(
            title=ft.Text(T("add_rec")), 
            content=ft.Column([f_day, f_item, f_amt, f_cat, f_payment, sw_auto], tight=True), 
            actions=[ft.TextButton("Add", on_click=add), ft.TextButton("Cancel", on_click=cancel)]
        )
        page.open(dlg)
        
# [SECTION 6] ในไฟล์ main.py 
    # แก้ไขเฉพาะฟังก์ชัน pay_recurring

    def pay_recurring(item, amt, cat, day, check_month, payment_id=None, is_auto=False, suppress_refresh=False):
        try: 
            y, m = map(int, check_month.split('-'))
            d = datetime(y, m, day)
        except: 
            d = datetime.now()
        
        current_db.add_transaction("expense", item, amt, cat, d, payment_id=payment_id)
        
        if is_auto:
            safe_show_snack(f"⚡ Auto-Paid: {item} ({check_month})", "blue")
        else:
            safe_show_snack(f"Paid: {item} ({check_month})", "green")
            
        # ถ้าสั่งระงับ (True) จะไม่รีเฟรชหน้าจอ (ใช้สำหรับ Auto Pay ที่ทำเป็นลูป)
        if not suppress_refresh:
            refresh_ui()
            
    def open_top10_dialog(e):
        month_str = f"{cal.year}-{cal.month:02d}"
        d_font_delta, d_font_weight = get_font_specs()
        def get_list_view(t_type):
            data = current_db.get_top_transactions(t_type, month_str)
            if not data: return ft.Text("No data", color="grey")
            lv = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO)
            for i, (item, amt) in enumerate(data):
                col = COLOR_INCOME if t_type == "income" else COLOR_EXPENSE
                lv.controls.append(ft.Container(content=ft.Row([ft.Text(f"{i+1}. {item}", size=14+d_font_delta, expand=True), ft.Text(format_currency(amt), color=col, weight=d_font_weight, size=14+d_font_delta)]), padding=10, bgcolor=COLOR_SURFACE, border_radius=5))
            return lv
        tabs = ft.Tabs(selected_index=0, tabs=[ft.Tab(text="Expense", content=ft.Container(content=get_list_view("expense"), padding=10)), ft.Tab(text="Income", content=ft.Container(content=get_list_view("income"), padding=10))])
        dlg = ft.AlertDialog(title=ft.Text(f"{T('top_chart')} ({month_str})"), content=ft.Container(content=tabs, width=400, height=400), actions=[ft.TextButton("Close", on_click=lambda e: [setattr(dlg, 'open', False), page.update()])])
        page.open(dlg)

    # ///////////////////////////////////////////////////////////////
    # [SECTION 7] SETTINGS & CLOUD
    # ///////////////////////////////////////////////////////////////
    def open_settings(e):
        open_settings_dialog(page, current_db, config, refresh_ui, init_application, cloud_mgr)

    # [FIX: BIND SETTINGS BUTTON]
    btn_settings.on_click = open_settings

# ///////////////////////////////////////////////////////////////
    # [SECTION 8] VOICE SYSTEM
    # ///////////////////////////////////////////////////////////////
    def start_listen(e, t_type):
        # -------------------------------------------------------
        # [CHECK CONDITION]
        # -------------------------------------------------------
        now = datetime.now()
        is_current_month = (cal.year == now.year and cal.month == now.month)
        is_date_selected = (current_filter_date is not None)

        if not (is_current_month or is_date_selected):
            msg = "Please select a date first." if config.get("lang") == "en" else "กรุณาเลือกวันที่ในปฏิทิน ก่อนบันทึกรายการย้อนหลัง"
            safe_show_snack(f"⚠️ {msg}", "orange")
            return

        target_date = datetime.now()
        display_date = "Today"
        d_font_delta, _ = get_font_specs()
        
        # Determine target date
        if current_view_mode == "full" and current_filter_date:
            try: 
                sel_dt = datetime.strptime(current_filter_date, "%Y-%m-%d")
                now = datetime.now()
                target_date = datetime.combine(sel_dt.date(), now.time())
                display_date = target_date.strftime("%d/%m/%Y")
            except: pass
            
        visualizer = RealTimeVoiceVisualizer()
        txt_status = ft.Text(f"{T('listening')} ({display_date})", size=16+d_font_delta)
        recording_event = threading.Event()
        recording_event.set()
        
        def cancel_listen(e): 
            recording_event.clear()
            page.close(dlg_listen)
        
        dlg_listen = ft.AlertDialog(
            modal=True, 
            title=ft.Text("Voice Input"), 
            content=ft.Column([visualizer, txt_status], tight=True, horizontal_alignment="center"), 
            actions=[ft.TextButton(T("cancel"), on_click=cancel_listen)]
        )
        page.open(dlg_listen)

        def process_result(text):
            try: page.close(dlg_listen)
            except: pass
            
            # [DEBUG LOG 2] ดูผลลัพธ์หลังจากคำนวณเสร็จ
            amt_val, item_text = parse_thai_money(text)
            print(f"[DEBUG] Parsed Result -> Amount: {amt_val}, Item: '{item_text}'")
            
            cats = current_db.get_categories(t_type)
            cards = current_db.get_cards()
            
            # 1. Category Matching
            default_cat_obj = next((c for c in cats if c[1] == "อื่นๆ"), None)
            cat_val = default_cat_obj[1] if default_cat_obj else (cats[0][1] if cats else "Other")
            best_match_len = 0
            for cid, name, _, kw in cats:
                if name in item_text:
                    if len(name) > best_match_len: best_match_len = len(name); cat_val = name
                if kw:
                    for k in kw.split(','):
                        k_clean = k.strip()
                        if k_clean and k_clean in item_text:
                            if len(k_clean) > best_match_len: best_match_len = len(k_clean); cat_val = name
            
            # 2. Card Matching
            detected_card_id = "cash"
            sorted_cards = sorted(cards, key=lambda x: len(x[1]), reverse=True)
            if t_type != "income":
                for c in sorted_cards:
                    if c[1].lower() in text.lower():
                        detected_card_id = str(c[0])
                        pattern = re.compile(re.escape(c[1]), re.IGNORECASE)
                        item_text = pattern.sub("", item_text).strip()
                        break
            
            # 3. Fallback Amount (เผื่อ parse_thai_money พลาดจริงๆ)
            if amt_val == 0.0:
                 clean = text.replace(",", "")
                 nums = re.findall(r"[-+]?\d*\.\d+|\d+", clean)
                 if nums: amt_val = float(nums[0])
            
            if amt_val == 0.0: 
                safe_show_snack("Could not detect amount, please enter manually.", "orange")

            # --- Auto Save Logic ---
            auto_save_cancelled = False
            btn_save = None
            
            def stop_auto_save(e):
                nonlocal auto_save_cancelled
                if not auto_save_cancelled: 
                    auto_save_cancelled = True
                    if btn_save: 
                        btn_save.text = T("save")
                        btn_save.update()

            f_item = ft.TextField(label=T("item"), value=item_text, on_change=stop_auto_save, on_focus=stop_auto_save)
            
            f_amt = ft.TextField(
                label=T("amount"), 
                value=str(amt_val), 
                on_change=stop_auto_save, 
                on_focus=stop_auto_save, 
                keyboard_type=ft.KeyboardType.NUMBER,
                input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string="")
            )
            
            f_cat = ft.Dropdown(label=T("category"), options=[ft.dropdown.Option(c[1]) for c in cats], value=cat_val, on_change=stop_auto_save, on_focus=stop_auto_save)
            
            pay_opts = [ft.dropdown.Option("cash", "เงินสด / Cash")]
            if t_type != "income":
                for c in cards: pay_opts.append(ft.dropdown.Option(str(c[0]), f"บัตร: {c[1]}"))
            
            f_payment = ft.Dropdown(label=T("payment_method"), options=pay_opts, value=detected_card_id, on_change=stop_auto_save, on_focus=stop_auto_save)
            
            dlg_verify = None
            
            def confirm(e):
                try:
                    pid = int(f_payment.value) if f_payment.value and f_payment.value != "cash" else None
                    final_amt = float(f_amt.value) if f_amt.value else 0.0
                    if final_amt == 0:
                        safe_show_snack("Amount cannot be 0", "red")
                        return
                    new_id = current_db.add_transaction(t_type, f_item.value, final_amt, f_cat.value, date=target_date, payment_id=pid)
                    if dlg_verify: page.close(dlg_verify)
                    refresh_ui(new_id=new_id)
                    safe_show_snack(f"Saved to {display_date}!")
                except Exception as ex:
                    safe_show_snack(f"Error saving: {ex}", "red")

            def cancel_verify(e):
                if dlg_verify: page.close(dlg_verify)

            is_auto = current_db.get_setting("auto_save", "0") == "1"
            try: delay = int(current_db.get_setting("auto_save_delay", "0"))
            except: delay = 0

            # Direct Save
            if is_auto and delay == 0 and amt_val > 0:
                confirm(None)
            else:
                btn_save = ft.TextButton(T("save"), on_click=confirm)
                translated_type = T(t_type)
                dlg_verify = ft.AlertDialog(
                    title=ft.Text(f"{T('confirm_trans')} ({translated_type})"), 
                    content=ft.Column([f_item, f_amt, f_cat, f_payment], tight=True), 
                    actions=[btn_save, ft.TextButton(T("cancel"), on_click=cancel_verify)]
                )
                page.open(dlg_verify)
                
                if is_auto and delay > 0 and amt_val > 0:
                    def countdown():
                        for i in range(delay, 0, -1):
                            if not dlg_verify.open: return
                            if auto_save_cancelled: return
                            btn_save.text = f"{T('save')} ({i})"
                            btn_save.update()
                            time.sleep(1)
                        if dlg_verify.open and not auto_save_cancelled:
                            confirm(None)
                    threading.Thread(target=countdown, daemon=True).start()

        def record_thread():
            if not HAS_PYAUDIO: 
                txt_status.value = "Error: PyAudio missing"
                page.update()
                return
            
            p = pyaudio.PyAudio()
            stream = None
            try:
                stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
                frames = []
                silence_start = None
                has_spoken = False
                
                while recording_event.is_set():
                    try:
                        data = stream.read(1024, exception_on_overflow=False)
                        shorts = struct.unpack("%dh"%(len(data)//2), data)
                        rms = math.sqrt(sum(s**2 for s in shorts) / len(shorts))
                        visualizer.update_volume(rms)
                        if rms > 400: has_spoken = True; silence_start = None; frames.append(data)
                        elif has_spoken:
                            frames.append(data)
                            if silence_start is None: silence_start = time.time()
                            elif time.time() - silence_start > 2.0: break
                    except: break 
                
                if stream: stream.stop_stream(); stream.close(); p.terminate()
                try: page.close(dlg_listen)
                except: pass
                
                if frames and has_spoken:
                    safe_show_snack("Processing...", "blue")
                    r = sr.Recognizer()
                    try: 
                        text_res = r.recognize_google(sr.AudioData(b''.join(frames), 44100, 2), language="th")
                        
                        # ------------------------------------------------------------------
                        # [DEBUG LOG 1] ดูสิ่งที่ Google ส่งกลับมา (Raw Text)
                        # ------------------------------------------------------------------
                        print(f"\n[DEBUG] Google Raw: '{text_res}'")
                        safe_show_snack(f"Raw: {text_res}", "blue") 
                        # ------------------------------------------------------------------

                        process_result(text_res)
                    except sr.UnknownValueError: safe_show_snack("Could not understand audio", "red")
                    except Exception as e: safe_show_snack(f"Error: {e}", "red")
                else: safe_show_snack("No speech detected", "orange")
            except Exception as e: 
                print(f"Error: {e}")
                try: page.close(dlg_listen)
                except: pass

        threading.Thread(target=record_thread, daemon=True).start()

    btn_expense.on_click = lambda e: start_listen(e, "expense")
    btn_income.on_click = lambda e: start_listen(e, "income")
    
    
    # ///////////////////////////////////////////////////////////////
    # [SECTION 9] VIEW BUILDERS
    # ///////////////////////////////////////////////////////////////
    def build_full_view():
        sidebar = ft.Container(width=320, padding=ft.padding.only(left=20, right=20, top=10, bottom=20), bgcolor=COLOR_SURFACE, border_radius=15, content=ft.Column([
            ft.Row([txt_app_title, ft.Container(expand=True), btn_settings], alignment="spaceBetween"),
            cal,
            ft.Container(content=btn_reset_filter, alignment=ft.alignment.center),
            ft.Divider(),
            ft.Row([txt_heading_rec, ft.IconButton("add_circle", on_click=open_add_rec)], alignment="spaceBetween"),
            ft.Container(content=recurring_list_view, expand=True),
            ft.Row([btn_expense, btn_income], alignment="center", spacing=10)
        ]))

        main_pane = ft.Container(expand=True, padding=10, content=ft.Column([
            summary_section, budget_container, cards_row, ft.Divider(color="transparent"),
            ft.Row([txt_heading_recent, ft.OutlinedButton("Chart", icon="bar_chart", on_click=open_top10_dialog)], alignment="spaceBetween"),
            trans_list_view
        ]))
        
        sidebar.content.controls[0].controls.insert(2, ft.IconButton(icon="smartphone", tooltip="Compact Mode", icon_size=20, on_click=lambda _: switch_view("simple")))
        return ft.Row([main_pane, sidebar], expand=True)

    def build_simple_view():
        header = ft.Container(content=ft.Row([txt_simple_date, btn_to_full], alignment="spaceBetween", vertical_alignment="center"), padding=ft.padding.only(top=10, bottom=15))
        body = ft.Container(content=simple_list_view, expand=True, bgcolor=COLOR_SURFACE, border_radius=15, padding=10)
        footer = ft.Container(content=ft.Row([btn_simple_inc, btn_simple_exp], spacing=10, alignment="center"), padding=ft.padding.only(top=10, bottom=5))
        return ft.Container(content=ft.Column([header, body, footer], spacing=0), padding=5, expand=True)

    def build_splash_view():
        global splash_icon
        splash_icon = ft.Icon("account_balance_wallet", size=80, color=COLOR_PRIMARY, scale=0, animate_scale=ft.Animation(800, "elasticOut"))
        return ft.Container(content=ft.Column([splash_icon, ft.ProgressRing(width=25, height=25, stroke_width=3, color=COLOR_PRIMARY)], alignment="center", horizontal_alignment="center", spacing=30), alignment=ft.alignment.center, expand=True)

    # ///////////////////////////////////////////////////////////////
    # [SECTION 10] APP FLOW & STARTUP
    # ///////////////////////////////////////////////////////////////
    def switch_view(mode, should_center=True):
        nonlocal current_view_mode
        current_view_mode = mode
        main_container.opacity = 0; main_container.update(); time.sleep(0.3) 
        if mode == "simple": page.window.width = 400; page.window.height = 600
        else: page.window.width = 1200; page.window.height = 1000
        if should_center: page.window.center()
        
        if mode == "simple": main_container.content = build_simple_view()
        else: main_container.content = build_full_view()
        
        refresh_ui(); page.update(); time.sleep(0.15); main_container.opacity = 1; main_container.update()

    def init_application(selected_path):
        nonlocal current_db
        time.sleep(0.5)
        current_db = DatabaseManager(selected_path); current_db.connect(); config["db_path"] = selected_path; save_config(config)
        cal.set_db(current_db)
        switch_view(current_view_mode, should_center=False)

    def check_startup():
        main_container.content = build_splash_view(); page.update(); page.window.visible = True
        for i in range(0, 11): page.window.opacity = i / 10; page.update(); time.sleep(0.01)
        time.sleep(0.1); splash_icon.scale = 1.0; splash_icon.update(); time.sleep(1.5) 

        if os.path.exists(db_path): init_application(db_path)
        else:
            dlg = ft.AlertDialog(modal=True, title=ft.Text("Database Not Found"))
            def on_file_picked(e):
                if e.files: dlg.open = False; page.update(); init_application(e.files[0].path)
            pick_dialog = ft.FilePicker(on_result=on_file_picked); page.overlay.append(pick_dialog)
            def create_new(e): dlg.open = False; page.update(); init_application(DEFAULT_DB_NAME)
            dlg.content = ft.Text(f"Could not find: {db_path}"); dlg.actions = [ft.TextButton("Create New", on_click=create_new), ft.TextButton("Browse...", on_click=lambda _: pick_dialog.pick_files(allowed_extensions=["db"]))]; page.open(dlg)

    check_startup()
    
    def on_window_event(e):
        if e.data == "close":
            if current_view_mode == "full": config.update({"width": page.window.width, "height": page.window.height})
            save_config(config); page.window_destroy()
    page.on_window_event = on_window_event

if __name__ == "__main__":
    ft.app(target=main)