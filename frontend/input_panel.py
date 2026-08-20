import threading

import tkinter as tk

from backend.services.io_compiler import process_stream as compile_and_send_stream
from utils.logging_utils import append_log, log_error

INPUT_BOX_HEIGHT = 3

class InputPanelMixin:

    def _build_input_area(self, bottom_frame):
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

    def _on_enter_key(self, event):
        self._on_send()
        return "break"

    def _on_send(self):
        self._cancel_clipboard_countdown()

        text = self.input_box.get("1.0", "end-1c").strip()
        image = self.current_image

        if not text and image is None:
            return

        self._append_message("You", text, image=image)
        self.input_box.delete("1.0", tk.END)

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
