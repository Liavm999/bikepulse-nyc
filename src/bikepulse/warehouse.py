"""DuckDB persistence and idempotent model loading."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from bikepulse.config import Settings
from bikepulse.transform import StagingResult


def connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(settings.database_path))


def initialize_schema(connection: duckdb.DuckDBPyConnection, sql_path: Path) -> None:
    connection.execute(sql_path.read_text(encoding="utf-8"))


def load_run(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    staging: StagingResult,
) -> None:
    """Atomically load one run; replaying the run replaces, rather than duplicates, facts."""
    manifest_path = settings.raw_dir / staging.run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    station_file = str(staging.stations_path).replace("'", "''")
    status_file = str(staging.status_path).replace("'", "''")
    weather_file = str(staging.weather_path).replace("'", "''")

    connection.execute("BEGIN TRANSACTION")
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO core.dim_station
            SELECT
                incoming.station_id,
                incoming.station_name,
                incoming.latitude,
                incoming.longitude,
                incoming.capacity,
                incoming.region_id,
                incoming.station_type,
                COALESCE(existing.first_seen_at, incoming.captured_at::TIMESTAMPTZ),
                incoming.captured_at::TIMESTAMPTZ
            FROM read_csv_auto(?) AS incoming
            LEFT JOIN core.dim_station AS existing USING (station_id)
            """,
            [station_file],
        )
        connection.execute("DELETE FROM core.fact_station_status WHERE run_id = ?", [staging.run_id])
        connection.execute(
            """
            INSERT INTO core.fact_station_status
            SELECT
                run_id,
                snapshot_at::TIMESTAMPTZ,
                station_id,
                last_reported_at::TIMESTAMPTZ,
                bikes_available,
                ebikes_available,
                bikes_disabled,
                docks_available,
                docks_disabled,
                is_installed::BOOLEAN,
                is_renting::BOOLEAN,
                is_returning::BOOLEAN
            FROM read_csv_auto(?)
            """,
            [status_file],
        )
        connection.execute("DELETE FROM core.fact_weather WHERE run_id = ?", [staging.run_id])
        connection.execute(
            """
            INSERT INTO core.fact_weather
            SELECT
                run_id,
                observed_at::TIMESTAMP,
                latitude,
                longitude,
                temperature_c,
                precipitation_mm,
                wind_speed_kmh
            FROM read_csv_auto(?)
            """,
            [weather_file],
        )
        counts = [
            connection.execute(f"SELECT count(*) FROM read_csv_auto('{path}')").fetchone()[0]
            for path in (station_file, status_file, weather_file)
        ]
        connection.execute("DELETE FROM audit.pipeline_runs WHERE run_id = ?", [staging.run_id])
        connection.execute(
            "INSERT INTO audit.pipeline_runs VALUES (?, ?, ?, ?, ?, ?)",
            [staging.run_id, datetime.now(UTC), manifest["mode"], *counts],
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise

