import shutil
import subprocess
from pathlib import Path

from .discovery import DraculaApp


def get_installed_apps() -> set[str]:
    found: set[str] = set()
    found |= _from_applications_dir()
    found |= _from_brew()
    found |= _from_brew_cask()
    found |= _from_mas()
    found |= _from_config_hints()
    found |= _from_library_app_support()
    return found


def _from_applications_dir() -> set[str]:
    apps = set()
    for path in [Path("/Applications"), Path.home() / "Applications"]:
        for app in path.glob("*.app"):
            apps.add(_normalise(app.stem))
    return apps


def _from_brew() -> set[str]:
    if not shutil.which("brew"):
        return set()
    try:
        result = subprocess.run(
            ["brew", "list", "--formula"], capture_output=True, text=True, check=True
        )
        return {_normalise(line) for line in result.stdout.splitlines() if line.strip()}
    except subprocess.CalledProcessError:
        return set()


def _from_brew_cask() -> set[str]:
    if not shutil.which("brew"):
        return set()
    try:
        result = subprocess.run(
            ["brew", "list", "--cask"], capture_output=True, text=True, check=True
        )
        return {_normalise(line) for line in result.stdout.splitlines() if line.strip()}
    except subprocess.CalledProcessError:
        return set()


def _from_mas() -> set[str]:
    if not shutil.which("mas"):
        return set()
    try:
        result = subprocess.run(
            ["mas", "list"], capture_output=True, text=True, check=True
        )
        names = set()
        for line in result.stdout.splitlines():
            parts = line.split(None, 2)
            if len(parts) >= 2:
                names.add(_normalise(parts[1]))
        return names
    except subprocess.CalledProcessError:
        return set()


def _from_config_hints() -> set[str]:
    hints: dict[str, Path] = {
        "vim":       Path.home() / ".vimrc",
        "neovim":    Path.home() / ".config" / "nvim",
        "tmux":      Path.home() / ".tmux.conf",
        "zsh":       Path.home() / ".zshrc",
        "bash":      Path.home() / ".bashrc",
        "git":       Path.home() / ".gitconfig",
        "fish":      Path.home() / ".config" / "fish",
        "alacritty": Path.home() / ".config" / "alacritty",
        "kitty":     Path.home() / ".config" / "kitty",
        "wezterm":   Path.home() / ".config" / "wezterm",
        "iterm":     Path("~/Library/Application Support/iTerm2").expanduser(),
        "bat":       Path("~/Library/Application Support/bat").expanduser(),
        "delta":     Path.home() / ".gitconfig",
    }
    return {name for name, path in hints.items() if path.exists()}


def _from_library_app_support() -> set[str]:
    lib = Path("~/Library/Application Support").expanduser()
    if not lib.exists():
        return set()
    return {_normalise(p.name) for p in lib.iterdir() if p.is_dir()}


def _normalise(name: str) -> str:
    return name.lower().replace(" ", "-").removesuffix(".app")


def match_installed_to_themes(
    installed: set[str],
    themes: list[DraculaApp],
) -> list[DraculaApp]:
    matched = []
    for theme in themes:
        candidates = {_normalise(theme.repo_name)} | {_normalise(s) for s in theme.synonyms}
        if candidates & installed:
            matched.append(theme)
    return matched
