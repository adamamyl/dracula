from pathlib import Path
from unittest.mock import MagicMock, patch

from dracula_manager.discovery import (
    DraculaApp,
    _parse_paths_ts,
    enrich_with_website_metadata,
    fetch_github_repos,
    fetch_website_metadata,
)

MINIMAL_TS = """
export const paths = [
  { repo: "iterm", title: "iTerm", platform: ["macos"],
    synonyms: ["iterm2"], categories: ["terminal"] },
  { repo: "vim", title: "Vim", platform: ["linux", "macos"],
    synonyms: [], categories: ["editor"] },
]
"""

NO_REPO_TS = """
export const paths = [
  { title: "NoRepo", platform: ["macos"] },
]
"""

NO_ARRAY_TS = "export const paths = {};"


def test_parse_paths_ts_basic() -> None:
    result = _parse_paths_ts(MINIMAL_TS)
    assert "iterm" in result
    assert result["iterm"]["title"] == "iTerm"
    assert result["iterm"]["platforms"] == ["macos"]
    assert result["iterm"]["synonyms"] == ["iterm2"]
    assert result["iterm"]["categories"] == ["terminal"]


def test_parse_paths_ts_skips_entries_without_repo() -> None:
    result = _parse_paths_ts(NO_REPO_TS)
    assert result == {}


def test_parse_paths_ts_no_array() -> None:
    result = _parse_paths_ts(NO_ARRAY_TS)
    assert result == {}


def test_parse_paths_ts_platform_singular_mapped() -> None:
    result = _parse_paths_ts(MINIMAL_TS)
    assert "platforms" in result["iterm"]
    assert result["iterm"]["platforms"] == ["macos"]


def test_parse_paths_ts_multiple_entries() -> None:
    result = _parse_paths_ts(MINIMAL_TS)
    assert "vim" in result
    assert result["vim"]["platforms"] == ["linux", "macos"]


def test_fetch_github_repos_populates_fields() -> None:
    mock_repo = MagicMock()
    mock_repo.name = "iterm"
    mock_repo.full_name = "dracula/iterm"
    mock_repo.clone_url = "https://github.com/dracula/iterm.git"
    mock_repo.description = "Dracula for iTerm"
    mock_repo.updated_at.isoformat.return_value = "2026-01-01T00:00:00"

    mock_org = MagicMock()
    mock_org.get_repos.return_value = [mock_repo]

    with patch("dracula_manager.discovery.Github") as MockGithub:
        MockGithub.return_value.get_organization.return_value = mock_org
        apps = fetch_github_repos()

    assert len(apps) == 1
    assert apps[0].repo_name == "iterm"
    assert apps[0].full_name == "dracula/iterm"
    assert apps[0].updated_at == "2026-01-01T00:00:00"


def test_fetch_github_repos_no_updated_at() -> None:
    mock_repo = MagicMock()
    mock_repo.name = "vim"
    mock_repo.full_name = "dracula/vim"
    mock_repo.clone_url = "https://github.com/dracula/vim.git"
    mock_repo.description = None
    mock_repo.updated_at = None

    mock_org = MagicMock()
    mock_org.get_repos.return_value = [mock_repo]

    with patch("dracula_manager.discovery.Github") as MockGithub:
        MockGithub.return_value.get_organization.return_value = mock_org
        apps = fetch_github_repos()

    assert apps[0].updated_at == ""
    assert apps[0].description == ""


def test_fetch_website_metadata_missing_paths_ts(tmp_path: Path) -> None:
    with patch("dracula_manager.discovery.git") as mock_git:
        mock_git.Repo.clone_from.return_value = MagicMock()
        with patch("tempfile.TemporaryDirectory") as mock_tmp:
            mock_tmp.return_value.__enter__.return_value = str(tmp_path)
            result = fetch_website_metadata()
    assert result == {}


def test_fetch_website_metadata_parses_paths_ts(tmp_path: Path) -> None:
    paths_dir = tmp_path / "src" / "lib"
    paths_dir.mkdir(parents=True)
    (paths_dir / "paths.ts").write_text(MINIMAL_TS)

    with patch("dracula_manager.discovery.git") as mock_git:
        mock_git.Repo.clone_from.return_value = MagicMock()
        with patch("tempfile.TemporaryDirectory") as mock_tmp:
            mock_tmp.return_value.__enter__.return_value = str(tmp_path)
            result = fetch_website_metadata()

    assert "iterm" in result


def test_enrich_with_website_metadata_populates_fields() -> None:
    apps = [DraculaApp(
        repo_name="iterm", full_name="dracula/iterm",
        clone_url="https://github.com/dracula/iterm.git",
        description="iTerm theme", updated_at="2026-01-01T00:00:00"
    )]

    with patch("dracula_manager.discovery.fetch_website_metadata") as mock_meta:
        mock_meta.return_value = {
            "iterm": {
                "title": "iTerm",
                "platforms": ["macos"],
                "synonyms": ["iterm2"],
                "categories": ["terminal"],
            }
        }
        result = enrich_with_website_metadata(apps)

    assert result[0].title == "iTerm"
    assert result[0].platforms == ["macos"]
    assert result[0].synonyms == ["iterm2"]
    assert result[0].categories == ["terminal"]


def test_enrich_does_not_overwrite_updated_at() -> None:
    apps = [DraculaApp(
        repo_name="iterm", full_name="dracula/iterm",
        clone_url="https://github.com/dracula/iterm.git",
        description="", updated_at="2026-01-01T00:00:00"
    )]

    with patch("dracula_manager.discovery.fetch_website_metadata") as mock_meta:
        mock_meta.return_value = {
            "iterm": {"title": "iTerm", "platforms": [], "synonyms": [], "categories": []}
        }
        result = enrich_with_website_metadata(apps)

    assert result[0].updated_at == "2026-01-01T00:00:00"
