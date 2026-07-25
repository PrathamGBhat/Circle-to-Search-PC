import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys
import psutil

# Global config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LISTENER_SCRIPT = os.path.join(BASE_DIR, "listener.py")
PID_FILE = os.path.join(BASE_DIR, "listener.pid")
PYTHONW = os.path.join(sys.exec_prefix, "Scripts", "pythonw.exe")

def get_running_pid():

    # Handle missing PID file
    if not os.path.exists(PID_FILE):
        return None

    # Try parsing PID file
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
    except (ValueError, OSError):
        return None

    # Handle missing PID
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

def start_listener():

    # Show existing process if window hangs and start button is clickable twice
    if get_running_pid():
        messagebox.showinfo("Already running", "The listener is already active.")
        refresh()
        return

    # Creation flags for new listener process
    CREATE_NO_WINDOW = 0x08000000 # Don't open command prompt
    DETACHED_PROCESS = 0x00000008 # Make it a separate process from the control panel

    # Start new process
    subprocess.Popen(
        [PYTHONW, LISTENER_SCRIPT],
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        close_fds=True,
    )

    # Refresh after delay
    root.after(800, refresh)  # give it a moment to write its PID file

def stop_listener():
    pid = get_running_pid()

    # Handle missing PID
    if not pid:
        messagebox.showinfo("Not running", "The listener isn't currently active.")
        refresh()
        return

    # Terminate process
    try:
        psutil.Process(pid).terminate()
    except psutil.NoSuchProcess:
        pass

    # Cleanup PID file and refresh
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    refresh()

def refresh():
    pid = get_running_pid()

    # If pid exists, show running pid, disable start, enable stop button
    if pid:
        status_label.config(text=f"● Running (PID {pid})", fg="green")
        start_btn.config(state=tk.DISABLED)
        stop_btn.config(state=tk.NORMAL)

    # If pid doesn't exist, show stopped, enable start, disable stop button
    else:
        status_label.config(text="● Stopped", fg="red")
        start_btn.config(state=tk.NORMAL)
        stop_btn.config(state=tk.DISABLED)

# Root tile config
root = tk.Tk()
root.title("Hotkey Listener Control")
root.geometry("280x140")
root.resizable(False, False)

# Initialize content of root tile
status_label = tk.Label(root, text="Checking...", font=("Segoe UI", 12))
status_label.pack(pady=15)
btn_frame = tk.Frame(root)
btn_frame.pack()

# Start button
start_btn = tk.Button(btn_frame, text="Start", width=10, command=start_listener)
start_btn.grid(row=0, column=0, padx=5)

# Stop button
stop_btn = tk.Button(btn_frame, text="Stop", width=10, command=stop_listener)
stop_btn.grid(row=0, column=1, padx=5)

# Refresh button
refresh_btn = tk.Button(root, text="Refresh", command=refresh)
refresh_btn.pack(pady=10)

refresh()
root.mainloop()