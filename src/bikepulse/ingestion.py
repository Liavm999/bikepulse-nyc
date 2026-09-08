"""Acquire GBFS and weather payloads into an immutable raw landing zone."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from bikepulse.config import Settings
from bikepulse.http import get_json

LOGGER = logging.getLogger(__name__)
SOURCE_FILES = {
    "station_information": "station_information.json",
    "station_status": "station_status.json",
    "weather": "weather.json",
}


@dataclass(frozen=True)
class IngestionResult:
    run_id: str
    raw_run_dir: Path
    manifest_path: Path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_snapshot(
    settings: Settings,
    *,
    source: Literal["live", "sample"] = "sample",
    run_id: str | None = None,
) -> IngestionResult:
    """Land one source snapshot and a checksum manifest.

    A caller-supplied run_id makes replay behavior explicit. Existing raw files with
    identical content are retained; conflicting content fails instead of overwriting evidence.
    """
    captured_at = datetime.now(UTC)
    run_id = run_id or captured_at.strftime("%Y%m%dT%H%M%SZ")
    raw_run_dir = settings.raw_dir / run_id
    raw_run_dir.mkdir(parents=True, exist_ok=True)

    urls = {
        "station_information": settings.station_information_url,
        "station_status": settings.station_status_url,
        "weather": settings.weather_url,
    }
    manifest_sources: list[dict[str, Any]] = []

    for source_name, filename in SOURCE_FILES.items():
        destination = raw_run_dir / filename
        if source == "sample":
            sample_path = settings.sample_dir / filename
            if not sample_path.exists():
                raise FileNotFoundError(
                    f"sample source missing: {sample_path}; run with --source live first"
                )
            incoming = sample_path.read_bytes()
            if destination.exists() and destination.read_bytes() != incoming:
                raise FileExistsError(f"refusing to overwrite conflicting raw file: {destination}")
            if not destination.exists():
                shutil.copyfile(sample_path, destination)
        else:
            payload = get_json(
                urls[source_name],
                timeout=settings.http_timeout_seconds,
                max_attempts=settings.http_max_attempts,
            )
            encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            if destination.exists() and destination.read_bytes() != encoded:
                raise FileExistsError(f"refusing to overwrite conflicting raw file: {destination}")
            if not destination.exists():
                destination.write_bytes(encoded)

        manifest_sources.append(
            {
                "name": source_name,
                "file": filename,
                "url": urls[source_name],
                "bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
            }
        )

    manifest = {
        "run_id": run_id,
        "captured_at": captured_at.isoformat(),
        "mode": source,
        "sources": manifest_sources,
    }
    manifest_path = raw_run_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    LOGGER.info("raw snapshot landed", extra={"run_id": run_id, "source": source})
    return IngestionResult(run_id=run_id, raw_run_dir=raw_run_dir, manifest_path=manifest_path)


def refresh_sample(settings: Settings, *, station_limit: int = 200) -> None:
    """Capture a compact, matching subset of the live feeds for offline demonstrations."""
    information = get_json(
        settings.station_information_url,
        timeout=settings.http_timeout_seconds,
        max_attempts=settings.http_max_attempts,
    )
    status = get_json(
        settings.station_status_url,
        timeout=settings.http_timeout_seconds,
        max_attempts=settings.http_max_attempts,
    )
    weather = get_json(
        settings.weather_url,
        timeout=settings.http_timeout_seconds,
        max_attempts=settings.http_max_attempts,
    )

    info_rows = information.get("data", {}).get("stations", [])[:station_limit]
    station_ids = {str(row["station_id"]) for row in info_rows}
    status_rows = [
        row
        for row in status.get("data", {}).get("stations", [])
        if str(row.get("station_id")) in station_ids
    ]
    compact_information = {**information, "data": {"stations": info_rows}}
    compact_status = {**status, "data": {"stations": status_rows}}

    settings.sample_dir.mkdir(parents=True, exist_ok=True)
    _write_json(settings.sample_dir / SOURCE_FILES["station_information"], compact_information)
    _write_json(settings.sample_dir / SOURCE_FILES["station_status"], compact_status)
    _write_json(settings.sample_dir / SOURCE_FILES["weather"], weather)
    _write_json(
        settings.sample_dir / "provenance.json",
        {
            "captured_at": datetime.now(UTC).isoformat(),
            "description": "Compact unmodified records captured from the configured public APIs.",
            "station_count": len(info_rows),
            "status_count": len(status_rows),
            "sources": {
                "station_information": settings.station_information_url,
                "station_status": settings.station_status_url,
                "weather": settings.weather_url,
            },
        },
    )

