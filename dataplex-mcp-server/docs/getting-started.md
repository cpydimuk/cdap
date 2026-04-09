# Getting Started

This guide walks you through installing the Dataplex MCP Server,
authenticating to Google Cloud, connecting it to an MCP host, and
making your first tool call.

## Prerequisites

- **Python 3.10+** — check with `python --version`.
- **A Google Cloud project** with the Dataplex API enabled. Enable it
  with:
  ```bash
  gcloud services enable dataplex.googleapis.com
  ```
- **IAM permissions.** At minimum `roles/dataplex.viewer` on the
  project. Add `roles/dataplex.editor` if you want to use `run_task`
  or `run_data_scan`.
- **An MCP host** — Claude Desktop, Claude Code, or any other client
  that can launch a stdio MCP server.

## Install

### From source (recommended while in alpha)

```bash
git clone https://github.com/cpydimuk/cdap.git
cd cdap/dataplex-mcp-server
pip install -e .
```

The editable install exposes a `dataplex-mcp-server` console script.
Verify it:

```bash
which dataplex-mcp-server
dataplex-mcp-server --help 2>&1 || true   # the server speaks MCP; no CLI help
```

### Isolated install with a virtual environment

Recommended if you don't want to pollute your system Python:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Any MCP host launching the server needs to point to this virtualenv's
`dataplex-mcp-server` binary (or invoke `python -m dataplex_mcp_server`
using the virtualenv's Python).

## Authenticate

The server uses **Application Default Credentials (ADC)**. Choose the
method that matches your environment:

| Environment | Recommended method |
| --- | --- |
| Local developer workstation | `gcloud auth application-default login` |
| CI / build agent / container | `GOOGLE_APPLICATION_CREDENTIALS` pointing to a service-account key file |
| GCE, GKE, Cloud Run, Cloud Functions | Metadata server — no setup required |
| Workload Identity Federation | Configured credentials file via ADC |

For a user login:

```bash
gcloud auth application-default login
```

For a service-account key:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

> **Security note:** treat service-account key files like passwords.
> Prefer Workload Identity Federation or short-lived credentials in
> production.

## Set default project and region

Two environment variables let every tool call omit `project_id` and
`location`:

```bash
export DATAPLEX_PROJECT_ID=my-gcp-project
export DATAPLEX_LOCATION=us-central1
```

`DATAPLEX_PROJECT_ID` falls back to `GOOGLE_CLOUD_PROJECT` if unset.
You can always override per call by passing the arguments explicitly.

## Smoke test

Before wiring the server into an MCP host, confirm it can start and
talk to Dataplex. The quickest path is to call a handler directly:

```python
# smoke_test.py
from dataplex_mcp_server.dataplex_client import DataplexClient, DataplexConfig
from dataplex_mcp_server.server import _build_tool_registry

client = DataplexClient(DataplexConfig(
    project_id="my-gcp-project",
    location="us-central1",
))
_, handlers = _build_tool_registry(client)

print(handlers["list_lakes"]())
```

```bash
python smoke_test.py
```

A successful run prints a (possibly empty) list of lake dictionaries.
Errors point at authentication, permissions, or the wrong region; see
[Troubleshooting](troubleshooting.md).

## Connect to an MCP host

### Claude Desktop

Edit your Claude Desktop config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

Add a `dataplex` entry under `mcpServers`:

```json
{
  "mcpServers": {
    "dataplex": {
      "command": "dataplex-mcp-server",
      "env": {
        "DATAPLEX_PROJECT_ID": "my-gcp-project",
        "DATAPLEX_LOCATION": "us-central1",
        "GOOGLE_APPLICATION_CREDENTIALS": "/Users/me/.config/gcloud/sa.json"
      }
    }
  }
}
```

Restart Claude Desktop. The Dataplex tools appear in the tools panel.

### Claude Code (CLI)

```bash
claude mcp add dataplex -- dataplex-mcp-server
```

Then export the environment variables in the shell that launches
`claude`, or edit the generated MCP config entry to set them inline.

### Other MCP hosts

Any host that can launch a stdio MCP server works. Point the host at
the `dataplex-mcp-server` executable (or
`python -m dataplex_mcp_server`) and pass `DATAPLEX_PROJECT_ID`,
`DATAPLEX_LOCATION`, and `GOOGLE_APPLICATION_CREDENTIALS` via its
environment configuration.

## Your first prompt

With the server connected, ask the host something like:

> "List all Dataplex lakes in the project and summarize them."

The model will call `list_lakes`, receive a JSON array, and format it
into a human-readable summary. Follow-up prompts can drill down:

> "Show me the zones in the `retail` lake, and for each list the
> assets."

This chains `list_zones` → `list_assets` transparently.

## Next steps

- Read the [Tool Reference](tools-reference.md) for the full API
  surface.
- Learn how [Configuration](configuration.md) defaults and overrides
  interact.
- Extend the server with new tools in the [Development](development.md)
  guide.
