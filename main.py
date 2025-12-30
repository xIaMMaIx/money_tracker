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
import dialogs

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
    
    # [MODIFIED] ลดขนาดฟอนต์ของการ์ดลงเป็นพิเศษเพื่อให้เรียง 4 ใบได้พอดี
    summary_font_delta = current_font_delta - 4 

    card_inc = SummaryCard("income", "+0.00", COLOR_INCOME, "arrow_upward", summary_font_delta, current_font_weight_str)
    card_exp = SummaryCard("expense", "-0.00", COLOR_EXPENSE, "arrow_downward", summary_font_delta, current_font_weight_str)
    card_bal = SummaryCard("balance", "0.00", COLOR_PRIMARY, "account_balance_wallet", summary_font_delta, current_font_weight_str)
    card_net = SummaryCard("Net Worth", "0.00", "cyan", "monetization_on", summary_font_delta, current_font_weight_str)

    txt_summary_header = ft.Text(T("overview"), color="grey")
    
    # [MODIFIED] กลับมาใช้ Row เดียว 4 ใบ และลด spacing เหลือ 2
    summary_row = ft.Row([card_inc, card_exp, card_bal, card_net], spacing=2, expand=True)

    # --- Budget Widgets ---
    txt_budget_title = ft.Text(T("budget"), color="grey", size=12)
    txt_budget_value = ft.Text("- / -", color="white", size=12)
    pb_budget = ft.ProgressBar(value=0, color=COLOR_PRIMARY, bgcolor=COLOR_SURFACE, height=6, border_radius=3)
    
    # --- Summary Section (Tighter Layout) ---
    summary_section = ft.Container(
        content=ft.Column([
            txt_summary_header, 
            summary_row, # ใช้แถวเดียว
            ft.Container(height=5),
            ft.Divider(height=1, color="white10"),
            ft.Row([txt_budget_title, txt_budget_value], alignment="spaceBetween"),
            pb_budget
        ], spacing=8),
        padding=15, # ลด Padding ลงนิดหน่อย
        border=ft.border.all(1, "#333333"), 
        border_radius=15, 
        margin=ft.margin.only(bottom=10)
    )
    
    txt_heading_recent = ft.Text("Recent")
    txt_heading_rec = ft.Text("Recurring")
    
    btn_reset_filter = ft.OutlinedButton("Reset Filter", icon="refresh")
    
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
        
        # [MODIFIED] คำนวณขนาดฟอนต์เล็กสำหรับ Card 4 ใบ
        summary_font_delta = current_font_delta - 4
        
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
        
        # [MODIFIED] ใช้ summary_font_delta
        card_inc.update_style(summary_font_delta, current_font_weight_str)
        card_exp.update_style(summary_font_delta, current_font_weight_str)
        card_bal.update_style(summary_font_delta, current_font_weight_str)
        card_net.update_style(summary_font_delta, current_font_weight_str)

        cal.update_style(current_font_delta, current_font_weight_str)

        if current_filter_date:
            try:
                dt_obj = datetime.strptime(current_filter_date, "%Y-%m-%d"); formatted = dt_obj.strftime("%d %B %Y"); txt_heading_recent.value = formatted
            except: txt_heading_recent.value = current_filter_date
        else: txt_heading_recent.value = T("recent_trans")
        
        txt_simple_date.value = datetime.now().strftime("%d %B %Y")
        
        btn_reset_filter.text = T("reset_filter"); 
        card_inc.txt_title.value = T("income"); 
        card_exp.txt_title.value = T("expense"); 
        card_bal.txt_title.value = T("balance"); 
        
        card_net.txt_title.value = "Net Worth" if current_lang == "en" else "ความมั่งคั่งสุทธิ"

        btn_expense.text = T("expense")
        btn_income.text = T("income")
        btn_simple_exp.content.controls[1].value = T("expense")
        btn_simple_inc.content.controls[1].value = T("income")
        btn_simple_exp.tooltip = T("expense"); btn_simple_inc.tooltip = T("income")
        
        page.update()

    def process_auto_pay():
        recs = current_db.get_recurring()
        if not recs: return

        check_month = f"{cal.year}-{cal.month:02d}"
        real_now = datetime.now()
        
        is_real_current_month = (cal.year == real_now.year and cal.month == real_now.month)
        if not is_real_current_month: return
        
        current_day_val = real_now.day
        
        for r in recs:
            try:
                rid, day, item_name, amt, cat, pid, auto = r
            except ValueError:
                rid, day, item_name, amt, cat = r[:5]
                pid, auto = None, 0
            
            if auto == 1 and day <= current_day_val:
                if not current_db.is_recurring_paid_v2(item_name, amt, cat, check_month, pid):
                    dialogs.pay_recurring_action(page, current_db, refresh_ui, item_name, amt, cat, day, check_month, pid, is_auto=True, suppress_refresh=True)

    def refresh_ui(new_id=None):
        if not current_db: return
        
        process_auto_pay()
        update_all_labels()
        
        now = datetime.now()
        is_current_month = (cal.year == now.year and cal.month == now.month)
        is_date_selected = (current_filter_date is not None)
        enable_buttons = is_current_month or is_date_selected
        
        bg_exp = COLOR_BTN_EXPENSE if enable_buttons else "grey"
        bg_inc = COLOR_BTN_INCOME if enable_buttons else "grey"
        
        btn_expense.bgcolor = bg_exp; btn_income.bgcolor = bg_inc
        btn_simple_exp.bgcolor = bg_exp; btn_simple_inc.bgcolor = bg_inc

        current_db.check_and_rollover(cal.year, cal.month)
        current_month_str = f"{cal.year}-{cal.month:02d}"
        
        month_name = datetime(cal.year, cal.month, 1).strftime("%B %Y")
        txt_summary_header.value = f"{T('overview')} ({month_name})"
        
        inc, exp, bal = current_db.get_summary(current_month_str)
        
        total_debt = 0.0
        try:
            total_debt = current_db.get_total_debt()
        except AttributeError:
            pass
            
        net_worth = bal - total_debt

        card_inc.txt_value.value = f"+{format_currency(inc)}"
        card_exp.txt_value.value = f"-{format_currency(exp)}"
        card_bal.txt_value.value = f"{format_currency(bal)}"
        
        card_net.txt_value.value = f"{format_currency(net_worth)}"
        card_net.txt_value.color = COLOR_INCOME if net_worth >= 0 else COLOR_EXPENSE
        
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
                cards_row.controls.append(MiniCardWidget(
                    c, 
                    lambda d: dialogs.open_pay_card_dialog(page, current_db, config, refresh_ui, d, current_filter_date),
                    lambda d: dialogs.open_card_history_dialog(page, current_db, config, refresh_ui, d, cal.year, cal.month),
                    usage, 
                    col=dynamic_col
                ))
            cards_row.visible = True
        else: cards_row.visible = False
        
        if current_view_mode == "simple":
             rows = current_db.get_transactions(None, month_filter=current_month_str)
        else:
             rows = current_db.get_transactions(current_filter_date, month_filter=current_month_str)
        
        d_font_delta, d_font_weight = get_font_specs()

        # Helper สำหรับเรียก Dialog
        def call_delete(tid):
            dialogs.confirm_delete(page, current_db, config, refresh_ui, tid)
        def call_edit(data):
            dialogs.open_edit_dialog(page, current_db, config, refresh_ui, data)

        if current_view_mode == "full":
            trans_list_view.controls.clear(); animated_card = None; current_date_grp = None
            for r in rows:
                dt_obj = parse_db_date(r[5]); date_str = dt_obj.strftime("%d %B %Y")
                if date_str != current_date_grp: current_date_grp = date_str; trans_list_view.controls.append(ft.Container(content=ft.Text(date_str, size=12+d_font_delta, weight="bold", color="grey"), padding=ft.padding.only(top=10, bottom=5)))
                is_new = (r[0] == new_id)
                card = TransactionCard(r, call_delete, call_edit, d_font_delta, d_font_weight, is_new=is_new, minimal=False)
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
                    card = TransactionCard(r, call_delete, call_edit, d_font_delta, d_font_weight, minimal=True)
                    simple_list_view.controls.append(card)
            page.update()

    def update_recurring_list():
        d_font_delta, d_font_weight = get_font_specs()
        recurring_list_view.controls.clear()
        
        recs = current_db.get_recurring()
        if not recs: 
            recurring_list_view.controls.append(ft.Text(T("no_items"), color="grey", size=12+d_font_delta))
            return

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
            
            if auto == 1 and pid:
                if is_paid:
                    btn = ft.ElevatedButton(T("paid"), disabled=True, height=25)
                else:
                    c_color = card_map[pid]['color'] if pid in card_map else "yellow"
                    
                    btn = ft.Container(
                        content=ft.Text("Auto", size=12, color=c_color, weight="bold"),
                        padding=ft.padding.symmetric(horizontal=10, vertical=2),
                        border=ft.border.all(1, c_color),
                        border_radius=5,
                        tooltip="Waiting for auto-pay date"
                    )
            else:
                pay_func = lambda e, i=item_name, a=amt, c=cat, d=day, cm=check_month, p=pid: dialogs.pay_recurring_action(page, current_db, refresh_ui, i,a,c,d,cm,p)
                btn = ft.ElevatedButton(T("paid"), disabled=True, height=25) if is_paid else ft.ElevatedButton(T("pay"), style=ft.ButtonStyle(bgcolor=COLOR_PRIMARY, color="white"), height=25, on_click=pay_func)
            
            del_func = lambda e, id=rid: dialogs.confirm_delete_rec(page, current_db, config, refresh_ui, id)

            row_content = ft.Row([
                day_container, 
                ft.Container(content=ft.Column([
                    ft.Text(item_name, weight=d_font_weight, size=14+d_font_delta), 
                    ft.Row(meta_info, spacing=5)
                ], spacing=0, alignment="center"), expand=True, padding=ft.padding.only(left=10)), 
                ft.Container(content=btn, padding=ft.padding.only(right=5)), 
                ft.Container(content=ft.IconButton("close", icon_size=12, width=24, height=24, style=ft.ButtonStyle(padding=0), icon_color="grey", on_click=del_func), padding=ft.padding.only(right=5))
            ], spacing=0, alignment="spaceBetween")
            
            card = ft.Container(content=row_content, bgcolor=COLOR_HIGHLIGHT, border_radius=10, padding=0, height=45, clip_behavior=ft.ClipBehavior.HARD_EDGE)
            recurring_list_view.controls.append(card)
            
    # ///////////////////////////////////////////////////////////////
    # [SECTION 6] DIALOG ACTIONS -> MOVED TO dialogs.py
    # ///////////////////////////////////////////////////////////////
    
    # --- Link Local Functions to Dialogs Module ---
    def open_add_rec(e):
        dialogs.open_add_rec_dialog(page, current_db, config, refresh_ui)
        
    def open_top10_dialog(e):
        d_font_specs = get_font_specs()
        dialogs.open_top10_dialog(page, current_db, config, cal.year, cal.month, d_font_specs)

    # ///////////////////////////////////////////////////////////////
    # [SECTION 7] SETTINGS & CLOUD
    # ///////////////////////////////////////////////////////////////
    def open_settings(e):
        open_settings_dialog(page, current_db, config, refresh_ui, init_application, cloud_mgr)

    btn_settings.on_click = open_settings

    # ///////////////////////////////////////////////////////////////
    # [SECTION 8] VOICE SYSTEM
    # ///////////////////////////////////////////////////////////////
    def start_listen(e, t_type):
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
            
            amt_val, item_text = parse_thai_money(text)
            
            cats = current_db.get_categories(t_type)
            cards = current_db.get_cards()
            
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
            
            detected_card_id = "cash"
            sorted_cards = sorted(cards, key=lambda x: len(x[1]), reverse=True)
            if t_type != "income":
                for c in sorted_cards:
                    if c[1].lower() in text.lower():
                        detected_card_id = str(c[0])
                        pattern = re.compile(re.escape(c[1]), re.IGNORECASE)
                        item_text = pattern.sub("", item_text).strip()
                        break
            
            if amt_val == 0.0:
                 clean = text.replace(",", "")
                 nums = re.findall(r"[-+]?\d*\.\d+|\d+", clean)
                 if nums: amt_val = float(nums[0])
            
            if amt_val == 0.0: 
                safe_show_snack("Could not detect amount, please enter manually.", "orange")

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
                        safe_show_snack(f"Raw: {text_res}", "blue") 
                        process_result(text_res)
                    except sr.UnknownValueError: safe_show_snack("Could not understand audio", "red")
                    except Exception as e: safe_show_snack(f"Error: {e}", "red")
                else: safe_show_snack("No speech detected", "orange")
            except Exception as e: 
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
            summary_section, 
            cards_row, 
            ft.Divider(color="transparent"),
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