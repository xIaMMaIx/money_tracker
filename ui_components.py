# ui_components.py
import flet as ft
import random
import calendar
from datetime import datetime
from const import *
from utils import format_currency, hex_with_opacity, get_heavier_weight

class TransactionCard(ft.Container):
    def __init__(self, data, onDelete, onEdit, font_delta=0, font_weight="w600", is_new=False, minimal=False):
        super().__init__()
        self.tid, self.ttype, self.item, self.amount, self.category, self.date_str, self.card_name = data
        
        if self.ttype == "income": main_color = COLOR_INCOME
        elif self.ttype == "repayment": main_color = "#29B6F6"
        else: main_color = COLOR_EXPENSE
        
        base_size = 14 + font_delta
        title_size = 16 + font_delta
        amt_size = 16 + font_delta
        
        self.actions_container = ft.Container(content=ft.Row([ft.IconButton(icon="edit", icon_color=COLOR_PRIMARY, tooltip="Edit", on_click=lambda e: onEdit(data)), ft.IconButton(icon="delete", icon_color=COLOR_BTN_EXPENSE, tooltip="Delete", on_click=lambda e: onDelete(self.tid))], spacing=0), width=0, opacity=0, animate=ft.Animation(300, "easeOut"), animate_opacity=200, clip_behavior=ft.ClipBehavior.HARD_EDGE)
        
        meta_info = [ft.Text(f"{self.category}", size=base_size - 2, color="grey")]
        if self.card_name: meta_info.append(ft.Container(content=ft.Text(self.card_name, size=10, color="white"), bgcolor="#333333", padding=ft.padding.symmetric(horizontal=4, vertical=2), border_radius=4))
        
        sign = "+" if self.ttype in ["income", "repayment"] else "-"
        amt_text = f"{sign}{format_currency(self.amount)}"
        if self.ttype == "repayment": amt_text = f"Pay {format_currency(self.amount)}"
        
        if minimal:
            card_content = ft.Row([
                ft.Column([
                    ft.Text(self.item, weight=font_weight, size=title_size),
                    ft.Row(meta_info, spacing=5)
                ], expand=True, spacing=0),
                ft.Row([
                    ft.Text(amt_text, color=main_color, weight=font_weight, size=amt_size), 
                    self.actions_container
                ], spacing=0, alignment="end")
            ], alignment="spaceBetween", vertical_alignment="center")
            self.padding = ft.padding.symmetric(horizontal=5, vertical=8)
            self.border = ft.border.only(bottom=ft.BorderSide(1, "#333333"))
        else:
            card_content = ft.Row([ft.Container(expand=True, padding=ft.padding.symmetric(horizontal=10, vertical=5), content=ft.Row([ft.Row([ft.Container(content=ft.Icon("check_circle" if self.ttype=="repayment" else "circle", size=10 if self.ttype=="repayment" else 8, color=main_color), padding=5, bgcolor=hex_with_opacity(main_color, 0.1), border_radius=8), ft.Column([ft.Text(self.item, weight=font_weight, size=title_size), ft.Row(meta_info, spacing=5)], expand=True, spacing=0)]), ft.Row([ft.Text(amt_text, color=main_color, weight=font_weight, size=amt_size), self.actions_container], spacing=0, alignment="end")], alignment="spaceBetween"))], spacing=0)
            self.padding = 0
            self.border = ft.border.only(bottom=ft.BorderSide(3, main_color))
            
        self.content = card_content; self.on_hover = self.toggle_actions; self.animate_opacity = 500; self.opacity = 0 if is_new else 1; 
        self.bgcolor = COLOR_SURFACE; self.border_radius = ft.border_radius.only(top_left=5, top_right=5); self.margin = ft.margin.only(bottom=2)

    def toggle_actions(self, e): is_hover = (e.data == "true"); self.actions_container.width = 80 if is_hover else 0; self.actions_container.opacity = 1 if is_hover else 0; self.actions_container.update()

class SummaryCard(ft.Container):
    def __init__(self, title_key, value, color, icon_name, font_delta=0, font_weight="w600"):
        super().__init__()
        self.title_key = title_key; self.color = color; self.icon_name = icon_name
        self.txt_title = ft.Text(title_key, color="grey")
        self.txt_value = ft.Text(value, color=color)
        self.icon_widget = ft.Icon(icon_name, color=color)
        
        self.content = ft.Column([ft.Row([self.icon_widget, self.txt_title], spacing=5), self.txt_value], spacing=5)
        self.padding = 20; self.bgcolor = COLOR_SURFACE; self.border_radius = 12; self.expand = True
        self.update_style(font_delta, font_weight) 

    def update_style(self, font_delta, font_weight):
        title_size = 14 + font_delta
        val_size = 26 + font_delta
        heavy_weight = get_heavier_weight(font_weight)
        
        self.txt_title.size = title_size
        self.txt_value.size = val_size
        self.txt_value.weight = heavy_weight
        self.icon_widget.size = 20 + (font_delta/2)

class CalendarWidget(ft.Column):
    def __init__(self, page, on_select, font_delta=0, font_weight="w600"):
        super().__init__()
        self.page_ref = page
        self.on_select = on_select
        self.font_delta = font_delta
        self.font_weight = font_weight
        self.now = datetime.now()
        self.year, self.month = self.now.year, self.now.month
        self.sel_date = None
        self.db = None
        
        self.header_text = ft.Text(weight=font_weight, text_align=ft.TextAlign.CENTER)
        
        # ปรับ header_btn ให้คลิกง่ายขึ้น
        self.header_btn = ft.Container(
            content=self.header_text, 
            padding=ft.padding.symmetric(horizontal=10, vertical=5), 
            border_radius=5, 
            ink=True, 
            on_click=lambda e: self.page_ref.open(self.date_picker),
            alignment=ft.alignment.center
        )
        
        self.grid = ft.Column(spacing=2) # เพิ่ม spacing เล็กน้อยเพื่อให้ไม่เบียดกันจนคลิกยาก
        self.date_picker = ft.DatePicker(on_change=self.on_date_picked, on_dismiss=None, first_date=datetime(2000, 1, 1), last_date=datetime(2100, 12, 31))
        self.page_ref.overlay.append(self.date_picker)
        
        self.controls = [
            ft.Row([
                ft.IconButton("chevron_left", on_click=lambda e: self.nav(-1), tooltip="Previous Month"), 
                self.header_btn, 
                ft.IconButton("chevron_right", on_click=lambda e: self.nav(1), tooltip="Next Month")
            ], alignment="spaceBetween"), 
            ft.Row([
                ft.Container(content=ft.Text(d, color="grey", size=10), width=30, alignment=ft.alignment.center) 
                for d in ["Mo","Tu","We","Th","Fr","Sa","Su"]
            ], alignment="spaceBetween"), 
            self.grid
        ]
        self.update_style(font_delta, font_weight)
        self.render()

    def set_db(self, db_instance):
        self.db = db_instance
        self.render()

    def update_style(self, font_delta, font_weight):
        self.font_delta = font_delta
        self.font_weight = font_weight
        self.header_text.size = 14 + font_delta
        self.header_text.weight = font_weight
        
        nav_row = self.controls[0]
        nav_row.controls[0].icon_size = 16 + font_delta
        nav_row.controls[2].icon_size = 16 + font_delta
        
        day_row = self.controls[1]
        for container in day_row.controls:
             container.content.size = 10 + font_delta
        self.render()

    def on_date_picked(self, e):
        if self.date_picker.value: 
            d = self.date_picker.value
            self.year = d.year
            self.month = d.month
            self.sel_date = d
            self.render()
            self.update()
            self.on_select(d.strftime("%Y-%m-%d"))
    
    def nav(self, d): 
        self.month += d
        if self.month > 12:
            self.month = 1
            self.year += 1
        elif self.month < 1:
            self.month = 12
            self.year -= 1
        
        self.render()
        self.update()
        self.on_select(None)
    
    def render(self):
        # อัปเดตชื่อเดือน
        self.header_text.value = datetime(self.year, self.month, 1).strftime("%B %Y")
        self.grid.controls.clear()
        
        active_days = set()
        if self.db:
             month_str = f"{self.year}-{self.month:02d}"
             active_days = self.db.get_active_days(month_str)

        cal_data = calendar.monthcalendar(self.year, self.month)
        
        # ปรับขนาด Cell ให้ใหญ่ขึ้นเล็กน้อยเพื่อรองรับ Dot และคลิกง่ายขึ้นใน Web
        base_cell_size = 30 + (self.font_delta * 0.5)
        
        for week in cal_data:
            row = ft.Row(alignment="spaceBetween")
            for day in week:
                if day == 0: 
                    row.controls.append(ft.Container(width=base_cell_size, height=base_cell_size))
                else:
                    is_today = (day == datetime.now().day and self.month == datetime.now().month and self.year == datetime.now().year)
                    is_sel = (self.sel_date and day == self.sel_date.day and self.month == self.sel_date.month and self.year == self.sel_date.year)
                    has_data = day in active_days 
                    
                    # สีพื้นหลัง (วงกลม)
                    bg_color = COLOR_PRIMARY if is_sel else "transparent"
                    
                    # สีตัวอักษร
                    txt_color = "#121212" if is_sel else "white"
                    if is_today and not is_sel:
                        txt_color = COLOR_PRIMARY  # วันปัจจุบันให้ตัวหนังสือสีฟ้า ถ้าไม่ได้เลือก
                    
                    # Border (สำหรับวันปัจจุบันเท่านั้น)
                    border = ft.border.all(1, "grey") if (is_today and not is_sel) else None
                    
                    # [แก้ข้อ 2] จุด (Dot Indicator) แทนเส้นใต้
                    dot_color = "transparent"
                    if has_data:
                        dot_color = "white" if is_sel else COLOR_PRIMARY
                    
                    # สร้าง Content ภายในแบบ Column (ตัวเลขขี่คอกับจุด)
                    inner_content = ft.Column([
                        ft.Text(str(day), size=12+self.font_delta, color=txt_color, weight="bold" if is_sel or is_today else "normal"),
                        ft.Container(width=4, height=4, border_radius=2, bgcolor=dot_color) # จุดอยู่ตรงนี้
                    ], alignment="center", spacing=2, horizontal_alignment="center")

                    # [แก้ข้อ 1] Container หลักสำหรับการคลิก
                    # เอา ink=False ออกถ้า Web ยังกระตุก แต่ปกติการจัด Alignment ให้ Center จะช่วยเรื่อง Hit Test ได้
                    day_container = ft.Container(
                        content=inner_content,
                        width=base_cell_size,
                        height=base_cell_size,
                        alignment=ft.alignment.center,
                        border_radius=base_cell_size/2,
                        bgcolor=bg_color,
                        border=border,
                        ink=True, 
                        on_click=lambda e, d=day: self.set_date(d)
                    )
                    row.controls.append(day_container)
            self.grid.controls.append(row)
            
    def set_date(self, day): 
        self.sel_date = datetime(self.year, self.month, day)
        self.render()
        self.update()
        # ส่งค่ากลับไปที่ mainweb
        self.on_select(self.sel_date.strftime("%Y-%m-%d"))

    def reset(self): 
        self.now = datetime.now()
        self.year = self.now.year
        self.month = self.now.month
        self.sel_date = None
        self.render()
        self.update()
        self.on_select(None)

class RealTimeVoiceVisualizer(ft.Row):
    def __init__(self): super().__init__(alignment="center", spacing=4, height=60); self.bars = [ft.Container(width=6, height=5, bgcolor=COLOR_PRIMARY, border_radius=3, animate=ft.Animation(50, "easeOut")) for _ in range(12)]; self.controls = self.bars
    def update_volume(self, rms_value): scale = min(rms_value / 15, 55); mid = len(self.bars) // 2; [setattr(bar, 'height', max(5, scale - (abs(i - mid) * 3) + random.randint(-5, 5))) for i, bar in enumerate(self.bars)]; self.update()

class CreditCardWidget(ft.Container):
    def __init__(self, card_data, onEdit, onDelete, usage=0.0):
        super().__init__()
        self.cid, self.name, self.limit, self.closing_day, self.color = card_data
        self.onEdit = onEdit; self.onDelete = onDelete; self.usage = usage; self.limit = float(self.limit)
        
        raw_percent = self.usage / self.limit if self.limit > 0 else 0
        percent = max(0.0, min(raw_percent, 1.0))
        
        prog_color = "white" if percent <= 0.7 else ("#FF5252" if percent > 0.9 else "#FFAB40")
        self.content = ft.Column([
            ft.Row([ft.Row([ft.Icon(name="credit_card", color="white70", size=18), ft.Text(self.name, weight="bold", size=16, color="white")], spacing=5), ft.PopupMenuButton(items=[ft.PopupMenuItem(icon="edit", text="Edit", on_click=lambda e: self.onEdit(card_data)), ft.PopupMenuItem(icon="delete", text="Delete", on_click=lambda e: self.onDelete(self.cid))], icon="more_horiz", icon_color="white70", padding=0)], alignment="spaceBetween"),
            ft.Container(height=10),
            ft.Row([ft.Text(f"Used: {format_currency(self.usage)}", size=12, color="white70"), ft.Text(f"Limit: {format_currency(self.limit)}", size=12, color="white70")], alignment="spaceBetween"),
            ft.ProgressBar(value=percent, color=prog_color, bgcolor="white24", height=6, border_radius=3),
            ft.Container(content=ft.Row([ft.Text(f"Available: {format_currency(self.limit - self.usage)}", size=11, color="white54", weight="bold"), ft.Text(f"Closing Day: {self.closing_day}", size=11, color="white54")], alignment="spaceBetween"), margin=ft.margin.only(top=5))
        ], spacing=2)
        self.bgcolor = self.color if self.color else "#424242"; self.padding = 15; self.border_radius = 12; self.height = 130; self.shadow = ft.BoxShadow(blur_radius=10, color="#4D000000", offset=ft.Offset(2, 4))

class MiniCardWidget(ft.Container):
    def __init__(self, card_data, onPay, onShowHistory, usage=0.0, col=None):
        super().__init__(col=col)
        self.cid, self.name, self.limit, self.closing_day, self.color = card_data
        self.usage = usage; self.limit = float(self.limit)
        
        raw_percent = self.usage / self.limit if self.limit > 0 else 0
        percent = max(0.0, min(raw_percent, 1.0))
        
        prog_color = "white" if percent <= 0.5 else ("#FFAB40" if percent <= 0.8 else "#FF5252")
        
        name_widget = ft.Container(
            content=ft.Row([
                ft.Icon("credit_card", size=16, color="white70"), 
                ft.Text(self.name, size=14, weight="bold", color="white", no_wrap=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
            ], spacing=5),
            on_click=lambda e: onShowHistory(card_data), 
            ink=True,
            border_radius=5,
            padding=ft.padding.symmetric(horizontal=5, vertical=2),
        )

        pay_btn = ft.Container(
            content=ft.Icon("payment", size=16, color="white70"), # ขยาย icon นิดหน่อย
            padding=5, 
            border_radius=5, 
            bgcolor="white10", 
            ink=True, 
            on_click=lambda e: onPay(card_data), 
            tooltip=f"Pay {self.name}"
        )

        display_text = f"{format_currency(self.usage)} / {format_currency(self.limit - self.usage)}"

        self.content = ft.Column([
            # [บรรทัดที่ 1] ชื่อบัตร และ ปุ่มจ่ายเงิน
            ft.Row([
                name_widget, 
                pay_btn
            ], alignment="spaceBetween", vertical_alignment="center"), 
            
            # [บรรทัดที่ 2] ยอดเงิน (ตัวใหญ่ขึ้น)
            ft.Container(
                content=ft.Text(display_text, size=16, weight="bold", color="white"),
                padding=ft.padding.only(left=8, top=2, bottom=2)
            ),

            # [บรรทัดที่ 3] Progress Bar
            ft.ProgressBar(value=percent, color=prog_color, bgcolor="black26", height=4, border_radius=2)
        ], spacing=2, alignment="spaceBetween") # จัดระยะห่างให้พอดี
        
        self.bgcolor = self.color if self.color else "#424242"
        self.padding = ft.padding.all(10)
        self.border_radius = 12
        self.height = 80 # เพิ่มความสูงเพื่อให้แสดงผลได้ครบ 3 ส่วน
        self.shadow = ft.BoxShadow(blur_radius=5, color="#4D000000", offset=ft.Offset(0, 2))