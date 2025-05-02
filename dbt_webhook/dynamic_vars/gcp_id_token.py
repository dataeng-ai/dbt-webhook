import google.auth
import google.auth.transport.requests

from dbt_webhook import events
from dbt_webhook.config import baseHookConfig
from dbt_webhook.dynamic_vars.base import DynamicValueBase
from google.oauth2 import id_token

class GcpIdentityToken(DynamicValueBase):
    def get_value(self, node_config: baseHookConfig) -> str:
        """Gets an identity token using Application Default Credentials or a service account key."""

        credentials, _ = google.auth.default()
        audience = node_config.webhook_url
        request = google.auth.transport.requests.Request()
        if isinstance(credentials, google.oauth2.service_account.Credentials):
            events.debug(events.ServiceAccountIdentityToken(credentials.service_account_email))
            token = id_token.fetch_id_token(request, audience)
        else:
            credentials.refresh(request)
            token = credentials.id_token

        return token
