"""MCP server exposing Google Cloud Dataplex operations.

The server is built on the low-level ``mcp.server.Server`` API so that
tool schemas can be declared explicitly. Communication uses stdio, which
is the standard transport for locally-hosted MCP servers.

Authentication uses Google Cloud Application Default Credentials (ADC).
Run ``gcloud auth application-default login`` or set the
``GOOGLE_APPLICATION_CREDENTIALS`` environment variable before starting
the server.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from .dataplex_client import DataplexClient, DataplexConfig

logger = logging.getLogger("dataplex_mcp_server")

SERVER_NAME = "dataplex-mcp-server"
SERVER_VERSION = "0.1.0"


# ---------------------------------------------------------------------- #
# Tool schema definitions.
#
# Each entry pairs the MCP tool metadata with the Python callable that
# implements it. Arguments are passed through as keyword arguments.
# ---------------------------------------------------------------------- #
_LOCATION_PROPS = {
    "project_id": {
        "type": "string",
        "description": (
            "Google Cloud project ID. Defaults to DATAPLEX_PROJECT_ID or "
            "GOOGLE_CLOUD_PROJECT when omitted."
        ),
    },
    "location": {
        "type": "string",
        "description": (
            "Google Cloud region (e.g. 'us-central1'). Defaults to "
            "DATAPLEX_LOCATION when omitted."
        ),
    },
}

_PAGING_PROPS = {
    "page_size": {
        "type": "integer",
        "description": "Maximum number of results to return per page.",
        "minimum": 1,
        "maximum": 1000,
    },
    "filter": {
        "type": "string",
        "description": "Optional Dataplex filter expression.",
    },
}


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _build_tool_registry(
    client: DataplexClient,
) -> tuple[list[types.Tool], dict[str, Callable[..., Any]]]:
    """Return the MCP tool list and a handler map keyed by tool name."""

    tools: list[types.Tool] = []
    handlers: dict[str, Callable[..., Any]] = {}

    def register(
        name: str,
        description: str,
        schema: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        tools.append(
            types.Tool(name=name, description=description, inputSchema=schema)
        )
        handlers[name] = handler

    # ---------------- Lakes ----------------
    register(
        name="list_lakes",
        description=(
            "List Dataplex lakes in a given Google Cloud project and location."
        ),
        schema=_schema({**_LOCATION_PROPS, **_PAGING_PROPS}),
        handler=lambda **kw: client.list_lakes(
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            page_size=kw.get("page_size"),
            filter_=kw.get("filter"),
        ),
    )
    register(
        name="get_lake",
        description="Fetch details of a single Dataplex lake by ID.",
        schema=_schema(
            {
                "lake_id": {"type": "string", "description": "Lake identifier."},
                **_LOCATION_PROPS,
            },
            required=["lake_id"],
        ),
        handler=lambda **kw: client.get_lake(
            lake_id=kw["lake_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
        ),
    )

    # ---------------- Zones ----------------
    register(
        name="list_zones",
        description="List zones inside a Dataplex lake.",
        schema=_schema(
            {
                "lake_id": {"type": "string", "description": "Parent lake identifier."},
                **_LOCATION_PROPS,
                **_PAGING_PROPS,
            },
            required=["lake_id"],
        ),
        handler=lambda **kw: client.list_zones(
            lake_id=kw["lake_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            page_size=kw.get("page_size"),
            filter_=kw.get("filter"),
        ),
    )
    register(
        name="get_zone",
        description="Fetch details of a single Dataplex zone.",
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                "zone_id": {"type": "string"},
                **_LOCATION_PROPS,
            },
            required=["lake_id", "zone_id"],
        ),
        handler=lambda **kw: client.get_zone(
            lake_id=kw["lake_id"],
            zone_id=kw["zone_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
        ),
    )

    # ---------------- Assets ----------------
    register(
        name="list_assets",
        description="List assets attached to a Dataplex zone.",
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                "zone_id": {"type": "string"},
                **_LOCATION_PROPS,
                **_PAGING_PROPS,
            },
            required=["lake_id", "zone_id"],
        ),
        handler=lambda **kw: client.list_assets(
            lake_id=kw["lake_id"],
            zone_id=kw["zone_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            page_size=kw.get("page_size"),
            filter_=kw.get("filter"),
        ),
    )
    register(
        name="get_asset",
        description="Fetch details of a single Dataplex asset.",
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                "zone_id": {"type": "string"},
                "asset_id": {"type": "string"},
                **_LOCATION_PROPS,
            },
            required=["lake_id", "zone_id", "asset_id"],
        ),
        handler=lambda **kw: client.get_asset(
            lake_id=kw["lake_id"],
            zone_id=kw["zone_id"],
            asset_id=kw["asset_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
        ),
    )

    # ---------------- Entities / Metadata ----------------
    register(
        name="list_entities",
        description=(
            "List metadata entities (tables or filesets) in a Dataplex zone. "
            "Set view to 'TABLES' or 'FILESETS'."
        ),
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                "zone_id": {"type": "string"},
                "view": {
                    "type": "string",
                    "enum": ["TABLES", "FILESETS"],
                    "description": "Entity view filter.",
                },
                **_LOCATION_PROPS,
                **_PAGING_PROPS,
            },
            required=["lake_id", "zone_id"],
        ),
        handler=lambda **kw: client.list_entities(
            lake_id=kw["lake_id"],
            zone_id=kw["zone_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            view=kw.get("view"),
            page_size=kw.get("page_size"),
            filter_=kw.get("filter"),
        ),
    )
    register(
        name="get_entity",
        description=(
            "Fetch details of a single Dataplex metadata entity, including "
            "its schema. Use view='FULL' (default) for full details."
        ),
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                "zone_id": {"type": "string"},
                "entity_id": {"type": "string"},
                "view": {
                    "type": "string",
                    "enum": ["BASIC", "FULL", "SCHEMA"],
                    "description": "Entity view level.",
                },
                **_LOCATION_PROPS,
            },
            required=["lake_id", "zone_id", "entity_id"],
        ),
        handler=lambda **kw: client.get_entity(
            lake_id=kw["lake_id"],
            zone_id=kw["zone_id"],
            entity_id=kw["entity_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            view=kw.get("view"),
        ),
    )
    register(
        name="list_partitions",
        description="List partitions for a Dataplex metadata entity.",
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                "zone_id": {"type": "string"},
                "entity_id": {"type": "string"},
                **_LOCATION_PROPS,
                **_PAGING_PROPS,
            },
            required=["lake_id", "zone_id", "entity_id"],
        ),
        handler=lambda **kw: client.list_partitions(
            lake_id=kw["lake_id"],
            zone_id=kw["zone_id"],
            entity_id=kw["entity_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            page_size=kw.get("page_size"),
            filter_=kw.get("filter"),
        ),
    )

    # ---------------- Tasks ----------------
    register(
        name="list_tasks",
        description="List tasks defined on a Dataplex lake.",
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                **_LOCATION_PROPS,
                **_PAGING_PROPS,
            },
            required=["lake_id"],
        ),
        handler=lambda **kw: client.list_tasks(
            lake_id=kw["lake_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            page_size=kw.get("page_size"),
            filter_=kw.get("filter"),
        ),
    )
    register(
        name="get_task",
        description="Fetch details of a single Dataplex task.",
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                "task_id": {"type": "string"},
                **_LOCATION_PROPS,
            },
            required=["lake_id", "task_id"],
        ),
        handler=lambda **kw: client.get_task(
            lake_id=kw["lake_id"],
            task_id=kw["task_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
        ),
    )
    register(
        name="run_task",
        description=(
            "Trigger an on-demand run of a Dataplex task. Returns the created "
            "Job resource."
        ),
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                "task_id": {"type": "string"},
                **_LOCATION_PROPS,
            },
            required=["lake_id", "task_id"],
        ),
        handler=lambda **kw: client.run_task(
            lake_id=kw["lake_id"],
            task_id=kw["task_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
        ),
    )
    register(
        name="list_jobs",
        description="List execution jobs for a Dataplex task.",
        schema=_schema(
            {
                "lake_id": {"type": "string"},
                "task_id": {"type": "string"},
                **_LOCATION_PROPS,
                "page_size": _PAGING_PROPS["page_size"],
            },
            required=["lake_id", "task_id"],
        ),
        handler=lambda **kw: client.list_jobs(
            lake_id=kw["lake_id"],
            task_id=kw["task_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            page_size=kw.get("page_size"),
        ),
    )

    # ---------------- Data scans ----------------
    register(
        name="list_data_scans",
        description=(
            "List Dataplex data scans (data quality and data profile) in a "
            "project and location."
        ),
        schema=_schema({**_LOCATION_PROPS, **_PAGING_PROPS}),
        handler=lambda **kw: client.list_data_scans(
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            page_size=kw.get("page_size"),
            filter_=kw.get("filter"),
        ),
    )
    register(
        name="get_data_scan",
        description=(
            "Fetch a single Dataplex data scan. Use view='FULL' to include "
            "the full rule/spec definition."
        ),
        schema=_schema(
            {
                "data_scan_id": {"type": "string"},
                "view": {
                    "type": "string",
                    "enum": ["BASIC", "FULL"],
                    "description": "Data scan view level.",
                },
                **_LOCATION_PROPS,
            },
            required=["data_scan_id"],
        ),
        handler=lambda **kw: client.get_data_scan(
            data_scan_id=kw["data_scan_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            view=kw.get("view"),
        ),
    )
    register(
        name="run_data_scan",
        description="Trigger an on-demand run of a Dataplex data scan.",
        schema=_schema(
            {
                "data_scan_id": {"type": "string"},
                **_LOCATION_PROPS,
            },
            required=["data_scan_id"],
        ),
        handler=lambda **kw: client.run_data_scan(
            data_scan_id=kw["data_scan_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
        ),
    )
    register(
        name="list_data_scan_jobs",
        description="List job runs for a Dataplex data scan.",
        schema=_schema(
            {
                "data_scan_id": {"type": "string"},
                **_LOCATION_PROPS,
                "page_size": _PAGING_PROPS["page_size"],
            },
            required=["data_scan_id"],
        ),
        handler=lambda **kw: client.list_data_scan_jobs(
            data_scan_id=kw["data_scan_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            page_size=kw.get("page_size"),
        ),
    )
    register(
        name="get_data_scan_job",
        description=(
            "Fetch a single job run for a Dataplex data scan. Use view='FULL' "
            "to include full results including rule-level findings."
        ),
        schema=_schema(
            {
                "data_scan_id": {"type": "string"},
                "job_id": {"type": "string"},
                "view": {
                    "type": "string",
                    "enum": ["BASIC", "FULL"],
                    "description": "Data scan job view level.",
                },
                **_LOCATION_PROPS,
            },
            required=["data_scan_id", "job_id"],
        ),
        handler=lambda **kw: client.get_data_scan_job(
            data_scan_id=kw["data_scan_id"],
            job_id=kw["job_id"],
            project_id=kw.get("project_id"),
            location=kw.get("location"),
            view=kw.get("view"),
        ),
    )

    return tools, handlers


def build_server(client: DataplexClient | None = None) -> Server:
    """Build a configured MCP ``Server`` instance.

    Exposed as a standalone function so that tests can construct the
    server with an injected client.
    """
    client = client or DataplexClient()
    tools, handlers = _build_tool_registry(client)

    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return tools

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent]:
        handler = handlers.get(name)
        if handler is None:
            raise ValueError(f"Unknown tool: {name}")
        args = arguments or {}
        try:
            result = handler(**args)
        except Exception as exc:  # Surface SDK errors to the model clearly.
            logger.exception("Tool %s failed", name)
            payload = {"error": type(exc).__name__, "message": str(exc)}
            return [
                types.TextContent(
                    type="text", text=json.dumps(payload, indent=2, default=str)
                )
            ]
        return [
            types.TextContent(
                type="text", text=json.dumps(result, indent=2, default=str)
            )
        ]

    return server


async def _run() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "Starting %s v%s (defaults: project=%s, location=%s)",
        SERVER_NAME,
        SERVER_VERSION,
        DataplexConfig.from_env().project_id,
        DataplexConfig.from_env().location,
    )

    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    """Synchronous entry point used by the ``dataplex-mcp-server`` script."""
    import asyncio

    asyncio.run(_run())


if __name__ == "__main__":
    main()
