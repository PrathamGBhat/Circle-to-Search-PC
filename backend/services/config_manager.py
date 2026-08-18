from dataclasses import dataclass
from typing import Optional

from utils.logging_utils import append_log, log_error

# Providers the "Model provider" dropdown in the overlay offers, mapped to
# the env var name their key will eventually be written under in .env.
# Keep this in sync with .env.example.
PROVIDERS = {
    "Groq": "GROQ_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
    "Anthropic": "ANTHROPIC_API_KEY",
    "Gemini": "GEMINI_API_KEY",
    "DeepSeek": "DEEPSEEK_API_KEY",
    "Mistral": "MISTRAL_API_KEY",
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