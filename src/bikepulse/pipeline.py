"""Pipeline orchestration kept explicit enough to run locally or from a scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bikepulse.analytics import export_outputs
from bikepulse.config import Settings
from bikepulse.ingestion import ingest_snapshot
from bikepulse.quality import CheckResult, assert_run_quality
from bikepulse.transform import build_staging
from bikepulse.warehouse import connect, initialize_schema, load_run


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    checks: list[CheckResult]
    summary: dict[str, object]


def run_pipeline(
    settings: Settings,
    *,
    source: Literal["live", "sample"] = "sample",
    run_id: str | None = None,
) -> PipelineResult:
    ingestion = ingest_snapshot(settings, source=source, run_id=run_id)
    staging = build_staging(settings, ingestion)
    with connect(settings) as connection:
        initialize_schema(
            connection,
            settings.project_root / "sql" / "schema.sql",
            low_bike_threshold=settings.low_bike_threshold,
            low_dock_threshold=settings.low_dock_threshold,
        )
        load_run(connection, settings, staging)
        checks = assert_run_quality(connection, staging.run_id)
        summary = export_outputs(
            connection, run_id=staging.run_id, output_dir=settings.project_root / "outputs"
        )
    return PipelineResult(run_id=staging.run_id, checks=checks, summary=summary)
