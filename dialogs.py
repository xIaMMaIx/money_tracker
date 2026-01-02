# dialogs.py
import flet as ft
from datetime import datetime
from const import *
from utils import format_currency, parse_db_date

def T(config, key):
    lang = config.get("lang", "th")
    return TRANSLATIONS[lang].get(key, key)

def safe_show_snack(page, msg, color="green"):
    try: page.open(ft.SnackBar(content=ft.Text(msg), bgcolor=color))
    except: pass

def confirm_delete(page, db, config, refresh_cb, tid):
    def yes(e): 
        db.delete_transaction(tid)
        dlg.open = False
        page.update()
        refresh_cb()
    def no(e): 
        dlg.open = False
        page.update()
    dlg = ft.AlertDialog(title=ft.Text(T(config, "confirm_delete")), content=ft.Text(T(config, "msg_delete")), actions=[ft.TextButton(T(config, "delete"), on_click=yes), ft.TextButton(T(config, "cancel"), on_click=no)])
    page.open(dlg)

def confirm_delete_rec(page, db, config, refresh_cb, rid):
    def yes(e): 
        db.delete_recurring(rid)
        dlg.open = False
        page.update()
        refresh_cb()
    def no(e): 
        dlg.open = False
        page.update()
    dlg = ft.AlertDialog(title=ft.Text(T(config, "confirm_delete")), content=ft.Text(T(config, "msg_delete")), actions=[ft.TextButton(T(config, "delete"), on_click=yes), ft.TextButton(T(config, "cancel"), on_click=no)])
    page.open(dlg)

# [UPDATED] เพิ่ม DatePicker ให้แก้ไขวันที่ได้
def open_edit_dialog(page, db, config, refresh_cb, data):
    tid, ttype, item, amt, cat, date_str, current_card_name = data 
    
    # แปลงวันที่เดิม
    current_date_obj = parse_db_date(date_str)
    new_date_ref = {"val": current_date_obj} 
    
    txt_date = ft.Text(f"{current_date_obj.strftime('%d/%m/%Y')}")
    
    def on_date_change(e):
        new_date_ref["val"] = e.control.value
        txt_date.value = e.control.value.strftime("%d/%m/%Y")
        txt_date.update()

    dt_picker = ft.DatePicker(
        first_date=datetime(2000, 1, 1),
        last_date=datetime(2100, 12, 31),
        current_date=current_date_obj,
        on_change=on_date_change
    )
    page.overlay.append(dt_picker)
    
    btn_date = ft.OutlinedButton("Change Date", icon="calendar_today", on_click=lambda _: page.open(dt_picker))

    f_item = ft.TextField(label=T(config, "item"), value=item)
    f_amt = ft.TextField(label=T(config, "amount"), value=str(amt), keyboard_type=ft.KeyboardType.NUMBER, input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string=""))
    cats = db.get_categories(ttype if ttype != 'repayment' else 'expense')
    f_cat = ft.Dropdown(label=T(config, "category"), options=[ft.dropdown.Option(c[1]) for c in cats], value=cat)
    
    cards = db.get_cards()
    pay_opts = [ft.dropdown.Option("cash", "เงินสด / Cash")]
    current_pid_val = "cash"
    if ttype != "income":
        for c in cards:
            pay_opts.append(ft.dropdown.Option(str(c[0]), f"บัตร: {c[1]}"))
            if current_card_name and current_card_name == c[1]: current_pid_val = str(c[0])
    f_payment = ft.Dropdown(label=T(config, "payment_method"), options=pay_opts, value=current_pid_val)
    
    def save(e):
        try: 
            pid = int(f_payment.value) if f_payment.value != "cash" else None
            db.update_transaction(tid, f_item.value, float(f_amt.value), f_cat.value, pid, date=new_date_ref["val"])
            dlg.open = False
            page.update()
            refresh_cb()
        except: pass

    def cancel(e): 
        dlg.open = False
        page.update()
        
    dlg = ft.AlertDialog(title=ft.Text(T(config, "edit")), content=ft.Column([ft.Row([ft.Text("Date:"), txt_date, btn_date], alignment="spaceBetween"), f_item, f_amt, f_cat, f_payment], tight=True), actions=[ft.TextButton(T(config, "save"), on_click=save), ft.TextButton(T(config, "cancel"), on_click=cancel)])
    page.open(dlg)

def open_pay_card_dialog(page, db, config, refresh_cb, card_data, current_filter_date=None):
    cid, name, limit, _, _ = card_data
    current_usage = db.get_card_usage(cid)
    
    target_date = datetime.now()
    display_date_str = "Today"
    if current_filter_date:
        try:
            sel_dt = datetime.strptime(current_filter_date, "%Y-%m-%d")
            target_date = datetime.combine(sel_dt.date(), datetime.now().time())
            display_date_str = sel_dt.strftime("%d/%m/%Y")
        except: pass

    txt_info = ft.Text(f"Current Debt: {format_currency(current_usage)}")
    txt_date_info = ft.Text(f"Payment Date: {display_date_str}", size=12, color="grey")
    f_amt = ft.TextField(label="Payment Amount", value=str(current_usage), keyboard_type=ft.KeyboardType.NUMBER, autofocus=True, input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string=""))
    
    def save(e):
        try: amt = float(f_amt.value)
        except: safe_show_snack(page, "Invalid Amount", "red"); return
        if amt > 0: 
            db.add_transaction("repayment", f"Pay Card: {name}", amt, "Transfer/Debt", target_date, payment_id=cid)
            dlg.open = False
            page.update()
            refresh_cb()
            safe_show_snack(page, f"Paid {amt} to {name} on {display_date_str}")
    
    dlg = ft.AlertDialog(title=ft.Text(f"Pay {name}"), content=ft.Column([txt_info, txt_date_info, f_amt], tight=True), actions=[ft.TextButton("Pay", on_click=save), ft.TextButton("Cancel", on_click=lambda _: [setattr(dlg, 'open', False), page.update()])])
    page.open(dlg)

def open_card_history_dialog(page, db, config, refresh_cb, card_data, year, month):
    cid, name, _, _, _ = card_data
    month_str = f"{year}-{month:02d}"
    rows = db.get_card_transactions(cid, month_str)
    lv = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO, expand=True) 
    total_spent = 0.0
    total_paid = 0.0
    
    header_row = ft.Container(content=ft.Row([ft.Text(T(config, "day"), size=12, color="grey", width=40), ft.Text(T(config, "item"), size=12, color="grey", expand=True), ft.Text(T(config, "amount"), size=12, color="grey", width=80, text_align=ft.TextAlign.RIGHT)], alignment="spaceBetween"), padding=ft.padding.only(left=10, right=10, bottom=5), border=ft.border.only(bottom=ft.BorderSide(1, "#444444")))

    if not rows: lv.controls.append(ft.Container(content=ft.Text(T(config, "no_items"), color="grey", italic=True), alignment=ft.alignment.center, padding=20))
    else:
        for i, r in enumerate(rows):
            r_type, r_item, r_amt, r_date = r[1], r[2], r[3], parse_db_date(r[5]).strftime("%d/%m")
            item_color = COLOR_INCOME if r_type == "repayment" else COLOR_EXPENSE
            if r_type == "repayment": total_paid += r_amt
            else: total_spent += r_amt 
            item_row = ft.Container(content=ft.Row([ft.Text(r_date, size=12, color="white54", width=40), ft.Text(r_item, size=14, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS), ft.Text(format_currency(r_amt), size=14, color=item_color, weight="bold", width=80, text_align=ft.TextAlign.RIGHT)], alignment="spaceBetween"), padding=ft.padding.symmetric(horizontal=10, vertical=10), bgcolor=COLOR_SURFACE, border_radius=5)
            lv.controls.append(item_row)

    txt_paid = ft.Text(f"Paid: {format_currency(total_paid)}", size=14, weight="bold", color=COLOR_INCOME)
    txt_spent = ft.Text(f"Spent: {format_currency(total_spent)}", size=14, weight="bold", color=COLOR_EXPENSE)
    dlg = ft.AlertDialog(title=ft.Row([ft.Icon("credit_card", size=24, color=COLOR_PRIMARY), ft.Text(f"{name} ({month_str})")], spacing=10), content=ft.Container(content=ft.Column([header_row, lv, ft.Divider(height=1, color="grey"), ft.Row([txt_paid, txt_spent], alignment="spaceBetween")], spacing=10, expand=True), width=400, height=400, padding=0), actions=[ft.TextButton(T(config, "close"), on_click=lambda e: [setattr(dlg, 'open', False), page.update()])])
    page.open(dlg)
    
def open_add_rec_dialog(page, db, config, refresh_cb):
    f_item = ft.TextField(label=T(config, "item"))
    f_amt = ft.TextField(label=T(config, "amount"), keyboard_type=ft.KeyboardType.NUMBER, input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string=""))
    f_day = ft.Dropdown(label=T(config, "day"), options=[ft.dropdown.Option(str(i)) for i in range(1,32)], value="1")
    f_cat = ft.Dropdown(label=T(config, "category"), options=[ft.dropdown.Option(c[1]) for c in db.get_categories("expense")], value="อาหาร")
    cards = db.get_cards()
    pay_opts = [ft.dropdown.Option("cash", "เงินสด / Cash")]
    for c in cards: pay_opts.append(ft.dropdown.Option(str(c[0]), f"บัตร: {c[1]}"))
    sw_auto = ft.Switch(label="Auto Pay (ตัดอัตโนมัติเมื่อถึงวัน)", value=False, disabled=True)

    def on_payment_change(e):
        is_card = (f_payment.value != "cash")
        sw_auto.disabled = not is_card
        if not is_card: sw_auto.value = False
        sw_auto.update()
    f_payment = ft.Dropdown(label=T(config, "payment_method"), options=pay_opts, value="cash", on_change=on_payment_change)

    def add(e):
        try:
            pid = int(f_payment.value) if f_payment.value != "cash" else None
            auto_val = 1 if sw_auto.value else 0
            db.add_recurring(int(f_day.value), f_item.value, float(f_amt.value), f_cat.value, payment_id=pid, auto_pay=auto_val)
            dlg.open = False
            page.update()
            refresh_cb()
        except Exception as ex: safe_show_snack(page, f"Error: {ex}", "red")
    dlg = ft.AlertDialog(title=ft.Text(T(config, "add_rec")), content=ft.Column([f_day, f_item, f_amt, f_cat, f_payment, sw_auto], tight=True), actions=[ft.TextButton("Add", on_click=add), ft.TextButton("Cancel", on_click=lambda _: [setattr(dlg, 'open', False), page.update()])])
    page.open(dlg)

# [UPDATED] เพิ่ม selected_date_str เพื่อรับค่าวันที่จากปฏิทิน และ Logic จัดการวันที่
def pay_recurring_action(page, db, refresh_cb, item, amt, cat, day, check_month, payment_id=None, is_auto=False, suppress_refresh=False, selected_date_str=None):
    target_date = None
    try: y_rec, m_rec = map(int, check_month.split('-'))
    except: now_tmp = datetime.now(); y_rec, m_rec = now_tmp.year, now_tmp.month

    if is_auto:
        try: target_date = datetime(y_rec, m_rec, day)
        except ValueError: target_date = datetime(y_rec+1, 1, 1) if m_rec == 12 else datetime(y_rec, m_rec+1, 1)
    else:
        # 1. ถ้ามีวันจากปฏิทิน ใช้เลย
        if selected_date_str:
            try: target_date = datetime.combine(datetime.strptime(selected_date_str, "%Y-%m-%d").date(), datetime.now().time())
            except: pass

        # 2. ถ้าไม่มี และเป็นเดือนปัจจุบัน ใช้ Today
        if target_date is None:
            now = datetime.now()
            if now.year == y_rec and now.month == m_rec: target_date = now
            else: # 3. ถ้าคนละเดือน ใช้วันตามกำหนดการ
                try: target_date = datetime(y_rec, m_rec, day)
                except ValueError: target_date = datetime(y_rec+1, 1, 1) if m_rec == 12 else datetime(y_rec, m_rec+1, 1)

    db.add_transaction("expense", item, amt, cat, target_date, payment_id=payment_id)
    
    if is_auto: safe_show_snack(page, f"⚡ Auto-Paid: {item}", "blue")
    else: safe_show_snack(page, f"Paid: {item} on {target_date.strftime('%d/%m')}", "green")
    if not suppress_refresh: refresh_cb()

def open_top10_dialog(page, db, config, year, month, font_specs):
    month_str = f"{year}-{month:02d}"
    d_font_delta, d_font_weight = font_specs
    def get_list_view(t_type):
        data = db.get_top_transactions(t_type, month_str)
        if not data: return ft.Text("No data", color="grey")
        lv = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO)
        for i, (item, amt) in enumerate(data):
            col = COLOR_INCOME if t_type == "income" else COLOR_EXPENSE
            lv.controls.append(ft.Container(content=ft.Row([ft.Text(f"{i+1}. {item}", size=14+d_font_delta, expand=True), ft.Text(format_currency(amt), color=col, weight=d_font_weight, size=14+d_font_delta)]), padding=10, bgcolor=COLOR_SURFACE, border_radius=5))
        return lv
    tabs = ft.Tabs(selected_index=0, tabs=[ft.Tab(text="Expense", content=ft.Container(content=get_list_view("expense"), padding=10)), ft.Tab(text="Income", content=ft.Container(content=get_list_view("income"), padding=10))])
    dlg = ft.AlertDialog(title=ft.Text(f"{T(config, 'top_chart')} ({month_str})"), content=ft.Container(content=tabs, width=400, height=400), actions=[ft.TextButton("Close", on_click=lambda e: [setattr(dlg, 'open', False), page.update()])])
    page.open(dlg)