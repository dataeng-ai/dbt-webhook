import datetime
import json
import os
import requests

from dbt import tracking
from dbt.contracts.graph.manifest import Manifest
from dbt.contracts.graph.nodes import ManifestNode
from dbt.plugins.contracts import PluginArtifacts
from dbt.plugins.manager import dbt_hook, dbtPlugin
from dbt_common.events.base_types import EventMsg
from dbt_common.events.event_manager_client import get_event_manager
from dbt_common.invocation import get_invocation_id
from dbt_webhook import events
from dbt_webhook.webhook_model import WebhookCommand, CommandBase, Node
from dbt_webhook.config import dbtWebhookConfig, baseHookConfig, DynamicVarType
from dbt_webhook.dynamic_vars.gcp_id_token import GcpIdentityToken
from dbt.flags import get_flags
from jinja2 import Template


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
        self._config: dbtWebhookConfig | None = None
        self._nodes: dict[str, ManifestNode] = {}
        self._data = WebhookCommand(
            command_type=self._command_type,
            run_started_at=tracking.active_user.run_started_at.strftime("%Y-%m-%d %H:%M:%S.%f"),
            invocation_id=get_invocation_id(),
            nodes={},
        )
        super().__init__(project_name)

    def _get_config_file(self):
        return os.environ.get("DBT_WEBHOOK_CONFIG", DEFAULT_CONIG_FILE_NAME)

    def _get_command_type(self) -> str:
        cmd_type = os.environ.get("DBT_WEBHOOK_COMMAND_TYPE")
        if cmd_type:
            return cmd_type
        try:
            return get_flags().which
        except Exception as e:
            events.error(events.CommandTypeFetchError(e))

    def _call_hook(self, config: baseHookConfig, data: CommandBase) -> CommandBase:
        if not config or not config.webhook_url:
            return None
        if config.command_types and self._command_type not in config.command_types:
            return None

        headers = self._get_headers(config)
        template = Template(config.webhook_request_data_template)
        request_data = template.render(data=data.model_dump())
        request_data_json = json.loads(request_data)

        events.debug(events.HttpRequest(config.webhook_url))
        if config.webhok_method == "POST":
            response = requests.post(url=config.webhook_url, headers=headers, json=request_data_json)
        elif config.webhok_method == "PUT":
            response = requests.put(url=config.webhook_url, headers=headers, json=request_data_json)
        elif config.webhok_method == "GET":
            response = requests.get(url=config.webhook_url, headers=headers)

        response.raise_for_status()
        response_data = response.json()
        return data.__class__(**response_data)

    def _command_start_hook(self):
        if not self._config or not self._config.command_start_hook:
            return
        response: WebhookCommand = self._call_hook(self._config.command_start_hook, self._data)
        if not response:
            return
        for node in response.nodes.values():
            for meta_key, meta_value in node.meta.items():
                self._nodes[node.unique_id].config.meta[meta_key] = meta_value
                self._data.nodes[node.unique_id].meta[meta_key] = meta_value

    def _command_end_hook(self, msg: EventMsg):
        if not self._config or not self._config.command_end_hook:
            return
        finished_at_dt = datetime.datetime.fromtimestamp(msg.data.completed_at.seconds + msg.data.completed_at.nanos / 1e9)
        finished_at = finished_at_dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        self._data.run_finished_at = finished_at
        self._data.success = msg.data.success

        self._call_hook(self._config.command_end_hook, self._data)

    def _get_headers(self, node_config: baseHookConfig) -> dict[str, str]:
        if not node_config or not node_config.headers:
            return {}

        env_var_values = {}
        for var_name, var_type in node_config.dynamic_env_var_values.items():
            if var_type == DynamicVarType.GCP_IDENTITY_TOKEN:
                env_var_values[var_name] = GcpIdentityToken().get_value(node_config)
        for var_name in node_config.env_vars:
            if var_name not in os.environ:
                events.warn(events.EnvVariableValueNotPassed(var_name))
            env_var_values[var_name] = os.getenv(var_name, "")

        headers_ext = {}
        for header_name, header_value in node_config.headers.items():
            try:
                rendered_header_value = header_value.format(**env_var_values)
            except Exception as ex:
                events.error(events.HeaderValueRenderingError(header_name, header_value))
                return {}
            headers_ext[header_name] = rendered_header_value

        return headers_ext

    def _model_start_hook(self, msg: EventMsg) -> None:
        if not self._config or not self._config.model_start_hook:
            return
        if msg.data.node_info.resource_type not in self._config.model_start_hook.node_types:
            return

        unique_id = msg.data.node_info.unique_id
        self._data.nodes[unique_id].node_started_at = msg.data.node_info.node_started_at
        node = self._data.get_webhook_node(unique_id)
        self._call_hook(self._config.model_start_hook, node)

    def _model_end_hook(self, msg: EventMsg):
        if not self._config or not self._config.model_end_hook:
            return
        if msg.data.node_info.resource_type not in self._config.model_end_hook.node_types:
            return

        unique_id = msg.data.node_info.unique_id
        self._data.nodes[unique_id].node_finished_at = msg.data.node_info.node_finished_at
        self._data.nodes[unique_id].success = msg.data.node_info.node_status == "success"
        node = self._data.get_webhook_node(unique_id)
        self._call_hook(self._config.model_end_hook, node)

    def _init_node_model(self, node: ManifestNode):
        if node.resource_type != "model":
            return

        self._data.nodes[node.unique_id] = Node(
            unique_id=node.unique_id,
            target_database=node.database,
            target_schema=node.schema,
            target_table_name=node.alias,
            meta=node.config.meta,
        )
        self._nodes[node.unique_id] = node

    def _message_handler(self, msg: EventMsg) -> None:
        """
            Q024 - Began running node
            Q025 - Finished running node
            Q039 - command completed
        """
        if msg.info.code not in ("Q024", "Q025", "Q039"):
            return

        try:
            webhook_type = ""
            if msg.info.code == "Q024":
                webhook_type = "model_start_hook"
                self._model_start_hook(msg)
            elif msg.info.code == "Q025":
                webhook_type = "model_end_hook"
                self._model_end_hook(msg)
            elif msg.info.code == "Q039":
                webhook_type = "command_end_hook"
                self._command_end_hook(msg)
        except Exception as e:
            events.error(events.WebHookCallError(webhook_type, e))

    def initialize(self) -> None:
        try:
            self._config = dbtWebhookConfig.from_yaml(self._config_path)
        except Exception as e:
            events.error(events.ConfigReadError(e))

        get_event_manager().add_callback(self._message_handler)

    @dbt_hook
    def get_manifest_artifacts(self, manifest: Manifest) -> PluginArtifacts:
        try:
            if not self._config:
                return {}
            for node in manifest.nodes.values():
                self._init_node_model(node)

            self._command_start_hook()
        except Exception as e:
            events.error(events.PluginUnanhandledError(e))

        return {}
