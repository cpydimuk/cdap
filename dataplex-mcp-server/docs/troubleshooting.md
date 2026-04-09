# Troubleshooting

Common errors when running the Dataplex MCP Server and how to resolve
them.

## Authentication and identity

### `DefaultCredentialsError: Could not automatically determine credentials`

ADC is not set up on the machine running the server. Pick one:

- Run `gcloud auth application-default login` for interactive user
  credentials.
- Set `GOOGLE_APPLICATION_CREDENTIALS` to a service-account key file
  path.
- On GCE/GKE/Cloud Run, attach a service account to the resource.

Then restart the MCP host so it re-launches the server with the new
environment.

### `PermissionDenied: 403 Permission 'dataplex.lakes.list' denied`

The identity the server is running as lacks Dataplex IAM roles.

```bash
gcloud projects add-iam-policy-binding MY_PROJECT \
  --member="user:me@example.com" \
  --role="roles/dataplex.viewer"
```

For service accounts:

```bash
gcloud projects add-iam-policy-binding MY_PROJECT \
  --member="serviceAccount:SA_EMAIL" \
  --role="roles/dataplex.viewer"
```

Use `roles/dataplex.editor` if you need `run_task` or `run_data_scan`.

### Wrong project used

Symptom: tools succeed but list resources from an unexpected project.

Cause: `GOOGLE_CLOUD_PROJECT` is set globally and shadowing your
intended project. Set `DATAPLEX_PROJECT_ID` explicitly to take
precedence, or pass `project_id` in the tool call.

## Configuration errors

### `ValueError: project_id is required`

Neither `project_id` was passed to the tool nor `DATAPLEX_PROJECT_ID`
/ `GOOGLE_CLOUD_PROJECT` is set. Fix by setting the env var in the
MCP host config:

```json
"env": {
  "DATAPLEX_PROJECT_ID": "my-gcp-project",
  "DATAPLEX_LOCATION": "us-central1"
}
```

### `ValueError: location is required`

Same cause for `DATAPLEX_LOCATION`. Dataplex is region-scoped, so a
location is always required.

### `ValueError: Invalid entity view 'X'`

The `view` argument only accepts `TABLES` or `FILESETS`
(for `list_entities`) or `BASIC`/`FULL`/`SCHEMA` (for `get_entity`).
Case is ignored.

## API errors

### `NotFound: 404`

The resource name doesn't exist in the target project/location.
Double-check IDs and the region — a lake in `us-central1` is not
visible from `europe-west1`.

### `InvalidArgument: Request contains an invalid argument`

Usually caused by a malformed filter expression. Start without a
filter, confirm the tool works, then add the filter incrementally.

See [tool reference](tools-reference.md#filter-expression-syntax) for
examples.

### `FailedPrecondition` when running a task or scan

The task or scan exists but is in a state that can't be run — for
example, a task currently disabled, or a data scan whose source
asset no longer exists. Use `get_task` / `get_data_scan` to inspect
state first.

### Long-running requests time out

The server does not currently impose its own timeout; timeouts come
from the gRPC layer. If you see `DeadlineExceeded`, the underlying
API call took too long. Options:

- Narrow the scope (smaller `page_size`, tighter filter).
- Fetch a single resource with `get_*` instead of listing.
- For data scan results, use `view=BASIC` first, and only fetch
  `view=FULL` for the specific job of interest.

## MCP host issues

### The host doesn't see the tools

Check, in order:

1. The host's MCP server config points at a real, executable binary.
   Run that binary manually to confirm it starts. If you use a
   virtualenv, the path must be the venv's `bin/dataplex-mcp-server`.
2. The host was **restarted** after the config change — most hosts
   only read the config on startup.
3. The host's logs show the server launching. Claude Desktop logs
   live at
   `~/Library/Logs/Claude/mcp*.log` on macOS.
4. No stdout writes from a custom wrapper script. Anything printed
   to stdout that isn't MCP framing will corrupt the stream.

### "Server exited immediately"

Usually an import error or missing dependency. Run the server
manually to see the traceback:

```bash
dataplex-mcp-server < /dev/null
```

If it prints a Python traceback, fix the underlying issue (missing
`google-cloud-dataplex`, wrong Python version, etc.) and try again.

### Tools appear but every call returns an error

Check the host logs for the error payload; the server returns a
JSON body like `{"error": "PermissionDenied", "message": "..."}`
rather than crashing. The `error` field is the Python exception
class, which maps directly to a Google API status.

## Protocol and framing

### JSON decode errors in the host logs

Something is writing non-MCP content to the server's stdout. Common
causes:

- A `print(...)` call accidentally left in custom code. Replace it
  with `logger.info(...)` — the server's logging goes to stderr.
- A wrapper script that echoes commands before exec'ing the server.

### Unicode issues on Windows

Force UTF-8 on the host launch by setting
`PYTHONIOENCODING=utf-8` in the MCP host's env block. The server
itself serializes responses with `json.dumps` which is
ASCII-safe by default.

## Performance

### Listing a large project is slow

Dataplex pagination defaults are generous; a single `list_lakes`
call in a project with hundreds of lakes can take several seconds.
Use a `filter` expression to narrow the result set — for example,
filtering on `labels.team=platform` or `state=ACTIVE`.

### Repeated identical calls are slow

The server does not cache responses. If you need caching — for
example, a model that repeatedly asks for the same schema — add a
memoizing decorator around the `DataplexClient` method or implement
a cache layer in the calling host.

## Still stuck?

1. Reproduce the problem with the smoke-test snippet from
   [Getting Started](getting-started.md#smoke-test). That bypasses
   MCP entirely and tells you whether the issue is Dataplex-side or
   MCP-side.
2. Enable Google SDK debug logging (see
   [Development](development.md#debugging-tips)).
3. File an issue in the parent CDAP repository with the tool call,
   the arguments, and the full error payload.
