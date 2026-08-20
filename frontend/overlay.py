import os
import sys

import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frontend.window_manager import WindowManagerMixin
from frontend.chat_view import ChatViewMixin
from frontend.image_preview import ImagePreviewMixin
from frontend.clipboard_prompt import ClipboardPromptMixin
from frontend.input_panel import InputPanelMixin

class Overlay(
    WindowManagerMixin,
    ChatViewMixin,
    ImagePreviewMixin,
    ClipboardPromptMixin,
    InputPanelMixin,
):
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()

        self.window = None
        self.bottom_frame = None
        self.chat_log = None
        self.input_box = None
        self.status_label = None
        self.send_btn = None
        self.preview_frame = None
        self.preview_label = None
        self.remove_image_btn = None
        self._assistant_body_start = None
        self._stream_started = False

        self.current_image = None
        self._preview_photo = None
        self._chat_photos = [] 

        self.clipboard_prompt_frame = None
        self.clipboard_prompt_label = None
        self.clipboard_yes_btn = None
        self.clipboard_no_btn = None
        self._pending_clipboard_image = None
        self._pending_clipboard_text = None
        self._clipboard_countdown_remaining = 0
        self._clipboard_countdown_after_id = None

    def send(self, image=None, text=None):
        self.root.after(0, self._prepare_for_input, image, text)

    def run(self):
        self.root.mainloop()

    def _prepare_for_input(self, image=None, text=None):
        if self.window is not None and self.window.winfo_exists():
            self._reposition_window()
        else:
            self._create_window()

        self._cancel_clipboard_countdown()
        self.current_image = None
        self._update_preview()

        if image is not None or text is not None:
            self._start_clipboard_countdown(image, text)
        else:
            self.status_label.configure(text="Type a message and send")

        self.send_btn.configure(state="normal", text="Send")

        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self.input_box.focus_set()
