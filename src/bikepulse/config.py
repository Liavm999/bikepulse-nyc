"""Configuration loading with explicit environment-variable overrides."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    database_path: Path
    station_information_url: str
    station_status_url: str
    weather_url: str
    low_bike_threshold: int
    low_dock_threshold: int
    http_timeout_seconds: float
    http_max_attempts: int
    log_level: str

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def staging_dir(self) -> Path:
        return self.data_dir / "staging"

    @property
    def sample_dir(self) -> Path:
        return self.data_dir / "sample"


def load_settings(project_root: Path | None = None) -> Settings:
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    with (root / "config" / "settings.toml").open("rb") as handle:
        config = tomllib.load(handle)

    data_dir = Path(os.getenv("BIKEPULSE_DATA_DIR", str(root / "data")))
    database_path = Path(
        os.getenv("BIKEPULSE_DB_PATH", str(data_dir / "warehouse" / "bikepulse.duckdb"))
    )
    return Settings(
        project_root=root,
        data_dir=data_dir,
        database_path=database_path,
        station_information_url=config["sources"]["station_information_url"],
        station_status_url=config["sources"]["station_status_url"],
        weather_url=config["sources"]["weather_url"],
        low_bike_threshold=int(config["pipeline"]["low_bike_threshold"]),
        low_dock_threshold=int(config["pipeline"]["low_dock_threshold"]),
        http_timeout_seconds=float(os.getenv("BIKEPULSE_HTTP_TIMEOUT_SECONDS", "30")),
        http_max_attempts=int(os.getenv("BIKEPULSE_HTTP_MAX_ATTEMPTS", "3")),
        log_level=os.getenv("BIKEPULSE_LOG_LEVEL", "INFO"),
    )

