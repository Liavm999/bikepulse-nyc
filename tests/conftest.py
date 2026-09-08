from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from bikepulse.config import Settings, load_settings


@pytest.fixture
def isolated_project(tmp_path: Path) -> Settings:
    source_root = Path(__file__).resolve().parents[1]
    for directory in ("config", "sql"):
        shutil.copytree(source_root / directory, tmp_path / directory)
    shutil.copytree(source_root / "data" / "sample", tmp_path / "data" / "sample")
    return load_settings(tmp_path)

