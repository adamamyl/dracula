from pathlib import Path
from unittest.mock import MagicMock, patch

import dracula_manager.themes as themes_module
from dracula_manager.config import RunConfig
from dracula_manager.discovery import DraculaApp
from dracula_manager.manifest import AppEntry, Manifest


def make_app(repo_name: str = "vim", updated_at: str = "2026-01-01T00:00:00") -> DraculaApp:
    return DraculaApp(
        repo_name=repo_name,
        full_name=f"dracula/{repo_name}",
        clone_url=f"https://github.com/dracula/{repo_name}.git",
        description="",
        updated_at=updated_at,
    )


def test_ensure_theme_clones_when_absent(tmp_path: Path) -> None:
    app = make_app()
    cfg = RunConfig()

    with (
        patch.object(themes_module, "THEMES_DIR", tmp_path),
        patch("dracula_manager.themes.git") as mock_git,
    ):
        mock_git.Repo.clone_from.return_value = MagicMock()
        result = themes_module.ensure_theme(app, cfg)

    assert result["status"] == "cloned"
    mock_git.Repo.clone_from.assert_called_once()


def test_ensure_theme_current_when_head_unchanged(tmp_path: Path) -> None:
    app = make_app()
    cfg = RunConfig()
    dest = tmp_path / "vim"
    dest.mkdir()

    mock_repo = MagicMock()
    mock_repo.head.commit.hexsha = "abc123"

    with (
        patch.object(themes_module, "THEMES_DIR", tmp_path),
        patch("dracula_manager.themes.git") as mock_git,
    ):
        mock_git.Repo.return_value = mock_repo
        mock_repo.remotes.origin.pull.return_value = None
        result = themes_module.ensure_theme(app, cfg)

    assert result["status"] == "current"


def test_ensure_theme_updated_when_head_changes(tmp_path: Path) -> None:
    app = make_app()
    cfg = RunConfig()
    dest = tmp_path / "vim"
    dest.mkdir()

    mock_repo = MagicMock()
    mock_repo.head.commit.hexsha = "abc123"

    call_count = 0

    def hexsha_side_effect() -> str:
        nonlocal call_count
        call_count += 1
        return "abc123" if call_count == 1 else "def456"

    type(mock_repo.head.commit).hexsha = property(lambda self: hexsha_side_effect())

    with (
        patch.object(themes_module, "THEMES_DIR", tmp_path),
        patch("dracula_manager.themes.git") as mock_git,
    ):
        mock_git.Repo.return_value = mock_repo
        result = themes_module.ensure_theme(app, cfg)

    assert result["status"] in ("current", "updated")


def test_ensure_theme_dry_run_no_clone(tmp_path: Path) -> None:
    app = make_app()
    cfg = RunConfig(dry_run=True)

    with (
        patch.object(themes_module, "THEMES_DIR", tmp_path),
        patch("dracula_manager.themes.git") as mock_git,
    ):
        result = themes_module.ensure_theme(app, cfg)

    assert result["status"] == "would-clone"
    mock_git.Repo.clone_from.assert_not_called()


def test_ensure_theme_git_error(tmp_path: Path) -> None:
    import git

    app = make_app()
    cfg = RunConfig()

    with (
        patch.object(themes_module, "THEMES_DIR", tmp_path),
        patch("dracula_manager.themes.git") as mock_git,
    ):
        mock_git.Repo.clone_from.side_effect = git.GitCommandError("clone", 1)
        mock_git.GitCommandError = git.GitCommandError
        result = themes_module.ensure_theme(app, cfg)

    assert result["status"] == "error"
    assert "error" in result


def test_needs_processing_no_manifest() -> None:
    app = make_app()
    assert themes_module.needs_processing(app, None) is True


def test_needs_processing_app_not_in_manifest() -> None:
    app = make_app("vim")
    m = Manifest(hostname="test", last_run="2026-01-01", apps=[])
    assert themes_module.needs_processing(app, m) is True


def test_needs_processing_newer_upstream() -> None:
    app = make_app("vim", updated_at="2026-02-01T00:00:00")
    entry = AppEntry(repo_name="vim", status="current", last_updated="2026-01-01T00:00:00")
    m = Manifest(hostname="test", last_run="2026-01-01", apps=[entry])
    assert themes_module.needs_processing(app, m) is True


def test_needs_processing_same_timestamp() -> None:
    app = make_app("vim", updated_at="2026-01-01T00:00:00")
    entry = AppEntry(repo_name="vim", status="current", last_updated="2026-01-01T00:00:00")
    m = Manifest(hostname="test", last_run="2026-01-01", apps=[entry])
    assert themes_module.needs_processing(app, m) is False


def test_needs_processing_empty_timestamps() -> None:
    app = make_app("vim", updated_at="")
    entry = AppEntry(repo_name="vim", status="current", last_updated="")
    m = Manifest(hostname="test", last_run="2026-01-01", apps=[entry])
    assert themes_module.needs_processing(app, m) is True


def test_ensure_all_themes_force(tmp_path: Path) -> None:
    apps = [make_app("vim"), make_app("bat")]
    cfg = RunConfig(force=True)
    entry = AppEntry(repo_name="vim", status="current", last_updated="2026-01-01T00:00:00")
    m = Manifest(hostname="test", last_run="2026-01-01", apps=[entry])

    with (
        patch.object(themes_module, "THEMES_DIR", tmp_path),
        patch("dracula_manager.themes.ensure_theme") as mock_ensure,
    ):
        mock_ensure.side_effect = lambda app, cfg, **kw: {
            "repo": app.repo_name, "status": "cloned", "path": str(tmp_path / app.repo_name)
        }
        results = themes_module.ensure_all_themes(apps, cfg, m)

    assert len(results) == 2
    statuses = {r["repo"]: r["status"] for r in results}
    assert statuses["vim"] == "cloned"
    assert statuses["bat"] == "cloned"


def test_ensure_all_themes_skips_unchanged(tmp_path: Path) -> None:
    app_vim = make_app("vim", updated_at="2026-01-01T00:00:00")
    app_bat = make_app("bat", updated_at="2026-02-01T00:00:00")
    cfg = RunConfig(force=False)
    entry = AppEntry(repo_name="vim", status="current", last_updated="2026-01-01T00:00:00")
    m = Manifest(hostname="test", last_run="2026-01-01", apps=[entry])

    with (
        patch.object(themes_module, "THEMES_DIR", tmp_path),
        patch("dracula_manager.themes.ensure_theme") as mock_ensure,
    ):
        mock_ensure.side_effect = lambda app, cfg, **kw: {
            "repo": app.repo_name, "status": "cloned", "path": str(tmp_path / app.repo_name)
        }
        results = themes_module.ensure_all_themes([app_vim, app_bat], cfg, m)

    assert len(results) == 2
    statuses = {r["repo"]: r["status"] for r in results}
    assert statuses["vim"] == "current"
    assert statuses["bat"] == "cloned"


def test_ensure_all_themes_one_per_app(tmp_path: Path) -> None:
    apps = [make_app("vim"), make_app("bat"), make_app("iterm")]
    cfg = RunConfig(force=True)

    with (
        patch.object(themes_module, "THEMES_DIR", tmp_path),
        patch("dracula_manager.themes.ensure_theme") as mock_ensure,
    ):
        mock_ensure.side_effect = lambda app, cfg, **kw: {
            "repo": app.repo_name, "status": "cloned", "path": str(tmp_path / app.repo_name)
        }
        results = themes_module.ensure_all_themes(apps, cfg)

    assert len(results) == 3
