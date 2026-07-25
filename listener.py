from pynput import keyboard
import os
import sys
import time
import pyperclip

# File in same directory to track the pid of this listener script - Will be tracked by the control panel file
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listener.pid")

# File in same directory where captured text gets saved
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listener_log.txt")

HOTKEY = {keyboard.Key.ctrl_l, keyboard.Key.space}

# Tracks currently pressed keys
current_keys = set()

# To simulate key presses
kb_controller = keyboard.Controller()

def write_pid():

    # Write pid to file
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def cleanup():

    # Check if any pid file is there
    if os.path.exists(PID_FILE):
        try:

            # If it exists delete
            with open(PID_FILE) as f:
                if f.read().strip() == str(os.getpid()):
                    os.remove(PID_FILE)
        except Exception:
            pass

def on_activate():

    # Save backup of existing copied text into prev_clipb
    try:
        prev_clipb = pyperclip.paste()
    except Exception:
        prev_clipb = None

    # Initialize a clear clipboard
    pyperclip.copy("")
    time.sleep(0.05)

    # Release hotkeys
    kb_controller.release(keyboard.Key.ctrl_l)
    kb_controller.release(keyboard.Key.space)

    # Simulate Ctrl+C
    kb_controller.press(keyboard.Key.ctrl_l)
    kb_controller.press('c')
    kb_controller.release('c')
    kb_controller.release(keyboard.Key.ctrl_l)

    # Delay and store text from simulated copy into captured
    time.sleep(0.15)
    captured = pyperclip.paste()

    # Write captured text to file if exists
    if captured:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(captured + "\n---\n")

    # Restore original copied text if exists
    if prev_clipb is not None:
        pyperclip.copy(prev_clipb)

def on_press(key):

    # Check if its part of the hotkey combination
    if key in HOTKEY:
        current_keys.add(key)

        # If entire combination clicked, run the on_activate function
        if all(k in current_keys for k in HOTKEY):
            on_activate()

def on_release(key):

    # Stop tracking in current_keys
    current_keys.discard(key)

def main():
    write_pid()
    try:
        
        # Register user defined functions to respond to press and release
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    finally:
        cleanup()

if __name__ == "__main__":
    main()