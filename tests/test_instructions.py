from unittest.mock import patch

from dracula_manager.instructions import get_instructions, open_for_manual


def test_get_instructions_known_repo() -> None:
    steps = get_instructions("safari")
    assert isinstance(steps, list)
    assert len(steps) > 0


def test_get_instructions_unknown_repo() -> None:
    steps = get_instructions("unknown-app-xyz")
    assert steps == []


def test_open_for_manual_calls_bell() -> None:
    with (
        patch("dracula_manager.instructions.console") as mock_console,
        patch("dracula_manager.instructions.subprocess.run"),
    ):
        open_for_manual("safari")
    mock_console.bell.assert_called_once()


def test_open_for_manual_known_opener() -> None:
    with (
        patch("dracula_manager.instructions.console"),
        patch("dracula_manager.instructions.subprocess.run") as mock_run,
    ):
        open_for_manual("safari")
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "Safari" in call_args


def test_open_for_manual_unknown_no_subprocess() -> None:
    with (
        patch("dracula_manager.instructions.console"),
        patch("dracula_manager.instructions.subprocess.run") as mock_run,
    ):
        open_for_manual("unknown-app")
    mock_run.assert_not_called()
