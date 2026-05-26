# Dataplex MCP Server

**Version:** 0.1.0
**Status:** Alpha
**License:** Apache-2.0

The **Dataplex MCP Server** is a [Model Context Protocol](https://modelcontextprotocol.io/)
server that exposes [Google Cloud Dataplex](https://cloud.google.com/dataplex)
resources and operations as tools that any MCP-capable Large Language
Model (LLM) client can call. It lets an agent explore a Dataplex estate
in natural language — listing lakes, inspecting schemas, running data
quality scans, triggering tasks — without hand-writing gcloud or REST
calls.

## What is MCP?

The Model Context Protocol is an open standard that lets LLM
applications connect to external tools and data sources in a uniform
way. An **MCP server** exposes a set of named tools, each with a JSON
Schema describing its arguments. An **MCP host** (Claude Desktop,
Claude Code, Cursor, or any compatible client) discovers those tools
and surfaces them to the underlying model, which then chooses when to
call them.

## What this server exposes

Eighteen tools across five functional areas:

| Area | Tools |
| --- | --- |
| **Lakes / zones / assets** | `list_lakes`, `get_lake`, `list_zones`, `get_zone`, `list_assets`, `get_asset` |
| **Metadata** | `list_entities`, `get_entity`, `list_partitions` |
| **Tasks** | `list_tasks`, `get_task`, `run_task`, `list_jobs` |
| **Data scans (DQ & profile)** | `list_data_scans`, `get_data_scan`, `run_data_scan`, `list_data_scan_jobs`, `get_data_scan_job` |

All tools return JSON-serialized results that downstream models can
parse and reason over.

## Who should use it

- **Data platform teams** who want an LLM assistant that can answer
  questions like *"Which zones in our `retail` lake have failing data
  quality scans?"* or *"Trigger the `hourly-ingest` task and tell me
  when it's done."*
- **Analytics engineers** who want schema lookup and partition
  introspection from within their chat client.
- **Site reliability engineers** building runbooks that drive Dataplex
  operations from an AI copilot.

## Architecture at a glance

```text
┌────────────────┐  stdio/MCP  ┌────────────────────┐  gRPC   ┌──────────────────┐
│  MCP host      │ ──────────► │ Dataplex MCP       │ ──────► │ Google Cloud     │
│ (Claude, etc.) │ ◄────────── │ Server (this pkg)  │ ◄────── │ Dataplex API     │
└────────────────┘   JSON      └────────────────────┘         └──────────────────┘
```

The server is a thin adapter: the MCP layer handles protocol framing
and tool registration, a facade class wraps the `google-cloud-dataplex`
SDK, and every tool result is converted to a plain JSON object before
being returned to the host.

See [Architecture](architecture.md) for details.

## Documentation map

1. [Getting Started](getting-started.md) — install, authenticate, and
   make your first tool call.
2. [Configuration](configuration.md) — environment variables, defaults,
   authentication methods, IAM roles.
3. [Tool Reference](tools-reference.md) — every tool, its arguments,
   and its response shape.
4. [Architecture](architecture.md) — module layout, request flow,
   design decisions.
5. [Development](development.md) — contributing, testing, extending
   with new tools.
6. [Troubleshooting](troubleshooting.md) — common errors and fixes.

## Support

- **Issues / feature requests:** file a ticket in the parent CDAP
  repository.
- **Security disclosures:** follow the policy in the root `SECURITY.md`
  or `CONTRIBUTING.rst` of the repository.
