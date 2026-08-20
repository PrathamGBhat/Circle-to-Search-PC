import base64
import io as _io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PIL import Image

from backend.client import request_stream
from utils.logging_utils import append_log, log_error

@dataclass
class IORequest:

    # Request timestamp
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Text
    text: str = ""

    # Image
    image: Optional[Image.Image] = None
    image_b64: Optional[str] = None # base64-encoded copy, handy for API calls

    @property
    def has_text(self) -> bool:
        return bool(self.text)

    @property
    def has_image(self) -> bool:
        return self.image is not None

def _image_to_b64(image: Image.Image) -> str:
    buf = _io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def compile_input(text: str = "", image: Optional[Image.Image] = None) -> IORequest:

    # Text
    text = (text or "").strip()

    # Image
    image_b64 = _image_to_b64(image) if image is not None else None

    # Request object
    return IORequest(text=text, image=image, image_b64=image_b64)


@dataclass
class IOResponse:

    # Text
    text: str = ""

    # Error check
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

def compile_output(answer) -> IOResponse:

    # Answer
    if answer is None:
        return IOResponse(error="No response from backend")

    # Error
    if isinstance(answer, str) and answer.startswith("[Error:"):
        return IOResponse(error=answer)

    # Response object
    return IOResponse(text=answer)


def process_stream(text: str = "", image: Optional[Image.Image] = None, on_chunk=None):

    # Accept input and complile request object
    io_request = compile_input(text=text, image=image)

    if not io_request.has_text:
        append_log("No text attached")

    if not io_request.has_image:
        append_log("No image attached")

    if not io_request.has_text and not io_request.has_image:
        log_error("Request not sent - nothing to send")
        return IOResponse(error="Nothing to send")

    # Handle missing callback
    if on_chunk is None:
        append_log("Warning: Missing callback from overlay")
        on_chunk = lambda _piece: None # Streams to nowhere

    # Send to client, stream response and finally compile output to store in IOResponse
    try:
        result = request_stream(io_request, on_chunk)
    except Exception as exc:
        log_error("io_compiler: streaming backend call failed", exc)
        return IOResponse(error=str(exc))
    
    return compile_output(result["text"])