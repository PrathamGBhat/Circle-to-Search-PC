import os
import sys
import time
import subprocess

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.logging_utils import append_log, log_error

# Global config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMPOSE_FILE = os.path.join(BASE_DIR, "docker-compose.yml")
SERVICE_NAME = "litellm"
HEALTH_URL = "http://localhost:4000/health/liveliness"
TIMEOUT = 15
POLL_INTERVAL = 3

def _run(args, success):
    try:
    
        # Check if a container exists for this service
        cmd = args
        _CREATE_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        result = subprocess.run(
                cmd,
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                **_CREATE_NO_WINDOW,
            )

        # Handle failures if any
        if result is None or result.returncode != 0:
            log_error("Exists check failed with non-0 exit code")
            return False
    except FileNotFoundError as exc:
        log_error("Docker executable not found. Is Docker installed and on PATH?", exc)
        return False
    except subprocess.TimeoutExpired as exc:
        log_error(f"Command timed out: {' '.join(cmd)}", exc)
        return False

    append_log(f"Successful - {success}")
    return result.stdout.strip() # Return process ID if successful and "" or False if failed 


def exists_litellm():
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, "ps", "-a", "-q", SERVICE_NAME]
    return _run(cmd, "LiteLLM exists")

def is_running_litellm():
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, "ps", "--status", "running", "-q", SERVICE_NAME]
    return _run(cmd, "LiteLLM running")

def is_healthy_litellm():
    timeout = TIMEOUT
    deadline = time.time() + timeout

    # Poll health check URL till healthy or timeout
    while time.time() < deadline:
        try:
            response = requests.get(HEALTH_URL, timeout=3)
            if response.status_code == 200:
                append_log(f"'{SERVICE_NAME}' container is healthy")
                return True
        except requests.RequestException:
            pass

        time.sleep(POLL_INTERVAL)

    log_error(f"'{SERVICE_NAME}' container did not become healthy within {timeout}s")
    return False

def start_litellm():
    # Already running container
    if is_running_litellm():
        log_error("Container already running")
        return

    # Start container
    append_log(f"Starting '{SERVICE_NAME}' container...")
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d"]
    return _run(cmd, "LiteLLM started")

def stop_litellm():

    # Non existent container
    if not(exists_litellm()):
        log_error("Container doesn't exist")
        return

    # Already stopped container
    if not(is_running_litellm()):
        log_error("Container already stopped")
        return

    # Stop container
    append_log(f"Stopping '{SERVICE_NAME}' container...")
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, "down"]
    return _run(cmd, "LiteLLM stopped")


def restart_litellm():

    # Non existent container
    if not(exists_litellm()):
        log_error("Container doesn't exist, cannot restart")
        return

    # Already stopped container
    if not(is_running_litellm()):
        log_error("Container stopped, cannot restart")
        return

    # Restart container
    append_log(f"Restarting '{SERVICE_NAME}' container...")
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, "restart", SERVICE_NAME]
    return _run(cmd, "LiteLLM restarted")