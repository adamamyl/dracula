import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from dracula_manager.cli import app
from dracula_manager.discovery import DraculaApp
from dracula_manager.manifest import AppEntry, Manifest

runner = CliRunner()


def make_app(repo_name: str = "vim") -> DraculaApp:
    return DraculaApp(
        repo_name=repo_name,
        full_name=f"dracula/{repo_name}",
        clone_url=f"https://github.com/dracula/{repo_name}.git",
        description="",
    )


def make_sync_result(repo_name: str, status: str = "current") -> dict[str, str]:
    return {"repo": repo_name, "status": status, "path": f"/tmp/themes/{repo_name}"}


def test_resolve_github_token_explicit() -> None:
    from dracula_manager.cli import _resolve_github_token
    result = _resolve_github_token("mytoken")
    assert result == "mytoken"


def test_resolve_github_token_op_success() -> None:
    from dracula_manager.cli import _resolve_github_token
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "  optoken  \n"
    with patch("dracula_manager.cli.subprocess.run", return_value=mock_result):
        result = _resolve_github_token(None)
    assert result == "optoken"


def test_resolve_github_token_op_not_found() -> None:
    from dracula_manager.cli import _resolve_github_token
    with patch("dracula_manager.cli.subprocess.run", side_effect=FileNotFoundError):
        result = _resolve_github_token(None)
    assert result is None


def test_resolve_github_token_op_timeout() -> None:
    from dracula_manager.cli import _resolve_github_token
    with patch(
        "dracula_manager.cli.subprocess.run",
        side_effect=subprocess.TimeoutExpired("op", 5),
    ):
        result = _resolve_github_token(None)
    assert result is None


def test_sync_dry_run() -> None:
    with (
        patch("dracula_manager.cli.discovery.fetch_github_repos", return_value=[make_app()]),
        patch(
            "dracula_manager.cli.discovery.enrich_with_website_metadata",
            return_value=[make_app()],
        ),
        patch("dracula_manager.cli.detection.get_installed_apps", return_value={"vim"}),
        patch(
            "dracula_manager.cli.detection.match_installed_to_themes",
            return_value=[make_app()],
        ),
        patch("dracula_manager.cli.manifest.load_manifest", return_value=None),
        patch(
            "dracula_manager.cli.themes.ensure_all_themes",
            return_value=[make_sync_result("vim")],
        ),
        patch("dracula_manager.cli.apply.apply_if_possible", return_value="manual"),
        patch("dracula_manager.cli.instructions.get_instructions", return_value=[]),
        patch("dracula_manager.cli.manifest.save_manifest") as mock_save,
    ):
        result = runner.invoke(app, ["sync", "--dry-run"])

    assert result.exit_code == 0
    mock_save.assert_not_called()


def test_sync_quiet_no_output() -> None:
    with (
        patch("dracula_manager.cli.discovery.fetch_github_repos", return_value=[]),
        patch("dracula_manager.cli.discovery.enrich_with_website_metadata", return_value=[]),
        patch("dracula_manager.cli.detection.get_installed_apps", return_value=set()),
        patch("dracula_manager.cli.detection.match_installed_to_themes", return_value=[]),
        patch("dracula_manager.cli.manifest.load_manifest", return_value=None),
        patch("dracula_manager.cli.themes.ensure_all_themes", return_value=[]),
        patch(
            "dracula_manager.cli.manifest.save_manifest",
            return_value=Path("/tmp/manifest.json"),
        ),
        patch("dracula_manager.cli._commit_manifest"),
        patch("dracula_manager.cli._print_summary"),
    ):
        result = runner.invoke(app, ["sync", "--quiet"])

    assert result.exit_code == 0


def test_sync_update_only_filters_to_known() -> None:
    existing_manifest = Manifest(
        hostname="test",
        last_run="2026-01-01",
        apps=[AppEntry(repo_name="vim", status="current")],
    )
    with (
        patch(
            "dracula_manager.cli.discovery.fetch_github_repos",
            return_value=[make_app("vim"), make_app("bat")],
        ),
        patch(
            "dracula_manager.cli.discovery.enrich_with_website_metadata",
            return_value=[make_app("vim"), make_app("bat")],
        ),
        patch("dracula_manager.cli.detection.get_installed_apps", return_value={"vim", "bat"}),
        patch(
            "dracula_manager.cli.detection.match_installed_to_themes",
            return_value=[make_app("vim"), make_app("bat")],
        ),
        patch("dracula_manager.cli.manifest.load_manifest", return_value=existing_manifest),
        patch("dracula_manager.cli.themes.ensure_all_themes") as mock_ensure,
        patch("dracula_manager.cli.apply.apply_if_possible", return_value="manual"),
        patch("dracula_manager.cli.instructions.get_instructions", return_value=[]),
        patch(
            "dracula_manager.cli.manifest.save_manifest",
            return_value=Path("/tmp/manifest.json"),
        ),
        patch("dracula_manager.cli._commit_manifest"),
    ):
        mock_ensure.return_value = [make_sync_result("vim")]
        result = runner.invoke(app, ["sync", "--update-only", "--quiet"])

    assert result.exit_code == 0
    called_apps = mock_ensure.call_args[0][0]
    assert len(called_apps) == 1
    assert called_apps[0].repo_name == "vim"


def test_status_no_manifest() -> None:
    with patch("dracula_manager.cli.manifest.load_manifest", return_value=None):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 1


def test_status_with_manifest() -> None:
    m = Manifest(
        hostname="testhost",
        last_run="2026-01-01T00:00:00",
        apps=[AppEntry(repo_name="vim", status="applied")],
    )
    with patch("dracula_manager.cli.manifest.load_manifest", return_value=m):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "vim" in result.output


def test_install_launchd_calls_agent(tmp_path: Path) -> None:
    with patch("dracula_manager.cli.launchd.install_agent") as mock_install:
        result = runner.invoke(app, ["install-launchd", "--hour", "9", "--minute", "30"])
    assert result.exit_code == 0
    mock_install.assert_called_once_with(hour=9, minute=30)


def test_uninstall_launchd_calls_agent() -> None:
    with patch("dracula_manager.cli.launchd.uninstall_agent") as mock_uninstall:
        result = runner.invoke(app, ["uninstall-launchd"])
    assert result.exit_code == 0
    mock_uninstall.assert_called_once()


def test_sync_show_new_prints_second_table() -> None:
    with (
        patch(
            "dracula_manager.cli.discovery.fetch_github_repos",
            return_value=[make_app("vim")],
        ),
        patch(
            "dracula_manager.cli.discovery.enrich_with_website_metadata",
            return_value=[make_app("vim")],
        ),
        patch("dracula_manager.cli.detection.get_installed_apps", return_value={"vim"}),
        patch(
            "dracula_manager.cli.detection.match_installed_to_themes",
            return_value=[make_app("vim")],
        ),
        patch("dracula_manager.cli.manifest.load_manifest", return_value=None),
        patch(
            "dracula_manager.cli.themes.ensure_all_themes",
            return_value=[make_sync_result("vim")],
        ),
        patch("dracula_manager.cli.apply.apply_if_possible", return_value="manual"),
        patch("dracula_manager.cli.instructions.get_instructions", return_value=[]),
        patch(
            "dracula_manager.cli.manifest.save_manifest",
            return_value=Path("/tmp/manifest.json"),
        ),
        patch("dracula_manager.cli._commit_manifest"),
        patch("dracula_manager.cli._print_new_themes") as mock_new,
    ):
        result = runner.invoke(app, ["sync", "--show-new"])

    assert result.exit_code == 0
    mock_new.assert_called_once()


def test_commit_manifest_interactive_pushes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dracula_manager.cli import _commit_manifest
    from dracula_manager.config import RunConfig

    monkeypatch.delenv("DRACULA_LAUNCHD", raising=False)

    saved = tmp_path / "machines" / "testhost" / "manifest.json"
    saved.parent.mkdir(parents=True)
    saved.write_text("{}")

    mock_repo = MagicMock()
    mock_repo.working_dir = str(tmp_path)
    mock_repo.is_dirty.return_value = True

    with patch("git.Repo", return_value=mock_repo):
        _commit_manifest(saved, RunConfig())

    mock_repo.index.commit.assert_called_once()
    mock_repo.remotes.origin.push.assert_called_once()


def test_commit_manifest_launchd_no_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dracula_manager.cli import _commit_manifest
    from dracula_manager.config import RunConfig

    monkeypatch.setenv("DRACULA_LAUNCHD", "1")

    saved = tmp_path / "machines" / "testhost" / "manifest.json"
    saved.parent.mkdir(parents=True)
    saved.write_text("{}")

    mock_repo = MagicMock()
    mock_repo.working_dir = str(tmp_path)
    mock_repo.is_dirty.return_value = True

    with patch("git.Repo", return_value=mock_repo):
        _commit_manifest(saved, RunConfig())

    mock_repo.index.commit.assert_called_once()
    mock_repo.remotes.origin.push.assert_not_called()
