from datetime import datetime
from pathlib import Path
import traceback

# Global config
ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT_DIR / "logs" /"log.txt"

def append_log(*lines):

    # Confirm parent directory exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(LOG_FILE, "a", encoding="utf-8") as log_file:

        # If no input, just return timestamp
        if not lines:
            log_file.write(f"[{timestamp}]\n")
            return

        # Else, enter line by line
        log_file.write(f"[{timestamp}]\n{lines[0]}\n")
        for line in lines[1:]:
            if line.endswith("\n"):
                log_file.write(line)
            else:
                log_file.write(f"{line}\n")


def log_error(message, exc=None):

    # Append error in log
    if exc is None:
        append_log(f"ERROR: {message}")
        return
    append_log(f"ERROR: {message}", *traceback.format_exception(type(exc), exc, exc.__traceback__))