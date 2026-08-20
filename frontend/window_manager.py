import tkinter as tk

# Global config
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 320
CURSOR_OFFSET_X = 20
CURSOR_OFFSET_Y = 20

class WindowManagerMixin:
    def _create_window(self):
        x, y = self._get_cursor_position()

        self.window = tk.Toplevel(self.root)
        self.window.title("Circle to Search")
        self.window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
        self.window.minsize(260, 180)
        self.window.resizable(True, True)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self.window.pack_propagate(False)

        bottom_frame = tk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(4, 8))
        self.bottom_frame = bottom_frame

        self.status_label = tk.Label(self.window, text="", anchor="w")
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=8)

        self._build_clipboard_prompt_widgets()

        self._build_preview_widgets()

        self._build_input_area(bottom_frame)

        self._build_chat_log()

    def _reposition_window(self):
        x, y = self._get_cursor_position()
        self.window.geometry(f"+{x}+{y}")

    def _get_cursor_position(self):
        x = self.root.winfo_pointerx() + CURSOR_OFFSET_X
        y = self.root.winfo_pointery() + CURSOR_OFFSET_Y

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = min(x, screen_width - WINDOW_WIDTH)
        y = min(y, screen_height - WINDOW_HEIGHT)
        x = max(x, 0)
        y = max(y, 0)

        return x, y

    def _on_close(self):
        self._cancel_clipboard_countdown()
        self.window.withdraw()
