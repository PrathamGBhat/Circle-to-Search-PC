from dataclasses import dataclass, field
from typing import List, Optional

from utils.logging_utils import append_log, log_error

@dataclass
class ConfigRequest:
    
    # LLM config required by litellm
    custom_model_name: str = ""
    provider: str = ""
    model_name: str = ""
    api_key: str = ""

    # Hotkey config
    hotkey_keys: List[str] = field(default_factory=list)

    @property
    def is_hotkey_request(self) -> bool:
        return bool(self.hotkey_keys)

    @property
    def is_llm_request(self) -> bool:
        return all([self.custom_model_name, self.provider, self.model_name, self.api_key])


@dataclass
class ConfigResult:

    # Status and message
    ok: bool = True
    message: str = ""

    @property
    def error(self) -> Optional[str]:
        return None if self.ok else self.message

def _save_llm_config(request: ConfigRequest) -> ConfigResult:

    # Existing custom model name
    # TODO: Read from settings.json

    # Just append log for now to prove flow works
    append_log(
        "config_manager received configuration submission:",
        f"  provider           = {request.provider}",
        f"  api_key             = {'*' * max(len(request.api_key) - 4, 0)}{request.api_key[-4:]}",
        f"  custom_model_name  = {request.custom_model_name}",
        f"  model_name          = {request.model_name}",
    )

    return ConfigResult(ok=True, message="Configuration received (not yet persisted)")

def _save_hotkey(request: ConfigRequest) -> ConfigResult:

    # Just append log for now to prove flow works
    append_log(
        "config_manager received hotkey submission:",
        f"  keys = {' + '.join(request.hotkey_keys)}",
    )

    return ConfigResult(ok=True, message=f"Hotkey set to {' + '.join(request.hotkey_keys)} (not yet persisted)")

def save_configuration(request: ConfigRequest) -> ConfigResult:

    try:

        # Hotkey change
        if request.is_hotkey_request:
            _save_hotkey(request)

        # LLM config change
        if request.is_llm_request:
            _save_llm_config(request)
            
        return ConfigResult(ok=True, message=f"Request successful")

    except Exception as err:
        log_error(f"ConfigRequest failed with serverside error: '{err}'") 
        return ConfigResult(ok=False, message=f"Request failed serverside error. Check log for details") 