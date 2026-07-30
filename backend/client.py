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

def save_result(question, answer):
    append_log("Q: " + question,"A: " + answer, "---")

def send_to_backend(text):

    if not text:
        return

    append_log("Query sent")
    try:
        response = client.responses.create(model="my-groq-model", input=text)
        save_result(text, response.output_text)
        append_log("Response received")
        return response.output_text
    except Exception as e:
        log_error("Model client request failed", e)
        return f"[Error: model client request failed: {e}]"