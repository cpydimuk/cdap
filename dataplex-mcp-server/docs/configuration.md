# Configuration

This page documents every knob the Dataplex MCP Server exposes:
environment variables, authentication, IAM roles, transport, and
per-call overrides.

## Environment variables

| Variable | Purpose | Default | Required? |
| --- | --- | --- | --- |
| `DATAPLEX_PROJECT_ID` | Default Google Cloud project ID for tool calls. | — | One of this or `GOOGLE_CLOUD_PROJECT` must be set, unless every tool call passes `project_id` explicitly. |
| `GOOGLE_CLOUD_PROJECT` | Fallback default project ID. | — | Only used if `DATAPLEX_PROJECT_ID` is not set. |
| `DATAPLEX_LOCATION` | Default Dataplex region (e.g. `us-central1`). | — | Must be set unless every tool call passes `location` explicitly. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a service-account key JSON file. | — | Only if ADC cannot be resolved another way. |

Precedence for resolving project and location at a tool call site:

1. Explicit `project_id` / `location` arguments on the tool call.
2. `DataplexConfig` object passed into `DataplexClient`.
3. `DATAPLEX_PROJECT_ID` env var (or `GOOGLE_CLOUD_PROJECT` fallback).
4. `DATAPLEX_LOCATION` env var.

If neither layer resolves a value, the server raises a
`ValueError` with a clear message (`project_id is required…` or
`location is required…`).

## Authentication

The server uses **Application Default Credentials (ADC)** — it never
handles API keys directly. ADC is resolved in the following order by
the `google-auth` library:

1. `GOOGLE_APPLICATION_CREDENTIALS` environment variable pointing at a
   service-account key file.
2. User credentials from `gcloud auth application-default login`
   (stored under `~/.config/gcloud/application_default_credentials.json`).
3. The attached service account on GCE, GKE, Cloud Run, or Cloud
   Functions (metadata server).
4. Workload Identity Federation configured via a credentials file.

### Choosing a method

| Scenario | Recommendation |
| --- | --- |
| Local developer workstation | `gcloud auth application-default login` |
| Docker container on a dev laptop | Mount the gcloud ADC file read-only |
| CI / GitHub Actions | Use [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation) — avoid long-lived key files. |
| Cloud Run / GKE | Attach a service account with the right IAM roles. No key file needed. |
| Production VM | Use the attached service account via the metadata server. |

### Service account permissions

Grant the **minimum** role that covers your tool usage:

| Tools | Minimum role |
| --- | --- |
| Any `list_*` or `get_*` tool | `roles/dataplex.viewer` |
| `run_task`, `run_data_scan` | `roles/dataplex.editor` (or `roles/dataplex.dataScanJobRunner` + `roles/dataplex.taskUser` for finer grain) |
| Reading metadata via `list_entities`, `get_entity`, `list_partitions` | `roles/dataplex.metadataReader` (included in `viewer`) |

Grant on the project that hosts the Dataplex resources:

```bash
gcloud projects add-iam-policy-binding my-gcp-project \
  --member="serviceAccount:dataplex-mcp@my-gcp-project.iam.gserviceaccount.com" \
  --role="roles/dataplex.viewer"
```

## Per-call overrides

Every tool accepts `project_id` and `location` arguments. They
override the env-var defaults for that single call. This lets a single
running server inspect resources across multiple projects or regions
without restart.

Example MCP-host prompt that exercises overrides:

> "Compare the list of lakes in project `retail-prod` in `us-central1`
> with the lakes in project `retail-dev` in `europe-west1`."

The model will call `list_lakes` twice, supplying different
`project_id` / `location` each time.

## Transport

The server communicates over **stdio** — the default for
locally-hosted MCP servers. There is no HTTP or WebSocket endpoint.
The host launches the server as a subprocess and reads/writes
line-delimited MCP frames on the subprocess's stdin/stdout.

Logging is directed to **stderr** so it never collides with the MCP
protocol stream.

## Logging

The server uses the standard Python `logging` module under the
logger name `dataplex_mcp_server`. The default level is `INFO`. To
change it, export before launching:

```bash
export PYTHONLOGLEVEL=DEBUG    # or edit the host env block
```

Or inject configuration programmatically via `logging.basicConfig` if
you embed the server in another process.

## Client configuration (embedding)

When embedding `DataplexClient` directly (for scripts, tests, or a
different protocol layer), use `DataplexConfig`:

```python
from dataplex_mcp_server.dataplex_client import DataplexClient, DataplexConfig

client = DataplexClient(DataplexConfig(
    project_id="my-gcp-project",
    location="us-central1",
))
```

Or pull from the environment:

```python
client = DataplexClient(DataplexConfig.from_env())
```

`DataplexClient` is lazy: the underlying `DataplexServiceClient`,
`MetadataServiceClient`, and `DataScanServiceClient` are only
instantiated on first use, so construction is cheap and testable.

## Example host configurations

### Claude Desktop (macOS)

```json
{
  "mcpServers": {
    "dataplex-prod": {
      "command": "/Users/me/.venvs/dataplex/bin/dataplex-mcp-server",
      "env": {
        "DATAPLEX_PROJECT_ID": "retail-prod",
        "DATAPLEX_LOCATION": "us-central1",
        "GOOGLE_APPLICATION_CREDENTIALS": "/Users/me/.config/gcloud/prod-sa.json"
      }
    },
    "dataplex-dev": {
      "command": "/Users/me/.venvs/dataplex/bin/dataplex-mcp-server",
      "env": {
        "DATAPLEX_PROJECT_ID": "retail-dev",
        "DATAPLEX_LOCATION": "europe-west1",
        "GOOGLE_APPLICATION_CREDENTIALS": "/Users/me/.config/gcloud/dev-sa.json"
      }
    }
  }
}
```

Running two instances with different env blocks is the simplest way
to keep production and development lanes separate without exposing
write permissions on both at once.

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY dataplex-mcp-server/ /app/
RUN pip install --no-cache-dir .
ENTRYPOINT ["dataplex-mcp-server"]
```

Run with:

```bash
docker run --rm -i \
  -e DATAPLEX_PROJECT_ID=my-gcp-project \
  -e DATAPLEX_LOCATION=us-central1 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json \
  -v /path/to/sa.json:/secrets/sa.json:ro \
  dataplex-mcp-server:latest
```

The `-i` flag is required — stdio MCP servers must have stdin
attached.
