import os
import yaml

from dbt_common.events.event_manager_client import get_event_manager
from dbt_webhook import events
from enum import Enum
from pydantic import BaseModel

WEBHOOK_DATA = "{{ data | tojson }}"


class DynamicVarType(Enum):
    GCP_IDENTITY_TOKEN = "GCP_IDENTITY_TOKEN"


class baseHookConfig(BaseModel):
    """Command level hook config."""
    command_types: list[str] = ["run", "build"]
    webhook_url: str = ""
    webhok_method: str = "POST"
    webhook_request_data_template: str = WEBHOOK_DATA
    headers: dict[str, str] = {
        "Authorization": "bearer {DBT_WEBHOOK_AUTH_TOKEN}"
    }
    # expected that these environment variables passed outside
    env_vars: list[str] = []
    # these are run-time calculated values, key is environment variable name, value is how to calculate it
    dynamic_env_var_values: dict[str, DynamicVarType] = {}


class commandHookConfig(baseHookConfig):
    """Command level hook config."""
    pass


class modelHookConfig(baseHookConfig):
    """Model level hook config."""
    node_types: list[str] = ["model"]


class dbtWebhookConfig(BaseModel):
    """Configuration for dbt webhook."""

    command_start_hook: commandHookConfig | None = None
    command_end_hook: commandHookConfig | None = None
    model_start_hook: modelHookConfig | None = None
    model_end_hook: modelHookConfig | None = None

    @classmethod
    def from_yaml(cls, config_path: str) -> "dbtWebhookConfig":
        """Reads the dbt-webhook config file."""
        config: dbtWebhookConfig = None
        if os.path.exists(config_path):
            events.info(events.PluginConfigFoundFile(config_path))
            with open(config_path) as f:
                data = yaml.safe_load(f)
                config = dbtWebhookConfig(**data)
        else:
            events.warn(events.PluginConfigNotFound())
            config = dbtWebhookConfig()
        
        for sub_config in [
            config.command_start_hook,
            config.command_end_hook,
            config.model_start_hook,
            config.model_end_hook,
        ]:
            success = cls._validate_env_vars(sub_config)
            if not success:
                return None

        return config

    @classmethod
    def _validate_env_vars(cls, node_config: baseHookConfig) -> bool:
        success = True
        if not node_config or not node_config.headers:
            return success
        env_var_values = {}
        for var_name in node_config.dynamic_env_var_values:
            env_var_values[var_name] = ""
        for env_var in node_config.env_vars:
            env_var_values[env_var] = ""
            if env_var not in os.environ:
                events.warn(events.EnvVariableValueNotPassed(env_var))
                success = False
            
        for header_name, header_value in node_config.headers.items():
            try:
                header_value.format(**env_var_values)
            except Exception as ex:
                events.error(events.HeaderValueRenderingError(header_name, header_value))
                success = False
        return success
