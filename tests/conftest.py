from pathlib import Path

import pytest

from dracula_manager.config import RunConfig


@pytest.fixture
def tmp_aliases_dir(tmp_path: Path) -> Path:
    d = tmp_path / "aliases"
    d.mkdir()
    return d


@pytest.fixture
def mock_cfg() -> RunConfig:
    return RunConfig()


@pytest.fixture
def dry_cfg() -> RunConfig:
    return RunConfig(dry_run=True)
