import os
import sys
import time

from dotenv import load_dotenv
from openai import (
    OpenAI,
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_utils import append_log, log_error
load_dotenv()

VISION_MODEL_GROQ = "my-groq-model"

# Use the Groq model by default; keep the env override for compatibility.
VISION_MODEL = VISION_MODEL_GROQ

REQUEST_TIMEOUT = float(os.getenv("MODEL_REQUEST_TIMEOUT_SECONDS", "45"))

client = OpenAI(
    api_key=os.getenv("LITELLM_MASTER_KEY"),
    base_url=os.getenv("LITELLM_BASE_URL"),
    timeout=REQUEST_TIMEOUT,
)

# Keep the assistant honest about what it can and cannot verify.
def _build_system_instructions():
    lines = [
        "You are a helpful assistant.",
        "- If the question needs current, external, or fast-changing information you "
        "don't already know, say so plainly instead of guessing.",
        "- Never invent facts, numbers, names, links, or sources. If you don't know "
        "and can't look it up, say so rather than confidently making something up.",
    ]

    return "\n".join(lines)


class BackendError(Exception):
    """Raised for any failure talking to the model backend. The message is
    already safe to show directly to the user."""


def _build_messages(text):
    content = [{"type": "text", "text": text or ""}]

    return [
        {"role": "system", "content": _build_system_instructions()},
        {"role": "user", "content": content},
    ]


def stream_to_backend(io_request, on_chunk):
    """Stream a text response from the configured Groq model."""
    text = io_request.text

    if not text:
        raise BackendError("Nothing to send")

    timing = {
        "request_start": time.monotonic(),
        "first_token": None,
        "total": None,
    }

    messages = _build_messages(text)

    append_log("Query sent (stream)")
    full_text_parts = []

    try:
        create_kwargs = dict(
            model=VISION_MODEL,
            messages=messages,
            stream=True,
        )
        stream = client.chat.completions.create(**create_kwargs)

        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if choices:
                delta = getattr(choices[0], "delta", None)
                piece = getattr(delta, "content", None) if delta else None
                if piece:
                    if timing["first_token"] is None:
                        timing["first_token"] = time.monotonic()
                    full_text_parts.append(piece)
                    on_chunk(piece)

    except AuthenticationError as e:
        log_error("Model client streaming failed: invalid API key", e)
        raise BackendError("Invalid API key - check the provider key in Settings") from e
    except RateLimitError as e:
        log_error("Model client streaming failed: rate limited", e)
        raise BackendError("Rate limited by the model provider - try again shortly") from e
    except APITimeoutError as e:
        log_error("Model client streaming failed: timed out", e)
        raise BackendError("Request timed out - the model took too long to respond") from e
    except APIConnectionError as e:
        log_error("Model client streaming failed: connection error", e)
        raise BackendError("Could not reach the LiteLLM proxy - is it running?") from e
    except APIStatusError as e:
        log_error("Model client streaming failed: API status error", e)
        raise BackendError(f"Model provider error ({e.status_code})") from e
    except APIError as e:
        log_error("Model client streaming failed: API error", e)
        raise BackendError(f"Model client request failed: {e}") from e
    except Exception as e:
        log_error("Model client streaming failed: unexpected error", e)
        raise BackendError(f"Unexpected error: {e}") from e

    timing["total"] = time.monotonic() - timing["request_start"]
    full_text = "".join(full_text_parts).strip()

    if not full_text:
        append_log("Streaming finished with an empty response")
        raise BackendError("The model returned an empty response - try again")

    ttft = (
        f"{(timing['first_token'] - timing['request_start']):.2f}s"
        if timing["first_token"] is not None else "n/a"
    )
    append_log(
        "Response received (stream)",
        "Q: " + text,
        "A: " + full_text,
        f"timing: total={timing['total']:.2f}s ttft={ttft}",
        "---",
    )

    return {"text": full_text, "timing": timing}


def send_to_backend(io_request):
    """Non-streaming convenience wrapper, kept for anything that still
    wants a single blocking call (e.g. backend/__init__.py exports it)."""
    try:
        result = stream_to_backend(io_request, on_chunk=lambda _piece: None)
        return result["text"]
    except BackendError as e:
        return f"[Error: {e}]"