import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_utils import append_log, log_error
load_dotenv()

# Global config
SYSTEM_PROMPT = """
                You are a helpful assistant.
                - If the question needs current, external, or fast-changing information you 
                don't already know, say so plainly instead of guessing.
                - Never invent facts, numbers, names, links, or sources. If you don't know
                and can't look it up, say so rather than confidently making something up.
                """

ACTIVE_MODEL = "my-groq-model"
REQUEST_TIMEOUT = 45

# LiteLLM client compatible with OpenAI
litellm_client = OpenAI(
    api_key=os.getenv("LITELLM_MASTER_KEY"),
    base_url=os.getenv("LITELLM_BASE_URL"),
    timeout=REQUEST_TIMEOUT,
)


def _build_input(text, image_b64, image_format):
    content = []

    # Append text to content
    if text:
        content.append({"type": "text", "text": text})

    # Append image to content
    if image_b64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/{image_format.lower()};base64,{image_b64}",
            },
        })

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def request_stream(io_request, on_chunk):

    # Extract required fields from request object
    text = io_request.text if io_request.has_text else ""

    image_b64 = io_request.image_b64 if io_request.has_image else None
    image_format = getattr(io_request, "image_format", "PNG")

    full_text_parts = [] # List to hold entire stream as single string

    # Send request and stream response chunks to callback on_chunk
    append_log("Query sent")
    try:
        message_content = _build_input(text, image_b64, image_format)
        create_kwargs = dict(
            model=ACTIVE_MODEL,
            messages=message_content,
            stream=True,
        )
        stream = litellm_client.chat.completions.create(**create_kwargs)

        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if choices:
                delta = getattr(choices[0], "delta", None)
                piece = getattr(delta, "content", None) if delta else None
                if piece:
                    full_text_parts.append(piece)
                    on_chunk(piece)

    except Exception as exc:
        log_error("Model client streaming failed", exc)
        raise

    full_text = "".join(full_text_parts).strip()

    # Return full text
    append_log(
        "Response received (stream)",
        "Q: " + text,
        "A: " + full_text
    )
    return {"text": full_text}