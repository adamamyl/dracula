import os

import pytest

from dracula_manager.config import RunConfig


def test_from_env_quiet_when_launchd_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRACULA_LAUNCHD", "1")
    cfg = RunConfig.from_env()
    assert cfg.quiet is True


def test_from_env_not_quiet_when_launchd_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DRACULA_LAUNCHD", raising=False)
    cfg = RunConfig.from_env()
    assert cfg.quiet is False


def test_launchd_property_reflects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRACULA_LAUNCHD", "1")
    cfg = RunConfig()
    assert cfg.launchd is True


def test_launchd_property_false_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DRACULA_LAUNCHD", raising=False)
    cfg = RunConfig()
    assert cfg.launchd is False


def test_launchd_independent_of_quiet() -> None:
    cfg = RunConfig(quiet=True)
    # launchd depends on env var, not quiet flag
    assert "DRACULA_LAUNCHD" not in os.environ or cfg.launchd
