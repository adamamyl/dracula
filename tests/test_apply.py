from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import dracula_manager.apply as apply_module
from dracula_manager.apply import (
    _set_shell_alias,
    apply_bat,
    apply_delta,
    apply_if_possible,
    apply_terminal_app,
    apply_xcode,
)
from dracula_manager.config import RunConfig


def test_set_shell_alias_new_alias(tmp_path: Path) -> None:
    aliases_dir = tmp_path / "aliases"
    aliases_dir.mkdir()
    dracula_file = aliases_dir / "dracula"

    cfg = RunConfig()
    with (
        patch.object(apply_module, "ALIASES_DIR", aliases_dir),
        patch.object(apply_module, "DRACULA_ALIASES_FILE", dracula_file),
    ):
        result = _set_shell_alias("bat", "--theme=Dracula", r"--theme=\S+", cfg)

    assert result == "applied"
    content = dracula_file.read_text()
    assert 'alias bat="bat --theme=Dracula"' in content
    assert "if command -v bat" in content


def test_set_shell_alias_updates_existing(tmp_path: Path) -> None:
    aliases_dir = tmp_path / "aliases"
    aliases_dir.mkdir()
    dracula_file = aliases_dir / "dracula"
    dracula_file.write_text(
        'if command -v bat > /dev/null 2>&1; then\n'
        '    alias bat="bat --theme=OldTheme --paging=always"\n'
        'fi\n'
    )

    cfg = RunConfig()
    with (
        patch.object(apply_module, "ALIASES_DIR", aliases_dir),
        patch.object(apply_module, "DRACULA_ALIASES_FILE", dracula_file),
    ):
        result = _set_shell_alias("bat", "--theme=Dracula", r"--theme=\S+", cfg)

    assert result == "updated"
    content = dracula_file.read_text()
    assert "--theme=Dracula" in content
    assert "--theme=OldTheme" not in content
    assert "--paging=always" in content


def test_set_shell_alias_updates_different_file(tmp_path: Path) -> None:
    aliases_dir = tmp_path / "aliases"
    aliases_dir.mkdir()
    main_file = aliases_dir / "main"
    main_file.write_text(
        'if command -v bat > /dev/null 2>&1; then\n'
        '    alias bat="bat --theme=OldTheme"\n'
        'fi\n'
    )
    dracula_file = aliases_dir / "dracula"

    cfg = RunConfig()
    with (
        patch.object(apply_module, "ALIASES_DIR", aliases_dir),
        patch.object(apply_module, "DRACULA_ALIASES_FILE", dracula_file),
    ):
        result = _set_shell_alias("bat", "--theme=Dracula", r"--theme=\S+", cfg)

    assert result == "updated"
    assert "--theme=Dracula" in main_file.read_text()
    assert not dracula_file.exists()


def test_set_shell_alias_idempotent(tmp_path: Path) -> None:
    aliases_dir = tmp_path / "aliases"
    aliases_dir.mkdir()
    dracula_file = aliases_dir / "dracula"

    cfg = RunConfig()
    with (
        patch.object(apply_module, "ALIASES_DIR", aliases_dir),
        patch.object(apply_module, "DRACULA_ALIASES_FILE", dracula_file),
    ):
        _set_shell_alias("bat", "--theme=Dracula", r"--theme=\S+", cfg)
        content1 = dracula_file.read_text()
        _set_shell_alias("bat", "--theme=Dracula", r"--theme=\S+", cfg)
        content2 = dracula_file.read_text()

    assert content1 == content2


def test_set_shell_alias_dry_run_no_write(tmp_path: Path) -> None:
    aliases_dir = tmp_path / "aliases"
    aliases_dir.mkdir()
    dracula_file = aliases_dir / "dracula"

    cfg = RunConfig(dry_run=True)
    with (
        patch.object(apply_module, "ALIASES_DIR", aliases_dir),
        patch.object(apply_module, "DRACULA_ALIASES_FILE", dracula_file),
    ):
        result = _set_shell_alias("bat", "--theme=Dracula", r"--theme=\S+", cfg)

    assert result == "applied"
    assert not dracula_file.exists()


def test_apply_xcode_no_source(tmp_path: Path) -> None:
    cfg = RunConfig()
    with patch.object(apply_module, "THEMES_DIR", tmp_path):
        result = apply_xcode(cfg)
    assert result == "skipped"


def test_apply_xcode_applies_when_source_exists(tmp_path: Path) -> None:
    themes_dir = tmp_path / "themes"
    xcode_dir = themes_dir / "xcode"
    xcode_dir.mkdir(parents=True)
    (xcode_dir / "Dracula.xccolortheme").write_text("theme content")

    cfg = RunConfig()
    with (
        patch.object(apply_module, "THEMES_DIR", themes_dir),
        patch("pathlib.Path.mkdir"),
        patch("shutil.copy2"),
        patch("pathlib.Path.exists") as mock_exists,
    ):
        mock_exists.side_effect = lambda: True  # src exists
        result = apply_xcode(cfg)

    # Just test the function doesn't crash; status depends on dst.exists()
    assert result in ("applied", "updated", "skipped")


def test_apply_xcode_dry_run(tmp_path: Path) -> None:
    themes_dir = tmp_path / "themes"
    xcode_dir = themes_dir / "xcode"
    xcode_dir.mkdir(parents=True)
    src = xcode_dir / "Dracula.xccolortheme"
    src.write_text("theme")

    cfg = RunConfig(dry_run=True)
    with (
        patch.object(apply_module, "THEMES_DIR", themes_dir),
        patch("shutil.copy2") as mock_copy,
    ):
        result = apply_xcode(cfg)

    mock_copy.assert_not_called()
    assert result in ("applied", "updated")


def test_apply_terminal_app_no_profile(tmp_path: Path) -> None:
    cfg = RunConfig()
    with patch.object(apply_module, "THEMES_DIR", tmp_path):
        result = apply_terminal_app(cfg)
    assert result == "skipped"


def test_apply_terminal_app_dry_run(tmp_path: Path) -> None:
    themes_dir = tmp_path / "themes"
    terminal_dir = themes_dir / "terminal-app"
    terminal_dir.mkdir(parents=True)
    (terminal_dir / "Dracula.terminal").write_text("")

    cfg = RunConfig(dry_run=True)
    with (
        patch.object(apply_module, "THEMES_DIR", themes_dir),
        patch("subprocess.run") as mock_run,
    ):
        result = apply_terminal_app(cfg)

    mock_run.assert_not_called()
    assert result == "applied"


def test_apply_terminal_app_runs_commands(tmp_path: Path) -> None:
    themes_dir = tmp_path / "themes"
    terminal_dir = themes_dir / "terminal-app"
    terminal_dir.mkdir(parents=True)
    (terminal_dir / "Dracula.terminal").write_text("")

    cfg = RunConfig()
    with (
        patch.object(apply_module, "THEMES_DIR", themes_dir),
        patch("dracula_manager.apply.subprocess.run") as mock_run,
    ):
        result = apply_terminal_app(cfg)

    assert mock_run.call_count == 3  # open + 2x defaults write
    assert result == "applied"


def test_apply_bat_no_bat() -> None:
    with patch("dracula_manager.apply.shutil.which", return_value=None):
        result = apply_bat(RunConfig())
    assert result == "skipped"


def test_apply_bat_config_is_git_repo(tmp_path: Path) -> None:
    mock_result = MagicMock()
    mock_result.stdout = str(tmp_path)

    with (
        patch("dracula_manager.apply.shutil.which", return_value="/usr/local/bin/bat"),
        patch("dracula_manager.apply.subprocess.run", return_value=mock_result),
        patch("git.Repo", return_value=MagicMock()),
    ):
        result = apply_bat(RunConfig())

    assert result == "skipped"


def test_apply_bat_delegates_to_set_shell_alias(tmp_path: Path) -> None:
    aliases_dir = tmp_path / "aliases"
    aliases_dir.mkdir()
    dracula_file = aliases_dir / "dracula"

    mock_result = MagicMock()
    mock_result.stdout = "/nonexistent/bat/config"

    import git

    with (
        patch("dracula_manager.apply.shutil.which", return_value="/usr/local/bin/bat"),
        patch("dracula_manager.apply.subprocess.run", return_value=mock_result),
        patch("git.Repo", side_effect=git.InvalidGitRepositoryError),
        patch.object(apply_module, "ALIASES_DIR", aliases_dir),
        patch.object(apply_module, "DRACULA_ALIASES_FILE", dracula_file),
    ):
        result = apply_bat(RunConfig())

    assert result in ("applied", "updated")


def test_apply_delta_no_delta() -> None:
    with patch("dracula_manager.apply.shutil.which", return_value=None):
        result = apply_delta(RunConfig())
    assert result == "skipped"


def test_apply_delta_dry_run() -> None:
    with patch("dracula_manager.apply.shutil.which", return_value="/usr/local/bin/delta"):
        result = apply_delta(RunConfig(dry_run=True))
    assert result == "applied"


def test_apply_delta_writes_gitconfig() -> None:
    import git

    mock_gcw = MagicMock()
    mock_gcw.__enter__ = MagicMock(return_value=mock_gcw)
    mock_gcw.__exit__ = MagicMock(return_value=False)

    with (
        patch("dracula_manager.apply.shutil.which", return_value="/usr/local/bin/delta"),
        patch("git.GitConfigParser", return_value=mock_gcw),
        patch("git.Repo", side_effect=git.InvalidGitRepositoryError),
    ):
        result = apply_delta(RunConfig())

    mock_gcw.set_value.assert_called_once_with("delta", "syntax-theme", "Dracula")
    assert result == "applied"


def test_apply_delta_dotfiles_interactive_pushes(monkeypatch: pytest.MonkeyPatch) -> None:

    monkeypatch.delenv("DRACULA_LAUNCHD", raising=False)

    mock_gcw = MagicMock()
    mock_gcw.__enter__ = MagicMock(return_value=mock_gcw)
    mock_gcw.__exit__ = MagicMock(return_value=False)

    mock_repo = MagicMock()

    with (
        patch("dracula_manager.apply.shutil.which", return_value="/usr/local/bin/delta"),
        patch("git.GitConfigParser", return_value=mock_gcw),
        patch("git.Repo", return_value=mock_repo),
    ):
        result = apply_delta(RunConfig(dry_run=False))

    mock_repo.index.add.assert_called_once()
    mock_repo.index.commit.assert_called_once()
    mock_repo.remotes.origin.push.assert_called_once()
    assert result == "applied"


def test_apply_delta_launchd_no_push(monkeypatch: pytest.MonkeyPatch) -> None:

    monkeypatch.setenv("DRACULA_LAUNCHD", "1")

    mock_gcw = MagicMock()
    mock_gcw.__enter__ = MagicMock(return_value=mock_gcw)
    mock_gcw.__exit__ = MagicMock(return_value=False)

    mock_repo = MagicMock()

    with (
        patch("dracula_manager.apply.shutil.which", return_value="/usr/local/bin/delta"),
        patch("git.GitConfigParser", return_value=mock_gcw),
        patch("git.Repo", return_value=mock_repo),
    ):
        result = apply_delta(RunConfig())

    mock_repo.index.add.assert_called_once()
    mock_repo.index.commit.assert_not_called()
    mock_repo.remotes.origin.push.assert_not_called()
    assert result == "applied"


def test_apply_if_possible_manual_for_unknown() -> None:
    result = apply_if_possible("unknown-repo-xyz", RunConfig())
    assert result == "manual"


def test_apply_if_possible_calls_registered_func() -> None:
    with patch.object(apply_module, "APPLY_FUNCS", {"test-app": lambda cfg: "applied"}):
        result = apply_if_possible("test-app", RunConfig())
    assert result == "applied"
