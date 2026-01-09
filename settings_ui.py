# settings_ui.py

import flet as ft
import threading
import json
import time
from const import *
from utils import save_config
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

def _build_general_ui(page, current_db, config, init_app_callback, cloud_mgr):
    T = get_translator(config)
    
    # --- Input Fields ---
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
    mode_seg = ft.SegmentedButton(selected={curr_mode}, segments=[ft.Segment(value="simple", label=ft.Text(T("simple_mode"))), ft.Segment(value="full", label=ft.Text(T("full_mode")))])
    
    db_path_val = config.get("db_path", "")
    txt_db_path = ft.Text(db_path_val, size=12, color="grey", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1)
    
    db_picker = ft.FilePicker(on_result=lambda e: [setattr(txt_db_path, 'value', e.files[0].path), page.update()] if e.files else None)
    page.overlay.append(db_picker)
    
    # --- Purge Logic (Auto Push) ---
    def on_purge_click(e):
        if current_db.purge_deleted_data():
            msg = "Purge complete! Local data cleaned."
            
            # ถ้ามี Cloud Manager และ URL ให้ Push ขึ้น Cloud ทันที
            if cloud_mgr and cloud_mgr.base_url:
                msg += " Syncing to Cloud..."
                safe_show_snack(page, msg, "blue")
                
                def on_cloud_done(m, c="green"):
                    safe_show_snack(page, f"Cloud Purge: {m}", c)
                
                # Push แบบ Background Thread
                threading.Thread(target=cloud_mgr.force_push, args=(on_cloud_done,), daemon=True).start()
            else:
                safe_show_snack(page, msg, "green")
        else:
            safe_show_snack(page, "Error or nothing to purge.", "orange")

    btn_purge = ft.ElevatedButton(
        text="ล้างข้อมูลที่ถูกลบถาวร (Purge)", 
        icon="delete_forever", 
        bgcolor=COLOR_EXPENSE, 
        color="white", 
        on_click=on_purge_click, 
        tooltip="ลบข้อมูลที่ถูกลบแล้วออกจาก Database จริงๆ และ Sync ลบออกจาก Cloud ด้วย"
    )

    content = ft.Column([
        create_group(T("data_section"), [f_budget, ft.Divider(), ft.Text("Maintenance", size=12, color="grey"), btn_purge]),
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
    
    dd_font = ft.Dropdown(label=T("font_family"), options=[ft.dropdown.Option(x) for x in ["Prompt", "NotoSansThaiLooped", "NotoSansThai", "NotoSerifThai", "Anuphan", "PlaypenSans"]], value=curr_font)
    
    sl_weight = ft.Slider(min=100, max=900, divisions=8, value=curr_weight_int, label="{value}")
    txt_weight_label = ft.Text(f"{T('font_weight')}: {int(curr_weight_int)}")
    sl_weight.on_change = lambda e: [setattr(txt_weight_label, 'value', f"{T('font_weight')}: {int(e.control.value)}"), page.update()]
    
    sl_font_size = ft.Slider(min=12, max=24, divisions=12, label="{value}px", value=curr_size)
    txt_font_size_label = ft.Text(f"{T('font_size')}: {int(curr_size)}px")
    sl_font_size.on_change = lambda e: [setattr(txt_font_size_label, 'value', f"{T('font_size')}: {int(e.control.value)}px"), page.update()]
    
    lang_seg = ft.SegmentedButton(selected={config.get("lang", "th")}, segments=[ft.Segment(value="en", label=ft.Text("English")), ft.Segment(value="th", label=ft.Text("ไทย"))])
    
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
        type_seg = ft.SegmentedButton(selected={cat_state["type"]}, segments=[ft.Segment("expense", label=ft.Text(T("expense"))), ft.Segment("income", label=ft.Text(T("income")))], on_change=lambda e: [cat_state.update({"type": list(e.control.selected)[0]}), render_cat_grid()] if e.control.selected else None)
        
        btn_add = ft.ElevatedButton(T("add_category"), bgcolor=COLOR_PRIMARY, color="white", width=400, on_click=lambda _: render_cat_edit())
        
        grid_controls = [ft.ElevatedButton(text=name, bgcolor=COLOR_BUTTON_GREY, color="white", width=120, height=50, on_click=lambda e, data=(cid, name, keywords): render_cat_edit(data)) for cid, name, _, keywords in cat_list]
        
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
            def yes(e): 
                if current_db.delete_category(cid): render_cat_grid()
                else: safe_show_snack(page, "Cannot delete default", "red")
            cat_content_container.content = ft.Column([ft.Icon(name="warning", color="red", size=40), ft.Text(f"{T('msg_delete_cat')} ({f_name.value})", size=16), ft.Row([ft.ElevatedButton(T("delete"), on_click=yes, bgcolor="red", color="white"), ft.ElevatedButton(T("cancel"), on_click=lambda _: render_cat_grid())], alignment="center", spacing=20)], horizontal_alignment="center", alignment="center", spacing=20); cat_content_container.update()
            
        btn_save = ft.ElevatedButton(T("save"), bgcolor=COLOR_INCOME, color="white", on_click=save_cat, expand=True)
        controls = [ft.ElevatedButton(T("back"), on_click=lambda _: render_cat_grid(), icon="arrow_back"), txt_title, f_name, f_kw]
        if is_edit: controls.append(ft.Row([btn_save, ft.ElevatedButton(T("delete"), bgcolor=COLOR_EXPENSE, color="white", on_click=delete_cat_click, expand=True)], spacing=10))
        else: controls.append(ft.Row([btn_save], alignment=ft.MainAxisAlignment.CENTER))
        cat_content_container.content = ft.Column(controls, spacing=15); cat_content_container.update()
        
    render_cat_grid()
    return cat_content_container

def _build_card_ui(page, current_db, config, refresh_ui_callback, close_dialog_func):
    T = get_translator(config)
    main_stack = ft.Stack()
    card_list_col = ft.GridView(runs_count=2, max_extent=350, child_aspect_ratio=1.5, spacing=10, run_spacing=10, padding=10, expand=True)
    list_container = ft.Container(content=card_list_col, visible=True); edit_container = ft.Container(visible=False)
    
    def render_cards():
        card_list_col.controls.clear()
        cards = current_db.get_cards()
        if not cards: card_list_col.controls.append(ft.Text("No credit cards added", color="grey", italic=True))
        else: [card_list_col.controls.append(CreditCardWidget(c, open_card_edit, confirm_delete_card, current_db.get_card_usage(c[0]))) for c in cards]
        if card_list_col.page: card_list_col.update()
        
    def show_list(): edit_container.visible = False; list_container.visible = True; render_cards(); main_stack.update()
    
    def open_card_edit(data=None):
        is_edit = data is not None; c_id = data[0] if is_edit else None
        f_name = ft.TextField(label="Card Name", value=data[1] if is_edit else ""); f_limit = ft.TextField(label="Limit Amount", value=str(data[2]) if is_edit else "", keyboard_type=ft.KeyboardType.NUMBER); f_closing = ft.Dropdown(label="Closing Day", options=[ft.dropdown.Option(str(i)) for i in range(1, 32)], value=str(data[3]) if is_edit else "20")
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
                show_list(); refresh_ui_callback()
            except Exception as ex: safe_show_snack(page, f"Error: {ex}", "red")
        edit_content = ft.Column([ft.Text("Edit Card" if is_edit else "Add Card", size=20, weight="bold"), f_name, f_limit, f_closing, f_color, ft.Row([ft.TextButton(T("save"), on_click=save_card), ft.TextButton(T("cancel"), on_click=lambda _: show_list())])], tight=True)
        edit_container.content = edit_content; list_container.visible = False; edit_container.visible = True; main_stack.update()
        
    def confirm_delete_card(cid):
        def yes(e): current_db.delete_card(cid); show_list(); refresh_ui_callback()
        confirm_content = ft.Column([ft.Text(T("confirm_delete"), size=20, weight="bold", color="red"), ft.Text("Delete this card?"), ft.Row([ft.TextButton(T("delete"), on_click=yes), ft.TextButton(T("cancel"), on_click=lambda _: show_list())])], horizontal_alignment="center", spacing=20)
        edit_container.content = confirm_content; list_container.visible = False; edit_container.visible = True; main_stack.update()
        
    render_cards()
    list_container.content = ft.Column([ft.Row([ft.Text(T("credit_cards"), weight="bold", size=16), ft.ElevatedButton("+ Add Card", on_click=lambda _: open_card_edit())], alignment="spaceBetween"), ft.Container(content=card_list_col, height=400)], spacing=10)
    main_stack.controls = [list_container, edit_container]
    return main_stack

def _build_cloud_ui(page, current_db, config, refresh_ui_callback, cloud_mgr, close_dialog_func):
    T = get_translator(config)
    
    # --- Input Fields ---
    f_firebase_url = ft.TextField(
        label="Firebase URL (Realtime Database)", 
        value=config.get("firebase_url", ""), 
        expand=True, 
        text_size=12,
        hint_text="https://your-project-id.asia-southeast1.firebasedatabase.app"
    )

    f_cloud_key = ft.TextField(label=T("json_key"), value=current_db.get_setting("cloud_key"), expand=True, text_size=12)
    json_picker = ft.FilePicker(on_result=lambda e: [setattr(f_cloud_key, 'value', e.files[0].path), page.update()] if e.files else None)
    page.overlay.append(json_picker)

    # --- Save Settings Logic ---
    def save_cloud(e):
        # 1. Update Config & DB
        config["cloud_key"] = f_cloud_key.value
        config["firebase_url"] = f_firebase_url.value
        save_config(config)
        current_db.set_setting("cloud_key", f_cloud_key.value)
        
        # 2. Update Live Cloud Manager Object
        cloud_mgr.base_url = f_firebase_url.value.rstrip('/')
        cloud_mgr.secret_key = f_cloud_key.value
        
        safe_show_snack(page, "Cloud Settings Saved", "green")

    # --- UI Components ---
    txt_status = ft.Text("Ready", size=14, color="grey", text_align="center")
    
    # Buttons
    btn_check = ft.ElevatedButton(T("btn_check"), bgcolor="#1976D2", color="white", width=400)
    btn_compare = ft.ElevatedButton(T("btn_compare"), bgcolor=COLOR_WARNING, color="white", width=400)
    btn_pull = ft.ElevatedButton(T("btn_pull"), bgcolor=COLOR_EXPENSE, color="white", width=400)
    btn_push = ft.ElevatedButton(T("btn_push"), bgcolor=COLOR_PRIMARY, color="white", width=400)
    all_buttons = [btn_check, btn_compare, btn_pull, btn_push]

    # Containers for swapping views
    buttons_container = ft.Column([btn_check, btn_compare, btn_pull, btn_push], spacing=10, horizontal_alignment="center")
    
    # Confirmation Container
    txt_confirm_msg = ft.Text("", color="red", size=16, weight="bold")
    confirm_actions = ft.Row(alignment="center", spacing=20)
    confirm_container = ft.Column([
        ft.Icon(name="warning", color="orange", size=40),
        txt_confirm_msg,
        confirm_actions
    ], horizontal_alignment="center", spacing=20, visible=False)

    # Result Container
    txt_result_msg = ft.Text("", size=14)
    result_actions = ft.Row(alignment="center")
    result_container = ft.Column([
        ft.Text(T("compare_result"), weight="bold", size=16),
        ft.Container(content=txt_result_msg, padding=10, bgcolor=ft.Colors.BLACK12, border_radius=5),
        result_actions
    ], horizontal_alignment="center", spacing=20, visible=False)

    # --- Logic to switch views ---
    def show_confirm_view(msg_key, on_yes_callback):
        txt_confirm_msg.value = T(msg_key)
        confirm_actions.controls.clear()
        confirm_actions.controls.append(ft.ElevatedButton(T("yes"), bgcolor="red", color="white", on_click=lambda e: on_yes_callback()))
        confirm_actions.controls.append(ft.ElevatedButton(T("cancel"), on_click=lambda e: restore_buttons_view()))
        
        buttons_container.visible = False; result_container.visible = False; confirm_container.visible = True
        page.update()

    def show_result_view(msg):
        txt_result_msg.value = msg
        result_actions.controls.clear()
        result_actions.controls.append(ft.ElevatedButton(T("back"), on_click=lambda e: restore_buttons_view()))
        
        buttons_container.visible = False; confirm_container.visible = False; result_container.visible = True
        page.update()

    def restore_buttons_view():
        confirm_container.visible = False; result_container.visible = False; buttons_container.visible = True
        txt_status.value = "Ready"; txt_status.color = "grey"
        page.update()

    # --- Worker Thread for Cloud Operations ---
    def process_cloud_task(task_type):
        def update_status_cb(msg, color="white"):
            txt_status.value = msg
            txt_status.color = color
            txt_status.update()

        def toggle_buttons(enable=True):
            for btn in all_buttons: btn.disabled = not enable; btn.update()

        try:
            toggle_buttons(False)
            if not f_firebase_url.value: raise Exception("Firebase URL is missing")
            
            # Call CloudManager methods
            if task_type == "check":
                update_status_cb("Connecting...", "blue")
                success, msg = cloud_mgr.test_connection()
                if success: update_status_cb(f"Success: {msg}", "green")
                else: update_status_cb(f"Error: {msg}", "red")

            elif task_type == "push":
                cloud_mgr.force_push(callback=lambda m, c="white": update_status_cb(m, c))

            elif task_type == "pull":
                cloud_mgr.force_pull(callback=lambda m, c="white": update_status_cb(m, c))
                refresh_ui_callback()

            elif task_type == "compare":
                update_status_cb("Comparing...", "blue")
                result_str = cloud_mgr.compare_data()
                update_status_cb("Comparison Finished", "green")
                show_result_view(result_str)

        except Exception as e:
            update_status_cb(f"Error: {str(e)}", "red")
        
        finally:
            toggle_buttons(True)

    def run_task_wrapper(mode):
        threading.Thread(target=process_cloud_task, args=(mode,), daemon=True).start()

    # --- Assign Actions ---
    btn_check.on_click = lambda _: run_task_wrapper("check")
    btn_compare.on_click = lambda _: run_task_wrapper("compare")
    btn_pull.on_click = lambda _: show_confirm_view("confirm_pull", lambda: [restore_buttons_view(), run_task_wrapper("pull")])
    btn_push.on_click = lambda _: show_confirm_view("confirm_push", lambda: [restore_buttons_view(), run_task_wrapper("push")])

    return ft.Column([
        ft.Text(T("cloud_config"), weight="bold", size=16), 
        f_firebase_url,
        ft.Row([f_cloud_key, ft.IconButton(icon="folder_open", on_click=lambda _: json_picker.pick_files(allowed_extensions=["json"]))]), 
        ft.ElevatedButton(T("save"), on_click=save_cloud),
        ft.Divider(), 
        txt_status,
        buttons_container,
        confirm_container,
        result_container
    ], scroll=ft.ScrollMode.AUTO, spacing=15, horizontal_alignment="center")

# ///////////////////////////////////////////////////////////////
# [SECTION: ENTRY POINTS]
# ///////////////////////////////////////////////////////////////

def open_general_dialog(page, current_db, config, refresh_ui_callback, init_app_callback, cloud_mgr):
    T = get_translator(config)
    content, save_fn = _build_general_ui(page, current_db, config, init_app_callback, cloud_mgr)
    
    def on_save(e):
        if save_fn(): 
            dlg.open = False
            page.update()
        else: 
            dlg.open = False
            page.update()
            refresh_ui_callback()
            safe_show_snack(page, T("msg_success"))
            
    dlg = ft.AlertDialog(modal=True, title=ft.Text(T("general")), content=ft.Container(content=content, width=500, height=400), actions=[ft.TextButton(T("save"), on_click=on_save), ft.TextButton(T("cancel"), on_click=lambda _: [setattr(dlg, 'open', False), page.update()])])
    page.open(dlg)

def open_appearance_dialog(page, config, refresh_ui_callback):
    T = get_translator(config)
    content, save_fn = _build_appearance_ui(page, config)
    def on_save(e): save_fn(); dlg.open = False; page.update(); refresh_ui_callback(); safe_show_snack(page, T("msg_success"))
    dlg = ft.AlertDialog(modal=True, title=ft.Text(T("appearance")), content=ft.Container(content=content, width=500, height=400), actions=[ft.TextButton(T("save"), on_click=on_save), ft.TextButton(T("cancel"), on_click=lambda _: [setattr(dlg, 'open', False), page.update()])])
    page.open(dlg)

def open_category_dialog(page, current_db, config):
    T = get_translator(config)
    content = _build_category_ui(page, current_db, config, None)
    dlg = ft.AlertDialog(modal=True, title=ft.Text(T("categories")), content=ft.Container(content=content, width=500, height=500), actions=[ft.TextButton(T("close"), on_click=lambda _: [setattr(dlg, 'open', False), page.update()])])
    page.open(dlg)

def open_card_dialog(page, current_db, config, refresh_ui_callback):
    T = get_translator(config)
    content = _build_card_ui(page, current_db, config, refresh_ui_callback, None)
    dlg = ft.AlertDialog(modal=True, title=ft.Text(T("credit_cards")), content=ft.Container(content=content, width=500, height=500), actions=[ft.TextButton(T("close"), on_click=lambda _: [setattr(dlg, 'open', False), page.update()])])
    page.open(dlg)

def open_cloud_dialog(page, current_db, config, refresh_ui_callback, cloud_mgr):
    T = get_translator(config)
    content = _build_cloud_ui(page, current_db, config, refresh_ui_callback, cloud_mgr, None)
    dlg = ft.AlertDialog(modal=True, title=ft.Text(T("cloud")), content=ft.Container(content=content, width=500, height=500), actions=[ft.TextButton(T("close"), on_click=lambda _: [setattr(dlg, 'open', False), page.update()])])
    page.open(dlg)

def open_settings_dialog(page, current_db, config, refresh_ui_callback, init_app_callback, cloud_mgr):
    T = get_translator(config)
    dlg = None
    
    # 1. สร้างเนื้อหาแต่ละแท็บ
    tab_gen_content, save_gen = _build_general_ui(page, current_db, config, init_app_callback, cloud_mgr)
    tab_app_content, save_app = _build_appearance_ui(page, config)
    tab_cat_content = _build_category_ui(page, current_db, config, None)
    tab_card_content = _build_card_ui(page, current_db, config, refresh_ui_callback, None)
    tab_cloud_content = _build_cloud_ui(page, current_db, config, refresh_ui_callback, cloud_mgr, None)

    # 2. รวมเนื้อหาใส่ Tabs
    tabs = ft.Tabs(
        selected_index=0, 
        tabs=[
            ft.Tab(text=T("general"), content=ft.Container(content=tab_gen_content, padding=10)), 
            ft.Tab(text=T("appearance"), content=ft.Container(content=tab_app_content, padding=10)), 
            ft.Tab(text=T("categories"), content=ft.Container(content=tab_cat_content, padding=10)), 
            ft.Tab(text=T("credit_cards"), content=ft.Container(content=tab_card_content, padding=10)), 
            ft.Tab(text=T("cloud"), content=ft.Container(content=tab_cloud_content, padding=10))
        ], 
        height=500
    )

    # 3. ฟังก์ชันบันทึก
    def save_all(e):
        if save_gen(): 
            dlg.open = False
            page.update()
            return
        
        save_app()
        
        dlg.open = False
        page.update()
        refresh_ui_callback()
        safe_show_snack(page, T("msg_success"))

    # 4. เปิด Dialog
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(T("settings")),
        content=ft.Container(content=tabs, width=600, height=650), 
        actions=[
            ft.TextButton(T("save"), on_click=save_all),
            ft.TextButton(T("close"), on_click=lambda _: [setattr(dlg, 'open', False), page.update()])
        ]
    )
    page.open(dlg)