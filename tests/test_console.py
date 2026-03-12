from unittest.mock import patch

from dracula_manager.console import bat_warn, coffin_error, vampire_print


def test_coffin_error_calls_bell() -> None:
    with patch("dracula_manager.console.console") as mock_console:
        coffin_error("something went wrong")
        mock_console.print.assert_called_once()
        mock_console.bell.assert_called_once()


def test_vampire_print_uses_info_style_by_default() -> None:
    with patch("dracula_manager.console.console") as mock_console:
        vampire_print("hello")
        mock_console.print.assert_called_once()
        call_kwargs = mock_console.print.call_args
        assert call_kwargs.kwargs.get("style") == "info"


def test_bat_warn_uses_warning_style() -> None:
    with patch("dracula_manager.console.console") as mock_console:
        bat_warn("watch out")
        mock_console.print.assert_called_once()
        call_kwargs = mock_console.print.call_args
        assert call_kwargs.kwargs.get("style") == "warning"


def test_vampire_print_custom_style() -> None:
    with patch("dracula_manager.console.console") as mock_console:
        vampire_print("hello", style="success")
        call_kwargs = mock_console.print.call_args
        assert call_kwargs.kwargs.get("style") == "success"
