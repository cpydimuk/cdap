# Dataplex MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that
exposes Google Cloud [Dataplex](https://cloud.google.com/dataplex) as a
set of tools LLM clients can call. It lets an MCP-capable client (e.g.
Claude Desktop, Claude Code, or any other MCP host) browse lakes, zones,
assets, metadata entities, tasks, and data scans in a Dataplex estate,
and trigger on-demand runs of tasks and data scans.

## Features

The server exposes the following tools:

### Lakes / Zones / Assets
- `list_lakes` – List lakes in a project and location.
- `get_lake` – Fetch a single lake.
- `list_zones` – List zones in a lake.
- `get_zone` – Fetch a single zone.
- `list_assets` – List assets attached to a zone.
- `get_asset` – Fetch a single asset.

### Metadata (entities and partitions)
- `list_entities` – List tables or filesets in a zone.
- `get_entity` – Fetch a single entity including schema.
- `list_partitions` – List partitions for an entity.

### Tasks
- `list_tasks` – List tasks on a lake.
- `get_task` – Fetch a single task.
- `run_task` – Trigger an on-demand run of a task.
- `list_jobs` – List execution jobs for a task.

### Data scans (data quality and data profile)
- `list_data_scans` – List data scans in a project and location.
- `get_data_scan` – Fetch a single data scan (use `view=FULL` for full spec).
- `run_data_scan` – Trigger an on-demand run of a data scan.
- `list_data_scan_jobs` – List job runs for a data scan.
- `get_data_scan_job` – Fetch a specific data scan job (use `view=FULL` for rule-level findings).

All tool results are returned as JSON text content.

## Installation

Requires Python 3.10 or later.

```bash
cd dataplex-mcp-server
pip install -e .
```

This installs the package and the `dataplex-mcp-server` console script.

## Authentication

The server uses [Application Default Credentials
(ADC)](https://cloud.google.com/docs/authentication/application-default-credentials).
Either run:

```bash
gcloud auth application-default login
```

or set `GOOGLE_APPLICATION_CREDENTIALS` to a service account key file.
The identity used must have the Dataplex IAM permissions needed for the
operations you want to perform (for example
`roles/dataplex.viewer` for read-only use, or `roles/dataplex.editor`
to run tasks and data scans).

## Configuration

Two environment variables provide default values so that tool calls do
not need to repeat them:

| Variable | Description |
| --- | --- |
| `DATAPLEX_PROJECT_ID` | Default Google Cloud project ID. Falls back to `GOOGLE_CLOUD_PROJECT`. |
| `DATAPLEX_LOCATION` | Default region (e.g. `us-central1`). |

All tools also accept `project_id` and `location` arguments that
override the defaults on a per-call basis.

## Running

Run directly from the command line:

```bash
dataplex-mcp-server
```

Or as a module:

```bash
python -m dataplex_mcp_server
```

The server speaks MCP over stdio, which is the standard transport for
locally-hosted MCP servers.

## Claude Desktop / Claude Code configuration

Add the server to your MCP client configuration. For Claude Desktop
(`~/Library/Application Support/Claude/claude_desktop_config.json` on
macOS):

```json
{
  "mcpServers": {
    "dataplex": {
      "command": "dataplex-mcp-server",
      "env": {
        "DATAPLEX_PROJECT_ID": "my-gcp-project",
        "DATAPLEX_LOCATION": "us-central1",
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/key.json"
      }
    }
  }
}
```

For Claude Code, add a matching entry to your MCP server settings.

## Development

Install dev dependencies and run the test suite:

```bash
pip install -e '.[dev]'
pytest
ruff check .
```

## Project layout

```
dataplex-mcp-server/
├── pyproject.toml
├── README.md
├── src/dataplex_mcp_server/
│   ├── __init__.py
│   ├── __main__.py
│   ├── dataplex_client.py   # Google Cloud SDK facade
│   └── server.py            # MCP tool schemas + server setup
└── tests/
    └── test_dataplex_client.py
```

## License

Licensed under the Apache License, Version 2.0. See the root `LICENSE.txt`
of the CDAP repository for details.
