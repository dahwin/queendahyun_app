import sys
import os
import threading # Keep for now, might be replaced by QThread fully
import subprocess
import signal
import json
import re
import time
import asyncio
import aiohttp
from io import BytesIO
from PIL import Image
from mss import mss
import random
import string
import pyautogui
import nest_asyncio
import pyperclip
import requests # Keep for synchronous requests like /get_better
import base64
import mimetypes # For QueenDahyunChatClient if it needs to guess mimetypes

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import (QCoreApplication, QPropertyAnimation, QDate, QDateTime, 
                           QMetaObject, QObject, QPoint, QRect, QSize, QTime, QUrl, 
                           Qt, QEvent, QThread, Signal)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont, 
                          QFontDatabase, QIcon, QKeySequence, QLinearGradient, 
                          QPalette, QPainter, QPixmap, QRadialGradient, QTextCursor)
from PySide6.QtWidgets import *





from .ui import Ui_MainWindow # Assuming ui.py contains Ui_MainWindow

from .others import  get_user_data_path

nest_asyncio.apply()
pyautogui.PAUSE = 0.01

# --- Global Configuration & Helper ---
BASE_URL = "https://agi.queendahyun.site"

# Determine path and OS for resource loading (e.g., images)
try:
    # If running as a script, __file__ is defined
    CURRENT_SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Fallback if __file__ is not defined (e.g., in an interactive environment or frozen app)
    CURRENT_SCRIPT_PATH = os.getcwd()

IS_UBUNTU = 'linux' in sys.platform.lower()
    
def get_resource_path(relative_path):
     return relative_path

def generate_random_email(domain_list=None, length=10):
    if domain_list is None:
        domain_list = ['gmail.com', 'yahoo.com', 'outlook.com', 'example.com']
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    domain = random.choice(domain_list)
    return f"{username}@{domain}"

# --- UI Automation Specific Logic (UNCHANGED) ---
UI_AUTOMATION_SERVER_URL = f"{BASE_URL}/action_gui/"
UI_AUTOMATION_CAPTURE_INTERVAL = 0.05
UI_AUTOMATION_COMPRESSION_QUALITY = 90
UI_AUTOMATION_RESIZE_FACTOR = 1.0
UI_AUTOMATION_USE_JPEG = True
UI_AUTOMATION_USER_NAME = generate_random_email()

ui_automation_monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080} # Default, adjust if needed
ui_automation_mouse_icon = None
ui_automation_icon_width, ui_automation_icon_height = 0, 0

try:
    mouse_icon_path = get_resource_path("mouse_icon.png")
    if os.path.exists(mouse_icon_path):
        ui_automation_mouse_icon = Image.open(mouse_icon_path).resize((26, 26), Image.Resampling.NEAREST)
        ui_automation_icon_width, ui_automation_icon_height = ui_automation_mouse_icon.size
    else:
        print(f"Warning: Mouse icon '{mouse_icon_path}' not found.")
except Exception as e:
    print(f"Warning: Error loading mouse icon: {e}.")

def ui_automation_remove_user_session(username):
    url = f"{BASE_URL}/remove-user-session"
    data = {"username": username}
    try:
        response = requests.post(url, data=data)
        return response.json()
    except Exception as e:
        print(f"Error removing user session: {e}")
        return {"success": False, "error": str(e)}

def ui_automation_typee(text):
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")

def ui_automation_mouse_and_keyboard_action(data_str: str):
    x_match = re.search(r'x=(\d+)', data_str)
    y_match = re.search(r'y=(\d+)', data_str)
    action_match = re.search(r'action=([\w-]+)', data_str)
    
    if x_match and y_match and action_match:
        x = int(x_match.group(1))
        y = int(y_match.group(1))
        action = action_match.group(1).lower()
        
        print(f"UI Action: x={x}, y={y}, action={action}")
        if action == "left-click": pyautogui.click(x, y)
        elif action == "right-click": pyautogui.rightClick(x, y)
        elif action == "double-click": pyautogui.doubleClick(x, y)
        elif action == "move": pyautogui.moveTo(x, y)
        elif action == "enter": pyautogui.press('enter')
        else: print(f"Unknown UI action: {action}")
        time.sleep(0.5)
    else:
        print(f"Could not parse UI action: {data_str}")

def ui_automation_optimize_image(img: Image.Image):
    if UI_AUTOMATION_RESIZE_FACTOR < 1.0:
        new_width = int(img.width * UI_AUTOMATION_RESIZE_FACTOR)
        new_height = int(img.height * UI_AUTOMATION_RESIZE_FACTOR)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    img_format = "JPEG" if UI_AUTOMATION_USE_JPEG else "PNG"
    content_type = "image/jpeg" if UI_AUTOMATION_USE_JPEG else "image/png"
    
    img_byte_arr = BytesIO()
    if img_format == "JPEG":
        if img.mode == "RGBA": img = img.convert("RGB")
        img.save(img_byte_arr, format=img_format, quality=UI_AUTOMATION_COMPRESSION_QUALITY, optimize=True)
    else:
        img.save(img_byte_arr, format=img_format, optimize=True, compress_level=6)
    img_byte_arr.seek(0)
    return img_byte_arr, content_type

def ui_automation_capture_screenshot():
    with mss() as sct:
        sct_img = sct.grab(ui_automation_monitor)
        img = Image.frombytes("RGB", (sct_img.width, sct_img.height), sct_img.bgra, "raw", "BGRX")

        if ui_automation_mouse_icon:
            try:
                mouse_x_abs, mouse_y_abs = pyautogui.position()
                mouse_x_relative = mouse_x_abs - ui_automation_monitor["left"]
                mouse_y_relative = mouse_y_abs - ui_automation_monitor["top"]
                icon_pos_x = mouse_x_relative - ui_automation_icon_width // 2
                icon_pos_y = mouse_y_relative - ui_automation_icon_height // 2
                if (0 <= icon_pos_x < img.width - ui_automation_icon_width and \
                    0 <= icon_pos_y < img.height - ui_automation_icon_height):
                    img.paste(ui_automation_mouse_icon, (icon_pos_x, icon_pos_y), 
                              ui_automation_mouse_icon if ui_automation_mouse_icon.mode == 'RGBA' else None)
            except Exception as e: print(f"Error pasting mouse icon: {e}")
        return img

class UIAutomationWorker(QObject):
    status_update = Signal(str)
    ai_typed_text = Signal(str)
    action_performed = Signal(str)
    automation_finished = Signal(str)
    automation_started_signal = Signal()

    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.username = username
        self.running = False
        self.current_task_prompt = ""
        self.automation_loop_prompt = ""

    def set_task_prompt(self, prompt):
        self.current_task_prompt = prompt

    async def _get_better_command_async(self):
        pil_image = ui_automation_capture_screenshot()
        if pil_image.mode == 'RGBA':
            rgb_image = Image.new('RGB', pil_image.size, (255, 255, 255))
            rgb_image.paste(pil_image, mask=pil_image.split()[-1])
            pil_image = rgb_image
        
        buffered = BytesIO()
        pil_image.save(buffered, format="JPEG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        payload = {
            "image_base64": image_base64,
            "prompt": self.current_task_prompt
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{BASE_URL}/get_better", json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("better_command", self.current_task_prompt)
                    else:
                        return None
            except Exception:
                return None

    async def _send_screenshot_async(self, session, img, loop_prompt):
        try:
            img_bytes, content_type = ui_automation_optimize_image(img)
            form = aiohttp.FormData()
            form.add_field('file', img_bytes, filename='s.jpg' if UI_AUTOMATION_USE_JPEG else 's.png', content_type=content_type)
            form.add_field('username', self.username)
            form.add_field('prompt', loop_prompt)

            async with session.post(UI_AUTOMATION_SERVER_URL, data=form, timeout=aiohttp.ClientTimeout(total=190)) as response:
                first_line_bytes = await response.content.readline()
                if not first_line_bytes:
                    return {"success": False, "error": "Empty response (no metadata)"}
                
                processed_metadata = {}
                try:
                    metadata_str = first_line_bytes.decode('utf-8').strip()
                    processed_metadata = json.loads(metadata_str)
                    print(processed_metadata)
                except Exception as e:
                    return {"success": False, "error": f"Metadata error: {e}"}
                
                if processed_metadata.get("Done", False):
                    self.running = False

                if "instruction_data" in processed_metadata:
                    ins_d = processed_metadata['instruction_data']
                    ui_automation_mouse_and_keyboard_action(ins_d)

                if processed_metadata.get("streaming_ai_response"):
                    async for line_bytes in response.content:
                        if line_bytes:
                            try:
                                decoded_chunk = line_bytes.decode('utf-8').rstrip('\n')
                                if decoded_chunk.startswith("AI_STREAM_ERROR:"):
                                    continue
                                ui_automation_typee(decoded_chunk)
                            except UnicodeDecodeError:
                                pass
                return processed_metadata
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _automation_loop_async(self):
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    start_capture_time = time.time()
                    img = ui_automation_capture_screenshot()
                    result = await self._send_screenshot_async(session, img, self.automation_loop_prompt)
                    if not (result and result.get("success", False)):
                        await asyncio.sleep(1)
                    if self.running:
                        elapsed_total_cycle_time = time.time() - start_capture_time
                        sleep_duration = UI_AUTOMATION_CAPTURE_INTERVAL - elapsed_total_cycle_time
                        if sleep_duration > 0: await asyncio.sleep(sleep_duration)
                except pyautogui.FailSafeException:
                    self.running = False
                except Exception:
                    self.running = False
                    await asyncio.sleep(0.5)

    async def _run_main_automation_async(self):
        self.running = True
        self.automation_started_signal.emit()
        refined_task = await self._get_better_command_async()
        if not refined_task or not self.running:
            self.automation_finished.emit("Failed to refine task or stopped.")
            self.running = False
            return
        self.automation_loop_prompt = f"task : {refined_task}\ncurrent_state_image : see the current image i have provided!\nProvide exactly one complete response per state analysis, Never assume - always work from visible current state\n<image>"
        await self._automation_loop_async()
        if not self.running :
             self.automation_finished.emit("Automation task finished.")
        else:
            self.automation_finished.emit("Automation task sequence completed.")
        self.running = False

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_main_automation_async())
        except Exception as e:
            self.automation_finished.emit(f"Automation failed: {e}")
        finally:
            self.running = False
            self._cleanup_session()
            loop.close()
            asyncio.set_event_loop(None)

    def stop(self):
        self.running = False

    def _cleanup_session(self):
        ui_automation_remove_user_session(self.username)

class UIAutomationThread(QThread):
    def __init__(self, worker: UIAutomationWorker, parent=None):
        super().__init__(parent)
        self.worker = worker

    def run(self):
        self.worker.run()

    def request_stop(self):
        if self.worker:
            self.worker.stop()


# --- Multi-Turn Chat Client Logic (UPDATED) ---
class QueenDahyunChatClient(QObject):
    message_chunk_received = Signal(str)
    chat_stream_finished = Signal()
    chat_error = Signal(str)

    def __init__(self, username, server_url=BASE_URL, parent=None):
        super().__init__(parent)
        self.username = username
        self.server_url = server_url
        self.turn_count = 0
        self._is_running = False

    def chat(self, prompt, file_paths=None):
        self._is_running = True
        self.turn_count += 1
        
        data = {'username': self.username, 'prompt': prompt}
        files_to_upload = []
        file_handles = []

        # Enhanced headers for better streaming support, as in client_v2.py
        headers = {
            'Accept': 'text/plain',
            'Accept-Encoding': 'identity',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }

        try:
            if file_paths:
                for i, file_path in enumerate(file_paths):
                    if not os.path.exists(file_path):
                        self.chat_error.emit(f"File not found: {file_path}")
                        self._is_running = False
                        return
                    
                    f = open(file_path, 'rb')
                    file_handles.append(f)
                    files_to_upload.append((f'file{i}', (os.path.basename(file_path), f, mimetypes.guess_type(file_path)[0] or 'application/octet-stream')))
            
            # Use a session for keep-alive
            with requests.Session() as s:
                if files_to_upload:
                    response = s.post(
                        f"{self.server_url}/chat", 
                        files=files_to_upload, 
                        data=data, 
                        headers=headers, 
                        stream=True, 
                        timeout=(30, 300) # 30s connect, 5min read timeout
                    )
                else:
                    response = s.post(
                        f"{self.server_url}/chat", 
                        data=data, 
                        headers=headers, 
                        stream=True, 
                        timeout=(30, 300)
                    )

            if response.status_code == 200:
                # Use the improved chunk-by-chunk streaming
                for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
                    if not self._is_running:
                        self.chat_error.emit("Chat stopped by user.")
                        break 
                    if chunk:
                        self.message_chunk_received.emit(chunk)
                
                if self._is_running: # If not stopped by user
                    self.chat_stream_finished.emit()
            else:
                error_msg = f"Error: {response.status_code} - {response.text}"
                self.chat_error.emit(error_msg)
        
        except requests.exceptions.RequestException as e:
            if self._is_running:
                self.chat_error.emit(f"Network error: {e}")
        except Exception as e:
            if self._is_running:
                self.chat_error.emit(f"An unexpected error occurred: {e}")
        finally:
            for f_handle in file_handles:
                f_handle.close()
            self._is_running = False

    def stop(self):
        self._is_running = False

class ChatClientThread(QThread):
    client_message_chunk = Signal(str)
    client_chat_finished = Signal()
    client_chat_error = Signal(str)

    def __init__(self, username: str, prompt: str, file_paths: list = None, parent=None):
        super().__init__(parent)
        self.username = username
        self.prompt = prompt
        self.file_paths = file_paths if file_paths else []
        self.chat_client = None

    def run(self):
        # Create the chat client in the worker thread
        self.chat_client = QueenDahyunChatClient(username=self.username)
        
        # Connect signals
        self.chat_client.message_chunk_received.connect(self.client_message_chunk)
        self.chat_client.chat_stream_finished.connect(self.client_chat_finished)
        self.chat_client.chat_error.connect(self.client_chat_error)
        
        # Start the chat
        self.chat_client.chat(self.prompt, self.file_paths)

    def request_stop(self):
        if self.chat_client:
            self.chat_client.stop()

class MyMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.username = self._load_username()
        
        # Create UI automation worker once
        self.ui_automation_worker = UIAutomationWorker(username=UI_AUTOMATION_USER_NAME)
        self.ui_automation_thread = None
        
        # Connect signals once in __init__
        self.ui_automation_worker.automation_started_signal.connect(self.on_ui_automation_started)
        self.ui_automation_worker.automation_finished.connect(self.on_ui_automation_finished)
        
        # Chat client thread
        self.chat_client_thread = None
        
        self.selected_files_for_chat = []
        
        self.ui.send_btn.clicked.connect(self.send_user_message)
        self.ui.send_btn.clicked.connect(self.hide_download_completion_widgets)
        self.ui.force_stop_button.clicked.connect(self.force_stop_current_action)
        self.ui.force_stop_button.hide()

        self.ui.input_textEdit.setAcceptRichText(False)
        self.ui.input_textEdit.installEventFilter(self)
        
        self.closeEvent = self.custom_close_event
        
        self.ui.file_btn.clicked.connect(self.select_files_for_chat)

        self.active_animations = 0

    def _load_username(self):
        try:
            token_path = get_user_data_path('user_token.json')
            if os.path.exists(token_path):
                with open(token_path, 'r') as f:
                    data = json.load(f)
                    return data.get('username') or data.get('email', 'default_user') 
        except Exception as e:
            print(f"Error loading username: {e}")
        return 'default_user'

    def select_files_for_chat(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        if file_dialog.exec_():
            self.selected_files_for_chat = file_dialog.selectedFiles()
            self.ui.input_textEdit.setPlaceholderText(f"{len(self.selected_files_for_chat)} files selected. Type your prompt...")
            for file_path in self.selected_files_for_chat:
                 self.display_uploaded_file_preview(os.path.basename(file_path), file_path)

    def display_uploaded_file_preview(self, file_name, full_path):
        text_browser = self.ui.text_browser
        user_image_path = get_resource_path("user.png")
        preview_html = f"<p><img src='{user_image_path}' width='20' height='20'> <b>File selected:</b> {file_name}</p>"
        if full_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            preview_html += f"<p><small><i>Image: {file_name}</i></small></p>"
        text_browser.append(preview_html)
        text_browser.verticalScrollBar().setValue(text_browser.verticalScrollBar().maximum())

    def set_input_state(self, enabled: bool):
        self.ui.input_textEdit.setEnabled(enabled)
        self.ui.send_btn.setEnabled(enabled)
        self.ui.file_btn.setEnabled(enabled)
        self.ui.model_combo.setEnabled(enabled)
        self.ui.action_toggle.setEnabled(enabled)

    def start_processing_animation(self):
        self.active_animations += 1
        self.ui.upload_animation.show()
        self.ui.upload_animation.timer.start()

    def stop_processing_animation(self):
        self.active_animations -= 1
        if self.active_animations <= 0:
            self.active_animations = 0
            if hasattr(self.ui, 'upload_animation') and self.ui.upload_animation:
                 self.ui.upload_animation.stopAnimation()

    def send_user_message(self):
        user_input = self.ui.input_textEdit.toPlainText().strip()
        if not user_input and not self.selected_files_for_chat:
            return
            
        self.set_input_state(False)
        self.display_user_message(user_input if user_input else "[Sending files...]")
        self.start_processing_animation()

        if self.ui.action_toggle.is_on():
            if self.ui_automation_thread and self.ui_automation_thread.isRunning():
                self.ui.text_browser.append("<i>UI Automation is already in progress.</i>")
                self.set_input_state(True)
                self.stop_processing_animation()
                return

            self.ui.force_stop_button.show()
            self.ui_automation_worker.set_task_prompt(user_input)
            
            # Create new thread and start it
            self.ui_automation_thread = UIAutomationThread(self.ui_automation_worker)
            self.ui_automation_thread.start()

        else: # Chat Mode
            if self.chat_client_thread and self.chat_client_thread.isRunning():
                self.ui.text_browser.append("<i>Chat is already in progress.</i>")
                self.set_input_state(True)
                self.stop_processing_animation()
                return

            # Create new chat client thread
            self.chat_client_thread = ChatClientThread(self.username, user_input, self.selected_files_for_chat)
            
            # Connect signals
            self.chat_client_thread.client_message_chunk.connect(self.on_chat_message_chunk)
            self.chat_client_thread.client_chat_finished.connect(self.on_chat_finished)
            self.chat_client_thread.client_chat_error.connect(self.on_chat_error)
            
            self.start_ai_response_display()
            self.chat_client_thread.start()

        self.ui.input_textEdit.clear()
        self.ui.input_textEdit.setPlaceholderText("Type your message or select files...")
        self.selected_files_for_chat = []

    def on_ui_automation_started(self):
        self.display_action_working_message()

    def on_ui_automation_finished(self, result_message: str):
        self.finalize_ai_response_display()
        self.ui.text_browser.append(f"<b>Automation Result:</b> {result_message}")
        self.set_input_state(True)
        self.ui.force_stop_button.hide()
        self.stop_processing_animation()
        if self.ui_automation_thread:
            self.ui_automation_thread.quit()
            self.ui_automation_thread.wait()
            self.ui_automation_thread = None

    def on_chat_message_chunk(self, chunk: str):
        self.ui.text_browser.insertPlainText(chunk)
        self.ui.text_browser.verticalScrollBar().setValue(self.ui.text_browser.verticalScrollBar().maximum())
        if self.active_animations > 0 and self.ui.upload_animation.isVisible():
            self.stop_processing_animation()

    def on_chat_finished(self):
        self.finalize_ai_response_display()
        self.set_input_state(True)
        self.stop_processing_animation()
        if self.chat_client_thread:
            self.chat_client_thread.quit()
            self.chat_client_thread.wait()
            self.chat_client_thread = None

    def on_chat_error(self, error_message: str):
        self.finalize_ai_response_display()
        self.ui.text_browser.append(f"<font color='red'><b>Chat Error:</b> {error_message}</font>")
        self.set_input_state(True)
        self.ui.force_stop_button.hide()
        self.stop_processing_animation()
        if self.chat_client_thread:
            self.chat_client_thread.quit()
            self.chat_client_thread.wait()
            self.chat_client_thread = None

    def force_stop_current_action(self):
        if self.ui_automation_thread and self.ui_automation_thread.isRunning():
            self.ui.text_browser.append("<i>Attempting to stop UI automation...</i>")
            self.ui_automation_thread.request_stop() 
        elif self.chat_client_thread and self.chat_client_thread.isRunning():
            self.ui.text_browser.append("<i>Attempting to stop chat...</i>")
            self.chat_client_thread.request_stop()

    def custom_close_event(self, event):
        if hasattr(self.ui, 'upload_animation') and self.ui.upload_animation:
            self.ui.upload_animation.stopAnimation()
        
        if self.chat_client_thread and self.chat_client_thread.isRunning():
            self.chat_client_thread.request_stop()
            self.chat_client_thread.wait(2000)

        if self.ui_automation_thread and self.ui_automation_thread.isRunning():
            self.ui_automation_thread.request_stop()
            self.ui_automation_thread.wait(2000)

        super().closeEvent(event)

    def hide_download_completion_widgets(self):
        try:
            if hasattr(self.ui, 'download_compelete') and self.ui.download_compelete:
                 self.ui.download_compelete.setParent(None)
            if hasattr(self.ui, 'additional_label_3') and self.ui.additional_label_3:
                 self.ui.additional_label_3.setParent(None)
        except Exception as e:
            print(f"Error hiding widgets: {e}")

    def eventFilter(self, obj, event):
        if obj is self.ui.input_textEdit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                if event.modifiers() & Qt.ShiftModifier:
                    self.ui.input_textEdit.insertPlainText("\n")
                    return True
                else:
                    self.send_user_message()
                    return True
        return super().eventFilter(obj, event)




    def display_user_message(self, user_input):
        text_browser = self.ui.text_browser
        temp_user_img = get_user_data_path("temp_user_image.png")
        if not os.path.exists(temp_user_img):
            pixmap = QPixmap(get_resource_path("user.png"))
            scaled_pixmap = pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled_pixmap.save(temp_user_img, "PNG")
        user_message_html = f"""<table style='margin-bottom: 10px; width: 100%;'><tr><td style='vertical-align: top; width: 40px;'><img src='{temp_user_img}' width='40' height='40' style='border-radius: 20px;'></td><td style='vertical-align: top; padding-left: 10px;'><b>User:</b><br><div style='margin-top: 5px; white-space: pre-wrap; word-wrap: break-word;'><span style='font-size: 12pt;'>{user_input.replace('<', '<').replace('>', '>')}</span></div></td></tr></table>"""
        text_browser.append(user_message_html)
        text_browser.verticalScrollBar().setValue(text_browser.verticalScrollBar().maximum())

    def display_action_working_message(self):
        text_browser = self.ui.text_browser
        temp_ai_img = get_user_data_path("temp_qd_image.png")
        if not os.path.exists(temp_ai_img):
            pixmap = QPixmap(get_resource_path("queendahyun.png"))
            scaled_pixmap = pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled_pixmap.save(temp_ai_img, "PNG")
        ai_message_header = f"""<table style='margin-bottom: 10px; width: 100%;'><tr><td style='vertical-align: top; width: 50px;'><img src='{temp_ai_img}' width='50' height='50' style='border-radius: 10px;'></td><td style='vertical-align: top; padding-left: 10px;'><b>QueenDahyun (Automating):</b><br><div style='margin-top: 5px; white-space: pre-wrap; word-wrap: break-word;'><span style='font-size: 12pt;'>Working on your request...</span>"""
        text_browser.append(ai_message_header)
        text_browser.verticalScrollBar().setValue(text_browser.verticalScrollBar().maximum())

    def start_ai_response_display(self):
        text_browser = self.ui.text_browser
        temp_ai_img = get_user_data_path("temp_qd_image.png")
        if not os.path.exists(temp_ai_img):
            pixmap = QPixmap(get_resource_path("queendahyun.png"))
            scaled_pixmap = pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled_pixmap.save(temp_ai_img, "PNG")
        ai_message_header = f"""<table style='margin-bottom: 10px; width: 100%;'><tr><td style='vertical-align: top; width: 50px;'><img src='{temp_ai_img}' width='50' height='50' style='border-radius: 10px;'></td><td style='vertical-align: top; padding-left: 10px;'><b>QueenDahyun:</b><br><div style='margin-top: 5px; white-space: pre-wrap; word-wrap: break-word;'><span style='font-size: 12pt;'>"""
        cursor = text_browser.textCursor()
        cursor.movePosition(QTextCursor.End)
        text_browser.setTextCursor(cursor)
        text_browser.insertHtml(ai_message_header)
        text_browser.verticalScrollBar().setValue(text_browser.verticalScrollBar().maximum())

    def finalize_ai_response_display(self):
        text_browser = self.ui.text_browser
        closing_html = "</span></div></td></tr></table>"
        cursor = text_browser.textCursor()
        cursor.movePosition(QTextCursor.End)
        text_browser.setTextCursor(cursor)
        text_browser.insertHtml(closing_html)
        text_browser.verticalScrollBar().setValue(text_browser.verticalScrollBar().maximum())
