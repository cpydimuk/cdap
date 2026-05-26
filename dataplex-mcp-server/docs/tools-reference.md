# Tool Reference

Complete reference for every tool exposed by the Dataplex MCP Server.

All tools accept optional `project_id` and `location` arguments that
override the environment defaults. Paging-capable tools accept
`page_size` (1–1000) and a Dataplex-style `filter` expression. Return
values are always JSON and mirror the shape of the underlying
Dataplex REST/gRPC resources.

Unless noted otherwise, errors propagate as MCP tool responses with a
JSON body of the shape:

```json
{ "error": "<ExceptionClassName>", "message": "<human-readable>" }
```

The underlying Google API error codes (`NotFound`, `PermissionDenied`,
etc.) are preserved in the exception class name.

---

## Lake tools

### `list_lakes`

List Dataplex lakes within a project/location.

**Arguments**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `project_id` | string | No | Overrides env default. |
| `location` | string | No | Overrides env default. |
| `page_size` | integer (1–1000) | No | Server-side paging hint. |
| `filter` | string | No | Filter expression (e.g. `labels.env=prod`). |

**Returns** — JSON array of lake objects. Key fields:

| Field | Description |
| --- | --- |
| `name` | Fully qualified resource name (`projects/…/locations/…/lakes/…`). |
| `display_name` | Human-readable name. |
| `state` | `ACTIVE`, `CREATING`, `DELETING`, `ACTION_REQUIRED`. |
| `service_status` | Populated status block. |
| `metastore_status` | Attached metastore status, if any. |
| `create_time` / `update_time` | RFC 3339 timestamps. |

**Example call**

```json
{ "name": "list_lakes", "arguments": { "location": "us-central1" } }
```

### `get_lake`

Fetch a single lake.

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |

**Returns** — A single lake object with the same fields as
`list_lakes`.

---

## Zone tools

### `list_zones`

List zones inside a lake.

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |
| `page_size` | integer | No |
| `filter` | string | No |

**Returns** — JSON array of zone objects. Key fields include
`type` (`RAW` or `CURATED`), `resource_spec.location_type`
(`SINGLE_REGION` or `MULTI_REGION`), and `discovery_spec`.

### `get_zone`

Fetch a single zone.

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `zone_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |

---

## Asset tools

### `list_assets`

List assets attached to a zone.

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `zone_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |
| `page_size` | integer | No |
| `filter` | string | No |

**Returns** — JSON array of asset objects. Each asset binds a zone
to a concrete Cloud Storage bucket or BigQuery dataset via its
`resource_spec`.

### `get_asset`

Fetch a single asset.

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `zone_id` | string | **Yes** |
| `asset_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |

---

## Metadata tools

These tools hit the Dataplex Metadata Service, which exposes the
logical entities (tables and filesets) discovered inside a zone
along with their schemas and partitions.

### `list_entities`

List entities in a zone.

| Arg | Type | Required | Notes |
| --- | --- | --- | --- |
| `lake_id` | string | **Yes** | |
| `zone_id` | string | **Yes** | |
| `view` | enum `TABLES` \| `FILESETS` | No | Restrict to one entity kind. |
| `project_id` | string | No | |
| `location` | string | No | |
| `page_size` | integer | No | |
| `filter` | string | No | |

**Returns** — JSON array of entity summaries. Notable fields: `id`,
`type` (`TABLE` / `FILESET`), `asset`, `data_path`, `system`
(e.g. `CLOUD_STORAGE`, `BIGQUERY`), `format`.

### `get_entity`

Fetch a single entity including its schema.

| Arg | Type | Required | Notes |
| --- | --- | --- | --- |
| `lake_id` | string | **Yes** | |
| `zone_id` | string | **Yes** | |
| `entity_id` | string | **Yes** | |
| `view` | enum `BASIC` \| `FULL` \| `SCHEMA` | No | Defaults to `FULL`. |
| `project_id` | string | No | |
| `location` | string | No | |

**Returns** — entity object with `schema.fields` (name, type, mode),
`schema.partition_fields`, `compatibility` status, and pointers to
the backing asset.

### `list_partitions`

List partitions for an entity (useful for partitioned BigQuery or
Hive-style filesets).

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `zone_id` | string | **Yes** |
| `entity_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |
| `page_size` | integer | No |
| `filter` | string | No |

**Returns** — JSON array with each partition's `values`, `location`,
and `etag`.

---

## Task tools

Dataplex tasks run scheduled or on-demand Spark or notebook jobs
against lake resources.

### `list_tasks`

List tasks defined on a lake.

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |
| `page_size` | integer | No |
| `filter` | string | No |

**Returns** — array of task objects including `trigger_spec`
(schedule/on-demand), `execution_spec` (service account, args),
`spark` or `notebook` configuration block, and `execution_status`.

### `get_task`

Fetch a single task.

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `task_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |

### `run_task`

Trigger an on-demand run of a task. Requires write IAM
(`roles/dataplex.editor` or a narrower role with
`dataplex.tasks.run`).

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `task_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |

**Returns** — the created `Job` resource, including its `name` (which
can be fed back into `list_jobs` or future status-polling calls) and
`state`.

### `list_jobs`

List execution jobs for a task.

| Arg | Type | Required |
| --- | --- | --- |
| `lake_id` | string | **Yes** |
| `task_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |
| `page_size` | integer | No |

**Returns** — array of job objects with `state` (`RUNNING`,
`SUCCEEDED`, `FAILED`, `CANCELLED`), `start_time`, `end_time`, and
`message` for failures.

---

## Data scan tools

Data scans are Dataplex's managed data quality (DQ) and data profile
jobs. A scan is a reusable definition; each invocation produces a
`DataScanJob` with results.

### `list_data_scans`

List data scans in a project/location.

| Arg | Type | Required |
| --- | --- | --- |
| `project_id` | string | No |
| `location` | string | No |
| `page_size` | integer | No |
| `filter` | string | No |

**Returns** — array of scan summaries, each with `type`
(`DATA_QUALITY` or `DATA_PROFILE`), `data` (the source), and
`execution_spec`.

### `get_data_scan`

Fetch a single data scan.

| Arg | Type | Required | Notes |
| --- | --- | --- | --- |
| `data_scan_id` | string | **Yes** | |
| `view` | enum `BASIC` \| `FULL` | No | `FULL` returns the rules/profile spec. |
| `project_id` | string | No | |
| `location` | string | No | |

### `run_data_scan`

Trigger an on-demand data scan run.

| Arg | Type | Required |
| --- | --- | --- |
| `data_scan_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |

**Returns** — the created `DataScanJob` resource.

### `list_data_scan_jobs`

List jobs for a scan.

| Arg | Type | Required |
| --- | --- | --- |
| `data_scan_id` | string | **Yes** |
| `project_id` | string | No |
| `location` | string | No |
| `page_size` | integer | No |

### `get_data_scan_job`

Fetch a specific data scan job. Use `view=FULL` to see rule-level
results for data quality scans.

| Arg | Type | Required | Notes |
| --- | --- | --- | --- |
| `data_scan_id` | string | **Yes** | |
| `job_id` | string | **Yes** | |
| `view` | enum `BASIC` \| `FULL` | No | Defaults to `BASIC`. |
| `project_id` | string | No | |
| `location` | string | No | |

**Returns (FULL view)** — includes
`data_quality_result.rules_passing_percent`,
`data_quality_result.rules[*]` with `passed`, `evaluated_count`,
`passing_count`, and rule-specific metadata.

---

## Filter expression syntax

Dataplex uses the standard [Google AIP-160](https://google.aip.dev/160)
filter language. Examples:

| Expression | Meaning |
| --- | --- |
| `labels.env=prod` | Resources with label `env=prod`. |
| `state=ACTIVE` | Only active resources. |
| `type=CURATED` | Curated zones only. |
| `create_time > "2024-01-01T00:00:00Z"` | Created after a given instant. |

## Response size and paging

The server does **not** transparently paginate — it issues a single
`ListX` request per tool call. If you need to walk large result sets,
pass an explicit `page_size` and make successive calls, or add a new
tool that wraps the `ListX` iterator. See
[Development](development.md#adding-a-new-tool) for the pattern.
