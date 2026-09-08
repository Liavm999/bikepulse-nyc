"""Executable data-contract checks for each loaded snapshot."""

from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    observed: float
    expectation: str


class DataQualityError(RuntimeError):
    """Raised when one or more warehouse checks fail."""


def evaluate_run(connection: duckdb.DuckDBPyConnection, run_id: str) -> list[CheckResult]:
    queries = [
        (
            "status_rows_present",
            "SELECT count(*) FROM core.fact_station_status WHERE run_id = ?",
            lambda value: value > 0,
            "> 0",
        ),
        (
            "no_duplicate_station_status",
            """
            SELECT count(*) - count(DISTINCT station_id)
            FROM core.fact_station_status WHERE run_id = ?
            """,
            lambda value: value == 0,
            "= 0 duplicates",
        ),
        (
            "no_orphan_station_status",
            """
            SELECT count(*) FROM core.fact_station_status AS f
            LEFT JOIN core.dim_station AS d USING (station_id)
            WHERE f.run_id = ? AND d.station_id IS NULL
            """,
            lambda value: value == 0,
            "= 0 orphans",
        ),
        (
            "nonnegative_inventory",
            """
            SELECT count(*) FROM core.fact_station_status
            WHERE run_id = ? AND (
                bikes_available < 0 OR docks_available < 0 OR
                bikes_disabled < 0 OR docks_disabled < 0
            )
            """,
            lambda value: value == 0,
            "= 0 invalid rows",
        ),
        (
            "valid_station_coordinates",
            """
            SELECT count(*) FROM core.fact_station_status AS f
            JOIN core.dim_station AS d USING (station_id)
            WHERE f.run_id = ? AND NOT (
                d.latitude BETWEEN 40.0 AND 41.5 AND d.longitude BETWEEN -75.0 AND -72.5
            )
            """,
            lambda value: value == 0,
            "= 0 outside NYC bounds",
        ),
        (
            "station_metadata_coverage",
            """
            SELECT count(d.station_id)::DOUBLE / NULLIF(count(*), 0)
            FROM core.fact_station_status AS f
            LEFT JOIN core.dim_station AS d USING (station_id)
            WHERE f.run_id = ?
            """,
            lambda value: value >= 0.95,
            ">= 95%",
        ),
    ]
    results = []
    for name, sql, predicate, expectation in queries:
        observed = connection.execute(sql, [run_id]).fetchone()[0]
        numeric = float(observed or 0)
        results.append(CheckResult(name, bool(predicate(numeric)), numeric, expectation))
    return results


def assert_run_quality(connection: duckdb.DuckDBPyConnection, run_id: str) -> list[CheckResult]:
    results = evaluate_run(connection, run_id)
    failed = [result for result in results if not result.passed]
    if failed:
        details = "; ".join(
            f"{result.name}: observed {result.observed}, expected {result.expectation}"
            for result in failed
        )
        raise DataQualityError(f"data quality checks failed for {run_id}: {details}")
    return results

