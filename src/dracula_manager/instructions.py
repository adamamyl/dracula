import subprocess

from .console import console

MANUAL_INSTRUCTIONS: dict[str, list[str]] = {
    "safari": [
        "Install the Dracula Safari extension from the App Store.",
        "Enable in Safari → Settings → Extensions.",
    ],
}

BROWSER_SYNC_APPS = {
    "github", "duckduckgo", "hacker-news", "youtube",
    "stackoverflow", "google-calendar", "google",
}


def get_instructions(repo_name: str) -> list[str]:
    return MANUAL_INSTRUCTIONS.get(repo_name, [])


def open_for_manual(repo_name: str) -> None:
    console.bell()
    openers: dict[str, list[str]] = {
        "safari": ["open", "-a", "Safari"],
    }
    if cmd := openers.get(repo_name):
        subprocess.run(cmd, check=False)
