"""Materialize concise, recruiter-readable consumption outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb


def export_outputs(
    connection: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    output_dir: Path,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    health_rows = connection.execute(
        """
        SELECT health_status, count(*) AS stations
        FROM marts.station_health WHERE run_id = ?
        GROUP BY health_status ORDER BY stations DESC
        """,
        [run_id],
    ).fetchall()
    total = sum(row[1] for row in health_rows)
    summary = {
        "run_id": run_id,
        "station_count": total,
        "health_breakdown": {row[0]: row[1] for row in health_rows},
    }
    (output_dir / "pipeline_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    cursor = connection.execute(
        """
        SELECT station_name, bikes_available, docks_available,
               bikes_disabled + docks_disabled AS disabled_assets,
               health_status, round(bike_fill_ratio, 2) AS bike_fill_ratio
        FROM marts.station_health
        WHERE run_id = ? AND health_status <> 'healthy'
        ORDER BY CASE health_status WHEN 'offline' THEN 1 WHEN 'low_bikes' THEN 2 ELSE 3 END,
                 disabled_assets DESC, station_name
        LIMIT 25
        """,
        [run_id],
    )
    columns = [column[0] for column in cursor.description]
    with (output_dir / "stations_needing_attention.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(cursor.fetchall())
    return summary

