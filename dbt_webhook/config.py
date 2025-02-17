import os
import yaml

from dbt_common.events.event_manager_client import get_event_manager
from dbt_webhook import events
from pathlib import Path
from pydantic import BaseModel
from typing import Optional


class baseHookConfig(BaseModel):
    """Command level hook config."""
    command_types: list[str] = ["run", "build"]
    webhook_url: str = ""
    webhok_method: str = "POST"
    headers: dict[str, str] = {
        "Authorization": "bearer {DBT_WEBHOOK_AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    env_vars: list[str] = ["DBT_WEBHOOK_AUTH_TOKEN"]


class commandHookConfig(baseHookConfig):
    """Command level hook config."""
    pass


class modelHookConfig(baseHookConfig):
    """Model level hook config."""
    inject_meta: list[str] = []
    node_types: list[str] = ["model"]


class dbtWebhookConfig(BaseModel):
    """Configuration for dbt webhook."""

    command_start_hook: commandHookConfig | None = None
    command_end_hook: commandHookConfig | None = None
    model_start_hook: modelHookConfig | None = None
    model_end_hook: modelHookConfig | None = modelHookConfig()
    model_hook_on_command_start: modelHookConfig | None = modelHookConfig()

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
            config.model_hook_on_command_start,
        ]:
            success = cls._substitute_env_vars(sub_config)
            if not success:
                return None
        return config

    @classmethod
    def _substitute_env_vars(cls, node_config: baseHookConfig) -> bool:
        success = True
        if not node_config or not node_config.env_vars or not node_config.headers:
            return success
        headers_ext = {}
        env_var_values = {}
        for env_var in node_config.env_vars:
            if env_var not in os.environ:
                events.warn(events.EnvVariableValueNotPassed(env_var))
            env_var_values[env_var] = os.getenv(env_var, "")
        for header_name, header_value in node_config.headers.items():
            try:
                rendered_header_value = header_value.format(**env_var_values)
            except Exception as ex:
                events.error(events.HeaderValueRenderingError(header_name, header_value))
                success = False
            headers_ext[header_name] = rendered_header_value
        node_config.headers = headers_ext
        return success
