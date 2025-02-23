# dbt-webhook
![PyPI version](https://img.shields.io/pypi/v/dbt-webhook)

A **dbt** plugin that allows defining HTTP hooks for DBT commands and/or models, triggering them at execution start/end, and injecting the returned data into the model's metadata.

## How It Works

Below is a diagram describing how the plugin works and the different types of hooks:

![dbt-webhook design](docs/images/dbt-webhook-design.svg)

---

## Getting Started

`dbt-webhook` is designed to work with **dbt-core**, allowing data infrastructure teams to extend functionality via additional Python packages.

To start using `dbt-webhook`, follow these three steps:

### **1. Install the dbt-webhook Package**
Install `dbt-webhook` in your local development environment and in the environment running scheduled jobs (e.g., **Airflow**):

```sh
pip install dbt-webhook
```
### **2. Create a dbt-webhook Configuration File**
Create in work dir file `dbt_webhook.yml` and configure hooks you want to run.

Example Configuration

``` yaml
command_start_hook:
  command_types:
    - "compile"
  webhook_url: "https;//domain.example.com/dbt/command/start"
  webhok_method: "POST"
  headers:
    Content-Type: "application/json"

command_end_hook:
    # Same schema as above

model_start_hook:
    # Same schema as above

model_end_hook:
    # Same schema as above
```

Configuration Notes:
- By default, the plugin will search for `dbt_webhook.yml` in the working directory:
  - In **VSCode** (when using the dbt Power User extension), this is the **workspace directory**.
  - In **Airflow**, the working directory may differ (e.g., the **project directory**).
  - If the local and scheduled work directories differ, you can create a **symlink to avoid duplicating** the configuration file.
- If the HTTP endpoint requires authentication, pass secrets via environment variables:

``` yaml
  headers:
    Authorization: "bearer {DBT_WEBHOOK_AUTH_TOKEN}"
    Content-Type: "application/json"
  env_vars:
    - "DBT_WEBHOOK_AUTH_TOKEN"
```

### **3. Create HTTP Endpoints**
The format of request and response payloads is defined in [dbt_webhook/webhook_model.py](dbt_webhook/webhook_model.py) using Pydantic models.


#### Command Hooks Request/Response Schema

``` json
{
    "command_type": "run",
    "invocation_id": "<UUID generated on dbt command start>",
    "run_started_at": "<timestamp>",
    "run_finished_at": "<timestamp>",
    "success": True | False | None
    "nodes": {
        "model.project.my_first_dbt_model": {
            "unique_id": "model.project.my_first_dbt_model",
            "meta": {"field1": 'val1'},
            "node_started_at": "<timestamp>",
            "node_finished_at": "<timestamp>",
            "target_database": "<db | project>",
            "target_schema": "<dataset | schema>",
            "target_table_name": "my_first_dbt_model",
            "success": True | False | None,
        },
        "<some other model unique id>": {...},
        ...
    },
}
```

#### Node Hooks Request/Response Schema
For node hooks, the schema is similar, but instead of a nodes dictionary, there is a single node object:

``` json
{
    "command_type": "run",
    "invocation_id": "<UUID generated on dbt command start>",
    "run_started_at": "<timestamp>",
    "run_finished_at": "<timestamp>",
    "success": True | False | None
    "node": {
        "unique_id": "model.project.my_first_dbt_model",
        "meta": {"field1": 'val1'},
        "node_started_at": "<timestamp>",
        "node_finished_at": "<timestamp>",
        "target_database": "<db | project>",
        "target_schema": "<dataset | schema>",
        "target_table_name": "my_first_dbt_model",
        "success": True | False | None,
    },
}
```

## Contributing
Contributions are welcome! Feel free to submit issues or open pull requests on GitHub.
