import os
import sys
import threading

import pyperclip
from pynput import keyboard
from PIL import Image, ImageGrab

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from frontend.overlay import Overlay
from utils.logging_utils import append_log, log_error
from deployment.litellm.manager import start_litellm

PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listener.pid")
HOTKEY = [keyboard.Key.ctrl_l, keyboard.Key.shift_l, keyboard.Key.f9] # Ctrl + Shift + F9 by default

overlay = Overlay()
current_keys = set() # Track keys pressed

def start_backend_async():

    def _worker():
        try:
            start_litellm()
            thread.success=True
            thread.error=None
        except Exception as exc:
            thread.success = False
            thread.error = exc
            log_error("Failed to start the backend", exc)
            return

    thread = threading.Thread(target=_worker, daemon=True)
    thread.success = None
    thread.error = None
    thread.start()

    return thread

def hotkey_listener():

    # Register the defined functions to respond to press and release
    with keyboard.Listener(on_press=on_press, on_release=on_release) as kb_listener:
        kb_listener.join()

def write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def on_press(key):

    # Track keys pressed till all hotkeys activated
    if key in HOTKEY:
        current_keys.add(key)
        if all(k in current_keys for k in HOTKEY):
            on_activate()

def on_release(key):
    current_keys.discard(key)

def on_activate():
    try:

        # Capture any image from clipboard if it exists and send to overlay
        try:
            clipboard_img = ImageGrab.grabclipboard()
        except Exception as exc:
            clipboard_img = None
            log_error("Failed to read the clipboard", exc)

        image = clipboard_img if isinstance(clipboard_img, Image.Image) else None

        if image is not None:
            append_log("Image found on clipboard")
        else:
            append_log("No image on clipboard")

        # Capture any text from clipboard if it exists and send to overlay
        try:
            clipboard_text = pyperclip.paste()
        except Exception as exc:
            clipboard_text = None
            log_error("Failed to read text from the clipboard", exc)

        text = clipboard_text if isinstance(clipboard_text, str) and clipboard_text.strip() else None

        if text is not None:
            append_log("Text found on clipboard")
        else:
            append_log("No text on clipboard")

        # Send text and/or image to overlay
        append_log("Overlay opened")
        overlay.send(image=image, text=text)

    except Exception as exc:
        log_error("Failed while handling the hotkey activation", exc)

def cleanup():
    pass


def main():

    append_log(f"Process started with PID: {str(os.getpid())}")
    write_pid()

    try:

        # The keyboard listener runs in background while overlay runs
        listener_thread = threading.Thread(target=hotkey_listener, daemon=True)
        listener_thread.start()

        # Start backend
        backend_thread = start_backend_async()
        backend_thread.join()

        if backend_thread.success:
            append_log("Backend started")
        else:
            log_error("Failed to start the backend", backend_thread.error)

        overlay.run()

    finally:
        cleanup()

if __name__ == "__main__":
    main()