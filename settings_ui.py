# settings_ui.py

# ///////////////////////////////////////////////////////////////
# [SECTION: IMPORTS]
# ///////////////////////////////////////////////////////////////
import flet as ft
import threading
from const import *
from utils import HAS_GSPREAD, save_config
from ui_components import CreditCardWidget

# ///////////////////////////////////////////////////////////////
# [SECTION: MAIN ENTRY]
# ///////////////////////////////////////////////////////////////
def open_settings_dialog(page, current_db, config, refresh_ui_callback, init_app_callback, cloud_mgr):
    
    # [SECTION: HELPERS]
    def T(key): return TRANSLATIONS[config.get("lang", "th")].get(key, key)
    def safe_show_snack(msg, color="green"):
        try: page.open(ft.SnackBar(content=ft.Text(msg), bgcolor=color))
        except: pass

    # ///////////////////////////////////////////////////////////////
    # [SECTION: GENERAL SETTINGS UI]
    # ///////////////////////////////////////////////////////////////
    
    # --- Budget & Auto Save ---
    f_budget = ft.TextField(
        label=T("budget"), 
        value=current_db.get_setting("budget", "10000"),
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string="")
    )
    
    val_auto = current_db.get_setting("auto_save", "0") == "1"
    try: val_delay = float(current_db.get_setting("auto_save_delay", "0"))
    except: val_delay = 0
    sw_auto_save = ft.Switch(label=T("enable_auto_save"), value=val_auto)
    sl_delay = ft.Slider(min=0, max=5, divisions=5, label="{value}s", value=val_delay)
    txt_delay_label = ft.Text(f"{T('auto_save_delay')}: {int(val_delay)}s")
    sl_delay.on_change = lambda e: [setattr(txt_delay_label, 'value', f"{T('auto_save_delay')}: {int(e.control.value)}s"), page.update()]

    # --- Appearance (Font/Mode) ---
    curr_mode = config.get("startup_mode", "simple")
    
    mode_seg = ft.SegmentedButton(
        selected={curr_mode},
        segments=[
            ft.Segment(value="simple", label=ft.Text(T("simple_mode"))),
            ft.Segment(value="full", label=ft.Text(T("full_mode")))
        ]
    )

    curr_font = config.get("font_family", "Kanit")
    curr_size = config.get("font_size", 14)
    curr_weight_int = config.get("font_weight", 600)
    
    dd_font = ft.Dropdown(label=T("font_family"), options=[
        ft.dropdown.Option("Kanit"), ft.dropdown.Option("Prompt"), 
        ft.dropdown.Option("Sarabun"), ft.dropdown.Option("Mitr"), 
        ft.dropdown.Option("Roboto")
    ], value=curr_font)
    
    sl_weight = ft.Slider(min=100, max=900, divisions=8, value=curr_weight_int, label="{value}")
    txt_weight_label = ft.Text(f"{T('font_weight')}: {int(curr_weight_int)}")
    sl_weight.on_change = lambda e: [setattr(txt_weight_label, 'value', f"{T('font_weight')}: {int(e.control.value)}"), page.update()]
    
    sl_font_size = ft.Slider(min=12, max=24, divisions=12, label="{value}px", value=curr_size)
    txt_font_size_label = ft.Text(f"{T('font_size')}: {int(curr_size)}px")
    sl_font_size.on_change = lambda e: [setattr(txt_font_size_label, 'value', f"{T('font_size')}: {int(e.control.value)}px"), page.update()]

    def create_group(title, controls): 
        return ft.Container(content=ft.Column([ft.Text(title, weight="w600", color="grey", size=12), ft.Column(controls, spacing=10)], spacing=5), padding=10, border=ft.border.all(1, "#333333"), border_radius=10, margin=ft.margin.only(bottom=5))

    # --- Cloud & DB Inputs ---
    f_cloud_key = ft.TextField(label=T("json_key"), value=current_db.get_setting("cloud_key"), expand=True, text_size=12)
    f_sheet_name = ft.TextField(label=T("sheet_name"), value=current_db.get_setting("cloud_sheet"), expand=True)
    txt_cloud_status = ft.Text(f"{T('status')}: -", color="grey", italic=True)
    
    json_picker = ft.FilePicker(on_result=lambda e: [setattr(f_cloud_key, 'value', e.files[0].path), page.update()] if e.files else None)
    page.overlay.append(json_picker)
    
    db_path_val = config.get("db_path", "")
    txt_db_path = ft.Text(db_path_val, size=12, color="grey", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    db_picker = ft.FilePicker(on_result=lambda e: [setattr(txt_db_path, 'value', e.files[0].path), page.update()] if e.files else None)
    page.overlay.append(db_picker)

    def save_cloud(e):
        config["cloud_key"] = f_cloud_key.value; config["cloud_sheet"] = f_sheet_name.value; save_config(config)
        current_db.set_setting("cloud_key", f_cloud_key.value); current_db.set_setting("cloud_sheet", f_sheet_name.value)
        safe_show_snack("Cloud Config Saved")

    # ///////////////////////////////////////////////////////////////
    # [SECTION: CARDS TAB LOGIC]
    # ///////////////////////////////////////////////////////////////
    card_list_col = ft.GridView(runs_count=2, max_extent=350, child_aspect_ratio=1.5, spacing=10, run_spacing=10, padding=10, expand=True)

    def render_cards(run_update=True):
        card_list_col.controls.clear(); cards = current_db.get_cards()
        if not cards: 
            card_list_col.controls.append(ft.Text("No credit cards added", color="grey", italic=True))
        else:
            for c in cards:
                usage = current_db.get_card_usage(c[0])
                card_list_col.controls.append(CreditCardWidget(c, open_card_edit, confirm_delete_card, usage))
        if run_update: 
            try: card_list_col.update()
            except: pass

    def open_card_edit(data=None):
        page.close(dlg); is_edit = data is not None; c_id = data[0] if is_edit else None
        f_name = ft.TextField(label="Card Name", value=data[1] if is_edit else "")
        
        f_limit = ft.TextField(
            label="Limit Amount", 
            value=str(data[2]) if is_edit else "", 
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*\.?\d*$", replacement_string="")
        )
        
        f_closing = ft.Dropdown(label="Closing Day", options=[ft.dropdown.Option(str(i)) for i in range(1, 32)], value=str(data[3]) if is_edit else "20")
        colors = {"Green": "#2E7D32", "Blue": "#1565C0", "Red": "#C62828", "Purple": "#6A1B9A", "Orange": "#EF6C00", "Teal": "#00695C", "Grey": "#424242"}; f_color = ft.Dropdown(label="Color", options=[ft.dropdown.Option(k) for k in colors.keys()], value="Green")
        if is_edit and data[4]:
            for k, v in colors.items():
                if v == data[4]: f_color.value = k; break
        
        def save_card(e):
            try:
                name = f_name.value; limit = float(f_limit.value); day = int(f_closing.value); col_hex = colors.get(f_color.value, "#424242")
                if is_edit: current_db.update_card(c_id, name, limit, day, col_hex)
                else: current_db.add_card(name, limit, day, col_hex)
                page.close(dlg_card); render_cards(run_update=False); page.open(dlg); page.update()
            except Exception as ex: safe_show_snack(f"Error: {ex}", "red")
        
        def cancel_card(e): page.close(dlg_card); page.open(dlg)
        dlg_card = ft.AlertDialog(title=ft.Text("Edit Card" if is_edit else "Add Card"), content=ft.Column([f_name, f_limit, f_closing, f_color], tight=True), actions=[ft.TextButton(T("save"), on_click=save_card), ft.TextButton(T("cancel"), on_click=cancel_card)]); page.open(dlg_card)

    def confirm_delete_card(cid):
        page.close(dlg)
        def yes(e): 
            current_db.delete_card(cid)
            page.close(dlg_conf); render_cards(run_update=False); page.open(dlg); page.update(); refresh_ui_callback()
        def no(e): page.close(dlg_conf); page.open(dlg)
        dlg_conf = ft.AlertDialog(title=ft.Text(T("confirm_delete")), content=ft.Text("Delete this card?"), actions=[ft.TextButton(T("delete"), on_click=yes), ft.TextButton(T("cancel"), on_click=no)]); page.open(dlg_conf)

    # ///////////////////////////////////////////////////////////////
    # [SECTION: CATEGORIES TAB LOGIC]
    # ///////////////////////////////////////////////////////////////
    cat_content_container = ft.Container(); cat_state = {"type": "expense"}
    def render_cat_grid():
        cat_list = current_db.get_categories(cat_state["type"])
        def on_type_change(e):
            if e.control.selected: cat_state["type"] = list(e.control.selected)[0]; render_cat_grid()
        type_seg = ft.SegmentedButton(selected={cat_state["type"]}, segments=[ft.Segment("expense", label=ft.Text(T("expense"))), ft.Segment("income", label=ft.Text(T("income")))], on_change=on_type_change)
        btn_add = ft.ElevatedButton(T("add_category"), bgcolor=COLOR_PRIMARY, color="white", width=400, on_click=lambda _: render_cat_edit())
        grid_controls = []
        for cid, name, ctype, keywords in cat_list: grid_controls.append(ft.ElevatedButton(text=name, bgcolor=COLOR_BUTTON_GREY, color="white", width=120, height=50, on_click=lambda e, data=(cid, name, keywords): render_cat_edit(data)))
        cat_content_container.content = ft.Column([ft.Container(content=type_seg, alignment=ft.alignment.center), btn_add, ft.Row(grid_controls, wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)
        if cat_content_container.page: cat_content_container.update()

    def render_cat_edit(data=None):
        is_edit = data is not None; cid = data[0] if is_edit else None
        txt_title = ft.Text(T("edit_category") if is_edit else T("add_category"), size=20, weight="bold")
        f_name = ft.TextField(label=T("cat_name"), value=data[1] if is_edit else ""); f_kw = ft.TextField(label=T("keywords"), value=data[2] if is_edit else "", multiline=True, min_lines=3, max_lines=6)
        def save_cat(e):
            if not f_name.value: return
            if is_edit: current_db.update_category(cid, f_name.value, f_kw.value)
            else: current_db.add_category(f_name.value, cat_state["type"], f_kw.value)
            render_cat_grid()
        def delete_cat_click(e):
            def return_to_grid(e=None): page.close(dlg_conf); render_cat_grid(); page.open(dlg); page.update()
            def confirm_yes(e):
                success = current_db.delete_category(cid)
                if not success: safe_show_snack("Cannot delete default category", "red")
                else: return_to_grid(e)
            page.close(dlg); dlg_conf = ft.AlertDialog(title=ft.Text(T("confirm_delete")), content=ft.Text(f"{T('msg_delete_cat')} ({f_name.value})"), actions=[ft.TextButton(T("delete"), on_click=confirm_yes), ft.TextButton(T("cancel"), on_click=return_to_grid)], on_dismiss=return_to_grid); page.open(dlg_conf)
        btn_save = ft.ElevatedButton(T("save"), bgcolor=COLOR_INCOME, color="white", on_click=save_cat, expand=True)
        controls_list = [ft.ElevatedButton(T("back"), on_click=lambda _: render_cat_grid(), icon="arrow_back"), txt_title, f_name, f_kw]
        if is_edit: btn_del = ft.ElevatedButton(T("delete"), bgcolor=COLOR_EXPENSE, color="white", on_click=delete_cat_click, expand=True); controls_list.append(ft.Row([btn_save, btn_del], spacing=10))
        else: controls_list.append(ft.Row([btn_save], alignment=ft.MainAxisAlignment.CENTER))
        cat_content_container.content = ft.Column(controls_list, spacing=15)
        if cat_content_container.page: cat_content_container.update()

    # [SECTION: CLOUD SYNC LOGIC]
    def confirm_sync(mode):
        def on_yes(e): page.close(dlg_conf_sync); page.open(dlg); run_cloud_task(mode)
        def on_no(e): page.close(dlg_conf_sync); page.open(dlg)
        msg_key = "confirm_push" if mode == "push" else "confirm_pull"
        dlg_conf_sync = ft.AlertDialog(title=ft.Text(T("confirm_action")), content=ft.Text(T(msg_key)), actions=[ft.TextButton(T("yes"), on_click=on_yes), ft.TextButton(T("cancel"), on_click=on_no)])
        page.close(dlg); page.open(dlg_conf_sync)

    def run_cloud_task(task_type):
        if not HAS_GSPREAD: 
            txt_cloud_status.value = T("msg_lib_missing")
            txt_cloud_status.color = "red"
            page.update()
            return
            
        txt_cloud_status.value = T("msg_processing")
        txt_cloud_status.color = "blue"
        page.update()
        
        def thread_target():
            try:
                # 1. Connect Google Sheet
                wb = cloud_mgr.connect(f_cloud_key.value, f_sheet_name.value)
                
                # 2. Prepare Worksheets (Create if not exists)
                def get_or_create_sheet(title, rows="100", cols="10"):
                    try: return wb.worksheet(title)
                    except: return wb.add_worksheet(title=title, rows=rows, cols=cols)

                ws_trans = wb.sheet1 # Default sheet (Transactions)
                ws_cards = get_or_create_sheet("Cards")
                ws_cats = get_or_create_sheet("Categories")
                ws_rec = get_or_create_sheet("Recurring")
                
                # ---------------------------------------------------------
                # CASE 1: CHECK CONNECTION
                # ---------------------------------------------------------
                if task_type == "check": 
                    pass # Just connect is enough

                # ---------------------------------------------------------
                # CASE 2: PUSH (Local -> Cloud)
                # ---------------------------------------------------------
                elif task_type == "push":
                    # A. Transactions
                    trans = current_db.get_transactions()
                    data_t = [["ID", "Type", "Item", "Amount", "Category", "Date", "PaymentID"]]
                    for t in trans: data_t.append([str(x) for x in t])
                    ws_trans.clear()
                    ws_trans.update(range_name='A1', values=data_t)

                    # B. Credit Cards
                    cards = current_db.get_cards()
                    data_c = [["ID", "Name", "Limit", "ClosingDay", "Color"]]
                    for c in cards: data_c.append([str(x) for x in c])
                    ws_cards.clear()
                    ws_cards.update(range_name='A1', values=data_c)
                    
                    # C. Categories
                    cats = current_db.get_categories() # id, name, type, kw
                    data_cat = [["ID", "Name", "Type", "Keywords"]]
                    for c in cats: data_cat.append([str(x) for x in c])
                    ws_cats.clear()
                    ws_cats.update(range_name='A1', values=data_cat)
                    
                    # D. Recurring
                    recs = current_db.get_recurring() # id, day, item, amt, cat, pid, auto
                    data_rec = [["ID", "Day", "Item", "Amount", "Category", "PaymentID", "AutoPay"]]
                    for r in recs: data_rec.append([str(x) for x in r])
                    ws_rec.clear()
                    ws_rec.update(range_name='A1', values=data_rec)

                # ---------------------------------------------------------
                # CASE 3: PULL (Cloud -> Local)
                # ---------------------------------------------------------
                elif task_type == "pull":
                    # A. Transactions
                    all_t = ws_trans.get_all_values()
                    current_db.clear_all_transactions()
                    if len(all_t) > 1:
                        for row in all_t[1:]:
                            try:
                                if len(row) < 6: continue
                                t_type = row[1]; item = row[2]; 
                                amt = float(str(row[3]).replace(",", ""))
                                cat = row[4]; dt = row[5]
                                pid = int(row[6]) if len(row) > 6 and row[6] not in ["None", ""] else None
                                current_db.add_transaction(t_type, item, amt, cat, dt, pid)
                            except: pass
                    
                    # B. Credit Cards
                    all_c = ws_cards.get_all_values()
                    current_db.clear_all_cards()
                    if len(all_c) > 1:
                        for row in all_c[1:]:
                            try:
                                cid = int(row[0]); name = row[1]; limit = float(row[2])
                                close_d = int(row[3]); color = row[4]
                                current_db.add_card(name, limit, close_d, color, force_id=cid)
                            except: pass

                    # C. Categories
                    all_cat = ws_cats.get_all_values()
                    if len(all_cat) > 1:
                        current_db.clear_all_categories()
                        for row in all_cat[1:]:
                            try:
                                # Row format: ID, Name, Type, Keywords
                                cid = int(row[0])
                                name = row[1]
                                c_type = row[2]
                                kw = row[3] if len(row) > 3 else ""
                                current_db.add_category(name, c_type, kw, force_id=cid)
                            except: pass

                    # D. Recurring
                    all_rec = ws_rec.get_all_values()
                    if len(all_rec) > 1:
                        current_db.clear_all_recurring()
                        for row in all_rec[1:]:
                            try:
                                # Row format: ID, Day, Item, Amount, Category, PaymentID, AutoPay
                                rid = int(row[0])
                                day = int(row[1])
                                item = row[2]
                                amt = float(str(row[3]).replace(",", ""))
                                cat = row[4]
                                pid = int(row[5]) if len(row) > 5 and row[5] not in ["None", ""] else None
                                auto = int(row[6]) if len(row) > 6 and row[6] not in ["None", ""] else 0
                                current_db.add_recurring(day, item, amt, cat, payment_id=pid, auto_pay=auto, force_id=rid)
                            except: pass
                    
                    refresh_ui_callback()

                # ---------------------------------------------------------
                # CASE 4: COMPARE
                # ---------------------------------------------------------
                elif task_type == "compare":
                    def get_count(ws): return len(ws.get_all_values()) - 1
                    
                    c_trans = get_count(ws_trans)
                    c_cards = get_count(ws_cards)
                    c_cats = get_count(ws_cats)
                    c_recs = get_count(ws_rec)
                    
                    l_trans = len(current_db.get_transactions())
                    l_cards = len(current_db.get_cards())
                    l_cats = len(current_db.get_categories())
                    l_recs = len(current_db.get_recurring())
                    
                    msg = (f"Transactions: Local={l_trans} / Cloud={c_trans}\n"
                           f"Cards: Local={l_cards} / Cloud={c_cards}\n"
                           f"Categories: Local={l_cats} / Cloud={c_cats}\n"
                           f"Recurring: Local={l_recs} / Cloud={c_recs}")
                           
                    txt_cloud_status.value = "Done."; txt_cloud_status.color = "green"
                    
                    def close_res(e): page.close(dlg_res); page.open(dlg)
                    dlg_res = ft.AlertDialog(title=ft.Text("Compare Result"), content=ft.Text(msg), actions=[ft.TextButton("OK", on_click=close_res)])
                    page.close(dlg); page.open(dlg_res); page.update()
                    return

                txt_cloud_status.value = f"{T('msg_success')} ({task_type.upper()})"
                txt_cloud_status.color = "green"
                
            except Exception as e:
                def show_err():
                    def close_err(e): page.close(dlg_err); page.open(dlg); page.update()
                    page.close(dlg)
                    # [MODIFIED] Removed print(e)
                    dlg_err = ft.AlertDialog(title=ft.Text("Error"), content=ft.Text(str(e)), actions=[ft.TextButton("OK", on_click=close_err)], on_dismiss=close_err)
                    page.open(dlg_err); page.update()
                
                show_err()
                txt_cloud_status.value = f"{T('msg_error')}"
                txt_cloud_status.color = "red"
            
            page.update()

        threading.Thread(target=thread_target, daemon=True).start()

    btn_check = ft.ElevatedButton(T("btn_check"), bgcolor="#1976D2", color="white", width=400, on_click=lambda _: run_cloud_task("check"))
    btn_compare = ft.ElevatedButton(T("btn_compare"), bgcolor=COLOR_WARNING, color="white", width=400, on_click=lambda _: run_cloud_task("compare"))
    btn_pull = ft.ElevatedButton(T("btn_pull"), bgcolor=COLOR_EXPENSE, color="white", width=400, on_click=lambda _: confirm_sync("pull"))
    btn_push = ft.ElevatedButton(T("btn_push"), bgcolor=COLOR_PRIMARY, color="white", width=400, on_click=lambda _: confirm_sync("push"))

    # [SECTION: LANG & TAB ASSEMBLY]
    def on_lang_change(e):
        if e.control.selected:
            lang = list(e.control.selected)[0]; config["lang"] = lang; save_config(config)
            # Update labels dynamically
            f_budget.label = T("budget"); sw_auto_save.label = T("enable_auto_save"); txt_delay_label.value = f"{T('auto_save_delay')}: {int(sl_delay.value)}s"
            dd_font.label = T("font_family"); txt_font_size_label.value = f"{T('font_size')}: {int(sl_font_size.value)}px"; txt_weight_label.value = f"{T('font_weight')}: {int(sl_weight.value)}"
            
            # Update Tabs
            tabs.tabs[0].text = T("appearance")
            tabs.tabs[1].text = T("general")
            tabs.tabs[2].text = T("categories")
            tabs.tabs[3].text = T("credit_cards")
            tabs.tabs[4].text = T("cloud")
            
            # Update Segments
            mode_seg.segments[0].label = ft.Text(T("simple_mode"))
            mode_seg.segments[1].label = ft.Text(T("full_mode"))
            
            # Update Inputs
            f_cloud_key.label = T("json_key")
            f_sheet_name.label = T("sheet_name")
            
            dlg.update(); refresh_ui_callback()

    lang_seg = ft.SegmentedButton(selected={config.get("lang", "th")}, segments=[ft.Segment(value="en", label=ft.Text("English")), ft.Segment(value="th", label=ft.Text("ไทย"))], on_change=on_lang_change)

    tab_appear_content = ft.Column([create_group(T("language"), [lang_seg]), create_group(T("font_family"), [dd_font]), create_group(T("font_weight"), [txt_weight_label, sl_weight]), create_group(T("font_size"), [txt_font_size_label, sl_font_size])], scroll=ft.ScrollMode.AUTO)
    
    # [MODIFIED] Added Startup Mode Segment
    tab_gen_content = ft.Column([create_group(T("startup_mode"), [mode_seg]), create_group(T("db_file"), [txt_db_path, ft.ElevatedButton(T("select_file"), on_click=lambda _: db_picker.pick_files(allowed_extensions=["db"]), height=30)]), create_group(T("data_section"), [f_budget]), create_group(T("voice_opts"), [sw_auto_save, ft.Column([txt_delay_label, sl_delay], spacing=0)])], scroll=ft.ScrollMode.AUTO)
    
    tab_cards_content = ft.Column([ft.Row([ft.Text(T("credit_cards"), weight="bold", size=16), ft.ElevatedButton("+ Add Card", on_click=lambda _: open_card_edit())], alignment="spaceBetween"), ft.Container(content=card_list_col, height=400)], spacing=10)
    tab_cloud_content = ft.Column([ft.Text(T("cloud_config"), weight="bold", size=16), ft.Row([f_cloud_key, ft.IconButton(icon="folder_open", on_click=lambda _: json_picker.pick_files(allowed_extensions=["json"]))]), ft.Row([f_sheet_name, ft.ElevatedButton(T("save"), on_click=save_cloud)]), ft.Divider(), ft.Text(T("sync_actions"), weight="bold"), txt_cloud_status, ft.Column([btn_check, btn_compare, btn_pull, btn_push], horizontal_alignment="center", spacing=10)], scroll=ft.ScrollMode.AUTO, spacing=15, horizontal_alignment="center")

    tabs = ft.Tabs(selected_index=0, tabs=[ft.Tab(text=T("appearance"), content=ft.Container(content=tab_appear_content, padding=10)), ft.Tab(text=T("general"), content=ft.Container(content=tab_gen_content, padding=10)), ft.Tab(text=T("categories"), content=ft.Container(content=cat_content_container, padding=10)), ft.Tab(text=T("credit_cards"), content=ft.Container(content=tab_cards_content, padding=10)), ft.Tab(text=T("cloud"), content=ft.Container(content=tab_cloud_content, padding=10))], height=500)

    # [SECTION: SAVE ALL]
    def save_all(e):
        current_db.set_setting("budget", f_budget.value)
        current_db.set_setting("auto_save", "1" if sw_auto_save.value else "0")
        current_db.set_setting("auto_save_delay", str(int(sl_delay.value)))
        
        config["font_family"] = dd_font.value
        config["font_size"] = int(sl_font_size.value)
        config["font_weight"] = int(sl_weight.value)
        
        # [MODIFIED] Read from Segmented Button
        if mode_seg.selected:
            config["startup_mode"] = list(mode_seg.selected)[0]
            
        save_config(config)
        page.theme = ft.Theme(font_family=dd_font.value, scrollbar_theme=ft.ScrollbarTheme(thickness=0, thumb_visibility=False, track_visibility=False))
        
        if txt_db_path.value != db_path_val: init_app_callback(txt_db_path.value)
        else:
            page.update()
            refresh_ui_callback()
            
        dlg.open = False; page.update()
    
    dlg = ft.AlertDialog(content=ft.Container(content=tabs, width=600, height=650), actions=[ft.TextButton(T("save"), on_click=save_all)])
    page.open(dlg)
    render_cards(); render_cat_grid()