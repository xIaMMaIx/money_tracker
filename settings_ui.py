# settings_ui.py

import flet as ft
import threading
import json
from const import *
from utils import HAS_GSPREAD, save_config, GSPREAD_ERROR, parse_db_date
from ui_components import CreditCardWidget

# ///////////////////////////////////////////////////////////////
# [SECTION: HELPERS]
# ///////////////////////////////////////////////////////////////
def get_translator(config):
    return lambda key: TRANSLATIONS[config.get("lang", "th")].get(key, key)

def safe_show_snack(page, msg, color="green"):
    try: page.open(ft.SnackBar(content=ft.Text(msg), bgcolor=color))
    except: pass

def create_group(title, controls): 
    return ft.Container(
        content=ft.Column([
            ft.Text(title, weight="w600", color="grey", size=12), 
            ft.Column(controls, spacing=10)
        ], spacing=5), 
        padding=10, 
        border=ft.border.all(1, "#333333"), 
        border_radius=10, 
        margin=ft.margin.only(bottom=5)
    )

# ///////////////////////////////////////////////////////////////
# [SECTION: UI BUILDERS]
# ///////////////////////////////////////////////////////////////

def _build_general_ui(page, current_db, config, init_app_callback):
    T = get_translator(config)
    
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

    curr_mode = config.get("startup_mode", "simple")
    mode_seg = ft.SegmentedButton(
        selected={curr_mode},
        segments=[
            ft.Segment(value="simple", label=ft.Text(T("simple_mode"))),
            ft.Segment(value="full", label=ft.Text(T("full_mode")))
        ]
    )

    db_path_val = config.get("db_path", "")
    txt_db_path = ft.Text(db_path_val, size=12, color="grey", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    db_picker = ft.FilePicker(on_result=lambda e: [setattr(txt_db_path, 'value', e.files[0].path), page.update()] if e.files else None)
    page.overlay.append(db_picker)

    content = ft.Column([
        create_group(T("data_section"), [f_budget]),
        create_group(T("voice_opts"), [sw_auto_save, ft.Column([txt_delay_label, sl_delay], spacing=0)]),
        create_group(T("startup_mode"), [mode_seg]),
        create_group(T("db_file"), [txt_db_path, ft.ElevatedButton(T("select_file"), on_click=lambda _: db_picker.pick_files(allowed_extensions=["db"]), height=30)])
    ], scroll=ft.ScrollMode.AUTO)

    def save_logic():
        current_db.set_setting("budget", f_budget.value)
        current_db.set_setting("auto_save", "1" if sw_auto_save.value else "0")
        current_db.set_setting("auto_save_delay", str(int(sl_delay.value)))
        if mode_seg.selected: config["startup_mode"] = list(mode_seg.selected)[0]
        
        need_restart = False
        if txt_db_path.value != db_path_val:
            need_restart = True
            init_app_callback(txt_db_path.value)
            
        save_config(config)
        return need_restart

    return content, save_logic

def _build_appearance_ui(page, config):
    T = get_translator(config)
    
    curr_font = config.get("font_family", "Kanit")
    curr_size = config.get("font_size", 14)
    curr_weight_int = config.get("font_weight", 600)
    
    dd_font = ft.Dropdown(
        label=T("font_family"), 
        options=[
            ft.dropdown.Option("Prompt"), ft.dropdown.Option("NotoSansThaiLooped"),
            ft.dropdown.Option("NotoSansThai"), ft.dropdown.Option("NotoSerifThai"),
            ft.dropdown.Option("Anuphan"), ft.dropdown.Option("PlaypenSans"),
        ], 
        value=curr_font
    )
    
    sl_weight = ft.Slider(min=100, max=900, divisions=8, value=curr_weight_int, label="{value}")
    txt_weight_label = ft.Text(f"{T('font_weight')}: {int(curr_weight_int)}")
    sl_weight.on_change = lambda e: [setattr(txt_weight_label, 'value', f"{T('font_weight')}: {int(e.control.value)}"), page.update()]
    
    sl_font_size = ft.Slider(min=12, max=24, divisions=12, label="{value}px", value=curr_size)
    txt_font_size_label = ft.Text(f"{T('font_size')}: {int(curr_size)}px")
    sl_font_size.on_change = lambda e: [setattr(txt_font_size_label, 'value', f"{T('font_size')}: {int(e.control.value)}px"), page.update()]

    lang_seg = ft.SegmentedButton(
        selected={config.get("lang", "th")}, 
        segments=[ft.Segment(value="en", label=ft.Text("English")), ft.Segment(value="th", label=ft.Text("ไทย"))],
        on_change=lambda e: None 
    )

    content = ft.Column([
        create_group(T("language"), [lang_seg]),
        create_group(T("font_family"), [dd_font]),
        create_group(T("font_weight"), [txt_weight_label, sl_weight]),
        create_group(T("font_size"), [txt_font_size_label, sl_font_size])
    ], scroll=ft.ScrollMode.AUTO)

    def save_logic():
        config["font_family"] = dd_font.value
        config["font_size"] = int(sl_font_size.value)
        config["font_weight"] = int(sl_weight.value)
        if lang_seg.selected: config["lang"] = list(lang_seg.selected)[0]
        save_config(config)
        page.theme = ft.Theme(font_family=dd_font.value, scrollbar_theme=ft.ScrollbarTheme(thickness=0, thumb_visibility=False, track_visibility=False))
        return False

    return content, save_logic

def _build_category_ui(page, current_db, config, close_dialog_func):
    T = get_translator(config)
    cat_content_container = ft.Container()
    cat_state = {"type": "expense"}

    def render_cat_grid():
        cat_list = current_db.get_categories(cat_state["type"])
        type_seg = ft.SegmentedButton(
            selected={cat_state["type"]}, 
            segments=[ft.Segment("expense", label=ft.Text(T("expense"))), ft.Segment("income", label=ft.Text(T("income")))], 
            on_change=lambda e: [cat_state.update({"type": list(e.control.selected)[0]}), render_cat_grid()] if e.control.selected else None
        )
        
        btn_add = ft.ElevatedButton(T("add_category"), bgcolor=COLOR_PRIMARY, color="white", width=400, on_click=lambda _: render_cat_edit())
        grid_controls = []
        for cid, name, ctype, keywords in cat_list: 
            grid_controls.append(ft.ElevatedButton(text=name, bgcolor=COLOR_BUTTON_GREY, color="white", width=120, height=50, on_click=lambda e, data=(cid, name, keywords): render_cat_edit(data)))
            
        cat_content_container.content = ft.Column([
            ft.Container(content=type_seg, alignment=ft.alignment.center), btn_add,
            ft.Row(grid_controls, wrap=True, spacing=10, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)
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
            def back_to_grid(e=None): page.close(dlg_conf); render_cat_grid(); close_dialog_func(True); page.update() 
            def yes(e):
                if current_db.delete_category(cid): back_to_grid(e)
                else: safe_show_snack(page, "Cannot delete default", "red")
            close_dialog_func(False) 
            dlg_conf = ft.AlertDialog(title=ft.Text(T("confirm_delete")), content=ft.Text(f"{T('msg_delete_cat')} ({f_name.value})"), actions=[ft.TextButton(T("delete"), on_click=yes), ft.TextButton(T("cancel"), on_click=back_to_grid)])
            page.open(dlg_conf)

        btn_save = ft.ElevatedButton(T("save"), bgcolor=COLOR_INCOME, color="white", on_click=save_cat, expand=True)
        controls = [ft.ElevatedButton(T("back"), on_click=lambda _: render_cat_grid(), icon="arrow_back"), txt_title, f_name, f_kw]
        if is_edit: controls.append(ft.Row([btn_save, ft.ElevatedButton(T("delete"), bgcolor=COLOR_EXPENSE, color="white", on_click=delete_cat_click, expand=True)], spacing=10))
        else: controls.append(ft.Row([btn_save], alignment=ft.MainAxisAlignment.CENTER))
        cat_content_container.content = ft.Column(controls, spacing=15)
        if cat_content_container.page: cat_content_container.update()

    render_cat_grid()
    return cat_content_container

def _build_card_ui(page, current_db, config, refresh_ui_callback, close_dialog_func):
    T = get_translator(config)
    card_list_col = ft.GridView(runs_count=2, max_extent=350, child_aspect_ratio=1.5, spacing=10, run_spacing=10, padding=10, expand=True)

    def render_cards(run_update=True):
        card_list_col.controls.clear()
        cards = current_db.get_cards()
        if not cards: card_list_col.controls.append(ft.Text("No credit cards added", color="grey", italic=True))
        else:
            for c in cards:
                usage = current_db.get_card_usage(c[0])
                card_list_col.controls.append(CreditCardWidget(c, open_card_edit, confirm_delete_card, usage))
        if run_update: 
            try: card_list_col.update()
            except: pass

    def open_card_edit(data=None):
        close_dialog_func(False) 
        is_edit = data is not None; c_id = data[0] if is_edit else None
        f_name = ft.TextField(label="Card Name", value=data[1] if is_edit else "")
        f_limit = ft.TextField(label="Limit Amount", value=str(data[2]) if is_edit else "", keyboard_type=ft.KeyboardType.NUMBER)
        f_closing = ft.Dropdown(label="Closing Day", options=[ft.dropdown.Option(str(i)) for i in range(1, 32)], value=str(data[3]) if is_edit else "20")
        colors = {"Green": "#2E7D32", "Blue": "#1565C0", "Red": "#C62828", "Purple": "#6A1B9A", "Orange": "#EF6C00", "Teal": "#00695C", "Grey": "#424242"}
        f_color = ft.Dropdown(label="Color", options=[ft.dropdown.Option(k) for k in colors.keys()], value="Green")
        if is_edit and data[4]:
             for k, v in colors.items(): 
                 if v == data[4]: f_color.value = k; break
        
        def save_card(e):
            try:
                name = f_name.value; limit = float(f_limit.value); day = int(f_closing.value); col_hex = colors.get(f_color.value, "#424242")
                if is_edit: current_db.update_card(c_id, name, limit, day, col_hex)
                else: current_db.add_card(name, limit, day, col_hex)
                page.close(dlg_card); render_cards(False); close_dialog_func(True); page.update(); refresh_ui_callback()
            except Exception as ex: safe_show_snack(page, f"Error: {ex}", "red")
        
        dlg_card = ft.AlertDialog(title=ft.Text("Edit Card" if is_edit else "Add Card"), content=ft.Column([f_name, f_limit, f_closing, f_color], tight=True), actions=[ft.TextButton(T("save"), on_click=save_card), ft.TextButton(T("cancel"), on_click=lambda _: [page.close(dlg_card), close_dialog_func(True)])])
        page.open(dlg_card)

    def confirm_delete_card(cid):
        close_dialog_func(False)
        def yes(e): 
            current_db.delete_card(cid); page.close(dlg_conf); render_cards(False); close_dialog_func(True); page.update(); refresh_ui_callback()
        dlg_conf = ft.AlertDialog(title=ft.Text(T("confirm_delete")), content=ft.Text("Delete this card?"), actions=[ft.TextButton(T("delete"), on_click=yes), ft.TextButton(T("cancel"), on_click=lambda _: [page.close(dlg_conf), close_dialog_func(True)])])
        page.open(dlg_conf)

    render_cards(False)
    return ft.Column([ft.Row([ft.Text(T("credit_cards"), weight="bold", size=16), ft.ElevatedButton("+ Add Card", on_click=lambda _: open_card_edit())], alignment="spaceBetween"), ft.Container(content=card_list_col, height=400)], spacing=10)

def _build_cloud_ui(page, current_db, config, refresh_ui_callback, cloud_mgr, close_dialog_func):
    T = get_translator(config)
    
    f_cloud_key = ft.TextField(label=T("json_key"), value=current_db.get_setting("cloud_key"), expand=True, text_size=12)
    f_sheet_name = ft.TextField(label=T("sheet_name"), value=current_db.get_setting("cloud_sheet"), expand=True)
    
    txt_last_result = ft.Text("-", size=12, color="grey", italic=True)

    json_picker = ft.FilePicker(on_result=lambda e: [setattr(f_cloud_key, 'value', e.files[0].path), page.update()] if e.files else None)
    page.overlay.append(json_picker)

    # --- Loading Dialog ---
    loading_text = ft.Text("Processing...", size=16)
    dlg_loading = ft.AlertDialog(
        modal=True,
        content=ft.Column([
            ft.ProgressRing(),
            ft.Container(height=10),
            loading_text
        ], horizontal_alignment="center", tight=True, alignment="center"),
    )

    def show_loading(msg):
        loading_text.value = msg
        page.open(dlg_loading)
        page.update()

    def hide_loading():
        page.close(dlg_loading)
        page.update()

    def save_cloud(e):
        config["cloud_key"] = f_cloud_key.value
        config["cloud_sheet"] = f_sheet_name.value
        save_config(config)
        current_db.set_setting("cloud_key", f_cloud_key.value)
        current_db.set_setting("cloud_sheet", f_sheet_name.value)
        safe_show_snack(page, "Cloud Config Saved")

    # --- Core Logic ---
    def process_sync_thread(task_type):
        try:
            if not f_cloud_key.value or not f_sheet_name.value:
                raise Exception("Please setup Key file and Sheet name first.")

            wb = cloud_mgr.connect(f_cloud_key.value, f_sheet_name.value)
            
            def get_or_create_sheet(title, rows="100", cols="10"):
                try: return wb.worksheet(title)
                except: return wb.add_worksheet(title=title, rows=rows, cols=cols)

            if task_type == "push":
                loading_text.value = f"Pushing data to Cloud..."
                loading_text.update()

                ws_trans = get_or_create_sheet("Transactions", "5000", "10")
                ws_cards = get_or_create_sheet("Cards")
                ws_cats = get_or_create_sheet("Categories")
                ws_rec = get_or_create_sheet("Recurring")

                cards = current_db.get_cards()
                name_to_id = {c[1]: str(c[0]) for c in cards}

                trans = current_db.get_transactions()
                data_t = [["ID", "Type", "Item", "Amount", "Category", "Date", "PaymentID"]]
                for t in trans:
                    row_list = list(t)
                    clean_row = []
                    for x in row_list:
                        clean_row.append("" if x is None else str(x))
                    
                    card_name = row_list[6] if len(row_list) > 6 else None
                    real_pid = name_to_id.get(card_name, "") if card_name else ""
                    final_row = [str(row_list[0]), row_list[1], row_list[2], str(row_list[3]), row_list[4], str(row_list[5]), real_pid]
                    data_t.append(final_row)

                ws_trans.clear(); ws_trans.update(data_t)

                data_c = [["ID", "Name", "Limit", "ClosingDay", "Color"]]
                data_c.extend([[str(x) for x in c] for c in cards])
                ws_cards.clear(); ws_cards.update(data_c)

                cats = current_db.get_categories()
                data_cat = [["ID", "Name", "Type", "Keywords"]]
                data_cat.extend([[str(x) for x in c] for c in cats])
                ws_cats.clear(); ws_cats.update(data_cat)

                recs = current_db.get_recurring()
                data_rec = [["ID", "Day", "Item", "Amount", "Category", "PaymentID", "AutoPay"]]
                data_rec.extend([[str(x) for x in r] for r in recs])
                ws_rec.clear(); ws_rec.update(data_rec)

                msg = "Push Completed Successfully!"

            elif task_type == "pull":
                loading_text.value = f"Pulling data from Cloud..."
                loading_text.update()

                ws_trans = wb.worksheet("Transactions")
                ws_cards = wb.worksheet("Cards")
                ws_cats = wb.worksheet("Categories")
                ws_rec = wb.worksheet("Recurring")

                all_c = ws_cards.get_all_values()
                current_db.clear_all_cards()
                card_map = {}
                cards_data = []
                if len(all_c) > 1:
                    for row in all_c[1:]:
                        try:
                            cid = int(row[0])
                            name = row[1].strip()
                            cards_data.append((cid, name, float(row[2]), int(row[3]), row[4]))
                            card_map[name] = cid
                            card_map[str(cid)] = cid
                        except: pass
                if cards_data:
                    current_db.conn.executemany("INSERT INTO credit_cards (id, name, limit_amt, closing_day, color) VALUES (?, ?, ?, ?, ?)", cards_data)
                
                all_t = ws_trans.get_all_values()
                current_db.clear_all_transactions()
                trans_data = []
                if len(all_t) > 1:
                    for row in all_t[1:]:
                        try:
                            pid = None
                            raw_pid = row[6].strip() if len(row) > 6 else ""
                            if raw_pid and raw_pid != "None":
                                if raw_pid.isdigit(): pid = int(raw_pid)
                                else: pid = card_map.get(raw_pid)
                            dt_val = parse_db_date(row[5])
                            trans_data.append((row[1], row[2], float(str(row[3]).replace(",", "")), row[4], dt_val, pid))
                        except: pass
                if trans_data:
                    current_db.conn.executemany("INSERT INTO transactions (type, item, amount, category, date, payment_id) VALUES (?, ?, ?, ?, ?, ?)", trans_data)

                all_cat = ws_cats.get_all_values()
                current_db.clear_all_categories()
                cat_data = []
                if len(all_cat) > 1:
                    for row in all_cat[1:]:
                        try: cat_data.append((int(row[0]), row[1], row[2], row[3] if len(row) > 3 else ""))
                        except: pass
                if cat_data:
                    current_db.conn.executemany("INSERT INTO categories (id, name, type, keywords) VALUES (?, ?, ?, ?)", cat_data)

                try:
                    all_rec = ws_rec.get_all_values()
                    current_db.clear_all_recurring()
                    rec_data = []
                    if len(all_rec) > 1:
                        for row in all_rec[1:]:
                            try:
                                pid = None
                                raw_pid = str(row[5]).strip() if len(row) > 5 else ""
                                if raw_pid and raw_pid != "None":
                                    if raw_pid.isdigit(): pid = int(raw_pid)
                                    else: pid = card_map.get(raw_pid)
                                auto = 0
                                if len(row) > 6:
                                    raw_auto = str(row[6]).strip()
                                    if raw_auto.isdigit(): auto = int(raw_auto)
                                rec_data.append((int(row[0]), int(row[1]), row[2], float(str(row[3]).replace(",", "")), row[4], pid, auto))
                            except: pass
                    if rec_data:
                        current_db.conn.executemany("INSERT INTO recurring_expenses (id, day, item, amount, category, payment_id, auto_pay) VALUES (?, ?, ?, ?, ?, ?, ?)", rec_data)
                except: pass

                current_db.conn.commit()
                msg = "Pull Completed & Database Updated!"

            # Compare Logic
            elif task_type == "compare":
                loading_text.value = "Comparing data..."
                loading_text.update()

                ws_trans = get_or_create_sheet("Transactions")
                ws_cards = get_or_create_sheet("Cards")
                ws_cats = get_or_create_sheet("Categories")
                ws_rec = get_or_create_sheet("Recurring")

                def get_count(ws): 
                    vals = ws.get_all_values()
                    return len(vals) - 1 if vals else 0

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

                hide_loading()
                
                def show_res():
                    dlg_res = ft.AlertDialog(title=ft.Text("Compare Result"), content=ft.Text(msg), actions=[ft.TextButton("OK", on_click=lambda _: page.close(dlg_res))])
                    page.open(dlg_res); page.update()
                show_res()
                return 

            # Done Loop
            hide_loading()
            txt_last_result.value = f"Success: {msg}"
            txt_last_result.color = "green"
            txt_last_result.update()
            
            if task_type == "pull":
                refresh_ui_callback()
            safe_show_snack(page, msg)

        except Exception as e:
            hide_loading()
            err_msg = str(e)
            txt_last_result.value = f"Error: {err_msg}"
            txt_last_result.color = "red"
            txt_last_result.update()
            
            dlg_err = ft.AlertDialog(title=ft.Text("Sync Error"), content=ft.Text(err_msg, color="red"), actions=[ft.TextButton("OK", on_click=lambda _: page.close(dlg_err))])
            page.open(dlg_err)

    def run_cloud_task(task_type):
        show_loading(f"Connecting to Cloud ({task_type.upper()})...")
        threading.Thread(target=process_sync_thread, args=(task_type,), daemon=True).start()

    def confirm_sync(mode):
        close_dialog_func(False)
        msg = "confirm_push" if mode == "push" else "confirm_pull"
        def on_yes(e):
            page.close(dlg_conf)
            close_dialog_func(True)
            run_cloud_task(mode)
        dlg_conf = ft.AlertDialog(title=ft.Text(T("confirm_action")), content=ft.Text(T(msg)), actions=[ft.TextButton(T("yes"), on_click=on_yes), ft.TextButton(T("cancel"), on_click=lambda _: [page.close(dlg_conf), close_dialog_func(True)])])
        page.open(dlg_conf)

    return ft.Column([
        ft.Text(T("cloud_config"), weight="bold", size=16), 
        ft.Row([f_cloud_key, ft.IconButton(icon="folder_open", on_click=lambda _: json_picker.pick_files(allowed_extensions=["json"]))]), 
        ft.Row([f_sheet_name, ft.ElevatedButton(T("save"), on_click=save_cloud)]), 
        ft.Divider(), 
        ft.Row([ft.Text(T("sync_actions"), weight="bold"), ft.Container(content=txt_last_result, expand=True, padding=ft.padding.only(left=10))], alignment="center"),
        ft.Column([
            ft.ElevatedButton(T("btn_check"), bgcolor="#1976D2", color="white", width=400, on_click=lambda _: run_cloud_task("check")), 
            ft.ElevatedButton(T("btn_compare"), bgcolor=COLOR_WARNING, color="white", width=400, on_click=lambda _: run_cloud_task("compare")),
            ft.ElevatedButton(T("btn_pull"), bgcolor=COLOR_EXPENSE, color="white", width=400, on_click=lambda _: confirm_sync("pull")), 
            ft.ElevatedButton(T("btn_push"), bgcolor=COLOR_PRIMARY, color="white", width=400, on_click=lambda _: confirm_sync("push"))
        ], horizontal_alignment="center", spacing=10)
    ], scroll=ft.ScrollMode.AUTO, spacing=15, horizontal_alignment="center")

# ///////////////////////////////////////////////////////////////
# [SECTION: MODULAR ENTRY POINTS]
# ///////////////////////////////////////////////////////////////

def open_general_dialog(page, current_db, config, refresh_ui_callback, init_app_callback):
    T = get_translator(config)
    content, save_fn = _build_general_ui(page, current_db, config, init_app_callback)
    def on_save(e):
        if save_fn(): page.close(dlg) # Restart if needed handled inside
        else: page.close(dlg); refresh_ui_callback(); safe_show_snack(page, T("msg_success"))
    dlg = ft.AlertDialog(title=ft.Text(T("general")), content=ft.Container(content=content, width=500, height=400), actions=[ft.TextButton(T("save"), on_click=on_save), ft.TextButton(T("cancel"), on_click=lambda _: page.close(dlg))])
    page.open(dlg)

def open_appearance_dialog(page, config, refresh_ui_callback):
    T = get_translator(config)
    content, save_fn = _build_appearance_ui(page, config)
    def on_save(e):
        save_fn()
        page.close(dlg); refresh_ui_callback(); safe_show_snack(page, T("msg_success"))
    dlg = ft.AlertDialog(title=ft.Text(T("appearance")), content=ft.Container(content=content, width=500, height=400), actions=[ft.TextButton(T("save"), on_click=on_save), ft.TextButton(T("cancel"), on_click=lambda _: page.close(dlg))])
    page.open(dlg)

def open_category_dialog(page, current_db, config):
    T = get_translator(config)
    dlg = None
    def close_main(is_open):
        if is_open: page.open(dlg)
        else: page.close(dlg)
    content = _build_category_ui(page, current_db, config, close_main)
    dlg = ft.AlertDialog(title=ft.Text(T("categories")), content=ft.Container(content=content, width=500, height=500), actions=[ft.TextButton(T("close"), on_click=lambda _: page.close(dlg))])
    page.open(dlg)

def open_card_dialog(page, current_db, config, refresh_ui_callback):
    T = get_translator(config)
    dlg = None
    def close_main(is_open):
        if is_open: page.open(dlg)
        else: page.close(dlg)
    content = _build_card_ui(page, current_db, config, refresh_ui_callback, close_main)
    dlg = ft.AlertDialog(title=ft.Text(T("credit_cards")), content=ft.Container(content=content, width=500, height=500), actions=[ft.TextButton(T("close"), on_click=lambda _: page.close(dlg))])
    page.open(dlg)

def open_cloud_dialog(page, current_db, config, refresh_ui_callback, cloud_mgr):
    T = get_translator(config)
    dlg = None
    def close_main(is_open):
        if is_open: page.open(dlg)
        else: page.close(dlg)
    content = _build_cloud_ui(page, current_db, config, refresh_ui_callback, cloud_mgr, close_main)
    dlg = ft.AlertDialog(title=ft.Text(T("cloud")), content=ft.Container(content=content, width=500, height=500), actions=[ft.TextButton(T("close"), on_click=lambda _: page.close(dlg))])
    page.open(dlg)

# ///////////////////////////////////////////////////////////////
# [SECTION: LEGACY ENTRY POINT]
# ///////////////////////////////////////////////////////////////

def open_settings_dialog(page, current_db, config, refresh_ui_callback, init_app_callback, cloud_mgr):
    T = get_translator(config)
    dlg = None
    
    def toggle_main(is_open):
        if is_open: page.open(dlg)
        else: page.close(dlg)

    tab_gen_content, save_gen = _build_general_ui(page, current_db, config, init_app_callback)
    tab_app_content, save_app = _build_appearance_ui(page, config)
    tab_cat_content = _build_category_ui(page, current_db, config, toggle_main)
    tab_card_content = _build_card_ui(page, current_db, config, refresh_ui_callback, toggle_main)
    tab_cloud_content = _build_cloud_ui(page, current_db, config, refresh_ui_callback, cloud_mgr, toggle_main)

    tabs = ft.Tabs(
        selected_index=0, 
        tabs=[
            ft.Tab(text=T("appearance"), content=ft.Container(content=tab_app_content, padding=10)), 
            ft.Tab(text=T("general"), content=ft.Container(content=tab_gen_content, padding=10)), 
            ft.Tab(text=T("categories"), content=ft.Container(content=tab_cat_content, padding=10)), 
            ft.Tab(text=T("credit_cards"), content=ft.Container(content=tab_card_content, padding=10)), 
            ft.Tab(text=T("cloud"), content=ft.Container(content=tab_cloud_content, padding=10))
        ], 
        height=500
    )

    def save_all(e):
        if save_gen(): # Check for restart
             page.close(dlg)
             return
        save_app()
        page.close(dlg)
        refresh_ui_callback()
        safe_show_snack(page, T("msg_success"))

    dlg = ft.AlertDialog(
        content=ft.Container(content=tabs, width=600, height=650), 
        actions=[ft.TextButton(T("save"), on_click=save_all)]
    )
    page.open(dlg)