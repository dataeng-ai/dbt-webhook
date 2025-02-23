from pydantic import BaseModel
from typing import Any


class Node(BaseModel):
    unique_id: str | None = None
    target_database: str | None = None
    target_schema: str | None = None
    target_table_name: str | None = None
    node_started_at: str | None = None
    node_finished_at: str | None = None
    success: bool | None = None
    meta: dict[str, Any] = {}


class CommandBase(BaseModel):
    command_type: str | None = None
    invocation_id: str | None = None
    run_started_at: str | None = None
    run_finished_at: str | None = None
    success: bool | None = None


class WebhookNode(CommandBase):
    node: Node | None = None


class WebhookCommand(CommandBase):
    nodes: dict[str, Node] = {}

    def get_webhook_node(self, unique_id: str) -> WebhookNode:
        if unique_id not in self.nodes:
            raise KeyError(f"Node {unique_id} not exists")
        attributes = self.model_dump(exclude={"nodes"})

        return WebhookNode(**attributes, node=self.nodes[unique_id])
