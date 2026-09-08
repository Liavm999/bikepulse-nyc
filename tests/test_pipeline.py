from __future__ import annotations

import json

from bikepulse.ingestion import ingest_snapshot
from bikepulse.pipeline import run_pipeline
from bikepulse.quality import evaluate_run
from bikepulse.transform import build_staging
from bikepulse.warehouse import connect


def test_staging_preserves_matching_station_keys(isolated_project) -> None:
    ingestion = ingest_snapshot(isolated_project, source="sample", run_id="test-staging")
    staging = build_staging(isolated_project, ingestion)

    information = json.loads(
        (ingestion.raw_run_dir / "station_information.json").read_text(encoding="utf-8")
    )
    expected = len(information["data"]["stations"])
    assert len(staging.stations_path.read_text(encoding="utf-8").splitlines()) - 1 == expected
    assert len(staging.status_path.read_text(encoding="utf-8").splitlines()) - 1 == expected


def test_replaying_same_run_is_idempotent(isolated_project) -> None:
    first = run_pipeline(isolated_project, source="sample", run_id="stable-run")
    second = run_pipeline(isolated_project, source="sample", run_id="stable-run")

    assert first.summary == second.summary
    with connect(isolated_project) as connection:
        fact_count = connection.execute(
            "SELECT count(*) FROM core.fact_station_status WHERE run_id = 'stable-run'"
        ).fetchone()[0]
        audit_count = connection.execute(
            "SELECT count(*) FROM audit.pipeline_runs WHERE run_id = 'stable-run'"
        ).fetchone()[0]
    assert fact_count == first.summary["station_count"]
    assert audit_count == 1


def test_quality_check_detects_negative_inventory(isolated_project) -> None:
    result = run_pipeline(isolated_project, source="sample", run_id="bad-run")
    with connect(isolated_project) as connection:
        connection.execute(
            """
            UPDATE core.fact_station_status SET bikes_available = -1
            WHERE run_id = ? AND station_id = (
                SELECT min(station_id) FROM core.fact_station_status WHERE run_id = ?
            )
            """,
            [result.run_id, result.run_id],
        )
        checks = {check.name: check for check in evaluate_run(connection, result.run_id)}
    assert checks["nonnegative_inventory"].passed is False
    assert checks["nonnegative_inventory"].observed == 1

