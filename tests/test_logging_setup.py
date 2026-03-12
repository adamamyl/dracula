import logging
from pathlib import Path
from unittest.mock import patch

from freezegun import freeze_time

import dracula_manager.logging_setup as ls


def _reset_logging() -> None:
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()


def test_configure_logging_creates_log_file(tmp_path: Path) -> None:
    _reset_logging()
    with patch.object(ls, "LOG_DIR", tmp_path), freeze_time("2026-03-12"):
        ls.configure_logging()
    assert (tmp_path / "2026-03.log").exists()


def test_configure_logging_keeps_last_two(tmp_path: Path) -> None:
    _reset_logging()
    with patch.object(ls, "LOG_DIR", tmp_path):
        (tmp_path / "2026-01.log").touch()
        (tmp_path / "2026-02.log").touch()

        with freeze_time("2026-03-12"):
            ls.configure_logging()

        logs = sorted(tmp_path.glob("*.log"))
        assert len(logs) == 2
        assert (tmp_path / "2026-01.log") not in logs


def test_configure_logging_prunes_oldest(tmp_path: Path) -> None:
    _reset_logging()
    with patch.object(ls, "LOG_DIR", tmp_path):
        (tmp_path / "2025-12.log").touch()
        (tmp_path / "2026-01.log").touch()

        with freeze_time("2026-03-12"):
            ls.configure_logging()

        logs = sorted(tmp_path.glob("*.log"))
        names = [p.name for p in logs]
        assert "2025-12.log" not in names
        assert "2026-03.log" in names


def test_configure_logging_twice_leaves_two_files(tmp_path: Path) -> None:
    _reset_logging()
    with patch.object(ls, "LOG_DIR", tmp_path):
        with freeze_time("2026-02-01"):
            ls.configure_logging()
        _reset_logging()
        with freeze_time("2026-03-01"):
            ls.configure_logging()
        logs = sorted(tmp_path.glob("*.log"))
        assert len(logs) == 2
