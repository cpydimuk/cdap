"""Tests for the pure-Python helpers in ``dataplex_client``.

These tests avoid any real calls to Google Cloud. They focus on the
resource-path construction and config resolution logic so they can run
without credentials or network access. The heavyweight SDK surface is
exercised by integration tests (not included here).
"""

from __future__ import annotations

import sys
import types

import pytest


def _install_dataplex_stub() -> None:
    """Install a minimal stub for ``google.cloud.dataplex_v1``.

    The real SDK is not required for exercising path helpers and the
    view-enum parsers. Installing a stub keeps unit tests fast and
    dependency-free while still letting ``dataplex_client`` import
    cleanly.
    """
    if "google.cloud.dataplex_v1" in sys.modules:
        return

    google = sys.modules.setdefault("google", types.ModuleType("google"))
    cloud = sys.modules.setdefault("google.cloud", types.ModuleType("google.cloud"))
    google.cloud = cloud  # type: ignore[attr-defined]

    dataplex_v1 = types.ModuleType("google.cloud.dataplex_v1")

    class _Enum(int):
        pass

    def _make_enum(**members: int):
        ns = types.SimpleNamespace(**{k: _Enum(v) for k, v in members.items()})
        return ns

    class _Request:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class ListEntitiesRequest(_Request):
        EntityView = _make_enum(ENTITY_VIEW_UNSPECIFIED=0, TABLES=1, FILESETS=2)

    class GetEntityRequest(_Request):
        EntityView = _make_enum(ENTITY_VIEW_UNSPECIFIED=0, BASIC=1, SCHEMA=2, FULL=3)

    class GetDataScanRequest(_Request):
        DataScanView = _make_enum(DATA_SCAN_VIEW_UNSPECIFIED=0, BASIC=1, FULL=10)

    class GetDataScanJobRequest(_Request):
        DataScanJobView = _make_enum(DATA_SCAN_JOB_VIEW_UNSPECIFIED=0, BASIC=1, FULL=10)

    for name in (
        "ListLakesRequest",
        "ListZonesRequest",
        "ListAssetsRequest",
        "ListPartitionsRequest",
        "ListTasksRequest",
        "RunTaskRequest",
        "ListJobsRequest",
        "ListDataScansRequest",
        "RunDataScanRequest",
        "ListDataScanJobsRequest",
    ):
        setattr(dataplex_v1, name, type(name, (_Request,), {}))

    dataplex_v1.ListEntitiesRequest = ListEntitiesRequest
    dataplex_v1.GetEntityRequest = GetEntityRequest
    dataplex_v1.GetDataScanRequest = GetDataScanRequest
    dataplex_v1.GetDataScanJobRequest = GetDataScanJobRequest

    class _FakeServiceClient:
        def __init__(self, *args, **kwargs):
            pass

    dataplex_v1.DataplexServiceClient = _FakeServiceClient
    dataplex_v1.MetadataServiceClient = _FakeServiceClient
    dataplex_v1.DataScanServiceClient = _FakeServiceClient

    sys.modules["google.cloud.dataplex_v1"] = dataplex_v1
    cloud.dataplex_v1 = dataplex_v1  # type: ignore[attr-defined]

    # Stub google.protobuf.json_format too, in case the real lib is absent.
    if "google.protobuf" not in sys.modules:
        protobuf = types.ModuleType("google.protobuf")
        json_format = types.ModuleType("google.protobuf.json_format")
        json_format.MessageToDict = lambda msg, **kw: {}  # type: ignore[attr-defined]
        protobuf.json_format = json_format  # type: ignore[attr-defined]
        sys.modules["google.protobuf"] = protobuf
        sys.modules["google.protobuf.json_format"] = json_format


_install_dataplex_stub()

from dataplex_mcp_server.dataplex_client import (  # noqa: E402
    DataplexClient,
    DataplexConfig,
    _parse_data_scan_job_view,
    _parse_data_scan_view,
    _parse_entity_view,
)


# --------------------------------------------------------------------- #
# Config.
# --------------------------------------------------------------------- #
def test_config_from_env_prefers_dataplex_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATAPLEX_PROJECT_ID", "dp-proj")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "gcp-proj")
    monkeypatch.setenv("DATAPLEX_LOCATION", "us-central1")

    config = DataplexConfig.from_env()
    assert config.project_id == "dp-proj"
    assert config.location == "us-central1"


def test_config_falls_back_to_google_cloud_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATAPLEX_PROJECT_ID", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "gcp-proj")
    monkeypatch.delenv("DATAPLEX_LOCATION", raising=False)

    config = DataplexConfig.from_env()
    assert config.project_id == "gcp-proj"
    assert config.location is None


# --------------------------------------------------------------------- #
# Resource path helpers.
# --------------------------------------------------------------------- #
@pytest.fixture
def client() -> DataplexClient:
    return DataplexClient(DataplexConfig(project_id="proj", location="us-central1"))


def test_location_path_uses_defaults(client: DataplexClient) -> None:
    assert client.location_path(None, None) == "projects/proj/locations/us-central1"


def test_location_path_overrides(client: DataplexClient) -> None:
    assert (
        client.location_path("other", "eu-west1")
        == "projects/other/locations/eu-west1"
    )


def test_lake_path(client: DataplexClient) -> None:
    assert (
        client.lake_path(None, None, "my-lake")
        == "projects/proj/locations/us-central1/lakes/my-lake"
    )


def test_zone_path(client: DataplexClient) -> None:
    assert client.zone_path(None, None, "my-lake", "my-zone") == (
        "projects/proj/locations/us-central1/lakes/my-lake/zones/my-zone"
    )


def test_asset_path(client: DataplexClient) -> None:
    expected = (
        "projects/proj/locations/us-central1/lakes/my-lake"
        "/zones/my-zone/assets/my-asset"
    )
    assert client.asset_path(None, None, "my-lake", "my-zone", "my-asset") == expected


def test_entity_path(client: DataplexClient) -> None:
    expected = (
        "projects/proj/locations/us-central1/lakes/my-lake"
        "/zones/my-zone/entities/ent-1"
    )
    assert client.entity_path(None, None, "my-lake", "my-zone", "ent-1") == expected


def test_task_path(client: DataplexClient) -> None:
    assert client.task_path(None, None, "my-lake", "my-task") == (
        "projects/proj/locations/us-central1/lakes/my-lake/tasks/my-task"
    )


def test_data_scan_path(client: DataplexClient) -> None:
    assert client.data_scan_path(None, None, "my-scan") == (
        "projects/proj/locations/us-central1/dataScans/my-scan"
    )


def test_missing_project_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATAPLEX_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("DATAPLEX_LOCATION", raising=False)
    client = DataplexClient(DataplexConfig())
    with pytest.raises(ValueError, match="project_id is required"):
        client.location_path(None, "us-central1")


def test_missing_location_raises() -> None:
    client = DataplexClient(DataplexConfig(project_id="proj"))
    with pytest.raises(ValueError, match="location is required"):
        client.location_path(None, None)


# --------------------------------------------------------------------- #
# View enum parsing.
# --------------------------------------------------------------------- #
def test_parse_entity_view_valid() -> None:
    assert int(_parse_entity_view("TABLES")) == 1
    assert int(_parse_entity_view("filesets")) == 2


def test_parse_entity_view_default() -> None:
    assert int(_parse_entity_view(None)) == 0


def test_parse_entity_view_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid entity view"):
        _parse_entity_view("OTHER")


def test_parse_data_scan_view() -> None:
    assert int(_parse_data_scan_view(None)) == 1  # BASIC is default
    assert int(_parse_data_scan_view("FULL")) == 10
    with pytest.raises(ValueError):
        _parse_data_scan_view("invalid")


def test_parse_data_scan_job_view() -> None:
    assert int(_parse_data_scan_job_view(None)) == 1
    assert int(_parse_data_scan_job_view("FULL")) == 10
    with pytest.raises(ValueError):
        _parse_data_scan_job_view("invalid")
