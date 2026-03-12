import plistlib
from pathlib import Path
from unittest.mock import patch

import dracula_manager.launchd as launchd_module
from dracula_manager.launchd import _dracula_bin, install_agent, uninstall_agent


def test_dracula_bin_ends_with_expected_path() -> None:
    result = _dracula_bin()
    assert result.endswith("dracula.venv/bin/dracula")


def test_install_agent_writes_plist(tmp_path: Path) -> None:
    plist_path = tmp_path / "com.adamamyl.draculamanager.plist"
    log_dir = tmp_path / "logs"

    with (
        patch.object(launchd_module, "PLIST_PATH", plist_path),
        patch.object(launchd_module, "LOG_DIR", log_dir),
        patch("dracula_manager.launchd.subprocess.run"),
    ):
        install_agent(hour=9, minute=30)

    assert plist_path.exists()
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)

    assert plist["StartCalendarInterval"]["Hour"] == 9
    assert plist["StartCalendarInterval"]["Minute"] == 30
    assert plist["Label"] == "com.adamamyl.draculamanager"


def test_install_agent_sets_dracula_launchd_env(tmp_path: Path) -> None:
    plist_path = tmp_path / "agent.plist"
    log_dir = tmp_path / "logs"

    with (
        patch.object(launchd_module, "PLIST_PATH", plist_path),
        patch.object(launchd_module, "LOG_DIR", log_dir),
        patch("dracula_manager.launchd.subprocess.run"),
    ):
        install_agent()

    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)

    assert plist["EnvironmentVariables"]["DRACULA_LAUNCHD"] == "1"


def test_install_agent_calls_launchctl(tmp_path: Path) -> None:
    plist_path = tmp_path / "agent.plist"
    log_dir = tmp_path / "logs"

    with (
        patch.object(launchd_module, "PLIST_PATH", plist_path),
        patch.object(launchd_module, "LOG_DIR", log_dir),
        patch("dracula_manager.launchd.subprocess.run") as mock_run,
    ):
        install_agent()

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "launchctl" in call_args
    assert "load" in call_args


def test_uninstall_agent_no_error_when_absent(tmp_path: Path) -> None:
    plist_path = tmp_path / "nonexistent.plist"
    with patch.object(launchd_module, "PLIST_PATH", plist_path):
        uninstall_agent()  # should not raise


def test_uninstall_agent_removes_file(tmp_path: Path) -> None:
    plist_path = tmp_path / "agent.plist"
    plist_path.write_bytes(b"")

    with (
        patch.object(launchd_module, "PLIST_PATH", plist_path),
        patch("dracula_manager.launchd.subprocess.run"),
    ):
        uninstall_agent()

    assert not plist_path.exists()


def test_uninstall_agent_calls_launchctl_unload(tmp_path: Path) -> None:
    plist_path = tmp_path / "agent.plist"
    plist_path.write_bytes(b"")

    with (
        patch.object(launchd_module, "PLIST_PATH", plist_path),
        patch("dracula_manager.launchd.subprocess.run") as mock_run,
    ):
        uninstall_agent()

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "launchctl" in call_args
    assert "unload" in call_args
