"""Normalize nested source payloads into typed, tabular staging files."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from bikepulse.config import Settings
from bikepulse.ingestion import IngestionResult


@dataclass(frozen=True)
class StagingResult:
    run_id: str
    staging_run_dir: Path
    stations_path: Path
    status_path: Path
    weather_path: Path


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"expected object in {path}")
    return payload


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _iso_from_epoch(value: int | float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, UTC).isoformat()


def build_staging(settings: Settings, ingestion: IngestionResult) -> StagingResult:
    """Flatten one raw run while preserving its run identifier for lineage."""
    raw_dir = ingestion.raw_run_dir
    stage_dir = settings.staging_dir / ingestion.run_id
    stage_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_json(ingestion.manifest_path)
    station_information = _load_json(raw_dir / "station_information.json")
    station_status = _load_json(raw_dir / "station_status.json")
    weather = _load_json(raw_dir / "weather.json")

    stations = [
        {
            "run_id": ingestion.run_id,
            "captured_at": manifest["captured_at"],
            "station_id": str(row["station_id"]),
            "station_name": row.get("name"),
            "latitude": row.get("lat"),
            "longitude": row.get("lon"),
            "capacity": row.get("capacity"),
            "region_id": row.get("region_id"),
            "station_type": row.get("station_type"),
        }
        for row in station_information.get("data", {}).get("stations", [])
    ]
    statuses = [
        {
            "run_id": ingestion.run_id,
            "snapshot_at": _iso_from_epoch(station_status.get("last_updated")),
            "station_id": str(row["station_id"]),
            "last_reported_at": _iso_from_epoch(row.get("last_reported")),
            "bikes_available": row.get("num_bikes_available"),
            "ebikes_available": row.get("num_ebikes_available"),
            "bikes_disabled": row.get("num_bikes_disabled"),
            "docks_available": row.get("num_docks_available"),
            "docks_disabled": row.get("num_docks_disabled"),
            "is_installed": row.get("is_installed"),
            "is_renting": row.get("is_renting"),
            "is_returning": row.get("is_returning"),
        }
        for row in station_status.get("data", {}).get("stations", [])
    ]
    current = weather.get("current", {})
    weather_rows = [
        {
            "run_id": ingestion.run_id,
            "observed_at": current.get("time"),
            "latitude": weather.get("latitude"),
            "longitude": weather.get("longitude"),
            "temperature_c": current.get("temperature_2m"),
            "precipitation_mm": current.get("precipitation"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
        }
    ]

    stations_path = stage_dir / "stations.csv"
    status_path = stage_dir / "station_status.csv"
    weather_path = stage_dir / "weather.csv"
    _write_csv(stations_path, stations, list(stations[0]) if stations else ["run_id"])
    _write_csv(status_path, statuses, list(statuses[0]) if statuses else ["run_id"])
    _write_csv(weather_path, weather_rows, list(weather_rows[0]))
    return StagingResult(
        run_id=ingestion.run_id,
        staging_run_dir=stage_dir,
        stations_path=stations_path,
        status_path=status_path,
        weather_path=weather_path,
    )

