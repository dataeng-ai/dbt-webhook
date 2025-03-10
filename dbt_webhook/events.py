import traceback

from dbt_common.events.base_types import EventLevel
from dbt_common.events.event_manager_client import get_event_manager
from dbt_common.events.types import Note

MESSAGE_PREFIX = "[dbtWebhook]"


class BaseMessage:
    def message(self) -> str:
        raise NotImplementedError()
    
    def prefixed_message(self):
        return f"{MESSAGE_PREFIX}: {self.message()}"

    def to_note(self):
        return Note(msg=self.prefixed_message())


def debug(msg: BaseMessage):
    get_event_manager().fire_event(msg.to_note(), level=EventLevel.DEBUG)


def warn(msg: BaseMessage):
    get_event_manager().fire_event(msg.to_note(), level=EventLevel.WARN)


def info(msg: BaseMessage):
    get_event_manager().fire_event(msg.to_note(), level=EventLevel.INFO)


def error(msg: BaseMessage):
    get_event_manager().fire_event(msg.to_note(), level=EventLevel.ERROR)


class PluginInit(BaseMessage):
    def message(self) -> str:
        return "plugin initialization"


class PluginConfigNotFound(BaseMessage):
    def message(self) -> str:
        return (
            "plugin config not found, expected config passed " +
            "as `DBT_WEBHOOK_CONFIG` env variable or `dbt_webhook.yml` "+
            "file located in working directory."
        )


class PluginConfigFoundFile(BaseMessage):
    def __init__(self, file_path):
        self._file_path = file_path

    def message(self) -> str:
        return f"read config from `{self._file_path}` file"


class EnvVariableValueNotPassed(BaseMessage):
    def __init__(self, env_var: str):
        self._env_var = env_var

    def message(self) -> str:
        return f"config expects environment variable {self._env_var} which was not passed, will be used ''."""


class HeaderValueRenderingError(BaseMessage):
    def __init__(self, header_name: str, header_value: str):
        self._header_name = header_name
        self._header_value = header_value

    def message(self) -> str:
        return f"error rendering `{self._header_name}` header value: `{self._header_value}`."""


class ConfigReadError(BaseMessage):
    def __init__(self, err: Exception):
        self._err = err

    def message(self) -> str:
        return f"Error getting dbt webhook config: {self._err}"


class CommandTypeFetchError(BaseMessage):
    def __init__(self, err: Exception):
        self._err = err

    def message(self) -> str:
        return (
            "Error getting dbt command type. Command type can be passed as env var " +
            "`DBT_WEBHOOK_COMMAND_TYPE`, or fetched from args. {self._err}."
        )

class WebHookCallError(BaseMessage):
    def __init__(self, webhook_type: str, err: Exception):
        self._err = err
        self._webhook_type = webhook_type

    def message(self) -> str:
        return f"error calling webhook {self._webhook_type}: {self._err}"


class ServiceAccountIdentityToken(BaseMessage):
    def __init__(self, sa_email: str):
        self._sa_email = sa_email

    def message(self) -> str:
        return f"generated identity token for: {self._sa_email}"


class PluginUnanhandledError(BaseMessage):
    def __init__(self, err: Exception):
        self._err = err

    def message(self) -> str:
        traceback.print_exc()
        return f"unanhandled error: {self._err}"


class HttpRequest(BaseMessage):
    def __init__(self, url: str):
        self._url = url

    def message(self) -> str:
        return f"call http: {self._url}"
