from dataclasses import dataclass
from typing import Optional

from utils.logging_utils import append_log, log_error

# Providers the "Model provider" dropdown in the overlay offers, mapped to
# the env var name their key will eventually be written under in .env.
# Keep this in sync with .env.example.
PROVIDERS = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "OpenRouter": "OPENROUTER_API_KEY",
}


@dataclass
class ConfigRequest:

    # Selected in the provider dropdown, e.g. "Gemini"
    provider: str = ""

    # Pasted by the user - not validated here, an invalid key is still
    # accepted so the rest of the form stays usable
    api_key: str = ""

    # Free-text label the user picks for this model, e.g. "my-gemini-model"
    custom_model_name: str = ""

    # The model string litellm_params.model expects, e.g. "gemini/gemini-3.5-flash"
    model_name: str = ""

    @property
    def is_complete(self) -> bool:
        return all([self.provider, self.api_key, self.custom_model_name, self.model_name])


@dataclass
class ConfigResult:

    # Whether the request was accepted
    ok: bool = True

    # Human-readable message the overlay can show in its status label
    message: str = ""

    @property
    def error(self) -> Optional[str]:
        return None if self.ok else self.message


def save_configuration(request: ConfigRequest) -> ConfigResult:
    """
    Entry point overlay.py calls when the user hits "Save" on the settings
    panel. This is currently a stub: it just confirms the data arrived
    intact and logs it, so overlay.py can be wired up and tested end to end
    before the real pipeline exists.

    The real implementation (next step) will, in order:
      1. Write request.api_key into .env under PROVIDERS[request.provider]
      2. Insert (provider, custom_model_name, model_name) into the sqlite db
      3. Call a second function that reads the db and regenerates
         deployment/litellm/litellm_config.yaml
      4. Restart the litellm docker container (deployment/litellm/manager.py)
      5. Return success/failure for the overlay to display
    """

    if request.provider not in PROVIDERS:
        log_error(f"config_manager received unknown provider: '{request.provider}'")
        return ConfigResult(ok=False, message=f"Unknown provider '{request.provider}'")

    if not request.is_complete:
        log_error(f"config_manager received an incomplete request: {request}")
        return ConfigResult(ok=False, message="Missing one or more required fields")

    # For now, just prove the data made it here from the overlay.
    append_log(
        "config_manager received configuration submission:",
        f"  provider           = {request.provider}",
        f"  api_key             = {'*' * max(len(request.api_key) - 4, 0)}{request.api_key[-4:]}",
        f"  custom_model_name  = {request.custom_model_name}",
        f"  model_name          = {request.model_name}",
    )

    # TODO: steps 1-4 above go here.

    return ConfigResult(ok=True, message="Configuration received (not yet persisted)")


@dataclass
class HotkeyRequest:

    # Ordered list of key identifiers captured by the overlay's hotkey
    # recorder, e.g. ["Control_L", "Shift_L", "F9"]. These are raw Tk
    # keysyms for now - whatever normalization/mapping to pynput's Key
    # names (as used by windows/listener.py's HOTKEY constant) happens is
    # left for the real implementation.
    keys: list = None

    def __post_init__(self):
        if self.keys is None:
            self.keys = []

    @property
    def is_complete(self) -> bool:
        return bool(self.keys)


def save_hotkey(request: HotkeyRequest) -> ConfigResult:
    """
    Entry point overlay.py calls when the user records and saves a new
    global hotkey combo. Currently a stub, mirroring save_configuration():
    it just confirms the captured keys arrived intact and logs them.

    The real implementation (next step) will need to:
      1. Persist the new combo (sqlite, alongside the model config, or a
         small dedicated hotkey config file)
      2. Get windows/listener.py's running HOTKEY updated to match - since
         the listener process owns the pynput keyboard.Listener, this
         likely means either restarting the listener process or adding a
         "reload hotkey" signal it can pick up without a full restart
      3. Return success/failure for the overlay to display
    """

    if not request.is_complete:
        log_error(f"config_manager received an empty hotkey request: {request}")
        return ConfigResult(ok=False, message="No hotkey captured")

    append_log(
        "config_manager received hotkey submission:",
        f"  keys = {' + '.join(request.keys)}",
    )

    # TODO: steps 1-2 above go here.

    return ConfigResult(ok=True, message=f"Hotkey set to {' + '.join(request.keys)} (not yet persisted)")