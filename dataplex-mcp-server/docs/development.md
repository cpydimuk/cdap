# Development

Guide for contributors: repository layout, local setup, testing,
linting, and the recipe for adding new tools.

## Local setup

```bash
git clone https://github.com/cpydimuk/cdap.git
cd cdap/dataplex-mcp-server

python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

The `[dev]` extra pulls in `pytest`, `pytest-asyncio`, and `ruff`.

## Running tests

```bash
pytest                 # run all tests
pytest -v              # verbose
pytest tests/test_dataplex_client.py::test_lake_path
```

The existing suite avoids any real Google Cloud calls. A stub for
`google.cloud.dataplex_v1` is installed in `tests/test_dataplex_client.py`
before the client module is imported, so the tests run offline.

If you want to run **integration** tests against a real Dataplex
project, set `DATAPLEX_PROJECT_ID` / `DATAPLEX_LOCATION` and drive the
`DataplexClient` methods directly. Integration tests are intentionally
**not** committed to the repository — keep them out of CI unless you
gate them behind a secret-bearing environment.

## Linting and formatting

```bash
ruff check .
ruff format .
```

The project targets Python 3.10+ with these rule sets:
`E`, `F`, `W`, `I`, `B`, `UP` (see `[tool.ruff.lint]` in
`pyproject.toml`). Line length is 100 characters.

## Adding a new tool

The server is designed so that adding a tool is a three-step change
in at most two files. Worked example: let's add `cancel_job`, which
cancels a running Dataplex task job.

### Step 1 — add the operation to `DataplexClient`

Open `src/dataplex_mcp_server/dataplex_client.py` and add a method:

```python
def cancel_job(
    self,
    lake_id: str,
    task_id: str,
    job_id: str,
    project_id: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    name = (
        f"{self.task_path(project_id, location, lake_id, task_id)}"
        f"/jobs/{job_id}"
    )
    request = dataplex_v1.CancelJobRequest(name=name)
    # CancelJob returns google.protobuf.Empty; return a simple ack.
    self.dataplex.cancel_job(request=request)
    return {"cancelled": name}
```

Reuse existing path helpers wherever possible so that
project/location resolution stays in one place.

### Step 2 — register the tool in `server.py`

Inside `_build_tool_registry`, add a `register(...)` call in the
Tasks section:

```python
register(
    name="cancel_job",
    description="Cancel a running Dataplex task job.",
    schema=_schema(
        {
            "lake_id": {"type": "string"},
            "task_id": {"type": "string"},
            "job_id": {"type": "string"},
            **_LOCATION_PROPS,
        },
        required=["lake_id", "task_id", "job_id"],
    ),
    handler=lambda **kw: client.cancel_job(
        lake_id=kw["lake_id"],
        task_id=kw["task_id"],
        job_id=kw["job_id"],
        project_id=kw.get("project_id"),
        location=kw.get("location"),
    ),
)
```

### Step 3 — add tests

Add unit tests in `tests/test_dataplex_client.py` for any new path
helpers or argument parsing. You can also assert that the registry
contains the new tool:

```python
from dataplex_mcp_server.dataplex_client import DataplexClient, DataplexConfig
from dataplex_mcp_server.server import _build_tool_registry

def test_cancel_job_registered():
    client = DataplexClient(DataplexConfig(project_id="p", location="us-central1"))
    tools, handlers = _build_tool_registry(client)
    assert "cancel_job" in handlers
    tool = next(t for t in tools if t.name == "cancel_job")
    assert set(tool.inputSchema["required"]) == {"lake_id", "task_id", "job_id"}
```

### Step 4 — document it

Add an entry under the right section of `docs/tools-reference.md`.
Keep the argument table, return shape, and an example call consistent
with the existing entries.

## Conventions

- **Snake case everywhere.** Field names in responses use Dataplex's
  snake_case, preserved by `preserving_proto_field_name=True`.
- **Argument names match Dataplex resource segments** (`lake_id`,
  `zone_id`, `asset_id`, `entity_id`, `task_id`, `data_scan_id`,
  `job_id`). This keeps prompts and tool calls easy to reason about.
- **`filter_` in Python, `filter` in JSON schema.** Python reserves
  `filter`, so the Python signature uses `filter_`, but the MCP
  schema and user-facing argument name is `filter`.
- **Return dicts, not proto messages.** Always run results through
  `_to_dict` before handing them back to the server layer.
- **Fail loudly.** Validation errors should raise `ValueError`
  with a message that explains what was missing and how to fix it.

## Release checklist

When cutting a new version:

1. Bump `version` in `pyproject.toml` and `__init__.py`.
2. Update `SERVER_VERSION` in `server.py`.
3. Update `CHANGELOG.md` (create it the first time).
4. Run the full suite: `pytest && ruff check .`.
5. Tag the commit: `git tag dataplex-mcp-server-v0.2.0`.
6. Build and publish: `python -m build && twine upload dist/*`
   (if publishing to a package index).

## Continuous integration

The project currently relies on the parent CDAP build pipeline and
`pytest` / `ruff` run locally. When adding CI:

- Run tests on Python 3.10, 3.11, 3.12.
- Cache `~/.cache/pip`.
- Never set real Google Cloud credentials in public CI. Any
  integration tests must run in a private lane with Workload Identity
  Federation.

## Debugging tips

- **See raw MCP traffic.** Run the host with its debug flag (e.g.
  Claude Desktop's developer log) and look at the JSON frames going
  in and out.
- **Run a handler directly.** Use the smoke-test snippet from
  [Getting Started](getting-started.md#smoke-test) — it bypasses the
  MCP transport entirely and surfaces underlying API errors.
- **Enable SDK logging.**

  ```python
  import logging
  logging.getLogger("google.api_core").setLevel(logging.DEBUG)
  logging.getLogger("google.auth").setLevel(logging.DEBUG)
  ```

  Useful for diagnosing permission and auth errors.
