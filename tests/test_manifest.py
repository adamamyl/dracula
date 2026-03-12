from pathlib import Path
from unittest.mock import patch

import dracula_manager.manifest as manifest_module
from dracula_manager.manifest import AppEntry, Manifest, load_manifest, manifest_path, save_manifest


def test_manifest_path_uses_short_hostname(tmp_path: Path) -> None:
    with (
        patch.object(manifest_module, "MACHINES_DIR", tmp_path),
        patch("socket.gethostname", return_value="myhost.local"),
    ):
        path = manifest_path()
    assert path == tmp_path / "myhost" / "manifest.json"


def test_manifest_path_with_explicit_hostname(tmp_path: Path) -> None:
    with patch.object(manifest_module, "MACHINES_DIR", tmp_path):
        path = manifest_path("testhost")
    assert path == tmp_path / "testhost" / "manifest.json"


def test_load_manifest_returns_none_when_absent(tmp_path: Path) -> None:
    with patch.object(manifest_module, "MACHINES_DIR", tmp_path):
        result = load_manifest("nonexistent")
    assert result is None


def test_save_manifest_round_trip(tmp_path: Path) -> None:
    entries = [
        AppEntry(repo_name="vim", status="applied", path="/some/path", last_updated="2026-01-01"),
        AppEntry(repo_name="bat", status="current"),
    ]
    with (
        patch.object(manifest_module, "MACHINES_DIR", tmp_path),
        patch("socket.gethostname", return_value="testhost"),
    ):
        save_manifest(entries)
        loaded = load_manifest("testhost")

    assert loaded is not None
    assert loaded.hostname == "testhost"
    assert len(loaded.apps) == 2
    assert loaded.apps[0].repo_name == "vim"
    assert loaded.apps[0].status == "applied"
    assert loaded.apps[1].repo_name == "bat"


def test_save_manifest_creates_parent_dir(tmp_path: Path) -> None:
    entries = [AppEntry(repo_name="vim", status="applied")]
    with (
        patch.object(manifest_module, "MACHINES_DIR", tmp_path),
        patch("socket.gethostname", return_value="newhost"),
    ):
        save_manifest(entries)
    assert (tmp_path / "newhost" / "manifest.json").exists()


def test_load_manifest_parses_json(tmp_path: Path) -> None:
    host_dir = tmp_path / "myhost"
    host_dir.mkdir()
    manifest_file = host_dir / "manifest.json"
    m = Manifest(
        hostname="myhost",
        last_run="2026-01-01T00:00:00",
        apps=[AppEntry(repo_name="vim", status="applied")],
    )
    manifest_file.write_text(m.model_dump_json(indent=2))

    with patch.object(manifest_module, "MACHINES_DIR", tmp_path):
        loaded = load_manifest("myhost")

    assert loaded is not None
    assert loaded.hostname == "myhost"
    assert loaded.apps[0].repo_name == "vim"
