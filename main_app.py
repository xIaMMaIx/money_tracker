# main.py

# ///////////////////////////////////////////////////////////////
# [SECTION 1] IMPORTS & CONFIG
# ///////////////////////////////////////////////////////////////
import flet as ft
import threading
import time
import os
import traceback
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
# [SECTION 3] MAIN ENTRY POINT
# ///////////////////////////////////////////////////////////////
def main(page: ft.Page):
    # [DEBUG] ครอบ Try-Except ใหญ่สุดเพื่อกันจอดำ และแสดง Error ถ้ามี
    try:
        real_main(page)
    except Exception as e:
        page.bgcolor = "black"
        page.clean()
        page.add(
            ft.SafeArea( # ใช้ SafeArea แม้แต่หน้า Error
                ft.Column([
                    ft.Icon("error", color="red", size=50),
                    ft.Text("CRITICAL ERROR", color="red", size=20, weight="bold"),
                    ft.Text(f"App crashed on startup:\n{str(e)}", color="white"),
                    ft.Text(traceback.format_exc(), color="grey", size=10, font_family="monospace")
                ], scroll=ft.ScrollMode.AUTO)
            )
        )
        page.update()

def real_main(page: ft.Page):
    global main_container, splash_icon
    
    # --- Load Config ---
    config = load_config()
    
    # [FIX] แก้บั๊ก Path Windows (C:\...) ติดมาในมือถือ
    current_db_path = config.get("db_path", DEFAULT_DB_NAME)
    if ":" in current_db_path or "\\" in current_db_path or "/" in current_db_path:
        current_db_path = os.path.basename(current_db_path)
        if not current_db_path: current_db_path = DEFAULT_DB_NAME
        config["db_path"] = current_db_path
        save_config(config)

    # --- Mobile Window Setup ---
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        font_family=config.get("font_family", "Kanit"),
        scrollbar_theme=ft.ScrollbarTheme(thickness=0, thumb_visibility=False, track_visibility=False)
    )
    
    # Container หลักที่จะเปลี่ยนเนื้อหาข้างใน
    main_container = ft.Container(expand=True)
    
    # [FIX: SAFE AREA] ครอบด้วย SafeArea เพื่อกันไม่ให้ทับ Status Bar ด้านบน/ล่าง
    page.add(ft.SafeArea(main_container, expand=True))

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
    cloud_mgr = CloudManager()
    
    # Search variable
    current_search_query = ""

    def T(key): return TRANSLATIONS[current_lang].get(key, key)
    def safe_show_snack(msg, color="green"):
        try: page.open(ft.SnackBar(content=ft.Text(msg), bgcolor=color))
        except: pass
    
    # ///////////////////////////////////////////////////////////////
    # [SECTION 4] UI COMPONENTS (Mobile Optimized)
    # ///////////////////////////////////////////////////////////////
    
    # --- 1. App Bar & Navigation ---
    def open_drawer(e):
        page.open(nav_drawer)

    def close_drawer(e):
        page.close(nav_drawer)

    # Drawer Items (เมนูข้าง)
    nav_drawer = ft.NavigationDrawer(
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Icon("account_balance_wallet", size=48, color=COLOR_PRIMARY),
                    ft.Text(T("app_title"), size=20, weight="bold", color="white"),
                ], alignment="center", horizontal_alignment="center"),
                bgcolor=COLOR_SURFACE, padding=20, margin=ft.margin.only(bottom=10)
            ),
            ft.NavigationDrawerDestination(icon="home", label="Dashboard"),
            ft.Divider(),
            ft.NavigationDrawerDestination(icon="repeat", label=T("recurring")),
            ft.NavigationDrawerDestination(icon="pie_chart", label=T("top_chart")),
            ft.NavigationDrawerDestination(icon="cloud_sync", label="Cloud Sync"),
            ft.Divider(),
            ft.NavigationDrawerDestination(icon="settings", label=T("settings")),
        ],
        on_change=lambda e: handle_drawer_change(e)
    )

    def handle_drawer_change(e):
        idx = e.control.selected_index
        page.close(nav_drawer)
        
        # Reset selection (optional)
        e.control.selected_index = 0
        
        # [FIXED] แก้เลข index ให้เรียงตามลำดับเมนูจริง (ไม่นับ Divider)
        if idx == 0: # Dashboard
            pass 
        elif idx == 1: # Recurring (เดิมเป็น 2)
            show_recurring_dialog()
        elif idx == 2: # Chart (เดิมเป็น 3)
            open_top10_dialog(None)
        elif idx == 3: # Cloud (เดิมเป็น 4)
            # เปิด Tab cloud ใน Settings
            open_settings_dialog(page, current_db, config, refresh_ui, init_application, cloud_mgr)
        elif idx == 4: # Settings (เดิมเป็น 6)
            open_settings_dialog(page, current_db, config, refresh_ui, init_application, cloud_mgr)

    # --- 2. Date & Calendar Header ---
    txt_month_header = ft.Text("Month", size=18, weight="bold")
    
    # Calendar Wrapper (Dialog)
    def show_calendar_dialog(e):
        cal_container = ft.Container(padding=10, bgcolor=COLOR_SURFACE, border_radius=10)
        cal.width = 300 
        cal_container.content = cal
        
        dlg_cal = ft.AlertDialog(
            content=cal_container,
            content_padding=0,
            actions=[
                ft.TextButton(T("reset_filter"), on_click=lambda _: [cal.reset(), clear_search(None), page.close(dlg_cal)]),
                ft.TextButton(T("close"), on_click=lambda _: page.close(dlg_cal))
            ]
        )
        page.open(dlg_cal)

    btn_month_selector = ft.Container(
        content=ft.Row([
            ft.Icon("calendar_month", color=COLOR_PRIMARY, size=20),
            txt_month_header,
            ft.Icon("arrow_drop_down", color="grey")
        ], spacing=5, alignment="center"),
        ink=True,
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        on_click=show_calendar_dialog
    )

    # --- 3. Summary Cards (Horizontal Scroll) ---
    summary_font_delta = current_font_delta - 4 
    
    card_bal = SummaryCard("balance", "0.00", COLOR_PRIMARY, "account_balance_wallet", summary_font_delta, current_font_weight_str)
    card_inc = SummaryCard("income", "+0.00", COLOR_INCOME, "arrow_upward", summary_font_delta, current_font_weight_str)
    card_exp = SummaryCard("expense", "-0.00", COLOR_EXPENSE, "arrow_downward", summary_font_delta, current_font_weight_str)
    card_net = SummaryCard("Net Worth", "0.00", "cyan", "monetization_on", summary_font_delta, current_font_weight_str)
    
    for c in [card_bal, card_inc, card_exp, card_net]:
        c.width = 160 
        c.height = 80
        c.padding = 10

    summary_row = ft.Row(
        [card_inc, card_exp, card_bal, card_net], 
        scroll=ft.ScrollMode.HIDDEN, 
        spacing=10
    )

    # --- 4. Budget Bar ---
    txt_budget_value = ft.Text("- / -", color="white", size=12)
    pb_budget = ft.ProgressBar(value=0, color=COLOR_PRIMARY, bgcolor=COLOR_SURFACE, height=8, border_radius=4)
    budget_container = ft.Column([
        ft.Row([ft.Text(T("budget"), size=12, color="grey"), txt_budget_value], alignment="spaceBetween"),
        pb_budget
    ], spacing=5)

    # --- 5. Credit Cards (Horizontal Scroll) ---
    cards_row = ft.Row(scroll=ft.ScrollMode.HIDDEN, spacing=10, visible=False)

    # --- 6. Transactions List ---
    txt_heading_recent = ft.Text(T("recent_trans"), size=16, weight="bold")
    trans_list_view = ft.Column(spacing=2) 
    
    # Search UI
    def clear_search(e):
        nonlocal current_search_query
        current_search_query = ""
        txt_search.value = ""
        btn_search_icon.icon = "search"
        refresh_ui()

    def execute_search(e):
        nonlocal current_search_query
        current_search_query = txt_search.value
        refresh_ui()
    
    is_search_visible = False
    txt_search = ft.TextField(
        hint_text="Search...", height=40, text_size=14, content_padding=10, expand=True,
        bgcolor=COLOR_SURFACE, border_radius=8, on_submit=execute_search, visible=False
    )
    
    def toggle_search(e):
        nonlocal is_search_visible
        is_search_visible = not is_search_visible
        txt_search.visible = is_search_visible
        txt_month_header.visible = not is_search_visible 
        if not is_search_visible:
            clear_search(None)
        page.update()

    btn_search_icon = ft.IconButton("search", on_click=toggle_search)

    # --- 7. Bottom Action Buttons (Sticky) ---
    btn_expense = ft.Container(
        content=ft.Row([ft.Icon("remove_circle_outline", size=24, color="white"), ft.Text(T("expense"), size=16, weight="bold", color="white")], alignment="center", spacing=5),
        bgcolor=COLOR_BTN_EXPENSE, border_radius=15, height=55, expand=True, ink=True
    )
    btn_income = ft.Container(
        content=ft.Row([ft.Icon("add_circle_outline", size=24, color="white"), ft.Text(T("income"), size=16, weight="bold", color="white")], alignment="center", spacing=5),
        bgcolor=COLOR_BTN_INCOME, border_radius=15, height=55, expand=True, ink=True
    )

    # --- Calendar Logic ---
    def on_date_change(d): 
        nonlocal current_filter_date
        current_filter_date = d
        refresh_ui()
    
    cal = CalendarWidget(page, on_date_change, current_font_delta, current_font_weight_str)

    # ///////////////////////////////////////////////////////////////
    # [SECTION 5] CORE LOGIC (REFRESH & UPDATE)
    # ///////////////////////////////////////////////////////////////
    def update_all_labels():
        nonlocal current_lang, current_font_delta, current_font_weight_str
        current_lang = config.get("lang", "th")
        current_font_delta, current_font_weight_str = get_font_specs()
        
        summary_font_delta = current_font_delta - 4
        
        nav_drawer.controls[1].label = "Dashboard"
        nav_drawer.controls[3].label = T("recurring")
        nav_drawer.controls[4].label = T("top_chart")
        nav_drawer.controls[7].label = T("settings")

        card_inc.txt_title.value = T("income")
        card_exp.txt_title.value = T("expense")
        card_bal.txt_title.value = T("balance")
        card_net.txt_title.value = "Net Worth" if current_lang == "en" else "ความมั่งคั่งสุทธิ"
        
        for c in [card_bal, card_inc, card_exp, card_net]:
            c.update_style(summary_font_delta, current_font_weight_str)

        cal.update_style(current_font_delta, current_font_weight_str)

        if current_filter_date:
            try:
                dt_obj = datetime.strptime(current_filter_date, "%Y-%m-%d")
                formatted = dt_obj.strftime("%d %B %Y")
                txt_heading_recent.value = formatted
            except: txt_heading_recent.value = current_filter_date
        else: 
            txt_heading_recent.value = T("recent_trans")
        
        btn_expense.content.controls[1].value = T("expense")
        btn_income.content.controls[1].value = T("income")
        
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
        
        # Net Worth ซ่อนเมื่อดูเดือนเก่า
        card_net.visible = is_current_month
        
        bg_exp = COLOR_BTN_EXPENSE if enable_buttons else "grey"
        bg_inc = COLOR_BTN_INCOME if enable_buttons else "grey"
        
        btn_expense.bgcolor = bg_exp; btn_income.bgcolor = bg_inc

        current_db.check_and_rollover(cal.year, cal.month)
        current_month_str = f"{cal.year}-{cal.month:02d}"
        
        month_name = datetime(cal.year, cal.month, 1).strftime("%B %Y")
        txt_month_header.value = month_name
        
        inc, exp, bal = current_db.get_summary(current_month_str)
        
        cards_db = current_db.get_cards()
        total_debt = 0.0
        
        if cards_db:
             for c in cards_db:
                 total_debt += current_db.get_card_usage(c[0], current_month_str)

        net_worth = bal - total_debt

        card_inc.txt_value.value = f"+{format_currency(inc)}"
        card_exp.txt_value.value = f"-{format_currency(exp)}"
        card_bal.txt_value.value = f"{format_currency(bal)}"
        card_net.txt_value.value = f"{format_currency(net_worth)}"
        card_net.txt_value.color = COLOR_INCOME if net_worth >= 0 else COLOR_EXPENSE
        
        try: limit = float(current_db.get_setting("budget", "10000"))
        except: limit = 10000.0
        _, mon_exp, _ = current_db.get_summary(current_month_str)
        ratio = mon_exp / limit if limit > 0 else 0
        pb_budget.value = min(ratio, 1.0)
        pb_budget.color = COLOR_PRIMARY if ratio < 0.5 else ("orange" if ratio < 0.8 else COLOR_EXPENSE)
        txt_budget_value.value = f"{format_currency(mon_exp)} / {format_currency(limit)}"
        
        cards_row.controls.clear()
        if cards_db:
            for c in cards_db: 
                usage_cumulative = current_db.get_card_usage(c[0], current_month_str)
                mc = MiniCardWidget(
                    c, 
                    lambda d: dialogs.open_pay_card_dialog(page, current_db, config, refresh_ui, d, current_filter_date),
                    lambda d: dialogs.open_card_history_dialog(page, current_db, config, refresh_ui, d, cal.year, cal.month),
                    usage_cumulative, 
                    col=None
                )
                mc.width = 160
                cards_row.controls.append(mc)
            cards_row.visible = True
        else: 
            cards_row.visible = False
        
        rows = []
        if current_search_query:
            rows = current_db.search_transactions(current_search_query)
            txt_heading_recent.value = f"Search: '{current_search_query}' ({len(rows)})"
            cards_row.visible = False 
        else:
            cards_row.visible = True if current_db.get_cards() else False
            rows = current_db.get_transactions(current_filter_date, month_filter=current_month_str)
        
        d_font_delta, d_font_weight = get_font_specs()

        def call_delete(tid):
            dialogs.confirm_delete(page, current_db, config, refresh_ui, tid)
        def call_edit(data):
            dialogs.open_edit_dialog(page, current_db, config, refresh_ui, data)

        trans_list_view.controls.clear()
        
        if not rows:
            trans_list_view.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(name="note_add", size=48, color=COLOR_SURFACE),
                        ft.Text(T("no_items"), color="grey")
                    ], horizontal_alignment="center", spacing=10),
                    alignment=ft.alignment.center,
                    padding=40
                )
            )
        
        current_date_grp = None
        for r in rows:
            dt_obj = parse_db_date(r[5])
            date_str = dt_obj.strftime("%d %B %Y")
            
            if date_str != current_date_grp: 
                current_date_grp = date_str
                trans_list_view.controls.append(
                    ft.Container(
                        content=ft.Text(date_str, size=12+d_font_delta, weight="bold", color="grey"), 
                        padding=ft.padding.only(top=15, bottom=5)
                    )
                )
            
            is_new = (r[0] == new_id)
            card = TransactionCard(r, call_delete, call_edit, d_font_delta, d_font_weight, is_new=is_new, minimal=True)
            trans_list_view.controls.append(card)
            
            if is_new: 
                card.bgcolor = "#2C2C2C"

        page.update()

    # ///////////////////////////////////////////////////////////////
    # [SECTION 6] LOGIC - DIALOGS & ACTIONS
    # ///////////////////////////////////////////////////////////////
    def open_add_rec(e):
        dialogs.open_add_rec_dialog(page, current_db, config, refresh_ui)
        
    def open_top10_dialog(e):
        d_font_specs = get_font_specs()
        dialogs.open_top10_dialog(page, current_db, config, cal.year, cal.month, d_font_specs)

    def show_recurring_dialog():
        rec_col = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO, height=400)
        
        def refresh_rec_list():
            rec_col.controls.clear()
            recs = current_db.get_recurring()
            if not recs:
                rec_col.controls.append(ft.Text(T("no_items"), color="grey"))
                return

            check_month = f"{cal.year}-{cal.month:02d}"
            
            for r in recs:
                 rid, day, item_name, amt, cat = r[:5]
                 pid = r[5] if len(r) > 5 else None
                 auto = r[6] if len(r) > 6 else 0
                 
                 is_paid = current_db.is_recurring_paid_v2(item_name, amt, cat, check_month, pid)
                 
                 btn_text = T("paid") if is_paid else T("pay")
                 btn_state = True if is_paid else False
                 
                 pay_func = lambda e, i=item_name, a=amt, c=cat, d=day, p=pid: [
                     dialogs.pay_recurring_action(page, current_db, refresh_ui, i,a,c,d,check_month,p, selected_date_str=current_filter_date),
                     page.close(dlg_rec)
                 ]
                 
                 del_func = lambda e, id=rid: [
                     dialogs.confirm_delete_rec(page, current_db, config, lambda: [refresh_ui(), refresh_rec_list()], id)
                 ]

                 row = ft.Container(
                     content=ft.Row([
                         ft.Container(ft.Text(f"{day:02d}", weight="bold"), bgcolor="black26", width=40, alignment=ft.alignment.center, padding=5, border_radius=5),
                         ft.Column([ft.Text(item_name), ft.Text(format_currency(amt), color=COLOR_EXPENSE, size=12)], expand=True, spacing=0),
                         ft.ElevatedButton(btn_text, disabled=btn_state, on_click=pay_func, height=30, style=ft.ButtonStyle(padding=5)),
                         ft.IconButton("close", icon_size=16, on_click=del_func)
                     ]),
                     bgcolor=COLOR_SURFACE, padding=5, border_radius=8
                 )
                 rec_col.controls.append(row)
            rec_col.update()

        refresh_rec_list()
        
        dlg_rec = ft.AlertDialog(
            title=ft.Row([ft.Text(T("recurring")), ft.IconButton("add", on_click=lambda _: open_add_rec(None))], alignment="spaceBetween"),
            content=ft.Container(rec_col, width=300),
            actions=[ft.TextButton(T("close"), on_click=lambda _: page.close(dlg_rec))]
        )
        page.open(dlg_rec)

    # ///////////////////////////////////////////////////////////////
    # [SECTION 7] MANUAL INPUT
    # ///////////////////////////////////////////////////////////////
    def open_manual_add(e, t_type):
        now = datetime.now()
        is_current_month = (cal.year == now.year and cal.month == now.month)
        is_date_selected = (current_filter_date is not None)

        if not (is_current_month or is_date_selected):
            msg = "Please select a date first." if config.get("lang") == "en" else "กรุณาเลือกวันที่ในปฏิทิน ก่อนบันทึกรายการย้อนหลัง"
            safe_show_snack(f"⚠️ {msg}", "orange")
            return

        target_date = datetime.now()
        if current_filter_date:
            try: 
                sel_dt = datetime.strptime(current_filter_date, "%Y-%m-%d")
                target_date = datetime.combine(sel_dt.date(), datetime.now().time())
            except: pass

        f_item = ft.TextField(label=T("item"), autofocus=True)
        f_amt = ft.TextField(
            label=T("amount"), 
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string="")
        )
        
        cats = current_db.get_categories(t_type)
        cat_opts = [ft.dropdown.Option(c[1]) for c in cats]
        default_cat = cats[0][1] if cats else "General"
        f_cat = ft.Dropdown(label=T("category"), options=cat_opts, value=default_cat)

        pay_opts = [ft.dropdown.Option("cash", "เงินสด / Cash")]
        cards = current_db.get_cards()
        if t_type == "expense":
             for c in cards:
                 pay_opts.append(ft.dropdown.Option(str(c[0]), f"บัตร: {c[1]}"))
        f_payment = ft.Dropdown(label=T("payment_method"), options=pay_opts, value="cash")

        def save(e):
            if not f_amt.value:
                 safe_show_snack("Please enter amount", "red")
                 return
            try:
                amt = float(f_amt.value)
                item = f_item.value if f_item.value else "No Name"
                pid = int(f_payment.value) if f_payment.value != "cash" else None
                
                new_id = current_db.add_transaction(t_type, item, amt, f_cat.value, date=target_date, payment_id=pid)
                
                page.close(dlg)
                refresh_ui(new_id=new_id)
                safe_show_snack(f"Saved {T(t_type)}: {item} ({format_currency(amt)})")
            except Exception as ex:
                safe_show_snack(f"Error: {ex}", "red")

        dlg = ft.AlertDialog(
            title=ft.Text(f"Add {T(t_type)}"),
            content=ft.Column([f_item, f_amt, f_cat, f_payment], tight=True),
            actions=[
                ft.TextButton(T("save"), on_click=save), 
                ft.TextButton(T("cancel"), on_click=lambda _: page.close(dlg))
            ]
        )
        page.open(dlg)

    btn_expense.on_click = lambda e: open_manual_add(e, "expense")
    btn_income.on_click = lambda e: open_manual_add(e, "income")

    # ///////////////////////////////////////////////////////////////
    # [SECTION 8] VIEW BUILDERS (Mobile Layout)
    # ///////////////////////////////////////////////////////////////
    def build_mobile_view():
        app_bar = ft.Container(
            content=ft.Row([
                ft.IconButton("menu", on_click=open_drawer),
                ft.Container(expand=True, content=ft.Row([txt_search, btn_month_selector], alignment="center")),
                btn_search_icon
            ], alignment="spaceBetween"),
            padding=ft.padding.only(left=5, right=5, top=10, bottom=10),
            bgcolor=COLOR_BG
        )

        content_scroll = ft.Column([
            ft.Container(height=10),
            summary_row, 
            ft.Container(content=budget_container, padding=ft.padding.symmetric(horizontal=15)),
            ft.Container(height=10),
            cards_row, 
            ft.Container(
                content=ft.Row([txt_heading_recent], alignment="spaceBetween"),
                padding=ft.padding.symmetric(horizontal=15, vertical=5)
            ),
            ft.Container(content=trans_list_view, padding=ft.padding.symmetric(horizontal=15)),
            ft.Container(height=80) 
        ], scroll=ft.ScrollMode.AUTO, expand=True)

        bottom_dock = ft.Container(
            content=ft.Row([btn_income, btn_expense], spacing=10),
            padding=15,
            bgcolor=hex_with_opacity(COLOR_BG, 0.95), 
            border=ft.border.only(top=ft.BorderSide(1, "#333333")),
        )

        return ft.Column([
            app_bar,
            content_scroll,
            bottom_dock
        ], spacing=0, expand=True)

    def build_splash_view():
        global splash_icon
        splash_icon = ft.Icon("account_balance_wallet", size=80, color=COLOR_PRIMARY, scale=0, animate_scale=ft.Animation(800, "elasticOut"))
        return ft.Container(content=ft.Column([splash_icon, ft.ProgressRing(width=25, height=25, stroke_width=3, color=COLOR_PRIMARY)], alignment="center", horizontal_alignment="center", spacing=30), alignment=ft.alignment.center, expand=True)
        
    # ///////////////////////////////////////////////////////////////
    # [SECTION 9] APP FLOW
    # ///////////////////////////////////////////////////////////////
    def init_application(selected_path):
        nonlocal current_db
        time.sleep(0.5)
        current_db = DatabaseManager(selected_path); current_db.connect(); config["db_path"] = selected_path; save_config(config)
        cal.set_db(current_db)
        
        main_container.content = build_mobile_view()
        refresh_ui()
        main_container.update()

    def check_startup():
        # [FIX] ไม่มีการเล่นกับ page.window.opacity แล้ว
        main_container.content = build_splash_view()
        page.update()
        time.sleep(1.0) 

        if os.path.exists(db_path): init_application(db_path)
        else:
            dlg = ft.AlertDialog(modal=True, title=ft.Text("Database Not Found"))
            def on_file_picked(e):
                if e.files: dlg.open = False; page.update(); init_application(e.files[0].path)
            pick_dialog = ft.FilePicker(on_result=on_file_picked); page.overlay.append(pick_dialog)
            def create_new(e): dlg.open = False; page.update(); init_application(DEFAULT_DB_NAME)
            dlg.content = ft.Text(f"Could not find: {db_path}"); dlg.actions = [ft.TextButton("Create New", on_click=create_new), ft.TextButton("Browse...", on_click=lambda _: pick_dialog.pick_files(allowed_extensions=["db"]))]; page.open(dlg)

    def start_auto_sync():
        def sync_loop():
            # [FIX] Try-Catch เพื่อป้องกัน Thread พังเงียบๆ
            try:
                current_conf = load_config()
                target_path = current_conf.get("db_path", "modern_money.db")
                if not os.path.isabs(target_path):
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    target_path = os.path.join(base_dir, target_path)

                last_mtime = 0
                if os.path.exists(target_path):
                    last_mtime = os.path.getmtime(target_path)

                while True:
                    time.sleep(2)
                    try:
                        if os.path.exists(target_path):
                            current_mtime = os.path.getmtime(target_path)
                            wal_path = target_path + "-wal"
                            if os.path.exists(wal_path):
                                current_mtime = max(current_mtime, os.path.getmtime(wal_path))

                            if current_mtime != last_mtime:
                                last_mtime = current_mtime
                                # [WARNING] การเรียก refresh_ui จาก Thread อาจไม่ปลอดภัยในบางครั้ง
                                # แต่ถ้า page object ยังอยู่ก็พอได้ (ใช้ try กันไว้)
                                try: refresh_ui()
                                except: pass
                    except: pass
            except: pass
        
        threading.Thread(target=sync_loop, daemon=True).start()

    start_auto_sync()
    check_startup()

if __name__ == "__main__":
    ft.app(target=main)