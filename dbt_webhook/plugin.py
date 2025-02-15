import os
import requests
import sys

from dbt import tracking
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode
from dbt.plugins.contracts import PluginArtifacts
from dbt.plugins.manager import dbt_hook, dbtPlugin
from dbt_common.events.base_types import EventMsg
from dbt_common.events.event_manager_client import get_event_manager
from dbt_common.invocation import get_invocation_id
from dbt_webhook import events
from dbt_webhook.config import dbtWebhookConfig, modelHookConfig, commandHookConfig
from google.protobuf.message import Message

DEFAULT_CONIG_FILE_NAME = "dbt_webhook.yml"


class dbtWebhook(dbtPlugin):
    """
        DBT plugin allows:
            1) run webhook:
                - at start of command execution
                - at the end of command execution
                - at start of model execution
                - at the end of model execution
            2) inject return data from model.start hook to model meta.
    """

    def __init__(self, project_name: str):
        events.info(events.PluginInit())
        self._config_path = self._get_config_file()
        self._command_type = self._get_command_type()
        self._run_started_at = tracking.active_user.run_started_at.strftime("%Y-%m-%d %H:%M:%S")
        self._invocation_id = get_invocation_id()
        self._config: dbtWebhookConfig | None = None
        super().__init__(project_name)

    def _get_config_file(self):
        return os.environ.get("dbt_webhook_CONFIG", DEFAULT_CONIG_FILE_NAME)

    def _get_command_type(self) -> str:
        cmd_type = os.environ.get("dbt_webhook_COMMAND_TYPE")
        if cmd_type:
            return cmd_type
        if len(sys.argv) > 1:
            return sys.argv[1].lower()
        events.error(events.CommandTypeFetchError())
        return None

    def _call_command_start_hook(self):
        if not self._config.command_start_hook or not self._config.command_start_hook.webhook_url:
            return
        cfg = self._config.command_start_hook
        url = cfg.webhook_url

        webhock_data = {
            "invocation_id": self._invocation_id,
            "start_time": self._run_started_at,
        }
        
        if cfg.webhok_method == "POST":
            response = requests.post(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "PUT":
            response = requests.put(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "GET":
            response = requests.get(url=url, headers=cfg.headers)

        response.raise_for_status()

    def _call_command_end_hook(self, msg: EventMsg):
        if not self._config.command_end_hook or not self._config.command_end_hook.webhook_url:
            return
        cfg = self._config.command_end_hook
        url = cfg.webhook_url

        webhock_data = {
            "invocation_id": self._invocation_id,
            "start_time": self._run_started_at,
            "completed_at_seconds": msg.data.completed_at.seconds,
            "success": msg.data.success,
        }


        if cfg.webhok_method == "POST":
            response = requests.post(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "PUT":
            response = requests.put(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "GET":
            response = requests.get(url=url, headers=cfg.headers)

        response.raise_for_status()

    def _call_model_start_hook(self, msg: EventMsg) -> None:
        if not self._config.model_start_hook or not self._config.model_start_hook.webhook_url:
            return
        cfg = self._config.model_start_hook
        url = cfg.webhook_url
        if msg.data.node_info.resource_type != "model":
            return

        webhock_data = {
            "invocation_id": self._invocation_id,
            "target_database": msg.data.node_info.node_relation.database,
            "target_schema": msg.data.node_info.node_relation.schema,
            "target_table_name": msg.data.node_info.node_relation.alias,
            "start_time": msg.data.node_info.node_started_at,
            "success": msg.data.node_info.node_status == "success",
        }

        if cfg.inject_meta and msg.data.node_info.meta.fields:
            for meta_key in  cfg.inject_meta:
                meta_value = msg.data.node_info.meta.fields.get(meta_key)
                webhock_data[meta_key] = meta_value
        
        if cfg.webhok_method == "POST":
            response = requests.post(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "PUT":
            response = requests.put(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "GET":
            response = requests.get(url=url, headers=cfg.headers)

        response.raise_for_status()

    def _call_model_end_hook(self, msg: EventMsg):
        if not self._config.model_end_hook or not self._config.model_end_hook.webhook_url:
            return
        cfg = self._config.model_end_hook
        url = cfg.webhook_url
        if msg.data.node_info.resource_type != "model":
            return

        webhock_data = {
            "invocation_id": self._invocation_id,
            "target_database": msg.data.node_info.node_relation.database,
            "target_schema": msg.data.node_info.node_relation.schema,
            "target_table_name": msg.data.node_info.node_relation.alias,
            "start_time": msg.data.node_info.node_started_at,
            "end_time": msg.data.node_info.node_started_at,
            "success": msg.data.node_info.node_status == "success",
        }

        if cfg.inject_meta and msg.data.node_info.meta.fields:
            for meta_key in  cfg.inject_meta:
                meta_value = msg.data.node_info.meta.fields.get(meta_key)
                webhock_data[meta_key] = meta_value
        
        if cfg.webhok_method == "POST":
            response = requests.post(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "PUT":
            response = requests.put(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "GET":
            response = requests.get(url=url, headers=cfg.headers)

        response.raise_for_status()

    def _call_node_hook_on_command_start(self, node: ManifestNode):
        if not self._config.model_hook_on_command_start or not self._config.model_hook_on_command_start.webhook_url:
            return
        cfg = self._config.model_hook_on_command_start
        url = cfg.webhook_url

        if node.resource_type not in cfg.node_types:
            return

        webhock_data = {
            "invocation_id": self._invocation_id,
            "start_time": self._run_started_at,
            "target_database": node.database,
            "target_schema": node.schema,
            "target_table_name": node.alias,
        }

        if cfg.webhok_method == "POST":
            response = requests.post(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "PUT":
            response = requests.put(url=url, headers=cfg.headers, json=webhock_data)
        elif cfg.webhok_method == "GET":
            response = requests.get(url=url, headers=cfg.headers)

        response.raise_for_status()

        data = response.json()
        if not cfg.inject_meta:
            return
        for meta_key in cfg.inject_meta:
            node.meta[meta_key] = data.get(meta_key)

    def _message_handler(self, msg: EventMsg) -> None:
        """
            Q024 - Began running node
            Q025 - Finished running node
            Q039 - command completed
        """
        if msg.info.code not in ("Q024", "Q025", "Q039"):
            return

        try:        
            if msg.info.code == "Q024":
                self._call_model_start_hook(msg)
            elif msg.info.code == "Q025":
                self._call_model_end_hook(msg)
            elif msg.info.code == "Q039":
                self._call_command_end_hook(msg)
        except Exception as e:
            events.error(events.WebHookCallError(e))

    def initialize(self) -> None:
        try:
            self._config = dbtWebhookConfig.from_yaml(self._config_path)
        except Exception as e:
            events.error(events.ConfigReadError(e))

        if not self._command_type or not self._config:
            return

        self._call_command_start_hook()

        get_event_manager().add_callback(self._message_handler)

    @dbt_hook
    def get_manifest_artifacts(self, manifest: Manifest) -> PluginArtifacts:
        if not self._config or not self._config.model_hook_on_command_start:
            return {}

        for node in manifest.nodes.values():
            try:
                self._call_node_hook_on_command_start(node)
            except Exception as e:
                events.error(events.WebHookCallError(e))

        return {}
