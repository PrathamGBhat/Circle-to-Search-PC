import os
import sys
import time
import subprocess

import psutil
from PIL import Image
import pystray

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_utils import LOG_FILE, log_error, append_log

# Global config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
LISTENER_SCRIPT = os.path.join(BASE_DIR, "listener.py")
PID_FILE = os.path.join(BASE_DIR, "listener.pid")
ICON_FILE = os.path.join(PROJECT_ROOT, "assets", "icon.png")
PYTHONW = (os.path.join(os.path.dirname(BASE_DIR), "venv", "Scripts", "pythonw.exe") # Venv pythonw
           or os.path.join(sys.base_prefix, "pythonw.exe")) # Default to global pythonw
APP_NAME = "Hotkey Listener Control"

tray_icon = None
is_loading = False # Disables start and stop buttons when loading

def get_running_pid():

    # Missing PID file
    if not os.path.exists(PID_FILE):
        return None

    # Try parsing PID file
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
    except (ValueError, OSError):
        return None

    # Missing process with PID found
    if not psutil.pid_exists(pid):
        return None

    # If both PID and PID file exist, verify actual process and return PID
    try:
        proc = psutil.Process(pid)
        cmdline = " ".join(proc.cmdline())
        if "listener.py" in cmdline:
            return pid
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    return None

def start_listener(icon=None, item=None):
    global is_loading
    pid=get_running_pid()

    # Check for pre-existing process with required PID
    if pid:
        notify(icon, "Already running", "The listener is already active.")
        return

    # Enter loading state
    is_loading = True
    refresh(icon)

    # Start new process
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as err:

            CREATE_NO_WINDOW = 0x08000000 # Don't open command prompt
            DETACHED_PROCESS = 0x00000008 # Make it a separate process from the control panel

            subprocess.Popen(
                [PYTHONW, LISTENER_SCRIPT],
                creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
                close_fds=True,
                stderr=err,
                stdout=err,
            )

    except Exception as exc:
        log_error("Failed to start the listener process", exc)
        notify(icon, "Start failed", "Could not start the listener. Check log.txt for details.")
        return

    finally:
        while not(os.path.exists(PID_FILE)):
            is_loading = True # Loading state till the PID file doesn't exist
            refresh(icon)
        is_loading = False
        refresh(icon)

    time.sleep(0.8)

def start_enabled(item=None):
    global is_loading
    if is_loading:
        return False
    pid = get_running_pid()
    return pid is None # True if pid!=None

def stop_listener(icon=None, item=None):
    global is_loading
    pid = get_running_pid()

    # Missing PID
    if not pid:
        notify(icon, "Not running", "The listener isn't currently active.")
        return

    # Enter loading state
    is_loading = True
    refresh(icon)

    try:

        # Terminate process
        psutil.Process(pid).terminate()
        append_log("Listener stopped")

        # Cleanup PID file
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except psutil.NoSuchProcess:
        pass
    finally:

        while os.path.exists(PID_FILE):
            is_loading = True # Loading state till the PID file is not removed
            refresh(icon)
        is_loading = False
        refresh(icon)

def stop_enabled(item=None):
    global is_loading
    if is_loading:
        return False
    pid = get_running_pid()
    return pid is not None # True if pid==None

def refresh(icon=None, item=None):
    if icon is not None:
        icon.update_menu()

def exit_action(icon, item=None):
    icon.stop()

def update_icon_text(item=None):
    global is_loading
    if is_loading:
        return "Loading..."
    
    pid = get_running_pid()
    return f"Running (PID {pid})" if pid else "Stopped"

def notify(icon, title, message):
    if icon is not None:
        try:
            icon.notify(message, title)
            append_log(f"{title}: {message}")
            return
        except Exception:
            pass
    append_log(f"{title}: {message}")

def main():
    global tray_icon

    menu = pystray.Menu(
        pystray.MenuItem(update_icon_text, None, enabled=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start", start_listener, enabled=start_enabled),
        pystray.MenuItem("Stop", stop_listener, enabled=stop_enabled),
        pystray.MenuItem("Refresh", refresh, enabled=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", exit_action),
    )

    tray_icon = pystray.Icon(
        "hotkey_listener_control",
        icon=Image.open(ICON_FILE),
        title=APP_NAME,
        menu=menu,
    )

    tray_icon.run()

if __name__ == "__main__":
    main()
