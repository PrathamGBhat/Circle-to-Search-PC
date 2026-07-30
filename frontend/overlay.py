import os
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import send_to_backend
from utils.logging_utils import append_log, log_error

# Default popup size and offset from the cursor position
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 320
CURSOR_OFFSET_X = 20
CURSOR_OFFSET_Y = 20

class Overlay:
    """
    Small resizable popup shown near the cursor after a capture, similar
    to the Circle to Search popup. Shows the captured text and a single
    "Explain" button that forwards the text to the Ollama client.
    """

    def __init__(self):
        # Hidden root window - keeps the Tk mainloop alive for the app.
        # This must live on the main thread; the hotkey listener runs
        # separately in a background thread and talks to this instance
        # through show(), which is thread-safe.
        self.root = tk.Tk()
        self.root.withdraw()

        self.window = None
        self.text_box = None
        self.status_label = None
        self.explain_btn = None
        self.current_text = ""

    # Called from the listener's (background) thread
    def show(self, text):
        self.root.after(0, self._build_window, text)

    def run(self):
        # Blocks - must be called from the main thread
        self.root.mainloop()

    def _build_window(self, text):
        self.current_text = text or ""

        if self.window is not None and self.window.winfo_exists():
            self._reposition_window()
        else:
            self._create_window()

        self.text_box.configure(state="normal")
        self.text_box.delete("1.0", tk.END)
        self.text_box.insert(tk.END, self.current_text)
        self.text_box.configure(state="disabled")

        self.status_label.configure(text="Captured text ready")
        self.explain_btn.configure(state="normal", text="Explain")

        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def _create_window(self):
        x, y = self._get_cursor_position()

        self.window = tk.Toplevel(self.root)
        self.window.title("Circle to Search")
        self.window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
        self.window.minsize(260, 180)
        self.window.resizable(True, True)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self.text_box = scrolledtext.ScrolledText(
            self.window, wrap=tk.WORD, state="disabled", borderwidth=0
        )
        self.text_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        bottom_frame = tk.Frame(self.window)
        bottom_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.status_label = tk.Label(bottom_frame, text="", anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.explain_btn = tk.Button(
            bottom_frame, text="Explain", command=self._on_explain
        )
        self.explain_btn.pack(side=tk.RIGHT)

    def _reposition_window(self):
        x, y = self._get_cursor_position()
        self.window.geometry(f"+{x}+{y}")

    def _get_cursor_position(self):
        x = self.root.winfo_pointerx() + CURSOR_OFFSET_X
        y = self.root.winfo_pointery() + CURSOR_OFFSET_Y
        return x, y

    def _on_close(self):
        # Hide rather than destroy so the same window can be reused
        self.window.withdraw()

    def _on_explain(self):
        if not self.current_text:
            return

        self.explain_btn.configure(state="disabled")
        self.status_label.configure(text="Sending to Ollama...")
        append_log("Explain clicked, sending to Ollama")

        threading.Thread(
            target=self._send_to_ollama, args=(self.current_text,), daemon=True
        ).start()

    def _send_to_ollama(self, text):
        # NOTE: core.ollama_client.send_to_backend() currently only logs the answer
        # to log.txt and doesn't return it, so the overlay can't show the
        # response yet. That'll be the next step once ollama_client.py is
        # updated to return the answer instead of just saving it.
        try:
            send_to_backend(text)
            self.root.after(0, self._on_explain_done, "Response saved to log")
        except Exception as exc:
            log_error("Overlay failed while calling the Ollama client", exc)
            self.root.after(0, self._on_explain_done, "Error - check log for details")

    def _on_explain_done(self, message):
        self.status_label.configure(text=message)
        self.explain_btn.configure(state="normal")