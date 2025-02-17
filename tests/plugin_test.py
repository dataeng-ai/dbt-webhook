import dbt_webhook
import os
import pkgutil
import requests
import sys
import unittest
import warnings

from dbt.cli.main import dbtRunner, dbtRunnerResult
from dbt_common.invocation import get_invocation_id
from dbt_webhook import events
from dbt_webhook import plugin
import unittest.mock as mock


class TestDbtWebhook(unittest.TestCase):
    def setUp(self):
        warnings.simplefilter("ignore", DeprecationWarning)
        self.hook_messages: list[str] = []
        package_path = os.path.abspath("..")
        sys.path.append(package_path)
        self.dbt = dbtRunner(callbacks=[self._event_collector])
        self.cli_args = ['compile', '--no-send-anonymous-usage-stats', '--select', 'my_first_dbt_model', '--project-dir', "test_1"]
        os.environ["DBT_WEBHOOK_COMMAND_TYPE"] = self.cli_args[0]
        os.environ["DBT_WEBHOOK_AUTH_TOKEN"] = "somesecrettoken"
        self.post_patcher = mock.patch.object(requests, "post", autospec=True)
        self.post_mock = self.post_patcher.start()
    
    def tearDown(self):
        self.post_patcher.stop()

    def _event_collector(self, msg):
        if msg.info.code == "Z050" and msg.info.msg.startswith(events.MESSAGE_PREFIX):
            self.hook_messages.append(msg.info.msg)

    def test_initialization_started(self):
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)

        self.assertTrue(res.success)
        self.assertIn(events.PluginInit().prefixed_message(), self.hook_messages)

    def test_config_default_file(self):
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)

        self.assertIn(events.PluginConfigFoundFile(plugin.DEFAULT_CONIG_FILE_NAME).prefixed_message(), self.hook_messages)        
        self.assertTrue(res.success)

    def test_config_custom_file(self):
        custom_config = "dbt_webhook_custom_config.yml"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")

        self.assertIn(events.PluginConfigFoundFile(custom_config).prefixed_message(), self.hook_messages)        
        self.assertTrue(res.success)

    @mock.patch.object(plugin.dbtWebhook, "_get_config_file", return_value="")
    def test_no_config_file(self, _):
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)

        self.assertIn(events.PluginConfigNotFound().prefixed_message(), self.hook_messages)        
        self.assertTrue(res.success)

    def test_env_var_value_not_passed(self):
        env_var_name = "DBT_WEBHOOK_AUTH_TOKEN"
        env_var_val = os.environ.pop(env_var_name)

        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ[env_var_val] = env_var_name

        self.assertIn(events.EnvVariableValueNotPassed(env_var_name).prefixed_message(), self.hook_messages)        
        self.assertTrue(res.success)

    def test_env_var_not_defined(self):
        custom_config = "dbt_webhook_var_not_defined.yml"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")

        self.assertIn(
            events.HeaderValueRenderingError("SomeOtherHeader", "{DBT_MISSING_VAR}").prefixed_message(),
            self.hook_messages
        )
        self.assertTrue(res.success)

    def test_invalid_yaml(self):
        custom_config = "dbt_webhook_invalid_yaml.yml"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")

        search_str = events.ConfigReadError(Exception("")).prefixed_message()
        found = any([msg.startswith(search_str) for msg in self.hook_messages])
        self.assertTrue(found)
        self.assertTrue(res.success)

    def test_command_start_hook_success(self):
        custom_config = "dbt_webhook_command_start_hook.yml"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")

        self.post_mock.assert_called_once_with(
            url="a/b/c",
            headers={"Content-Type": "application/json"},
            json={
                "invocation_id": mock.ANY,
                "start_time": mock.ANY
            }
        )
        self.assertTrue(res.success)

    def test_command_end_hook_success(self):
        custom_config = "dbt_webhook_command_end_hook.yml"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")

        self.post_mock.assert_called_once_with(
            url="a/b/c",
            headers={"Content-Type": "application/json"},
            json={
                "invocation_id": mock.ANY,
                "start_time": mock.ANY,
                "completed_at_seconds": mock.ANY,
                "success": True,
            }
        )
        self.assertTrue(res.success)

    def test_model_start_hook_success(self):
        custom_config = "dbt_webhook_model_start_hook.yml"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")

        self.post_mock.assert_called_once_with(
            url="a/b/c",
            headers={"Content-Type": "application/json"},
            json={
                "invocation_id": mock.ANY,
                "target_database": mock.ANY,
                "target_schema": mock.ANY,
                "target_table_name": "my_first_dbt_model",
                "start_time": mock.ANY,
                "success": mock.ANY,
            }
        )
        self.assertTrue(res.success)

    def test_model_end_hook_success(self):
        custom_config = "dbt_webhook_model_end_hook.yml"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")

        self.post_mock.assert_called_once_with(
            url="a/b/c",
            headers={"Content-Type": "application/json"},
            json={
                "invocation_id": mock.ANY,
                "target_database": mock.ANY,
                "target_schema": mock.ANY,
                "target_table_name": "my_first_dbt_model",
                "start_time": mock.ANY,
                "end_time": mock.ANY,
                "success": mock.ANY,
            }
        )
        self.assertTrue(res.success)

    def test_model_hook_on_command_start_success(self):
        custom_config = "dbt_webhook_model_hook_on_command_start.yml"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")

        self.assertEqual(self.post_mock.call_count, 2)
        self.assertEqual(
            self.post_mock.call_args_list[0],
            mock.call(
                url="a/b/c",
                headers={"Content-Type": "application/json"},
                json={
                    "invocation_id": mock.ANY,
                    "target_database": mock.ANY,
                    "target_schema": mock.ANY,
                    "target_table_name": mock.ANY,
                    "start_time": mock.ANY,
                }
            )
        )
        self.assertTrue(res.success)

    def test_cmd_start_header_env_var(self):
        custom_config = "dbt_webhook_cmd_start_header_env_var.yml"
        bearer = "xyz"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        os.environ["DBT_WEBHOOK_AUTH_TOKEN"] = bearer
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")
        os.environ.pop("DBT_WEBHOOK_AUTH_TOKEN")

        self.post_mock.assert_called_once_with(
            url="a/b/c",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer}"},
            json=mock.ANY
        )
        self.assertTrue(res.success)

    def test_model_on_cmd_start_header_env_var(self):
        custom_config = "dbt_webhook_model_on_cmd_start_header_env_var.yml"
        bearer = "xyz"
        os.environ["DBT_WEBHOOK_CONFIG"] = custom_config
        os.environ["DBT_WEBHOOK_AUTH_TOKEN"] = bearer
        res: dbtRunnerResult = self.dbt.invoke(self.cli_args)
        os.environ.pop("DBT_WEBHOOK_CONFIG")
        os.environ.pop("DBT_WEBHOOK_AUTH_TOKEN")

        self.assertEqual(
            self.post_mock.call_args_list[0],
            mock.call(
                url="a/b/c",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer}"},
                json=mock.ANY
            )
        )
        self.assertTrue(res.success)


if __name__ == "__main__":
    unittest.main()
