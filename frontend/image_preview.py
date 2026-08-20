import tkinter as tk
from PIL import ImageTk

PREVIEW_THUMB_SIZE = (160, 120)

class ImagePreviewMixin:
    def _build_preview_widgets(self):
        self.preview_frame = tk.Frame(self.window)
        self.preview_label = tk.Label(self.preview_frame, anchor="w")
        self.preview_label.pack(side=tk.LEFT)
        self.remove_image_btn = tk.Button(
            self.preview_frame, text="Remove image", command=self._remove_image
        )
        self.remove_image_btn.pack(side=tk.RIGHT)

    def _update_preview(self):
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
