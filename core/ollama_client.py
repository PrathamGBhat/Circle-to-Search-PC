import os
import subprocess
import time
from pathlib import Path

import requests


MODULE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = MODULE_DIR.parent / "windows" / "ollama_output.txt"

# Ollama config
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_URL = OLLAMA_HOST + "/api/generate"
OLLAMA_MODEL = "qwen3:4b"  # change to whatever model you have pulled, e.g. "mistral", "phi3", etc.

# Server config
STARTUP_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 0.5

# Subprocess instruction
CREATE_NO_WINDOW = 0x08000000


def ping_server():

    # Return true if server responds and vice versa
    try:
        requests.get(OLLAMA_HOST, timeout=2)
        return True
    except requests.exceptions.RequestException:
        return False


def start_ollama():

    # Start server if offline
    if not ping_server():
        try:

            # Start subprocess
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )

            waited = 0

            # Poll till server ready or server timeout
            while waited < STARTUP_TIMEOUT_SECONDS:
                time.sleep(POLL_INTERVAL_SECONDS)
                waited += POLL_INTERVAL_SECONDS
                if ping_server():
                        return True # If server ready
            return False # If timeout

        # Handle exceptions
        except FileNotFoundError: # Ollama not installed
            return False
        except Exception:
            return False

    # If first ping is successful return True
    return True


def query_ollama(prompt):

    # Send prompt to ollama
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()

    # Handle exceptions
    except requests.exceptions.ConnectionError:
        return "[Error: could not connect to Ollama. Is 'ollama serve' running on localhost:11434?]"
    except requests.exceptions.Timeout:
        return "[Error: Ollama took too long to respond.]"
    except Exception as e:
        return f"[Error talking to Ollama: {e}]"


def save_result(question, answer):

    # Save output from ollama to file
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write("Q: " + question + "\n")
        f.write("A: " + answer + "\n")
        f.write("---\n")


# Endpoint hit by listener.py
def handle(text):

    # Handle missing text
    if not text:
        return

    # Handle offline server
    if not start_ollama():
        save_result(text, "[Error: Ollama server could not be started or did not respond in time.]")
        return

    # Query ollama
    answer = query_ollama(text)

    # Save answer to file
    save_result(text, answer)