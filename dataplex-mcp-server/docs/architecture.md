# Architecture

This page explains how the Dataplex MCP Server is structured, how a
request flows through it, and the design trade-offs behind the
current layout.

## Module layout

```
dataplex-mcp-server/
├── pyproject.toml               # packaging, deps, console script
├── README.md                    # short overview (points at docs/)
├── docs/                        # this documentation
├── src/dataplex_mcp_server/
│   ├── __init__.py              # package version
│   ├── __main__.py              # `python -m dataplex_mcp_server`
│   ├── dataplex_client.py       # Google Cloud SDK facade
│   └── server.py                # MCP server + tool registry
└── tests/
    └── test_dataplex_client.py  # path / config / enum tests
```

Three concepts worth naming up front:

- **`DataplexConfig`** — a frozen dataclass that holds the default
  project and location. Built from explicit arguments or from the
  environment via `DataplexConfig.from_env()`.
- **`DataplexClient`** — a facade over three Google Cloud service
  clients (`DataplexServiceClient`, `MetadataServiceClient`,
  `DataScanServiceClient`). It owns resource-path construction and
  converts proto responses to plain dicts.
- **Tool registry** — a list of `mcp.types.Tool` objects paired with
  callables, built in `server._build_tool_registry`. The MCP `Server`
  instance uses `handle_list_tools` and `handle_call_tool` handlers
  to route traffic through the registry.

## Request flow

```text
     ┌──────────────────┐
     │ MCP host         │  "list_lakes"
     │ (Claude, etc.)   │──┐
     └──────────────────┘  │
                           │ JSON-RPC over stdio
                           ▼
     ┌────────────────────────────────────────────┐
     │ mcp.server.Server                          │
     │  ├─ handle_list_tools  ─┐                  │
     │  └─ handle_call_tool    │                  │
     │        │                │                  │
     │        ▼                ▼                  │
     │   tool registry (name → Tool, handler)     │
     └────────────────────────┬───────────────────┘
                              │
                              ▼
     ┌────────────────────────────────────────────┐
     │ DataplexClient                             │
     │  ├─ resource-path helpers                  │
     │  ├─ _resolve_project / _resolve_location   │
     │  └─ dataplex / metadata / data_scan (lazy) │
     └────────────────────────┬───────────────────┘
                              │ gRPC
                              ▼
     ┌────────────────────────────────────────────┐
     │ google-cloud-dataplex SDK                  │
     │ (DataplexServiceClient, MetadataService…)  │
     └────────────────────────┬───────────────────┘
                              │ HTTPS / gRPC-Web
                              ▼
     ┌────────────────────────────────────────────┐
     │ Dataplex API (dataplex.googleapis.com)     │
     └────────────────────────────────────────────┘
```

Concretely, when the host calls `list_lakes`:

1. The host sends an MCP `tools/call` frame with
   `name="list_lakes"` and `arguments={...}`.
2. `handle_call_tool` looks up the handler by name and invokes it
   with the arguments as keyword arguments.
3. The handler (a lambda in the registry) calls
   `DataplexClient.list_lakes(...)`.
4. `DataplexClient` resolves the effective project/location, builds a
   `ListLakesRequest`, and dispatches it through the lazily-created
   `DataplexServiceClient`.
5. The SDK returns a paged iterator of proto messages; each is
   converted to a plain dict with `proto.Message.to_dict` (or
   `MessageToDict` as a fallback).
6. The resulting list is serialized to JSON via `json.dumps(..., default=str)`
   and wrapped in a single `TextContent` item in the MCP response.

## Design decisions

### Stdio transport

The server only supports stdio. Local subprocess transport is the
de-facto standard for single-user MCP servers and maps cleanly onto
the way MCP hosts already launch tools. HTTP/WebSocket support could
be added later with `mcp.server.sse` or a custom transport layer
without changing the tool registry.

### Low-level `mcp.server.Server` instead of `FastMCP`

`FastMCP` generates tool schemas from Python type hints. That's
ergonomic for small projects but hides what the MCP host actually
sees. Using the low-level `Server` API means every tool ships with
an **explicit JSON Schema**, so:

- Hosts get precise validation errors.
- Enums (`view`), numeric bounds (`page_size` 1–1000), and
  descriptions are first-class.
- The schema is trivially testable and diffable across versions.

### Facade class instead of raw SDK calls in the server

Three benefits:

- **Testability.** Path construction and config resolution can be
  unit-tested without the real SDK.
- **Lazy client construction.** `DataplexClient` only builds a given
  service client the first time it's used, so an entirely unused
  `DataScanServiceClient` never gets built.
- **Consistent error surface.** All SDK calls funnel through one
  place, making it easy to add retries, metrics, or caching later.

### Proto → dict conversion

Returning proto messages directly would require the host to
understand the Dataplex protobuf schema. Converting to JSON-friendly
dicts makes results self-describing and LLM-friendly, at the cost of
losing strict typing. `_to_dict` handles:

1. proto-plus messages (`proto.Message`) via their class-level
   `to_dict`.
2. Classic `google.protobuf.Message` via `MessageToDict`
   (`preserving_proto_field_name=True`, so field names stay snake_case).
3. Already-dict values, passed through untouched.
4. `None`, returned as `{}`.

### Error surfacing

Rather than letting exceptions propagate up and become opaque MCP
protocol errors, `handle_call_tool` catches them and returns a
JSON body with `error` and `message`. This gives the LLM something
it can read and act on (for example, retrying with a valid
argument).

### Single-file tool registry

All tool registrations live in one function, `_build_tool_registry`.
With 18 tools this is still easy to scan; if the server grows past
~40 tools, splitting the registry by functional area (lakes,
metadata, scans, tasks) is the obvious refactor.

## Extension points

Intentionally shaped so you can plug into them:

| Hook | How to use it |
| --- | --- |
| **Add a tool** | Add a `register(...)` call inside `_build_tool_registry`. |
| **Add a Dataplex operation** | Add a method on `DataplexClient`, then a tool that calls it. |
| **Inject a custom client (tests)** | `build_server(client=my_fake)` bypasses the default `DataplexClient`. |
| **Change transport** | Replace `stdio_server()` in `_run()` with another MCP transport. |
| **Add observability** | Wrap `DataplexClient` methods in a logging/metrics decorator; the server layer is untouched. |

## Dependency boundaries

```text
mcp.server  ──────┐
                  ├── server.py ──────── dataplex_client.py ──── google-cloud-dataplex
mcp.types   ──────┘
```

- `dataplex_client.py` depends on `google.cloud.dataplex_v1` but
  **not** on `mcp`.
- `server.py` depends on both — it is the only place the two
  worlds meet.
- Unit tests stub `google.cloud.dataplex_v1` so that
  `dataplex_client.py` can be exercised without network access.

This separation means the client class could be reused from a
different protocol layer (e.g. a REST wrapper, a CLI, or a different
MCP framing layer) with zero changes.
