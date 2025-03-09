from abc import ABC, abstractmethod
from dbt_webhook.config import baseHookConfig


class DynamicValueBase(ABC):
    @abstractmethod
    def get_value(self, node_config: baseHookConfig) -> str:
        raise NotImplementedError()
