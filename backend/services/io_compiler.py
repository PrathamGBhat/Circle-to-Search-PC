import base64
import io as _io
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PIL import Image

from backend.client import BackendError, send_to_backend, stream_to_backend
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
    def has_image(self) -> bool:
        return self.image is not None

@dataclass
class IOResponse:

    # Text
    text: str = ""

    # Error check
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

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


def compile_output(answer) -> IOResponse:

    # Answer
    if answer is None:
        return IOResponse(error="No response from backend")

    # Error
    if isinstance(answer, str) and answer.startswith("[Error:"):
        return IOResponse(error=answer)

    # Response object
    return IOResponse(text=answer)

def process(text: str = "", image: Optional[Image.Image] = None) -> IOResponse:

    # Accept input and complile request object
    io_request = compile_input(text=text, image=image)

    if not io_request.text and not io_request.has_image:
        return IOResponse(error="Nothing to send")

    if io_request.has_image:
        append_log("io_compiler: image attached (not yet sent to model - text-only backend)")

    # Get answer and compile response object
    try:
        answer = send_to_backend(io_request)
    except Exception as exc:
        log_error("io_compiler: backend call failed", exc)
        return IOResponse(error=str(exc))
    
    return compile_output(answer)


def process_stream(text: str = "", image: Optional[Image.Image] = None, on_chunk=None):
    """
    Streaming counterpart to process(). Compiles the request, then streams
    the backend's (grounded, vision-capable) response, calling
    on_chunk(piece) for every incremental piece of text as it arrives.

    Returns (IOResponse, timing) where timing is a dict with prep_time,
    request_start, first_token, total, and grounded - or None if the
    request never got far enough to produce timing info.
    """
    t_prep_start = time.monotonic()
    io_request = compile_input(text=text, image=image)
    prep_time = time.monotonic() - t_prep_start

    if not io_request.text and not io_request.has_image:
        return IOResponse(error="Nothing to send"), None

    if io_request.has_image:
        append_log(f"io_compiler: image prepared for send (prep={prep_time:.3f}s)")

    if on_chunk is None:
        on_chunk = lambda _piece: None

    try:
        result = stream_to_backend(io_request, on_chunk)
    except BackendError as exc:
        return IOResponse(error=str(exc)), None
    except Exception as exc:
        log_error("io_compiler: streaming backend call failed", exc)
        return IOResponse(error=str(exc)), None

    timing = result["timing"]
    timing["prep_time"] = prep_time

    return compile_output(result["text"]), timing