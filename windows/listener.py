import os
import sys
import threading
import time

from pynput import keyboard
import pyperclip

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from frontend.overlay import Overlay
from utils.logging_utils import append_log, log_error

PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listener.pid")
HOTKEY = [keyboard.Key.ctrl_l, keyboard.Key.shift_l, keyboard.Key.f9] # Ctrl + Shift + F9 by default

overlay = Overlay()
kb_simulator = keyboard.Controller()
current_keys = set() # Track keys pressed

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
        
        # Save backup of existing copied text into prev_clipb
        try:
            prev_clipb = pyperclip.paste()
        except Exception as exc:
            prev_clipb = None
            log_error("Failed to read the clipboard before copying", exc)

        # Initialize a clear clipboard
        pyperclip.copy("")
        time.sleep(0.05)

        # Release hotkeys and simulate Ctrl + C
        for i in HOTKEY:
            kb_simulator.release(i)

        kb_simulator.press(keyboard.Key.ctrl_l)
        kb_simulator.press('c')
        kb_simulator.release('c')
        kb_simulator.release(keyboard.Key.ctrl_l)

        # Delay and store text from simulated copy into captured
        time.sleep(0.15)
        captured = pyperclip.paste()

        # Show the overlay with the captured text
        if captured:
            append_log("Text copied")
            append_log("Captured text:", captured, "---")

            append_log("Overlay opened")
            overlay.send(captured)

        # Restore original copied text
        if prev_clipb is not None:
            pyperclip.copy(prev_clipb)

    except Exception as exc:
        log_error("Failed while handling the hotkey activation", exc)

def cleanup():

    # Delete PID file and stop corresponding process if it exists
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                if f.read().strip() == str(os.getpid()):
                    os.remove(PID_FILE)
        except Exception:
            pass

def main():

    append_log(f"Process started with PID: {str(os.getpid())}")
    write_pid()

    try:
        
        # The keyboard listener runs in background while overlay runs
        listener_thread = threading.Thread(target=hotkey_listener, daemon=True)
        listener_thread.start()
        overlay.run()

    finally:
        cleanup()




if __name__ == "__main__":
    main()