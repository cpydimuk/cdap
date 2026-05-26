"""Thin wrapper around the google-cloud-dataplex SDK.

The wrapper isolates every call to the Google Cloud SDK so that the MCP
server layer can stay focused on protocol concerns. Results are converted
to plain dictionaries using ``proto.Message.to_dict`` so they can be
serialized to JSON for the MCP client.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from google.cloud import dataplex_v1
from google.protobuf.json_format import MessageToDict


def _to_dict(message: Any) -> dict[str, Any]:
    """Convert a protobuf/proto-plus message into a plain dict.

    Handles both ``proto.Message`` (proto-plus) and ``google.protobuf.Message``
    objects, as well as values that are already dicts.
    """
    if message is None:
        return {}
    if isinstance(message, dict):
        return message
    # proto-plus messages expose ``to_dict`` via the type class.
    to_dict = getattr(type(message), "to_dict", None)
    if callable(to_dict):
        return to_dict(message)
    # Fall back to the classic protobuf JSON serializer.
    return MessageToDict(message, preserving_proto_field_name=True)


@dataclass(frozen=True)
class DataplexConfig:
    """Default project and location used when arguments are omitted."""

    project_id: str | None = None
    location: str | None = None

    @classmethod
    def from_env(cls) -> "DataplexConfig":
        return cls(
            project_id=os.environ.get("DATAPLEX_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT"),
            location=os.environ.get("DATAPLEX_LOCATION"),
        )


class DataplexClient:
    """Facade over the Dataplex service clients used by the MCP server."""

    def __init__(self, config: DataplexConfig | None = None) -> None:
        self._config = config or DataplexConfig.from_env()
        self._dataplex: dataplex_v1.DataplexServiceClient | None = None
        self._metadata: dataplex_v1.MetadataServiceClient | None = None
        self._data_scan: dataplex_v1.DataScanServiceClient | None = None

    # ------------------------------------------------------------------ #
    # Lazy client accessors. Deferring construction keeps import/startup
    # cheap and makes unit testing simpler (clients can be injected).
    # ------------------------------------------------------------------ #
    @property
    def dataplex(self) -> dataplex_v1.DataplexServiceClient:
        if self._dataplex is None:
            self._dataplex = dataplex_v1.DataplexServiceClient()
        return self._dataplex

    @property
    def metadata(self) -> dataplex_v1.MetadataServiceClient:
        if self._metadata is None:
            self._metadata = dataplex_v1.MetadataServiceClient()
        return self._metadata

    @property
    def data_scan(self) -> dataplex_v1.DataScanServiceClient:
        if self._data_scan is None:
            self._data_scan = dataplex_v1.DataScanServiceClient()
        return self._data_scan

    # ------------------------------------------------------------------ #
    # Parent/name helpers.
    # ------------------------------------------------------------------ #
    def _resolve_project(self, project_id: str | None) -> str:
        project = project_id or self._config.project_id
        if not project:
            raise ValueError(
                "project_id is required. Pass it explicitly or set "
                "DATAPLEX_PROJECT_ID / GOOGLE_CLOUD_PROJECT."
            )
        return project

    def _resolve_location(self, location: str | None) -> str:
        loc = location or self._config.location
        if not loc:
            raise ValueError(
                "location is required. Pass it explicitly or set DATAPLEX_LOCATION."
            )
        return loc

    def location_path(self, project_id: str | None, location: str | None) -> str:
        return (
            f"projects/{self._resolve_project(project_id)}"
            f"/locations/{self._resolve_location(location)}"
        )

    def lake_path(
        self, project_id: str | None, location: str | None, lake_id: str
    ) -> str:
        return f"{self.location_path(project_id, location)}/lakes/{lake_id}"

    def zone_path(
        self,
        project_id: str | None,
        location: str | None,
        lake_id: str,
        zone_id: str,
    ) -> str:
        return f"{self.lake_path(project_id, location, lake_id)}/zones/{zone_id}"

    def asset_path(
        self,
        project_id: str | None,
        location: str | None,
        lake_id: str,
        zone_id: str,
        asset_id: str,
    ) -> str:
        return (
            f"{self.zone_path(project_id, location, lake_id, zone_id)}"
            f"/assets/{asset_id}"
        )

    def entity_path(
        self,
        project_id: str | None,
        location: str | None,
        lake_id: str,
        zone_id: str,
        entity_id: str,
    ) -> str:
        return (
            f"{self.zone_path(project_id, location, lake_id, zone_id)}"
            f"/entities/{entity_id}"
        )

    def task_path(
        self,
        project_id: str | None,
        location: str | None,
        lake_id: str,
        task_id: str,
    ) -> str:
        return f"{self.lake_path(project_id, location, lake_id)}/tasks/{task_id}"

    def data_scan_path(
        self,
        project_id: str | None,
        location: str | None,
        data_scan_id: str,
    ) -> str:
        return (
            f"{self.location_path(project_id, location)}/dataScans/{data_scan_id}"
        )

    # ------------------------------------------------------------------ #
    # Lakes.
    # ------------------------------------------------------------------ #
    def list_lakes(
        self,
        project_id: str | None = None,
        location: str | None = None,
        page_size: int | None = None,
        filter_: str | None = None,
    ) -> list[dict[str, Any]]:
        request = dataplex_v1.ListLakesRequest(
            parent=self.location_path(project_id, location),
            page_size=page_size or 0,
            filter=filter_ or "",
        )
        return [_to_dict(lake) for lake in self.dataplex.list_lakes(request=request)]

    def get_lake(
        self,
        lake_id: str,
        project_id: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        name = self.lake_path(project_id, location, lake_id)
        return _to_dict(self.dataplex.get_lake(name=name))

    # ------------------------------------------------------------------ #
    # Zones.
    # ------------------------------------------------------------------ #
    def list_zones(
        self,
        lake_id: str,
        project_id: str | None = None,
        location: str | None = None,
        page_size: int | None = None,
        filter_: str | None = None,
    ) -> list[dict[str, Any]]:
        request = dataplex_v1.ListZonesRequest(
            parent=self.lake_path(project_id, location, lake_id),
            page_size=page_size or 0,
            filter=filter_ or "",
        )
        return [_to_dict(zone) for zone in self.dataplex.list_zones(request=request)]

    def get_zone(
        self,
        lake_id: str,
        zone_id: str,
        project_id: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        name = self.zone_path(project_id, location, lake_id, zone_id)
        return _to_dict(self.dataplex.get_zone(name=name))

    # ------------------------------------------------------------------ #
    # Assets.
    # ------------------------------------------------------------------ #
    def list_assets(
        self,
        lake_id: str,
        zone_id: str,
        project_id: str | None = None,
        location: str | None = None,
        page_size: int | None = None,
        filter_: str | None = None,
    ) -> list[dict[str, Any]]:
        request = dataplex_v1.ListAssetsRequest(
            parent=self.zone_path(project_id, location, lake_id, zone_id),
            page_size=page_size or 0,
            filter=filter_ or "",
        )
        return [_to_dict(asset) for asset in self.dataplex.list_assets(request=request)]

    def get_asset(
        self,
        lake_id: str,
        zone_id: str,
        asset_id: str,
        project_id: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        name = self.asset_path(project_id, location, lake_id, zone_id, asset_id)
        return _to_dict(self.dataplex.get_asset(name=name))

    # ------------------------------------------------------------------ #
    # Entities and partitions (metadata service).
    # ------------------------------------------------------------------ #
    def list_entities(
        self,
        lake_id: str,
        zone_id: str,
        project_id: str | None = None,
        location: str | None = None,
        view: str | None = None,
        page_size: int | None = None,
        filter_: str | None = None,
    ) -> list[dict[str, Any]]:
        request = dataplex_v1.ListEntitiesRequest(
            parent=self.zone_path(project_id, location, lake_id, zone_id),
            view=_parse_entity_view(view),
            page_size=page_size or 0,
            filter=filter_ or "",
        )
        return [
            _to_dict(entity) for entity in self.metadata.list_entities(request=request)
        ]

    def get_entity(
        self,
        lake_id: str,
        zone_id: str,
        entity_id: str,
        project_id: str | None = None,
        location: str | None = None,
        view: str | None = None,
    ) -> dict[str, Any]:
        request = dataplex_v1.GetEntityRequest(
            name=self.entity_path(project_id, location, lake_id, zone_id, entity_id),
            view=_parse_entity_view(view) or dataplex_v1.GetEntityRequest.EntityView.FULL,
        )
        return _to_dict(self.metadata.get_entity(request=request))

    def list_partitions(
        self,
        lake_id: str,
        zone_id: str,
        entity_id: str,
        project_id: str | None = None,
        location: str | None = None,
        page_size: int | None = None,
        filter_: str | None = None,
    ) -> list[dict[str, Any]]:
        request = dataplex_v1.ListPartitionsRequest(
            parent=self.entity_path(
                project_id, location, lake_id, zone_id, entity_id
            ),
            page_size=page_size or 0,
            filter=filter_ or "",
        )
        return [
            _to_dict(p) for p in self.metadata.list_partitions(request=request)
        ]

    # ------------------------------------------------------------------ #
    # Tasks and jobs.
    # ------------------------------------------------------------------ #
    def list_tasks(
        self,
        lake_id: str,
        project_id: str | None = None,
        location: str | None = None,
        page_size: int | None = None,
        filter_: str | None = None,
    ) -> list[dict[str, Any]]:
        request = dataplex_v1.ListTasksRequest(
            parent=self.lake_path(project_id, location, lake_id),
            page_size=page_size or 0,
            filter=filter_ or "",
        )
        return [_to_dict(t) for t in self.dataplex.list_tasks(request=request)]

    def get_task(
        self,
        lake_id: str,
        task_id: str,
        project_id: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        name = self.task_path(project_id, location, lake_id, task_id)
        return _to_dict(self.dataplex.get_task(name=name))

    def run_task(
        self,
        lake_id: str,
        task_id: str,
        project_id: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        request = dataplex_v1.RunTaskRequest(
            name=self.task_path(project_id, location, lake_id, task_id)
        )
        return _to_dict(self.dataplex.run_task(request=request))

    def list_jobs(
        self,
        lake_id: str,
        task_id: str,
        project_id: str | None = None,
        location: str | None = None,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        request = dataplex_v1.ListJobsRequest(
            parent=self.task_path(project_id, location, lake_id, task_id),
            page_size=page_size or 0,
        )
        return [_to_dict(j) for j in self.dataplex.list_jobs(request=request)]

    # ------------------------------------------------------------------ #
    # Data scans (data quality & profile).
    # ------------------------------------------------------------------ #
    def list_data_scans(
        self,
        project_id: str | None = None,
        location: str | None = None,
        page_size: int | None = None,
        filter_: str | None = None,
    ) -> list[dict[str, Any]]:
        request = dataplex_v1.ListDataScansRequest(
            parent=self.location_path(project_id, location),
            page_size=page_size or 0,
            filter=filter_ or "",
        )
        return [_to_dict(s) for s in self.data_scan.list_data_scans(request=request)]

    def get_data_scan(
        self,
        data_scan_id: str,
        project_id: str | None = None,
        location: str | None = None,
        view: str | None = None,
    ) -> dict[str, Any]:
        request = dataplex_v1.GetDataScanRequest(
            name=self.data_scan_path(project_id, location, data_scan_id),
            view=_parse_data_scan_view(view),
        )
        return _to_dict(self.data_scan.get_data_scan(request=request))

    def run_data_scan(
        self,
        data_scan_id: str,
        project_id: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        request = dataplex_v1.RunDataScanRequest(
            name=self.data_scan_path(project_id, location, data_scan_id),
        )
        return _to_dict(self.data_scan.run_data_scan(request=request))

    def get_data_scan_job(
        self,
        data_scan_id: str,
        job_id: str,
        project_id: str | None = None,
        location: str | None = None,
        view: str | None = None,
    ) -> dict[str, Any]:
        name = (
            f"{self.data_scan_path(project_id, location, data_scan_id)}/jobs/{job_id}"
        )
        request = dataplex_v1.GetDataScanJobRequest(
            name=name,
            view=_parse_data_scan_job_view(view),
        )
        return _to_dict(self.data_scan.get_data_scan_job(request=request))

    def list_data_scan_jobs(
        self,
        data_scan_id: str,
        project_id: str | None = None,
        location: str | None = None,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        request = dataplex_v1.ListDataScanJobsRequest(
            parent=self.data_scan_path(project_id, location, data_scan_id),
            page_size=page_size or 0,
        )
        return [
            _to_dict(j) for j in self.data_scan.list_data_scan_jobs(request=request)
        ]


# ---------------------------------------------------------------------- #
# View enum parsing helpers.
# ---------------------------------------------------------------------- #
def _parse_entity_view(view: str | None):
    if not view:
        return dataplex_v1.ListEntitiesRequest.EntityView.ENTITY_VIEW_UNSPECIFIED
    upper = view.upper()
    mapping = {
        "TABLES": dataplex_v1.ListEntitiesRequest.EntityView.TABLES,
        "FILESETS": dataplex_v1.ListEntitiesRequest.EntityView.FILESETS,
    }
    if upper not in mapping:
        raise ValueError(
            f"Invalid entity view {view!r}. Expected one of: TABLES, FILESETS."
        )
    return mapping[upper]


def _parse_data_scan_view(view: str | None):
    if not view:
        return dataplex_v1.GetDataScanRequest.DataScanView.BASIC
    upper = view.upper()
    mapping = {
        "BASIC": dataplex_v1.GetDataScanRequest.DataScanView.BASIC,
        "FULL": dataplex_v1.GetDataScanRequest.DataScanView.FULL,
    }
    if upper not in mapping:
        raise ValueError(
            f"Invalid data scan view {view!r}. Expected one of: BASIC, FULL."
        )
    return mapping[upper]


def _parse_data_scan_job_view(view: str | None):
    if not view:
        return dataplex_v1.GetDataScanJobRequest.DataScanJobView.BASIC
    upper = view.upper()
    mapping = {
        "BASIC": dataplex_v1.GetDataScanJobRequest.DataScanJobView.BASIC,
        "FULL": dataplex_v1.GetDataScanJobRequest.DataScanJobView.FULL,
    }
    if upper not in mapping:
        raise ValueError(
            f"Invalid data scan job view {view!r}. Expected one of: BASIC, FULL."
        )
    return mapping[upper]
