import pystray
from PIL import Image, ImageDraw
import subprocess
import sys
import os
import webbrowser

# --- ตั้งค่า ---
SCRIPT_TO_RUN = "mainweb.py"
PORT = 8888
APP_NAME = "Money Tracker"

server_process = None

def create_icon_image():
    if os.path.exists("icon.png"):
        return Image.open("icon.png")

    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((8, 16, 56, 48), radius=8, fill="#5D4037", outline="#3E2723", width=2)
    d.rounded_rectangle((8, 16, 56, 32), radius=8, fill="#8D6E63", outline="#3E2723", width=0)
    d.ellipse((26, 26, 38, 38), fill="#FFD54F", outline="#F57F17", width=2)
    return image

def run_server():
    global server_process
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    # [จุดสำคัญที่แก้ไข] เพิ่ม stdout และ stderr เป็น DEVNULL เพื่อแก้ปัญหา pythonw crash
    cmd = [sys.executable, SCRIPT_TO_RUN]
    server_process = subprocess.Popen(
        cmd, 
        startupinfo=startupinfo,
        cwd=os.getcwd(),
        stdout=subprocess.DEVNULL, # ปิดการแสดงผลข้อความ
        stderr=subprocess.DEVNULL  # ปิดการแสดงผล Error
    )

def open_browser(icon, item):
    webbrowser.open(f"http://localhost:{PORT}")

def exit_app(icon, item):
    icon.stop()
    if server_process:
        server_process.terminate()
    sys.exit()

def setup_tray():
    image = create_icon_image()
    menu = (
        pystray.MenuItem('Open Money Tracker', open_browser, default=True),
        pystray.MenuItem('Exit', exit_app)
    )
    
    icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
    icon.run()

if __name__ == "__main__":
    run_server()
    setup_tray()