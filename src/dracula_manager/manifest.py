import socket
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

MACHINES_DIR = Path("~/projects/dracula/machines").expanduser()


class AppEntry(BaseModel):
    repo_name: str
    status: str
    path: str | None = None
    manual_steps: list[str] = []
    last_updated: str = ""


class Manifest(BaseModel):
    hostname: str
    last_run: str
    apps: list[AppEntry]


def manifest_path(hostname: str | None = None) -> Path:
    host = hostname or socket.gethostname().split(".")[0]
    return MACHINES_DIR / host / "manifest.json"


def load_manifest(hostname: str | None = None) -> Manifest | None:
    path = manifest_path(hostname)
    if path.exists():
        return Manifest.model_validate_json(path.read_text())
    return None


def save_manifest(entries: list[AppEntry], hostname: str | None = None) -> Path:
    host = hostname or socket.gethostname().split(".")[0]
    path = manifest_path(host)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(
        hostname=host,
        last_run=datetime.now(UTC).isoformat(),
        apps=entries,
    )
    path.write_text(manifest.model_dump_json(indent=2))
    return path
