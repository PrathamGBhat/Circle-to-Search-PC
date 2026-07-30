import os
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext

from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import send_to_backend
from utils.logging_utils import append_log, log_error

# Default popup size and offset from the cursor position
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 320
CURSOR_OFFSET_X = 20
CURSOR_OFFSET_Y = 20
INPUT_BOX_HEIGHT = 3

# Thumbnail sizes
PREVIEW_THUMB_SIZE = (160, 120)   # image waiting to be sent, shown above the input box
CHAT_THUMB_SIZE = (140, 100)      # image already sent, shown inline in the chat log

class Overlay:
    """
    Small resizable popup shown near the cursor after a capture, similar
    to the Circle to Search popup. Behaves like a lightweight chat window:
    if an image was captured (e.g. via the Snipping Tool) it's shown as a
    small preview above the input box; the user always types their own
    message, and every sent message (plus any attached image) and its
    reply is appended to a scrolling chat log above.
    """

    def __init__(self):
        # Hidden root window - keeps the Tk mainloop alive for the app.
        # This must live on the main thread; the hotkey listener runs
        # separately in a background thread and talks to this instance
        # through send(), which is thread-safe.
        self.root = tk.Tk()
        self.root.withdraw()

        self.window = None
        self.chat_log = None
        self.input_box = None
        self.status_label = None
        self.send_btn = None
        self.preview_frame = None
        self.preview_label = None
        self.remove_image_btn = None
        self._assistant_body_start = None

        # The image currently attached and waiting to be sent, plus a
        # reference to its Tk PhotoImage (Tk drops images without a live
        # Python reference, so we have to hold onto these ourselves).
        self.current_image = None
        self._preview_photo = None
        self._chat_photos = []  # keeps chat-log thumbnails alive

    # Called from the listener's (background) thread. Pass an `image`
    # (a PIL Image) when one was found on the clipboard; omit it to just
    # open/focus the overlay for a plain text message.
    def send(self, image=None):
        self.root.after(0, self._prepare_for_input, image)

    def run(self):
        # Blocks - must be called from the main thread
        self.root.mainloop()

    def _prepare_for_input(self, image=None):
        # Opens (or refocuses) the overlay and attaches the given image, if
        # any, as a pending preview. The user's own typing is what actually
        # becomes the message; nothing is pre-filled into the input box.
        if self.window is not None and self.window.winfo_exists():
            self._reposition_window()
        else:
            self._create_window()

        self.current_image = image
        self._update_preview()

        if image is not None:
            self.status_label.configure(text="Image attached - type a message and send")
        else:
            self.status_label.configure(text="Type a message and send")

        self.send_btn.configure(state="normal", text="Send")

        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self.input_box.focus_set()

    def _update_preview(self):
        # Shows/hides the pending-image preview above the input box.
        if self.current_image is not None:
            thumb = self.current_image.copy()
            thumb.thumbnail(PREVIEW_THUMB_SIZE)
            self._preview_photo = ImageTk.PhotoImage(thumb)
            self.preview_label.configure(image=self._preview_photo, text="")
            self.preview_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 4))
        else:
            self._preview_photo = None
            self.preview_label.configure(image="", text="")
            self.preview_frame.pack_forget()

    def _remove_image(self):
        self.current_image = None
        self._update_preview()
        self.status_label.configure(text="Image removed - type a message and send")

    def _append_message(self, sender, message, image=None):
        # Adds a labeled message (and optional thumbnail) to the chat log
        # and scrolls to the bottom. Returns the index right before the
        # message body, so callers (like the "Thinking..." placeholder) can
        # later replace just that body without touching the "Sender: " label.
        self.chat_log.configure(state="normal")
        if self.chat_log.index("end-1c") != "1.0":
            self.chat_log.insert(tk.END, "\n\n")
        self.chat_log.insert(tk.END, f"{sender}: ", ("sender",))
        body_start = self.chat_log.index("end-1c")

        if image is not None:
            thumb = image.copy()
            thumb.thumbnail(CHAT_THUMB_SIZE)
            photo = ImageTk.PhotoImage(thumb)
            self._chat_photos.append(photo)  # keep a reference alive
            self.chat_log.image_create(tk.END, image=photo)
            if message:
                self.chat_log.insert(tk.END, "\n")

        self.chat_log.insert(tk.END, message or "")
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)
        return body_start

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

        self.status_label = tk.Label(self.window, text="", anchor="w")
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=8)

        # Pending-image preview row (hidden until an image is attached)
        self.preview_frame = tk.Frame(self.window)
        self.preview_label = tk.Label(self.preview_frame, anchor="w")
        self.preview_label.pack(side=tk.LEFT)
        self.remove_image_btn = tk.Button(
            self.preview_frame, text="Remove image", command=self._remove_image
        )
        self.remove_image_btn.pack(side=tk.RIGHT)
        # Not packed here - _update_preview() packs/unpacks it as needed.

        input_frame = tk.Frame(bottom_frame)
        input_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.input_box = tk.Text(
            input_frame, wrap=tk.WORD, height=INPUT_BOX_HEIGHT, borderwidth=1,
            relief=tk.SOLID,
        )
        self.input_box.pack(fill=tk.BOTH, expand=True)
        self.input_box.bind("<Return>", self._on_enter_key)
        self.input_box.bind("<Shift-Return>", lambda e: None)

        self.send_btn = tk.Button(
            bottom_frame, text="Send", command=self._on_send, width=10
        )
        self.send_btn.pack(side=tk.RIGHT, padx=(6, 0), anchor="s")

        self.chat_log = scrolledtext.ScrolledText(
            self.window, wrap=tk.WORD, state="disabled", borderwidth=0
        )
        self.chat_log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
        self.chat_log.tag_configure("sender", font=("TkDefaultFont", 9, "bold"))

    def _reposition_window(self):
        x, y = self._get_cursor_position()
        self.window.geometry(f"+{x}+{y}")

    def _get_cursor_position(self):
        x = self.root.winfo_pointerx() + CURSOR_OFFSET_X
        y = self.root.winfo_pointery() + CURSOR_OFFSET_Y

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Keep the whole window on-screen so the bottom button bar can't
        # get pushed past the edge of the display.
        x = min(x, screen_width - WINDOW_WIDTH)
        y = min(y, screen_height - WINDOW_HEIGHT)
        x = max(x, 0)
        y = max(y, 0)

        return x, y

    def _on_close(self):
        # Hide rather than destroy so the same window can be reused
        self.window.withdraw()

    def _on_enter_key(self, event):
        # Enter sends the message; Shift+Enter (bound separately above)
        # falls through to the default behavior and inserts a newline.
        self._on_send()
        return "break"

    def _on_send(self):
        text = self.input_box.get("1.0", "end-1c").strip()
        image = self.current_image

        # Nothing to send if there's neither typed text nor an attached image
        if not text and image is None:
            return

        self._append_message("You", text, image=image)
        self.input_box.delete("1.0", tk.END)

        # The image has now been "sent" (dropped into the chat log), so
        # clear the pending preview for the next message.
        self.current_image = None
        self._update_preview()

        self.send_btn.configure(state="disabled")
        self.status_label.configure(text="Sending...")
        self._assistant_body_start = self._append_message("Assistant", "Thinking...")
        append_log("Send clicked, sending to backend")

        threading.Thread(
            target=self._send_to_backend, args=(text,), daemon=True
        ).start()

    def _send_to_backend(self, text):
        # send_to_backend() returns response.output_text directly, so we
        # can show the reply in the chat log instead of just logging it.
        try:
            answer = send_to_backend(text)
            self.root.after(0, self._on_send_done, answer, "Response received")
        except Exception as exc:
            log_error("Overlay failed while calling the backend", exc)
            self.root.after(
                0, self._on_send_done, "Error - check log for details", "Error - check log for details"
            )

    def _on_send_done(self, answer, status_message):
        # Replace the "Thinking..." placeholder body with the actual reply,
        # without touching the "Assistant: " label before it.
        self.chat_log.configure(state="normal")
        self.chat_log.delete(self._assistant_body_start, tk.END)
        self.chat_log.insert(tk.END, answer or "")
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)

        self.status_label.configure(text=status_message)
        self.send_btn.configure(state="normal")