import os
import sys
import threading

import tkinter as tk
from tkinter import scrolledtext
from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.services.io_compiler import process as compile_and_send
from backend.services.config_manager import ConfigRequest, PROVIDERS, save_configuration
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

# Settings panel geometry
SETTINGS_WINDOW_WIDTH = 360
SETTINGS_WINDOW_HEIGHT = 260

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

        # Settings panel (docker/model config). Built lazily on first open.
        self.settings_window = None
        self.settings_provider_var = None
        self.settings_provider_menu = None
        self.settings_api_key_entry = None
        self.settings_custom_model_entry = None
        self.settings_model_name_entry = None
        self.settings_save_btn = None
        self.settings_status_label = None

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

        # Top bar - just holds the settings button for now.
        top_frame = tk.Frame(self.window)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 0))
        settings_btn = tk.Button(
            top_frame, text="\u2699 Settings", command=self._open_settings
        )
        settings_btn.pack(side=tk.RIGHT)

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
        append_log("Send clicked, sending to backend")

        threading.Thread(
            target=self._send_to_backend, args=(text, image), daemon=True
        ).start()

    def _send_to_backend(self, text, image):
        # io_compiler.process() parses the text/image into a normalized
        # request, sends it to the backend, and returns a normalized
        # IOResponse we can render directly.
        try:
            response = compile_and_send(text, image)
            if response.ok:
                self.root.after(0, self._on_send_done, response.text, "Response received")
            else:
                self.root.after(0, self._on_send_done, response.error, response.error)
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

    # ------------------------------------------------------------------
    # Settings panel (docker/model config)
    #
    # Flow: user picks a provider from the dropdown and types an API key.
    # As soon as both are non-empty (the key is NOT validated - a wrong
    # key still unlocks the rest of the form) the custom model name and
    # litellm model name fields unlock. Save hands everything to
    # config_manager.save_configuration(), which for now just confirms it
    # received the data from here.
    # ------------------------------------------------------------------

    def _open_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.deiconify()
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        self._create_settings_window()

    def _create_settings_window(self):
        win = tk.Toplevel(self.root)
        win.title("Model Configuration")
        win.geometry(f"{SETTINGS_WINDOW_WIDTH}x{SETTINGS_WINDOW_HEIGHT}")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        self.settings_window = win

        form = tk.Frame(win)
        form.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        form.columnconfigure(1, weight=1)

        # Model provider dropdown
        tk.Label(form, text="Model provider").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.settings_provider_var = tk.StringVar(value="")
        self.settings_provider_menu = tk.OptionMenu(
            form, self.settings_provider_var, *PROVIDERS.keys(),
            command=lambda _choice: self._on_settings_unlock_check(),
        )
        self.settings_provider_menu.grid(row=0, column=1, sticky="ew", pady=(0, 8))

        # API key
        tk.Label(form, text="API key").grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.settings_api_key_entry = tk.Entry(form, show="*")
        self.settings_api_key_entry.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        self.settings_api_key_entry.bind("<KeyRelease>", lambda _e: self._on_settings_unlock_check())

        # Custom model name (locked until provider + api key are present)
        tk.Label(form, text="Custom model name").grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.settings_custom_model_entry = tk.Entry(form, state="disabled")
        self.settings_custom_model_entry.grid(row=2, column=1, sticky="ew", pady=(0, 8))

        # litellm_params.model name (locked until provider + api key are present)
        tk.Label(form, text="Model name (litellm)").grid(row=3, column=0, sticky="w", pady=(0, 8))
        self.settings_model_name_entry = tk.Entry(form, state="disabled")
        self.settings_model_name_entry.grid(row=3, column=1, sticky="ew", pady=(0, 8))

        hint = tk.Label(
            form,
            text="e.g. gemini/gemini-3.5-flash - see models.litellm.ai",
            anchor="w", font=("TkDefaultFont", 8), fg="gray30",
        )
        hint.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self.settings_save_btn = tk.Button(
            form, text="Save", state="disabled", command=self._on_save_settings
        )
        self.settings_save_btn.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))

        self.settings_status_label = tk.Label(form, text="", anchor="w", justify="left", wraplength=SETTINGS_WINDOW_WIDTH - 24)
        self.settings_status_label.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _on_settings_unlock_check(self):
        # Unlocks custom_model_name/model_name/Save as soon as a provider
        # is picked and *something* is typed as the API key. The key
        # itself is never validated here - even a wrong key unlocks the
        # rest of the form, per the intended UX.
        provider = self.settings_provider_var.get().strip()
        api_key = self.settings_api_key_entry.get().strip()
        unlock = bool(provider) and bool(api_key)

        new_state = "normal" if unlock else "disabled"
        self.settings_custom_model_entry.configure(state=new_state)
        self.settings_model_name_entry.configure(state=new_state)
        self.settings_save_btn.configure(state=new_state)

    def _on_save_settings(self):
        request = ConfigRequest(
            provider=self.settings_provider_var.get().strip(),
            api_key=self.settings_api_key_entry.get().strip(),
            custom_model_name=self.settings_custom_model_entry.get().strip(),
            model_name=self.settings_model_name_entry.get().strip(),
        )

        if not request.is_complete:
            self.settings_status_label.configure(
                text="Fill in custom model name and model name before saving.", fg="red"
            )
            return

        self.settings_save_btn.configure(state="disabled")
        self.settings_status_label.configure(text="Saving configuration...", fg="black")
        append_log("Settings Save clicked, sending config to config_manager")

        threading.Thread(
            target=self._send_settings_to_config_manager, args=(request,), daemon=True
        ).start()

    def _send_settings_to_config_manager(self, request):
        try:
            result = save_configuration(request)
            self.root.after(0, self._on_settings_save_done, result)
        except Exception as exc:
            log_error("Overlay failed while calling config_manager", exc)
            self.root.after(
                0, self._on_settings_save_done, None
            )

    def _on_settings_save_done(self, result):
        self.settings_save_btn.configure(state="normal")

        if result is None:
            self.settings_status_label.configure(
                text="Error - check log for details", fg="red"
            )
            return

        if result.ok:
            self.settings_status_label.configure(text=result.message or "Configuration set", fg="green")
        else:
            self.settings_status_label.configure(text=result.error or "Failed to save configuration", fg="red")