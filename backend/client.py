import os
import sys
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_utils import append_log, log_error

client = OpenAI(
    api_key="sk-1234", 
    base_url="http://localhost:4000"
)

TEXT_MODEL = "my-groq-model"
VISION_MODEL = "my-gemini-model"

def _build_input(text, image_b64, image_format):
    if not image_b64:
        return text

    content = []

    if text:
        content.append({"type": "input_text", "text": text})

    content.append({
        "type": "input_image",
        "image_url": f"data:image/{image_format.lower()};base64,{image_b64}",
    })
    
    return [{"role": "user", "content": content}]

def send_to_backend(io_request):
    text = io_request.text
    image_b64 = io_request.image_b64 if io_request.has_image else None
    image_format = getattr(io_request, "image_format", "PNG")

    if not text and not image_b64:
        return

    model = VISION_MODEL if image_b64 else TEXT_MODEL

    append_log("Query sent")
    try:
        response = client.responses.create(
            model=model, 
            input=_build_input(text, image_b64, image_format)
            )
        append_log("Q: " + text, "A: " + response.output_text, "---")
        append_log("Response received")
        return response.output_text
    except Exception as e:
        log_error("Model client request failed", e)
        return f"[Error: model client request failed: {e}]"