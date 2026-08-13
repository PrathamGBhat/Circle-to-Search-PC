import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_utils import append_log, log_error
load_dotenv()

VISION_MODEL = "my-gemini-model"

client = OpenAI(
    api_key=os.getenv("LITELLM_MASTER_KEY"), 
    base_url=os.getenv("LITELLM_BASE_URL")
)

def _build_input(text, image_b64, image_format):
    content = []

    # Append text to content
    if text:
        content.append({"type": "input_text", "text": text})

    # Append image to content
    if image_b64:
        content.append({
            "type": "input_image",
            "image_url": f"data:image/{image_format.lower()};base64,{image_b64}",
        })

    # Compiled input content
    return [{"role": "user", "content": content}]

def send_to_backend(io_request):

    # Accept required fields from request object
    text = io_request.text

    image_b64 = io_request.image_b64 if io_request.has_image else None
    image_format = getattr(io_request, "image_format", "PNG")

    if not text and not image_b64:
        return

    # Send to model provider - LiteLLM
    model = VISION_MODEL

    append_log("Query sent")
    try:
        response = client.responses.create(
            model=model, 
            input=_build_input(text, image_b64, image_format)
            )
        
        append_log("Response received")
        append_log("Q: " + text, "A: " + response.output_text, "---")
        return response.output_text
    except Exception as e:
        log_error("Model client request failed", e)
        return f"[Error: model client request failed: {e}]"