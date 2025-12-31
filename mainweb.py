# mainweb.py

# ///////////////////////////////////////////////////////////////
# [SECTION 1] IMPORTS & CONFIG
# ///////////////////////////////////////////////////////////////
import flet as ft
import threading
import time
import os
import sys
from datetime import datetime

# Local Imports
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

# ///////////////////////////////////////////////////////////////
# [SECTION 3] MAIN ENTRY POINT
# ///////////////////////////////////////////////////////////////
def main(page: ft.Page):
    global main_container
    
    # --- Web Page Setup ---
    page.title = "Modern Money Tracker (Web)"
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    
    config = load_config()
    
    page.theme = ft.Theme(
        font_family=config.get("font_family", "Kanit"),
        scrollbar_theme=ft.ScrollbarTheme(thickness=5, thumb_visibility=True, track_visibility=True)
    )
    
    main_container = ft.Container(
        expand=True,
        opacity=1, 
        padding=15
    )
    page.add(main_container)

    # --- Helpers ---
    def get_font_specs():
        s = config.get("font_size", 14)
        w = config.get("font_weight", 600)
        return s - 14, f"w{w}"

    current_font_delta, current_font_weight_str = get_font_specs()
    
    # --- State Variables ---
    current_db = None
    current_filter_date = None
    current_lang = config.get("lang", "th")
    cloud_mgr = CloudManager()

    def T(key): return TRANSLATIONS[current_lang].get(key, key)
    def safe_show_snack(msg, color="green"):
        try: page.open(ft.SnackBar(content=ft.Text(msg), bgcolor=color))
        except: pass
    
    # ///////////////////////////////////////////////////////////////
    # [SECTION 4] UI INITIALIZATION
    # ///////////////////////////////////////////////////////////////
    btn_settings = ft.IconButton("settings", icon_size=20)
    txt_app_title = ft.Text(T("app_title"), color=COLOR_PRIMARY)
    
    summary_font_delta = current_font_delta - 4 

    card_inc = SummaryCard("income", "+0.00", COLOR_INCOME, "arrow_upward", summary_font_delta, current_font_weight_str)
    card_exp = SummaryCard("expense", "-0.00", COLOR_EXPENSE, "arrow_downward", summary_font_delta, current_font_weight_str)
    card_bal = SummaryCard("balance", "0.00", COLOR_PRIMARY, "account_balance_wallet", summary_font_delta, current_font_weight_str)
    card_net = SummaryCard("Net Worth", "0.00", "cyan", "monetization_on", summary_font_delta, current_font_weight_str)

    txt_summary_header = ft.Text(T("overview"), color="grey")
    summary_row = ft.Row([card_inc, card_exp, card_bal, card_net], spacing=2, expand=True)

    txt_budget_title = ft.Text(T("budget"), color="grey", size=12)
    txt_budget_value = ft.Text("- / -", color="white", size=12)
    pb_budget = ft.ProgressBar(value=0, color=COLOR_PRIMARY, bgcolor=COLOR_SURFACE, height=6, border_radius=3)
    
    summary_section = ft.Container(
        content=ft.Column([
            txt_summary_header, 
            summary_row,
            ft.Container(height=5),
            ft.Divider(height=1, color="white10"),
            ft.Row([txt_budget_title, txt_budget_value], alignment="spaceBetween"),
            pb_budget
        ], spacing=8),
        padding=15, 
        border=ft.border.all(1, "#333333"), 
        border_radius=15, 
        margin=ft.margin.only(bottom=10)
    )
    
    txt_heading_recent = ft.Text("Recent")
    txt_heading_rec = ft.Text("Recurring")
    
    btn_reset_filter = ft.OutlinedButton("Reset Filter", icon="refresh")
    
    # ปุ่มกดบันทึก
    btn_expense = ft.ElevatedButton(
        text=T("expense"), 
        icon="remove", 
        bgcolor=COLOR_BTN_EXPENSE, 
        color="white",
        elevation=4,
        height=50,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15)),
        expand=True 
    )
    
    btn_income = ft.ElevatedButton(
        text=T("income"), 
        icon="add", 
        bgcolor=COLOR_BTN_INCOME, 
        color="white",
        elevation=4,
        height=50,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15)),
        expand=True 
    )
    
    # [FIX 1] ใช้ Column ธรรมดา + Scrollbar (เสถียรสุดบนเว็บ)
    trans_list_view = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=5)
    
    recurring_list_view = ft.Column(spacing=5, scroll="hidden")
    cards_row = ft.ResponsiveRow(spacing=10, run_spacing=10, visible=False)
    
    def on_date_change(d): 
        nonlocal current_filter_date
        current_filter_date = d
        refresh_ui()

    cal = CalendarWidget(page, on_date_change, current_font_delta, current_font_weight_str)
    btn_reset_filter.on_click = lambda e: [cal.reset()]

    # ///////////////////////////////////////////////////////////////
    # [SECTION 5] LOGIC
    # ///////////////////////////////////////////////////////////////
    def update_all_labels():
        nonlocal current_lang, current_font_delta, current_font_weight_str
        current_lang = config.get("lang", "th")
        current_font_delta, current_font_weight_str = get_font_specs()
        
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
        
        btn_reset_filter.text = T("reset_filter"); 
        card_inc.txt_title.value = T("income"); 
        card_exp.txt_title.value = T("expense"); 
        card_bal.txt_title.value = T("balance"); 
        card_net.txt_title.value = "Net Worth" if current_lang == "en" else "ความมั่งคั่งสุทธิ"

        btn_expense.text = T("expense")
        btn_income.text = T("income")

    def process_auto_pay():
        if not current_db: return
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
        
        current_month_str = f"{cal.year}-{cal.month:02d}"
        month_name = datetime(cal.year, cal.month, 1).strftime("%B %Y")
        txt_summary_header.value = f"{T('overview')} ({month_name})"
        
        current_db.check_and_rollover(cal.year, cal.month)

        inc, exp, bal = current_db.get_summary(current_month_str)
        
        cards_db = current_db.get_cards()
        total_debt = 0.0
        if cards_db:
             for c in cards_db:
                 total_debt += current_db.get_card_usage(c[0])

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
        
        cards_row.controls.clear()
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
        
        rows = current_db.get_transactions(current_filter_date, month_filter=current_month_str)
        
        d_font_delta, d_font_weight = get_font_specs()

        def call_delete(tid):
            dialogs.confirm_delete(page, current_db, config, refresh_ui, tid)
        def call_edit(data):
            dialogs.open_edit_dialog(page, current_db, config, refresh_ui, data)

        trans_list_view.controls.clear(); current_date_grp = None
        for r in rows:
            dt_obj = parse_db_date(r[5]); date_str = dt_obj.strftime("%d %B %Y")
            if date_str != current_date_grp: current_date_grp = date_str; trans_list_view.controls.append(ft.Container(content=ft.Text(date_str, size=12+d_font_delta, weight="bold", color="grey"), padding=ft.padding.only(top=10, bottom=5)))
            
            # [FIX 2] ลบ Animation ที่ทำให้ Web หน่วง/ค้างออก (is_new=False เสมอ)
            # การใส่ animation scroll บนเว็บ Flet มักทำให้หน้าจอกระตุกหรือขาว
            card = TransactionCard(r, call_delete, call_edit, d_font_delta, d_font_weight, is_new=False, minimal=False)
            trans_list_view.controls.append(card)
        
        update_recurring_list()
        
        try:
            page.update()
        except: pass

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
    # [SECTION 6] DIALOG & ACTIONS
    # ///////////////////////////////////////////////////////////////
    def open_add_rec(e):
        dialogs.open_add_rec_dialog(page, current_db, config, refresh_ui)
        
    def open_top10_dialog(e):
        d_font_specs = get_font_specs()
        dialogs.open_top10_dialog(page, current_db, config, cal.year, cal.month, d_font_specs)

    def open_settings(e):
        def on_db_changed(new_path):
            init_web(new_path)
        open_settings_dialog(page, current_db, config, refresh_ui, on_db_changed, cloud_mgr)

    btn_settings.on_click = open_settings

    def open_manual_add_dialog(t_type):
        cats = current_db.get_categories(t_type)
        cards = current_db.get_cards()
        
        f_item = ft.TextField(label=T("item"), autofocus=True)
        f_amt = ft.TextField(
            label=T("amount"), 
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string="")
        )
        
        default_cat = cats[0][1] if cats else "Other"
        f_cat = ft.Dropdown(
            label=T("category"), 
            options=[ft.dropdown.Option(c[1]) for c in cats], 
            value=default_cat
        )
        
        pay_opts = [ft.dropdown.Option("cash", "เงินสด / Cash")]
        if t_type != "income":
            for c in cards:
                pay_opts.append(ft.dropdown.Option(str(c[0]), f"บัตร: {c[1]}"))
        
        f_payment = ft.Dropdown(
            label=T("payment_method"), 
            options=pay_opts, 
            value="cash",
            visible=(t_type != "income")
        )

        target_date = datetime.now()
        if current_filter_date:
            try:
                sel_dt = datetime.strptime(current_filter_date, "%Y-%m-%d")
                target_date = datetime.combine(sel_dt.date(), datetime.now().time())
            except: pass
        
        display_date = target_date.strftime("%d/%m/%Y")

        def save(e):
            try:
                if not f_amt.value: 
                    safe_show_snack("Please enter amount", "red")
                    return
                
                amt = float(f_amt.value)
                item = f_item.value if f_item.value else T(t_type)
                cat = f_cat.value
                pid = int(f_payment.value) if (f_payment.value and f_payment.value != "cash") else None
                
                print(f"Saving: {t_type}, {item}, {amt}") 
                new_id = current_db.add_transaction(t_type, item, amt, cat, date=target_date, payment_id=pid)
                
                page.close(dlg)
                refresh_ui(new_id=new_id)
                safe_show_snack(f"Saved {item} ({format_currency(amt)}) to {display_date}")
                
            except Exception as ex:
                print(f"Error saving: {ex}") 
                safe_show_snack(f"Error: {ex}", "red")

        title_text = T("income") if t_type == "income" else T("expense")
        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon("edit_note"), ft.Text(f"{T('add_rec')} - {title_text}")]),
            content=ft.Column([
                ft.Text(f"Date: {display_date}", size=12, color="grey"),
                f_item, f_amt, f_cat, f_payment
            ], tight=True, width=400),
            actions=[
                ft.TextButton(T("save"), on_click=save),
                ft.TextButton(T("cancel"), on_click=lambda e: page.close(dlg))
            ]
        )
        page.open(dlg)

    btn_expense.on_click = lambda e: open_manual_add_dialog("expense")
    btn_income.on_click = lambda e: open_manual_add_dialog("income")

    # ///////////////////////////////////////////////////////////////
    # [SECTION 7] BUILD & RUN
    # ///////////////////////////////////////////////////////////////
    def build_full_view():
        sidebar = ft.Container(
            padding=ft.padding.only(left=20, right=20, top=10, bottom=20), 
            bgcolor=COLOR_SURFACE, 
            border_radius=15, 
            content=ft.Column([
                ft.Row([txt_app_title, ft.Container(expand=True), btn_settings], alignment="spaceBetween"),
                cal,
                ft.Container(content=btn_reset_filter, alignment=ft.alignment.center),
                ft.Divider(),
                ft.Row([txt_heading_rec, ft.IconButton("add_circle", on_click=open_add_rec)], alignment="spaceBetween"),
                ft.Container(content=recurring_list_view, expand=True),
                ft.Row([btn_expense, btn_income], alignment="center", spacing=10)
            ])
        )

        # [FIX 3] กำหนด expand=True ให้ Container แม่ และ Column แม่ เพื่อให้ลูกๆ ยืดได้เต็มที่
        main_pane = ft.Container(expand=True, padding=10, content=ft.Column([
            summary_section, 
            cards_row, 
            ft.Divider(color="transparent"),
            ft.Row([txt_heading_recent, ft.OutlinedButton("Chart", icon="bar_chart", on_click=open_top10_dialog)], alignment="spaceBetween"),
            # Container ที่หุ้ม trans_list_view ต้อง expand ด้วย
            ft.Container(content=trans_list_view, expand=True) 
        ], expand=True)) # <--- ใส่ expand=True ที่ Column นี้ด้วย สำคัญมาก
        
        return ft.ResponsiveRow([
            ft.Column([main_pane], col={"md": 9, "sm": 12}),
            ft.Column([sidebar], col={"md": 3, "sm": 12})
        ])

    def init_web(specific_path=None):
        nonlocal current_db
        
        target_path = specific_path
        if not target_path:
            current_conf = load_config()
            target_path = current_conf.get("db_path", "modern_money.db")

        if not os.path.isabs(target_path):
             base_dir = os.path.dirname(os.path.abspath(__file__))
             target_path = os.path.join(base_dir, target_path)

        print(f"Connecting to DB at: {target_path}")

        try:
            current_db = DatabaseManager(target_path)
            current_db.connect()
            cal.set_db(current_db)
            
            config["db_path"] = target_path
            
            main_container.content = build_full_view()
            refresh_ui()
        except Exception as e:
            print(f"Error Init DB: {e}")
            safe_show_snack(f"Database Error: {e}", "red")

    init_web()

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)# mainweb.py

# ///////////////////////////////////////////////////////////////
# [SECTION 1] IMPORTS & CONFIG
# ///////////////////////////////////////////////////////////////
import flet as ft
import threading
import time
import os
import sys
from datetime import datetime

# Local Imports
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

# ///////////////////////////////////////////////////////////////
# [SECTION 3] MAIN ENTRY POINT
# ///////////////////////////////////////////////////////////////
def main(page: ft.Page):
    global main_container
    
    # --- Web Page Setup ---
    page.title = "Modern Money Tracker (Web)"
    page.bgcolor = COLOR_BG
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK
    
    config = load_config()
    
    page.theme = ft.Theme(
        font_family=config.get("font_family", "Kanit"),
        scrollbar_theme=ft.ScrollbarTheme(thickness=5, thumb_visibility=True, track_visibility=True)
    )
    
    main_container = ft.Container(
        expand=True,
        opacity=1, 
        padding=15
    )
    page.add(main_container)

    # --- Helpers ---
    def get_font_specs():
        s = config.get("font_size", 14)
        w = config.get("font_weight", 600)
        return s - 14, f"w{w}"

    current_font_delta, current_font_weight_str = get_font_specs()
    
    # --- State Variables ---
    current_db = None
    current_filter_date = None
    current_lang = config.get("lang", "th")
    cloud_mgr = CloudManager()

    def T(key): return TRANSLATIONS[current_lang].get(key, key)
    def safe_show_snack(msg, color="green"):
        try: page.open(ft.SnackBar(content=ft.Text(msg), bgcolor=color))
        except: pass
    
    # ///////////////////////////////////////////////////////////////
    # [SECTION 4] UI INITIALIZATION
    # ///////////////////////////////////////////////////////////////
    btn_settings = ft.IconButton("settings", icon_size=20)
    txt_app_title = ft.Text(T("app_title"), color=COLOR_PRIMARY)
    
    summary_font_delta = current_font_delta - 4 

    card_inc = SummaryCard("income", "+0.00", COLOR_INCOME, "arrow_upward", summary_font_delta, current_font_weight_str)
    card_exp = SummaryCard("expense", "-0.00", COLOR_EXPENSE, "arrow_downward", summary_font_delta, current_font_weight_str)
    card_bal = SummaryCard("balance", "0.00", COLOR_PRIMARY, "account_balance_wallet", summary_font_delta, current_font_weight_str)
    card_net = SummaryCard("Net Worth", "0.00", "cyan", "monetization_on", summary_font_delta, current_font_weight_str)

    txt_summary_header = ft.Text(T("overview"), color="grey")
    summary_row = ft.Row([card_inc, card_exp, card_bal, card_net], spacing=2, expand=True)

    txt_budget_title = ft.Text(T("budget"), color="grey", size=12)
    txt_budget_value = ft.Text("- / -", color="white", size=12)
    pb_budget = ft.ProgressBar(value=0, color=COLOR_PRIMARY, bgcolor=COLOR_SURFACE, height=6, border_radius=3)
    
    summary_section = ft.Container(
        content=ft.Column([
            txt_summary_header, 
            summary_row,
            ft.Container(height=5),
            ft.Divider(height=1, color="white10"),
            ft.Row([txt_budget_title, txt_budget_value], alignment="spaceBetween"),
            pb_budget
        ], spacing=8),
        padding=15, 
        border=ft.border.all(1, "#333333"), 
        border_radius=15, 
        margin=ft.margin.only(bottom=10)
    )
    
    txt_heading_recent = ft.Text("Recent")
    txt_heading_rec = ft.Text("Recurring")
    
    btn_reset_filter = ft.OutlinedButton("Reset Filter", icon="refresh")
    
    # ปุ่มกดบันทึก
    btn_expense = ft.ElevatedButton(
        text=T("expense"), 
        icon="remove", 
        bgcolor=COLOR_BTN_EXPENSE, 
        color="white",
        elevation=4,
        height=50,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15)),
        expand=True 
    )
    
    btn_income = ft.ElevatedButton(
        text=T("income"), 
        icon="add", 
        bgcolor=COLOR_BTN_INCOME, 
        color="white",
        elevation=4,
        height=50,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=15)),
        expand=True 
    )
    
    # [FIX 1] ใช้ Column ธรรมดา + Scrollbar (เสถียรสุดบนเว็บ)
    trans_list_view = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=5)
    
    recurring_list_view = ft.Column(spacing=5, scroll="hidden")
    cards_row = ft.ResponsiveRow(spacing=10, run_spacing=10, visible=False)
    
    def on_date_change(d): 
        nonlocal current_filter_date
        current_filter_date = d
        refresh_ui()

    cal = CalendarWidget(page, on_date_change, current_font_delta, current_font_weight_str)
    btn_reset_filter.on_click = lambda e: [cal.reset()]

    # ///////////////////////////////////////////////////////////////
    # [SECTION 5] LOGIC
    # ///////////////////////////////////////////////////////////////
    def update_all_labels():
        nonlocal current_lang, current_font_delta, current_font_weight_str
        current_lang = config.get("lang", "th")
        current_font_delta, current_font_weight_str = get_font_specs()
        
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
        
        btn_reset_filter.text = T("reset_filter"); 
        card_inc.txt_title.value = T("income"); 
        card_exp.txt_title.value = T("expense"); 
        card_bal.txt_title.value = T("balance"); 
        card_net.txt_title.value = "Net Worth" if current_lang == "en" else "ความมั่งคั่งสุทธิ"

        btn_expense.text = T("expense")
        btn_income.text = T("income")

    def process_auto_pay():
        if not current_db: return
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
        
        current_month_str = f"{cal.year}-{cal.month:02d}"
        month_name = datetime(cal.year, cal.month, 1).strftime("%B %Y")
        txt_summary_header.value = f"{T('overview')} ({month_name})"
        
        current_db.check_and_rollover(cal.year, cal.month)

        inc, exp, bal = current_db.get_summary(current_month_str)
        
        cards_db = current_db.get_cards()
        total_debt = 0.0
        if cards_db:
             for c in cards_db:
                 total_debt += current_db.get_card_usage(c[0])

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
        
        cards_row.controls.clear()
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
        
        rows = current_db.get_transactions(current_filter_date, month_filter=current_month_str)
        
        d_font_delta, d_font_weight = get_font_specs()

        def call_delete(tid):
            dialogs.confirm_delete(page, current_db, config, refresh_ui, tid)
        def call_edit(data):
            dialogs.open_edit_dialog(page, current_db, config, refresh_ui, data)

        trans_list_view.controls.clear(); current_date_grp = None
        for r in rows:
            dt_obj = parse_db_date(r[5]); date_str = dt_obj.strftime("%d %B %Y")
            if date_str != current_date_grp: current_date_grp = date_str; trans_list_view.controls.append(ft.Container(content=ft.Text(date_str, size=12+d_font_delta, weight="bold", color="grey"), padding=ft.padding.only(top=10, bottom=5)))
            
            # [FIX 2] ลบ Animation ที่ทำให้ Web หน่วง/ค้างออก (is_new=False เสมอ)
            # การใส่ animation scroll บนเว็บ Flet มักทำให้หน้าจอกระตุกหรือขาว
            card = TransactionCard(r, call_delete, call_edit, d_font_delta, d_font_weight, is_new=False, minimal=False)
            trans_list_view.controls.append(card)
        
        update_recurring_list()
        
        try:
            page.update()
        except: pass

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
    # [SECTION 6] DIALOG & ACTIONS
    # ///////////////////////////////////////////////////////////////
    def open_add_rec(e):
        dialogs.open_add_rec_dialog(page, current_db, config, refresh_ui)
        
    def open_top10_dialog(e):
        d_font_specs = get_font_specs()
        dialogs.open_top10_dialog(page, current_db, config, cal.year, cal.month, d_font_specs)

    def open_settings(e):
        def on_db_changed(new_path):
            init_web(new_path)
        open_settings_dialog(page, current_db, config, refresh_ui, on_db_changed, cloud_mgr)

    btn_settings.on_click = open_settings

    def open_manual_add_dialog(t_type):
        cats = current_db.get_categories(t_type)
        cards = current_db.get_cards()
        
        f_item = ft.TextField(label=T("item"), autofocus=True)
        f_amt = ft.TextField(
            label=T("amount"), 
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string="")
        )
        
        default_cat = cats[0][1] if cats else "Other"
        f_cat = ft.Dropdown(
            label=T("category"), 
            options=[ft.dropdown.Option(c[1]) for c in cats], 
            value=default_cat
        )
        
        pay_opts = [ft.dropdown.Option("cash", "เงินสด / Cash")]
        if t_type != "income":
            for c in cards:
                pay_opts.append(ft.dropdown.Option(str(c[0]), f"บัตร: {c[1]}"))
        
        f_payment = ft.Dropdown(
            label=T("payment_method"), 
            options=pay_opts, 
            value="cash",
            visible=(t_type != "income")
        )

        target_date = datetime.now()
        if current_filter_date:
            try:
                sel_dt = datetime.strptime(current_filter_date, "%Y-%m-%d")
                target_date = datetime.combine(sel_dt.date(), datetime.now().time())
            except: pass
        
        display_date = target_date.strftime("%d/%m/%Y")

        def save(e):
            try:
                if not f_amt.value: 
                    safe_show_snack("Please enter amount", "red")
                    return
                
                amt = float(f_amt.value)
                item = f_item.value if f_item.value else T(t_type)
                cat = f_cat.value
                pid = int(f_payment.value) if (f_payment.value and f_payment.value != "cash") else None
                
                print(f"Saving: {t_type}, {item}, {amt}") 
                new_id = current_db.add_transaction(t_type, item, amt, cat, date=target_date, payment_id=pid)
                
                page.close(dlg)
                refresh_ui(new_id=new_id)
                safe_show_snack(f"Saved {item} ({format_currency(amt)}) to {display_date}")
                
            except Exception as ex:
                print(f"Error saving: {ex}") 
                safe_show_snack(f"Error: {ex}", "red")

        title_text = T("income") if t_type == "income" else T("expense")
        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon("edit_note"), ft.Text(f"{T('add_rec')} - {title_text}")]),
            content=ft.Column([
                ft.Text(f"Date: {display_date}", size=12, color="grey"),
                f_item, f_amt, f_cat, f_payment
            ], tight=True, width=400),
            actions=[
                ft.TextButton(T("save"), on_click=save),
                ft.TextButton(T("cancel"), on_click=lambda e: page.close(dlg))
            ]
        )
        page.open(dlg)

    btn_expense.on_click = lambda e: open_manual_add_dialog("expense")
    btn_income.on_click = lambda e: open_manual_add_dialog("income")

    # ///////////////////////////////////////////////////////////////
    # [SECTION 7] BUILD & RUN
    # ///////////////////////////////////////////////////////////////
    def build_full_view():
        sidebar = ft.Container(
            padding=ft.padding.only(left=20, right=20, top=10, bottom=20), 
            bgcolor=COLOR_SURFACE, 
            border_radius=15, 
            content=ft.Column([
                ft.Row([txt_app_title, ft.Container(expand=True), btn_settings], alignment="spaceBetween"),
                cal,
                ft.Container(content=btn_reset_filter, alignment=ft.alignment.center),
                ft.Divider(),
                ft.Row([txt_heading_rec, ft.IconButton("add_circle", on_click=open_add_rec)], alignment="spaceBetween"),
                ft.Container(content=recurring_list_view, expand=True),
                ft.Row([btn_expense, btn_income], alignment="center", spacing=10)
            ])
        )

        # [FIX 3] กำหนด expand=True ให้ Container แม่ และ Column แม่ เพื่อให้ลูกๆ ยืดได้เต็มที่
        main_pane = ft.Container(expand=True, padding=10, content=ft.Column([
            summary_section, 
            cards_row, 
            ft.Divider(color="transparent"),
            ft.Row([txt_heading_recent, ft.OutlinedButton("Chart", icon="bar_chart", on_click=open_top10_dialog)], alignment="spaceBetween"),
            # Container ที่หุ้ม trans_list_view ต้อง expand ด้วย
            ft.Container(content=trans_list_view, expand=True) 
        ], expand=True)) # <--- ใส่ expand=True ที่ Column นี้ด้วย สำคัญมาก
        
        return ft.ResponsiveRow([
            ft.Column([main_pane], col={"md": 9, "sm": 12}),
            ft.Column([sidebar], col={"md": 3, "sm": 12})
        ])

    def init_web(specific_path=None):
        nonlocal current_db
        
        target_path = specific_path
        if not target_path:
            current_conf = load_config()
            target_path = current_conf.get("db_path", "modern_money.db")

        if not os.path.isabs(target_path):
             base_dir = os.path.dirname(os.path.abspath(__file__))
             target_path = os.path.join(base_dir, target_path)

        print(f"Connecting to DB at: {target_path}")

        try:
            current_db = DatabaseManager(target_path)
            current_db.connect()
            cal.set_db(current_db)
            
            config["db_path"] = target_path
            
            main_container.content = build_full_view()
            refresh_ui()
        except Exception as e:
            print(f"Error Init DB: {e}")
            safe_show_snack(f"Database Error: {e}", "red")

    init_web()

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)