import plistlib
import subprocess
from pathlib import Path

AGENT_LABEL = "com.adamamyl.draculamanager"
PLIST_PATH = Path.home() / "Library/LaunchAgents" / f"{AGENT_LABEL}.plist"
LOG_DIR = Path("~/projects/dracula/logs").expanduser()


def _dracula_bin() -> str:
    return str(Path("~/projects/dracula/dracula.venv/bin/dracula").expanduser())


def install_agent(hour: int = 15, minute: int = 0) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = str(LOG_DIR / "dracula-launchd.log")

    plist: dict[str, object] = {
        "Label": AGENT_LABEL,
        "ProgramArguments": [_dracula_bin(), "sync", "--quiet"],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "RunAtLoad": False,
        "StandardOutPath": log_file,
        "StandardErrorPath": log_file,
        "WorkingDirectory": str(Path("~/projects/dracula").expanduser()),
        "EnvironmentVariables": {
            "DRACULA_LAUNCHD": "1",
        },
    }

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist, f)

    subprocess.run(["launchctl", "load", "-w", str(PLIST_PATH)], check=True)


def uninstall_agent() -> None:
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False)
        PLIST_PATH.unlink()
