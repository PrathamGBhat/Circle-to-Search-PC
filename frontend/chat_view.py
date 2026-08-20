import tkinter as tk
from tkinter import scrolledtext
from PIL import ImageTk

CHAT_THUMB_SIZE = (140, 100)

class ChatViewMixin:

    def _build_chat_log(self):
        self.chat_log = scrolledtext.ScrolledText(
            self.window, wrap=tk.WORD, state="disabled", borderwidth=0
        )
        self.chat_log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
        self.chat_log.tag_configure("sender", font=("TkDefaultFont", 9, "bold"))

    def _append_message(self, sender, message, image=None):
        self.chat_log.configure(state="normal")
        if self.chat_log.index("end-1c") != "1.0":
            self.chat_log.insert(tk.END, "\n\n")
        self.chat_log.insert(tk.END, f"{sender}: ", ("sender",))
        body_start = self.chat_log.index("end-1c")

        if image is not None:
            thumb = image.copy()
            thumb.thumbnail(CHAT_THUMB_SIZE)
            photo = ImageTk.PhotoImage(thumb)
            self._chat_photos.append(photo)
            self.chat_log.image_create(tk.END, image=photo)
            if message:
                self.chat_log.insert(tk.END, "\n")

        self.chat_log.insert(tk.END, message or "")
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)
        return body_start

    def _on_stream_chunk(self, piece):
        self.chat_log.configure(state="normal")
        if not self._stream_started:
            self.chat_log.delete(self._assistant_body_start, tk.END)
            self._stream_started = True
        self.chat_log.insert(tk.END, piece)
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)

    def _on_stream_done(self, answer, status_message):
        self.chat_log.configure(state="normal")
        self.chat_log.delete(self._assistant_body_start, tk.END)
        self.chat_log.insert(tk.END, answer or "")
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)

        self.status_label.configure(text=status_message)
        self.send_btn.configure(state="normal")

    def _on_stream_error(self, error_message):
        self.chat_log.configure(state="normal")
        self.chat_log.delete(self._assistant_body_start, tk.END)
        self.chat_log.insert(tk.END, error_message or "Error")
        self.chat_log.configure(state="disabled")
        self.chat_log.see(tk.END)

        self.status_label.configure(text=error_message or "Error")
        self.send_btn.configure(state="normal")
