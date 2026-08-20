import tkinter as tk

CLIPBOARD_COUNTDOWN_SECONDS = 3

class ClipboardPromptMixin:
    def _build_clipboard_prompt_widgets(self):
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

    def _start_clipboard_countdown(self, image, text):
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
        image = self._pending_clipboard_image
        text = self._pending_clipboard_text

        self._cancel_clipboard_countdown()

        if attach and image is not None:
            self.current_image = image
            self._update_preview()

        if attach and text:
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
