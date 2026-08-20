import os
import sys
import threading

import tkinter as tk
from tkinter import ttk, scrolledtext
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.services.io_compiler import process_stream as compile_and_send_stream
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

# How long the user has to decide whether clipboard content gets attached
CLIPBOARD_COUNTDOWN_SECONDS = 3

class Overlay:

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

        # The image currently attached and waiting to be sent, plus a
        # reference to its Tk PhotoImage (Tk drops images without a live
        # Python reference, so we have to hold onto these ourselves).
        self.current_image = None
        self._preview_photo = None
        self._chat_photos = []  # keeps chat-log thumbnails alive

        # Clipboard-attachment countdown ("Attach from clipboard? Yes/No"),
        # shown above the input box whenever a capture comes in with an
        # image and/or text on the clipboard. Nothing is actually attached
        # until the countdown resolves (either the timer runs out, which
        # attaches by default, or the user clicks Yes/No).
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
        # Opens (or refocuses) the overlay. If there's an image and/or text
        # on the clipboard, nothing is attached right away - instead a
        # short countdown prompt asks whether to attach it at all.
        if self.window is not None and self.window.winfo_exists():
            self._reposition_window()
        else:
            self._create_window()

        # A fresh capture always overrides whatever the previous countdown
        # (if any) was still deciding on.
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

    # ------------------------------------------------------------------
    # Clipboard attach-or-not countdown
    # ------------------------------------------------------------------

    def _start_clipboard_countdown(self, image, text):
        # Stash what's pending; nothing is attached until the countdown
        # resolves via timeout, Yes, or No.
        self._pending_clipboard_image = image
        self._pending_clipboard_text = text
        self._clipboard_countdown_remaining = CLIPBOARD_COUNTDOWN_SECONDS

        self.clipboard_prompt_frame.pack(
            side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 4), after=self.bottom_frame
        )
        self.clipboard_yes_btn.configure(state="normal")
        self.clipboard_no_btn.configure(state="normal")
        self.status_label.configure(text="")
        self._update_clipboard_prompt_label()
        self._clipboard_countdown_after_id = self.root.after(1000, self._clipboard_countdown_tick)

    def _update_clipboard_prompt_label(self):
        self.clipboard_prompt_label.configure(
            text=f"Attach from clipboard? Yes (default)   No        ...{self._clipboard_countdown_remaining}s"
        )

    def _clipboard_countdown_tick(self):
        self._clipboard_countdown_remaining -= 1
        if self._clipboard_countdown_remaining <= 0:
            self._resolve_clipboard_countdown(attach=True)
        else:
            self._update_clipboard_prompt_label()
            self._clipboard_countdown_after_id = self.root.after(1000, self._clipboard_countdown_tick)

    def _on_clipboard_yes(self):
        self._resolve_clipboard_countdown(attach=True)

    def _on_clipboard_no(self):
        self._resolve_clipboard_countdown(attach=False)

    def _resolve_clipboard_countdown(self, attach):
        # Grab the pending values before cancelling - cancel clears them.
        image = self._pending_clipboard_image
        text = self._pending_clipboard_text

        self._cancel_clipboard_countdown()

        if attach and image is not None:
            self.current_image = image
            self._update_preview()

        if attach and text:
            # Prefix the clipboard text into the input box rather than
            # dropping it - the user's own typing continues right after it,
            # nothing they type gets overwritten.
            self.input_box.insert("1.0", text)

        if attach and (image is not None or text):
            self.status_label.configure(text="Clipboard content attached - type a message and send")
        else:
            self.status_label.configure(text="Type a message and send")

    def _cancel_clipboard_countdown(self):
        if self._clipboard_countdown_after_id is not None:
            self.root.after_cancel(self._clipboard_countdown_after_id)
            self._clipboard_countdown_after_id = None
        if self.clipboard_prompt_frame is not None:
            self.clipboard_prompt_frame.pack_forget()
        self._pending_clipboard_image = None
        self._pending_clipboard_text = None

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
        self.bottom_frame = bottom_frame

        self.status_label = tk.Label(self.window, text="", anchor="w")
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=8)

        # Clipboard attach-or-not prompt row (small, sits just above the
        # input box). Hidden until a capture with clipboard content comes
        # in - _start_clipboard_countdown()/_cancel_clipboard_countdown()
        # pack/unpack it as needed.
        self.clipboard_prompt_frame = tk.Frame(self.window)
        self.clipboard_prompt_label = tk.Label(
            self.clipboard_prompt_frame, anchor="w", font=("TkDefaultFont", 8)
        )
        self.clipboard_prompt_label.pack(side=tk.LEFT)
        self.clipboard_no_btn = tk.Button(
            self.clipboard_prompt_frame, text="No", width=4, command=self._on_clipboard_no
        )
        self.clipboard_no_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self.clipboard_yes_btn = tk.Button(
            self.clipboard_prompt_frame, text="Yes", width=4, command=self._on_clipboard_yes
        )
        self.clipboard_yes_btn.pack(side=tk.RIGHT)
        # Not packed here - _start_clipboard_countdown() packs it as needed.

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
        self._cancel_clipboard_countdown()
        self.window.withdraw()

    def _on_enter_key(self, event):
        # Enter sends the message; Shift+Enter (bound separately above)
        # falls through to the default behavior and inserts a newline.
        self._on_send()
        return "break"

    def _on_send(self):
        # If the clipboard-attach countdown is still running, sending
        # manually counts as the user's own decision - stop the countdown
        # without attaching anything further.
        self._cancel_clipboard_countdown()

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
        self._stream_started = False
        append_log("Send clicked, sending to backend (stream)")

        threading.Thread(
            target=self._send_to_backend_stream, args=(text, image), daemon=True
        ).start()

    def _send_to_backend_stream(self, text, image):
        # io_compiler.process_stream() parses the text/image into a
        # normalized request, streams the backend's response chunk-by-chunk
        # (calling on_chunk from THIS background thread), and returns a
        # normalized IOResponse once the stream finishes.
        def on_chunk(piece):
            self.root.after(0, self._on_stream_chunk, piece)

        try:
            response = compile_and_send_stream(text, image, on_chunk=on_chunk)
            if response.ok:
                self.root.after(0, self._on_stream_done, response.text, "Response received")
            else:
                self.root.after(0, self._on_stream_error, response.error)
        except Exception as exc:
            log_error("Overlay failed while streaming from the backend", exc)
            self.root.after(0, self._on_stream_error, "Error - check log for details")

    def _on_stream_chunk(self, piece):
        # Called on the main thread (via root.after) for every incremental
        # piece of text as it streams in. The first chunk clears the
        # "Thinking..." placeholder; every chunk after that just appends.
        self.chat_log.configure(state="normal")
        if not self._stream_started:
            self.chat_log.delete(self._assistant_body_start, tk.END)
            self._stream_started = True
        self.chat_log.insert(tk.END, piece)
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)

    def _on_stream_done(self, answer, status_message):
        # Re-render the final text once more so the saved/displayed message
        # exactly matches what the backend returned (covers the edge case
        # of a request that streamed no chunks at all, e.g. immediate
        # failure after the "Thinking..." placeholder was shown).
        self.chat_log.configure(state="normal")
        self.chat_log.delete(self._assistant_body_start, tk.END)
        self.chat_log.insert(tk.END, answer or "")
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)

        self.status_label.configure(text=status_message)
        self.send_btn.configure(state="normal")

    def _on_stream_error(self, error_message):
        # Same placeholder-replacement as a successful reply, but for
        # errors surfaced from io_compiler/backend (timeouts, invalid key,
        # empty response, connection failures, etc.) - never leaves the UI
        # stuck on "Thinking..." or frozen.
        self.chat_log.configure(state="normal")
        self.chat_log.delete(self._assistant_body_start, tk.END)
        self.chat_log.insert(tk.END, error_message or "Error")
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)

        self.status_label.configure(text=error_message or "Error")
        self.send_btn.configure(state="normal")

