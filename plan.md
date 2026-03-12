# Dracula Theme Manager

I'm a serial terminal user who hates bright mode. This project keeps my entire machine consistently
themed with [Dracula](https://draculatheme.com/) across every supported app.

## What it does

- Discovers all apps the Dracula project supports (400+ repos at `github.com/dracula`)
- Detects which of those apps are installed on the current machine
- Manages theme checkouts in `~/projects/dracula/themes/` (standalone clones)
- Tells you what manual steps are needed where automation isn't possible; automates everything it can
- Keeps a per-machine manifest in a git repo so the setup can be reproduced
- Runs automatically via macOS launchd at 15:00 daily, logging changes monthly
- Produces Dracula-themed Rich output when run interactively; silent (errors only) when run by launchd

---

## Project structure

```
~/projects/dracula/
├── plan.md                          ← this file
├── pyproject.toml
├── .pre-commit-config.yaml
├── .python-version
├── dracula.venv/                    ← uv-managed venv (fixed path)
├── machines/
│   └── glaedr/                      ← $(hostname -s)
│       └── manifest.json
├── themes/                          ← git checkouts of dracula/* repos
│   ├── vim/
│   ├── iterm/
│   └── ...
├── logs/
│   ├── 2026-03.log                  ← current month
│   └── 2026-02.log                  ← previous month (older pruned)
└── src/
    └── dracula_manager/
        ├── __init__.py
        ├── __main__.py              ← entrypoint: `python -m dracula_manager`
        ├── cli.py                   ← Typer CLI
        ├── config.py                ← RunConfig dataclass (flags propagated to all modules)
        ├── discovery.py             ← fetch supported apps from GitHub org + draculatheme.com repo
        ├── detection.py             ← detect installed apps on this machine
        ├── themes.py                ← manage git checkouts
        ├── manifest.py              ← read/write machines/<host>/manifest.json
        ├── launchd.py               ← install/uninstall the launchd agent
        ├── apply.py                 ← automate theme application where possible
        ├── instructions.py          ← generate manual-step instructions per app
        └── console.py               ← shared Rich console, Dracula palette, helpers
```

---

## Flags

All flags are passed via a `RunConfig` dataclass (see `config.py`) so they propagate naturally
from the CLI layer down into every module without globals or extra parameters threading through
every function signature.

| Flag | Effect |
|------|--------|
| `--dry-run` | Show what would be done; make no changes to disk, git, or config files |
| `--verbose` | Extra output: show each theme being checked, detection sources used, etc. |
| `--debug` | Developer-level output: raw API responses, git commands, file paths |
| `--quiet` | Errors only; suppress all Rich output (also set automatically by launchd via `DRACULA_LAUNCHD=1`) |
| `--force` | Skip the "only update what's changed" optimisation; re-clone/pull and re-apply everything |
| `--update-only` | Only process themes already in the manifest that have a newer upstream commit; skip new discoveries |
| `--show-new` | After sync, print a table of themes available for newly-detected apps not yet in the manifest |

Flags are not mutually exclusive where sensible (e.g. `--dry-run --verbose` is useful). `--quiet`
and `--verbose`/`--debug` are mutually exclusive; `--quiet` wins.

---

## Output table

When running interactively (not quiet), the sync command prints a Rich table at the end summarising
what happened. Columns:

| Column | Notes |
|--------|-------|
| App | repo slug, e.g. `iterm` |
| Status | distinct emoji: `applied` ✔, `updated` ⬆, `cloned` ⬇, `current` —, `skipped` ⏭, `error` ⚰️, `manual` 🧄 |
| Platform match | ✔ if the theme's `platform` list includes `macos`; `?` if unknown |
| Action taken | brief human description, e.g. "copied to Xcode themes dir", "alias written to dotfiles" |
| Manual steps | non-empty only for apps requiring human action; rings bell 🔔 when any are present |

The `--show-new` flag appends a second table listing themes available for detected apps that have
never been synced, so the operator can decide to add them.

---

## Dependencies & tooling

### `pyproject.toml`

```toml
[project]
name = "dracula-manager"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "typer[all]>=0.12",          # CLI framework (includes rich)
    "rich>=13",                   # Dracula-themed terminal output
    "PyGithub>=2.3",              # GitHub API — list dracula/* repos, check for updates
    "gitpython>=3.1",             # Manage git clones, config reads/writes, add/commit/push
    "pydantic>=2",                # Validate manifest + config schemas
    "json5>=0.9",                 # Parse TypeScript/JS object literals from draculatheme.com src
    "tenacity>=8",                # Retry logic for GitHub API rate limits and transient git failures
]

[dependency-groups]
dev = [
    "ruff>=0.4",
    "mypy>=1.10",
    "bandit>=1.7",
    "pre-commit>=3",
    "pytest>=8",
    "pytest-mock>=3",             # mocker fixture — mock subprocess, git.Repo, GitHub API
    "pytest-cov>=5",              # coverage reporting
    "freezegun>=1",               # freeze datetime.now() in timestamp-sensitive tests
]

[project.scripts]
dracula = "dracula_manager.cli:app"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
strict = true
python_version = "3.12"

[tool.uv]
venv = "dracula.venv"
```

Note: `httpx` and `beautifulsoup4` are **not** needed — metadata comes from the draculatheme.com
source repo, not from scraping the live site.

### Setup

```bash
# create venv at the fixed path dracula.venv
uv sync

# install pre-commit hooks
uv run pre-commit install

# run
uv run dracula --help
```

---

## Pre-commit hooks

### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, json5]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.8
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
```

---

## Core modules

### `config.py` — shared run configuration

A single dataclass is created by the CLI and passed into every function that needs to
respect flags. Avoids global state and makes dry-run / verbose behaviour consistent everywhere.

```python
from dataclasses import dataclass
import os


@dataclass
class RunConfig:
    dry_run:     bool = False
    verbose:     bool = False
    debug:       bool = False
    quiet:       bool = False
    force:       bool = False
    update_only: bool = False
    show_new:    bool = False

    @classmethod
    def from_env(cls) -> "RunConfig":
        """Build a RunConfig from environment (used by launchd invocation)."""
        return cls(quiet=bool(os.getenv("DRACULA_LAUNCHD")))

    @property
    def launchd(self) -> bool:
        return bool(os.getenv("DRACULA_LAUNCHD"))
```

---

### `console.py` — Dracula palette + shared console

```python
from rich.console import Console
from rich.theme import Theme

# Official Dracula palette
DRACULA = {
    "background":  "#282a36",
    "foreground":  "#f8f8f2",
    "comment":     "#6272a4",
    "cyan":        "#8be9fd",
    "green":       "#50fa7b",
    "orange":      "#ffb86c",
    "pink":        "#ff79c6",
    "purple":      "#bd93f9",
    "red":         "#ff5555",
    "yellow":      "#f1fa8c",
}

dracula_theme = Theme({
    "info":      "bold " + DRACULA["cyan"],
    "success":   "bold " + DRACULA["green"],
    "warning":   "bold " + DRACULA["orange"],
    "error":     "bold " + DRACULA["red"],
    "muted":     DRACULA["comment"],
    "accent":    DRACULA["purple"],
    "highlight": DRACULA["pink"],
})

console = Console(theme=dracula_theme)

def vampire_print(msg: str, style: str = "info") -> None:
    console.print(f"🧛🏻 {msg}", style=style)

def bat_warn(msg: str) -> None:
    console.print(f"🦇 {msg}", style="warning")

def coffin_error(msg: str) -> None:
    console.print(f"⚰️  {msg}", style="error")
    console.bell()
```

---

### `discovery.py` — find all Dracula-supported apps

Two complementary sources, both from GitHub — no live-site scraping needed:

1. **`github.com/dracula` org API** — authoritative list of repos; each repo = one theme
2. **`github.com/dracula/draculatheme.com` source repo** — the website's own data file
   `src/lib/paths.ts` contains structured metadata per theme: title, platforms, synonyms,
   categories. We shallow-clone this repo into a temp dir and parse it with `json5`.

`paths.ts` exports a TypeScript array of object literals with unquoted keys and trailing commas —
valid JSON5 but not JSON. We extract the array literal with a single regex, then parse with
`json5.loads()`. No full TS parser needed; the format is simple and stable.

Example entry from `src/lib/paths.ts`:
```typescript
{ repo: "iterm", title: "iTerm", icon: "used/pack-7/haunted-house.svg",
  platform: ["macos"], synonyms: ["iterm2", "terminal"],
  categories: ["terminal"], legacyViews: 359069 },
```

`paths.ts` does not carry an `updated_at` field. Update recency comes from the GitHub API
(`repo.updated_at`) and is stored in the manifest's `last_updated` field. We do not need to
derive it from paths.ts.

Network calls use `tenacity` for exponential-backoff retry — GitHub returns 429 on rate-limit
and transient DNS/TLS failures happen. Both `fetch_github_repos` and `fetch_website_metadata`
are decorated; callers don't need to think about retries.

```python
import re
import json5
import git  # gitpython
import tempfile
from pathlib import Path
from github import Github, Auth
from dataclasses import dataclass, field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

WEBSITE_REPO = "https://github.com/dracula/draculatheme.com.git"
_RETRY = dict(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((Exception,)),  # narrowed per-function as needed
    reraise=True,
)


@dataclass
class DraculaApp:
    repo_name: str            # e.g. "visual-studio-code"
    full_name: str            # e.g. "dracula/visual-studio-code"
    clone_url: str
    description: str
    title: str = ""
    platforms: list[str] = field(default_factory=list)   # ["macos", "linux", ...]
    synonyms: list[str] = field(default_factory=list)    # alternative names for matching
    categories: list[str] = field(default_factory=list)
    updated_at: str = ""      # ISO timestamp from GitHub API; not from paths.ts


@retry(**_RETRY)
def fetch_github_repos(token: str | None = None) -> list[DraculaApp]:
    """
    List every repo in the dracula GitHub org.

    Anonymous access gives 60 req/hour — enough for this read-only operation
    since listing the org repos is a single paginated call. A token raises the
    limit to 5000/hour and is recommended if running frequently.
    Retried up to 4× with exponential backoff on any exception (rate limit, network).
    """
    g = Github(auth=Auth.Token(token) if token else None)
    org = g.get_organization("dracula")
    apps = []
    for repo in org.get_repos():
        apps.append(DraculaApp(
            repo_name=repo.name,
            full_name=repo.full_name,
            clone_url=repo.clone_url,
            description=repo.description or "",
            updated_at=repo.updated_at.isoformat() if repo.updated_at else "",
        ))
    return apps


def _parse_paths_ts(source: str) -> dict[str, dict]:
    """
    Parse draculatheme.com's src/lib/paths.ts using json5.

    The file exports a TypeScript array of object literals. We locate the
    array with a regex, then hand the raw JS/TS literal to json5 which handles
    unquoted keys, trailing commas, and single-line comments.
    """
    # Find the exported array: everything from the first `[` to the matching `]`
    match = re.search(r'=\s*(\[.*\])', source, re.DOTALL)
    if not match:
        return {}
    entries = json5.loads(match.group(1))
    return {
        e["repo"]: {
            "title":      e.get("title", ""),
            "platforms":  e.get("platform", []),   # note: key is "platform", not "platforms"
            "synonyms":   e.get("synonyms", []),
            "categories": e.get("categories", []),
        }
        for e in entries
        if isinstance(e, dict) and "repo" in e
    }


@retry(**_RETRY)
def fetch_website_metadata() -> dict[str, dict]:
    """
    Shallow-clone the draculatheme.com source repo into a temp dir and parse
    src/lib/paths.ts for structured per-app metadata.
    Retried up to 4× with exponential backoff on clone failures.
    """
    with tempfile.TemporaryDirectory() as tmp:
        git.Repo.clone_from(WEBSITE_REPO, tmp, depth=1)
        paths_ts = Path(tmp) / "src" / "lib" / "paths.ts"
        if not paths_ts.exists():
            return {}
        return _parse_paths_ts(paths_ts.read_text())


def enrich_with_website_metadata(apps: list[DraculaApp]) -> list[DraculaApp]:
    """Merge paths.ts metadata into the list from the GitHub API."""
    meta = fetch_website_metadata()
    for app in apps:
        if info := meta.get(app.repo_name):
            app.title      = info.get("title", "")
            app.platforms  = info.get("platforms", [])
            app.synonyms   = info.get("synonyms", [])
            app.categories = info.get("categories", [])
            # updated_at is NOT in paths.ts; it was set from the GitHub API above
    return apps
```

---

### `detection.py` — detect installed apps on macOS

```python
import shutil
import subprocess
from pathlib import Path


def get_installed_apps() -> set[str]:
    """
    Returns a set of normalised app identifiers found on this machine.
    Combines /Applications, Homebrew formulae, Homebrew casks, Mac App Store,
    config file hints, and ~/Library/Application Support.
    """
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
    """Homebrew formulae (CLI tools: bat, delta, vim, neovim, tmux, etc.)."""
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
    """Homebrew casks (GUI apps not in /Applications, e.g. some terminal emulators)."""
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
    """Mac App Store apps via `mas` CLI (brew install mas)."""
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
    """Detect CLI tools by config file/dir presence."""
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
        "delta":     Path.home() / ".gitconfig",  # delta config lives in gitconfig
    }
    return {name for name, path in hints.items() if path.exists()}


def _from_library_app_support() -> set[str]:
    """
    Scan ~/Library/Application Support for installed apps not caught elsewhere.
    This catches apps (especially from the Mac App Store) that don't appear in
    /Applications but do have a support directory.
    """
    lib = Path("~/Library/Application Support").expanduser()
    if not lib.exists():
        return set()
    return {_normalise(p.name) for p in lib.iterdir() if p.is_dir()}


def _normalise(name: str) -> str:
    """Lowercase, strip spaces and common suffixes for fuzzy matching."""
    return name.lower().replace(" ", "-").removesuffix(".app")


def match_installed_to_themes(
    installed: set[str],
    themes: list,  # list[DraculaApp]
) -> list:
    """
    Match installed app names against dracula repo names and their synonyms.
    Builds a candidate set per theme (repo slug + synonyms) and does a set
    intersection against the installed set — O(n) not O(n×m).
    """
    matched = []
    for theme in themes:
        candidates = {_normalise(theme.repo_name)} | {_normalise(s) for s in theme.synonyms}
        if candidates & installed:
            matched.append(theme)
    return matched
```

---

### `themes.py` — manage git checkouts

`ensure_all_themes` is smart about what it actually processes: it loads the current manifest
and skips themes that haven't changed upstream since the last sync, unless `--force` is set.
"Changed" means the GitHub API's `updated_at` for the repo is newer than the manifest's
`last_updated` for that entry. This avoids hammering 400+ repos on every launchd run.

```python
import git  # gitpython
from pathlib import Path
from .config import RunConfig
from .console import console, coffin_error

THEMES_DIR = Path("~/projects/dracula/themes").expanduser()


def ensure_theme(app, cfg: RunConfig, *, progress=None) -> dict:
    """
    Clone or pull a dracula theme repo into themes/<repo_name>/.
    Returns a dict with status: "cloned" | "updated" | "current" | "error"
    In dry-run mode, returns what would happen without touching the filesystem.
    """
    dest = THEMES_DIR / app.repo_name
    try:
        if not dest.exists():
            if cfg.dry_run:
                return {"repo": app.repo_name, "status": "would-clone", "path": str(dest)}
            git.Repo.clone_from(app.clone_url, dest, depth=1)
            status = "cloned"
        else:
            repo = git.Repo(dest)
            old_head = repo.head.commit.hexsha
            if not cfg.dry_run:
                repo.remotes.origin.pull()
            status = "updated" if (not cfg.dry_run and repo.head.commit.hexsha != old_head) else "current"
        return {"repo": app.repo_name, "status": status, "path": str(dest)}
    except git.GitCommandError as exc:
        coffin_error(f"Git error for {app.repo_name}: {exc}")
        return {"repo": app.repo_name, "status": "error", "error": str(exc)}


def needs_processing(app, existing_manifest) -> bool:
    """
    Return True if this app should be cloned/pulled this run.
    An app needs processing if:
      - It's not in the current manifest (new discovery), OR
      - The upstream repo's updated_at is newer than our last_updated in the manifest
    """
    if existing_manifest is None:
        return True
    entry = next((e for e in existing_manifest.apps if e.repo_name == app.repo_name), None)
    if entry is None:
        return True  # new app
    if not entry.last_updated or not app.updated_at:
        return True  # can't compare — process to be safe
    return app.updated_at > entry.last_updated


def ensure_all_themes(apps, cfg: RunConfig, existing_manifest=None) -> list[dict]:
    """
    Pull/clone matched themes in parallel with a Rich progress bar.
    Skips themes that haven't changed upstream unless cfg.force is set.
    """
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskProgressColumn
    from concurrent.futures import ThreadPoolExecutor, as_completed

    to_process = apps if cfg.force else [a for a in apps if needs_processing(a, existing_manifest)]
    skipped = [
        {"repo": a.repo_name, "status": "current", "path": str(THEMES_DIR / a.repo_name)}
        for a in apps if a not in to_process
    ]

    if cfg.verbose and skipped:
        console.print(f"  [muted]Skipping {len(skipped)} unchanged themes (use --force to override)[/]")

    results = list(skipped)
    if not to_process:
        return results

    with Progress(
        SpinnerColumn(style="bold magenta"),
        TextColumn("[accent]{task.description}"),
        BarColumn(bar_width=40, style="purple", complete_style="green"),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        overall = progress.add_task("🧛🏻 Syncing themes…", total=len(to_process))
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(ensure_theme, app, cfg): app for app in to_process}
            for future in as_completed(futures):
                results.append(future.result())
                progress.advance(overall)
    return results
```

---

### `apply.py` — automate theme application where possible

Some themes can be applied without user interaction. This module handles them.
The `instructions.py` module handles everything that genuinely needs a human.

Return values from `apply_if_possible`:
- `"applied"` — theme was applied for the first time
- `"updated"` — theme was already applied but has been refreshed/updated
- `"skipped"` — auto-apply exists but preconditions not met (e.g. managed by dotfiles that we shouldn't touch)
- `"manual"` — no auto-apply; caller should surface instructions

```python
import shutil
import subprocess
import re
from pathlib import Path
from .config import RunConfig

THEMES_DIR  = Path("~/projects/dracula/themes").expanduser()
ALIASES_DIR = Path("~/pseudohome/dotfiles/aliases").expanduser()
DRACULA_ALIASES_FILE = ALIASES_DIR / "dracula"


# ---------------------------------------------------------------------------
# Shared alias helper — used by every apply_* function that writes a shell alias
# ---------------------------------------------------------------------------

def _set_shell_alias(
    cmd: str,
    inject_flags: str,
    replace_pattern: str,
    cfg: RunConfig,
) -> str:
    """
    Write or update a shell alias for `cmd` across the dotfiles alias files.

    Algorithm:
    1. Scan every file in ALIASES_DIR for an existing `alias <cmd>="<cmd> …"` line.
    2. If found: extract the existing flags, strip any flag matching `replace_pattern`,
       inject `inject_flags`, and rewrite the entire if-block in-place in that file.
    3. If not found: append a new guarded block to DRACULA_ALIASES_FILE.

    The emitted alias always uses a portable availability guard:

        if command -v <cmd> > /dev/null 2>&1; then
            alias <cmd>="<cmd> <inject_flags> [<preserved-flags>]"
        fi

    Returns "applied" | "updated".
    Respects cfg.dry_run (reports what would happen, makes no changes).
    """
    alias_re = re.compile(rf'alias {re.escape(cmd)}="{re.escape(cmd)} ([^"]*)"')

    existing_match = None
    source_file: Path | None = None
    if ALIASES_DIR.exists():
        for f in sorted(ALIASES_DIR.glob("*")):
            if f.is_file():
                m = alias_re.search(f.read_text())
                if m:
                    existing_match = m
                    source_file = f
                    break

    # Preserve existing flags, stripping the one we're about to manage
    preserved = ""
    if existing_match:
        flags = re.sub(replace_pattern + r'\s*', '', existing_match.group(1)).strip()
        preserved = f" {flags}" if flags else ""

    new_alias = f'alias {cmd}="{cmd} {inject_flags}{preserved}"'
    new_block  = (
        f'if command -v {cmd} > /dev/null 2>&1; then\n'
        f'    {new_alias}\n'
        f'fi\n'
    )

    if cfg.dry_run:
        return "updated" if existing_match else "applied"

    if existing_match and source_file:
        original = source_file.read_text()
        rewritten = re.sub(
            rf'if command -v {re.escape(cmd)}.*?fi\n',
            new_block,
            original,
            flags=re.DOTALL,
        )
        source_file.write_text(rewritten)
        return "updated"
    else:
        DRACULA_ALIASES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with DRACULA_ALIASES_FILE.open("a") as f:
            f.write("\n" + new_block)
        return "applied"


# ---------------------------------------------------------------------------
# Per-app apply functions
# ---------------------------------------------------------------------------

def apply_xcode(cfg: RunConfig) -> str:
    """Copy Dracula colour theme into Xcode's user themes directory."""
    src = THEMES_DIR / "xcode" / "Dracula.xccolortheme"
    dst_dir = Path("~/Library/Developer/Xcode/UserData/FontAndColorThemes").expanduser()
    dst = dst_dir / src.name
    if not src.exists():
        return "skipped"
    already = dst.exists()
    if not cfg.dry_run:
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return "updated" if already else "applied"


def apply_terminal_app(cfg: RunConfig) -> str:
    """
    Install Dracula profile in Terminal.app and set it as default.
    Opening the .terminal file triggers Terminal to import the profile.
    `defaults write` sets it as the default and startup profile.
    """
    profile = THEMES_DIR / "terminal-app" / "Dracula.terminal"
    if not profile.exists():
        return "skipped"
    if cfg.dry_run:
        return "applied"
    subprocess.run(["open", str(profile)], check=True)
    domain = "com.apple.Terminal"
    for key in ("Default Window Settings", "Startup Window Settings"):
        subprocess.run(["defaults", "write", domain, key, "Dracula"], check=True)
    return "applied"


def apply_bat(cfg: RunConfig) -> str:
    """
    Configure bat to use the Dracula theme via a shell alias in dotfiles.
    Uses _set_shell_alias: scans all dotfiles/aliases/* for an existing bat
    alias, preserves other flags, injects --theme=Dracula.

    If bat is not on PATH, or its config directory is already inside a git
    repo (user manages it themselves), we leave it alone and return "skipped".
    """
    if not shutil.which("bat"):
        return "skipped"
    try:
        bat_config_dir = subprocess.run(
            ["bat", "--config-dir"], capture_output=True, text=True, check=True
        ).stdout.strip()
        git.Repo(bat_config_dir)   # raises InvalidGitRepositoryError if not a repo
        return "skipped"
    except (subprocess.CalledProcessError, git.InvalidGitRepositoryError, git.NoSuchPathError):
        pass

    return _set_shell_alias(
        cmd="bat",
        inject_flags="--theme=Dracula",
        replace_pattern=r"--theme=\S+",
        cfg=cfg,
    )


def apply_delta(cfg: RunConfig) -> str:
    """
    Set delta's syntax theme to Dracula in ~/.gitconfig.

    Uses gitpython throughout — no subprocess git calls — to avoid index corruption
    from mixing APIs.

    If gitconfig is inside a version-controlled dotfiles repo:
    - Interactive mode: write config, then git add + commit + push via gitpython
    - Launchd mode: write config, then git add only (push needs interactive auth)

    If gitconfig is not version-controlled: write via gitpython global config writer.
    """
    if not shutil.which("delta"):
        return "skipped"

    if cfg.dry_run:
        return "applied"

    # Write the config value using gitpython — avoids subprocess entirely
    import git as _git
    with _git.GitConfigParser(
        [str(Path.home() / ".gitconfig")], read_only=False
    ) as gcw:
        gcw.set_value("delta", "syntax-theme", "Dracula")

    # Check if the gitconfig lives inside a dotfiles repo
    gitconfig = Path.home() / ".gitconfig"
    try:
        dotfiles_repo = _git.Repo(gitconfig.parent, search_parent_directories=True)
    except (_git.InvalidGitRepositoryError, _git.NoSuchPathError):
        return "applied"

    # Stage the change
    dotfiles_repo.index.add([str(gitconfig)])
    if not cfg.launchd:
        dotfiles_repo.index.commit("dracula: set delta syntax-theme")
        dotfiles_repo.remotes.origin.push().raise_if_error()
    # In launchd mode: staged but not committed; user commits at next interactive session

    return "applied"


# Registry: repo_name → apply function
APPLY_FUNCS: dict[str, object] = {
    "xcode":        apply_xcode,
    "terminal-app": apply_terminal_app,
    "bat":          apply_bat,
    "delta":        apply_delta,
}


def apply_if_possible(repo_name: str, cfg: RunConfig) -> str:
    """
    Attempt to auto-apply a theme. See return values at the top of this module.
    """
    fn = APPLY_FUNCS.get(repo_name)
    if fn is None:
        return "manual"
    return fn(cfg)
```

---

### `manifest.py` — per-machine JSON manifest

```python
import socket
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

MACHINES_DIR = Path("~/projects/dracula/machines").expanduser()


class AppEntry(BaseModel):
    repo_name: str
    status: str           # "applied" | "updated" | "skipped" | "manual" | "cloned" | "current" | "error"
    path: str | None = None
    manual_steps: list[str] = []
    last_updated: str = ""   # ISO timestamp; compared against DraculaApp.updated_at to detect changes


class Manifest(BaseModel):
    hostname: str
    last_run: str
    apps: list[AppEntry]


def manifest_path(hostname: str | None = None) -> Path:
    # equivalent to `hostname -s`
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
        last_run=datetime.now(timezone.utc).isoformat(),
        apps=entries,
    )
    path.write_text(manifest.model_dump_json(indent=2))
    return path
```

---

### `instructions.py` — manual steps (last resort)

Only for things that genuinely cannot be automated. Everything that can be scripted
lives in `apply.py` instead. Rings the terminal bell when manual steps are surfaced,
so the operator's attention is drawn even if they've walked away.

```python
from .console import console

MANUAL_INSTRUCTIONS: dict[str, list[str]] = {
    "safari": [
        "Install the Dracula Safari extension from the App Store.",
        "Enable in Safari → Settings → Extensions.",
        # open_for_manual() opens Safari automatically before these are shown.
    ],
    # add more as discovered…
}

# Browser-extension themes (Chrome, Firefox, Edge) sync across machines via browser
# profile/extension sync — install once and they follow you everywhere.
BROWSER_SYNC_APPS = {
    "github", "duckduckgo", "hacker-news", "youtube",
    "stackoverflow", "google-calendar", "google",
}


def get_instructions(repo_name: str) -> list[str]:
    return MANUAL_INSTRUCTIONS.get(repo_name, [])


def open_for_manual(repo_name: str) -> None:
    """Open the relevant app and ring the bell before surfacing manual steps."""
    import subprocess
    console.bell()
    openers = {
        "safari": ["open", "-a", "Safari"],
    }
    if cmd := openers.get(repo_name):
        subprocess.run(cmd, check=False)
```

---

### `launchd.py` — install the launchd agent

Uses stdlib `plistlib`. Defaults to running at 15:00 daily using
`StartCalendarInterval` (a fixed clock time) rather than `StartInterval` (a relative
delay), so the sync always happens at a predictable moment rather than drifting.

`DRACULA_LAUNCHD=1` is set in the plist environment so `cli.py` and `RunConfig` know to
suppress Rich output and to skip git push (add+commit only; push needs interactive auth).

```python
import plistlib
import subprocess
from pathlib import Path

AGENT_LABEL = "com.adamamyl.draculamanager"
PLIST_PATH = Path.home() / "Library/LaunchAgents" / f"{AGENT_LABEL}.plist"
LOG_DIR = Path("~/projects/dracula/logs").expanduser()


def _dracula_bin() -> str:
    return str(Path("~/projects/dracula/dracula.venv/bin/dracula").expanduser())


def install_agent(hour: int = 15, minute: int = 0) -> None:
    """Write and load a launchd agent that runs `dracula sync` at the given time daily."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = str(LOG_DIR / "dracula-launchd.log")

    plist: dict = {
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
```

---

### `cli.py` — Typer CLI

All flags are collected into a `RunConfig` and threaded into every call that needs them.

```python
import os
import typer
from datetime import datetime, timezone
from pathlib import Path
from rich.table import Table
from .config import RunConfig
from .console import console, vampire_print, bat_warn
from . import discovery, detection, themes, manifest, launchd, instructions, apply
from .manifest import AppEntry

app = typer.Typer(
    name="dracula",
    help="🧛🏻 Keep your whole machine Dracula-themed.",
    rich_markup_mode="rich",
)


def _resolve_github_token(token: str | None) -> str | None:
    """
    Resolve a GitHub token. Priority:
      1. --token / GITHUB_TOKEN env var (explicit)
      2. 1Password CLI: `op read "op://Private/GitHub Dracula PAT/credential"`
         (requires `op` to be installed and signed in; skipped silently if not)
      3. None — fall back to anonymous (60 req/hour; fine for a single org listing)
    """
    if token:
        return token
    try:
        import subprocess
        result = subprocess.run(
            ["op", "read", "op://Private/GitHub Dracula PAT/credential"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


@app.command()
def sync(
    token:       str  = typer.Option(None,  envvar="GITHUB_TOKEN", help="GitHub PAT (falls back to 1Password, then anonymous)"),
    dry_run:     bool = typer.Option(False, "--dry-run",     help="Show what would be done; make no changes"),
    verbose:     bool = typer.Option(False, "--verbose",     help="Extra output"),
    debug:       bool = typer.Option(False, "--debug",       help="Developer-level output"),
    quiet:       bool = typer.Option(False, "--quiet", "-q", help="Errors only"),
    force:       bool = typer.Option(False, "--force",       help="Re-process all themes, even unchanged ones"),
    update_only: bool = typer.Option(False, "--update-only", help="Only update themes already in the manifest"),
    show_new:    bool = typer.Option(False, "--show-new",    help="Show newly available themes for detected apps"),
) -> None:
    """Sync theme checkouts for all installed apps and apply where possible."""
    cfg = RunConfig(
        dry_run=dry_run, verbose=verbose, debug=debug,
        quiet=quiet or bool(os.getenv("DRACULA_LAUNCHD")),
        force=force, update_only=update_only, show_new=show_new,
    )
    resolved_token = _resolve_github_token(token)

    if not cfg.quiet:
        vampire_print("Fetching supported apps from GitHub…")

    all_themes = discovery.fetch_github_repos(resolved_token)
    all_themes = discovery.enrich_with_website_metadata(all_themes)

    if not cfg.quiet:
        vampire_print(f"Found [accent]{len(all_themes)}[/] themes in the dracula org.")
        vampire_print("Detecting installed apps…")

    installed = detection.get_installed_apps()
    matched = detection.match_installed_to_themes(installed, all_themes)

    if cfg.update_only:
        existing = manifest.load_manifest()
        known = {e.repo_name for e in existing.apps} if existing else set()
        matched = [a for a in matched if a.repo_name in known]

    if not cfg.quiet:
        vampire_print(f"[success]{len(matched)}[/] themes match installed apps. Syncing…")

    existing_manifest = manifest.load_manifest()
    sync_results = themes.ensure_all_themes(matched, cfg, existing_manifest)

    entries = []
    for r in sync_results:
        repo_name = r["repo"]
        apply_status = apply.apply_if_possible(repo_name, cfg)
        steps = instructions.get_instructions(repo_name)
        if steps and not cfg.quiet:
            instructions.open_for_manual(repo_name)
        entries.append(AppEntry(
            repo_name=repo_name,
            status=apply_status if apply_status != "manual" else r["status"],
            path=r.get("path"),
            manual_steps=steps,
            last_updated=datetime.now(timezone.utc).isoformat(),
        ))

    if not cfg.dry_run:
        saved = manifest.save_manifest(entries)
        _commit_manifest(saved, cfg)

    if not cfg.quiet:
        _print_summary(entries, cfg)
        if not cfg.dry_run:
            vampire_print(f"Manifest saved to [muted]{saved}[/]")

    if cfg.show_new and not cfg.quiet:
        _print_new_themes(matched, all_themes, installed)


@app.command()
def status() -> None:
    """Show current manifest for this machine."""
    m = manifest.load_manifest()
    if not m:
        bat_warn("No manifest found. Run [highlight]dracula sync[/] first.")
        raise typer.Exit(1)

    table = Table(title=f"🧛🏻 {m.hostname} — last run {m.last_run[:10]}", border_style="purple")
    table.add_column("App", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Platform", style="muted")
    table.add_column("Manual steps", style="yellow")
    for entry in m.apps:
        table.add_row(entry.repo_name, entry.status, "—", "\n".join(entry.manual_steps) or "—")
    console.print(table)


@app.command()
def install_launchd(
    hour:   int = typer.Option(15, help="Hour to run (24h clock, default 15)"),
    minute: int = typer.Option(0,  help="Minute to run (default :00)"),
) -> None:
    """Install a launchd agent to run sync daily at the specified time."""
    launchd.install_agent(hour=hour, minute=minute)
    vampire_print(f"launchd agent installed — will run daily at {hour:02d}:{minute:02d}. 🦇")


@app.command()
def uninstall_launchd() -> None:
    """Remove the launchd agent."""
    launchd.uninstall_agent()
    vampire_print("launchd agent removed.")


def _commit_manifest(saved: Path, cfg: RunConfig) -> None:
    """
    Auto-commit and push the updated manifest.
    In launchd mode: add + commit only (push requires interactive auth).
    In interactive mode: add + commit + push.
    """
    try:
        import git
        repo = git.Repo(Path("~/projects/dracula").expanduser())
        rel = str(saved.relative_to(repo.working_dir))
        repo.index.add([rel])
        if repo.is_dirty(index=True):
            host = saved.parent.name
            repo.index.commit(f"manifest: {host} {datetime.now(timezone.utc):%Y-%m-%d}")
            if not cfg.launchd:
                repo.remotes.origin.push()
    except Exception:
        pass  # non-fatal: manifest is still written to disk


def _print_summary(entries: list[AppEntry], cfg: RunConfig) -> None:
    from rich.table import Table

    STATUS_STYLE = {
        "applied":  ("✔",  "success"),
        "updated":  ("⬆",  "warning"),
        "cloned":   ("⬇",  "success"),
        "current":  ("—",  "muted"),
        "skipped":  ("⏭", "muted"),
        "error":    ("⚰️", "error"),
        "manual":   ("🧄", "highlight"),
    }

    table = Table(title="🧛🏻 Dracula Sync Summary", border_style="purple", show_lines=False)
    table.add_column("App",          style="cyan",    no_wrap=True)
    table.add_column("Status",       style="green",   no_wrap=True)
    table.add_column("Platform",     style="muted",   no_wrap=True)
    table.add_column("Action",       style="accent")
    table.add_column("Manual steps", style="highlight")

    for e in entries:
        icon, style = STATUS_STYLE.get(e.status, ("", ""))
        table.add_row(
            e.repo_name,
            f"[{style}]{icon} {e.status}[/]",
            "—",
            "—",
            "\n".join(e.manual_steps) or "—",
        )

    console.print(table)

    if any(e.manual_steps for e in entries):
        console.bell()
        console.rule("[highlight]Manual steps required 🧄[/]")
        for e in (x for x in entries if x.manual_steps):
            console.print(f"  🧄 [highlight]{e.repo_name}[/]")
            for step in e.manual_steps:
                console.print(f"      • {step}")


def _print_new_themes(matched, all_themes, installed) -> None:
    """Print a table of available themes for detected apps not yet synced."""
    synced = {a.repo_name for a in matched}
    new_themes = [t for t in detection.match_installed_to_themes(installed, all_themes)
                  if t.repo_name not in synced]
    if not new_themes:
        return
    table = Table(title="🦇 New themes available", border_style="purple")
    table.add_column("App", style="cyan")
    table.add_column("Title", style="accent")
    table.add_column("Platforms", style="muted")
    for t in new_themes:
        table.add_row(t.repo_name, t.title or t.repo_name, ", ".join(t.platforms) or "?")
    console.print(table)
```

---

## Logging

Logs rotate monthly. A single helper writes to the current month's file and prunes anything older
than last month, keeping just two files at most.

```python
# src/dracula_manager/logging_setup.py
import logging
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("~/projects/dracula/logs").expanduser()


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    current = LOG_DIR / f"{now:%Y-%m}.log"

    logging.basicConfig(
        filename=current,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # Prune logs older than last month (keep at most 2 files)
    all_logs = sorted(LOG_DIR.glob("*.log"))
    for old_log in all_logs[:-2]:
        old_log.unlink()
```

---

## Manifest repo setup

The `machines/` directory should be committed to a personal GitHub repo
(e.g. `github.com/<you>/dracula`) so you can reconstruct the setup on a new machine.
`themes/` is gitignored — they're downstream checkouts, not your content.

```bash
cd ~/projects/dracula
git init
git remote add origin git@github.com:<you>/dracula.git
echo "themes/"       >> .gitignore
echo "dracula.venv/" >> .gitignore
echo "logs/"         >> .gitignore
git add .
git commit -m "init: dracula manager"
git push -u origin main
```

After each sync the CLI auto-commits and pushes the updated manifest (see `_commit_manifest`
in `cli.py`). In launchd mode, the commit is made locally but the push is deferred to the next
interactive session.

---

## `.python-version`

```
3.12
```

---

## First-run checklist

```bash
# 1. Clone this repo
git clone git@github.com:<you>/dracula.git ~/projects/dracula
cd ~/projects/dracula

# 2. Install uv (if not already)
curl -Ls https://astral.sh/uv/install.sh | sh

# 3. Create venv and install deps
uv sync

# 4. Install pre-commit hooks
uv run pre-commit install

# 5. GitHub token — sourced automatically from 1Password if `op` is signed in.
#    To set explicitly: export GITHUB_TOKEN=$(op read "op://Private/GitHub Dracula PAT/credential")
#    Or just omit; anonymous access is fine for the initial org listing.

# 6. Run first sync (interactive, full Rich output)
uv run dracula sync

# 7. Install the daily launchd agent (defaults to 15:00)
uv run dracula install-launchd
# or to customise the time:
uv run dracula install-launchd --hour 9 --minute 30

# 8. Check status any time
uv run dracula status
```

---

## App support notes (Social section from brief)

The following apps were listed as targets. Their dracula repo names and install approach:

| App | Dracula repo | Method |
|-----|-------------|--------|
| GitHub | `dracula/github` | Browser extension — syncs via browser profile |
| GitHub Pages | via GitHub | — |
| DuckDuckGo | `dracula/duckduckgo` | Browser extension — syncs via browser profile |
| Hacker News | `dracula/hacker-news` | Browser extension — syncs via browser profile |
| YouTube | `dracula/youtube` | Browser extension — syncs via browser profile |
| Figma | `dracula/figma` | Figma plugin (manual, one-time) |
| WordPress | `dracula/wordpress` | WP admin (manual, per-site) |
| Nextcloud | `dracula/nextcloud` | Nextcloud theme (manual, per-instance) |
| Stack Overflow | `dracula/stackoverflow` | Browser extension — syncs via browser profile |
| Google Calendar | `dracula/google-calendar` | Browser extension — syncs via browser profile |
| Google Search | `dracula/google` | Browser extension — syncs via browser profile |

**Browser extensions** (Chrome, Firefox, Edge) sync across machines automatically via browser
profile/extension sync. Install once and they follow you. The `instructions.py` module will
surface a one-time notice if the extension isn't present yet; afterwards the manifest records it
as done. Safari extensions go through the App Store and also persist across machines via iCloud.

---

## TODO

> Tests are written alongside each phase, not after. Each phase ends with a linter gate —
> `uv run ruff check . && uv run mypy . && uv run bandit -r src/` must be clean before moving on.

---

### Phase 0 — Project scaffolding

- [x] Create GitHub repo (`github.com/<you>/dracula`), push initial commit with `plan.md`
- [x] `git init`, set default branch to `main`
- [x] Write `.gitignore` (`themes/`, `dracula.venv/`, `logs/`, `__pycache__/`, `*.pyc`, `.mypy_cache/`, `.ruff_cache/`)
- [x] Write `pyproject.toml` (as per plan — including all runtime and dev deps)
- [x] Write `.python-version` (`3.12`)
- [x] Write `.pre-commit-config.yaml` (ruff, mypy, bandit)
- [x] `uv sync` — verify venv created at `dracula.venv/`
- [x] `uv run pre-commit install`
- [x] Create `src/dracula_manager/__init__.py` and `__main__.py`
- [x] Create `tests/conftest.py` (shared fixtures: `tmp_path`, `aliases_dir`, `mock_cfg`)
- [x] Create `machines/`, `themes/`, `logs/` directories (add `.gitkeep` where needed)
- [x] Write `README.md` (installation, usage, flag reference, how to add a new app)
- [x] 🔲 **Linter gate**: `pre-commit run --all-files` clean on scaffolding

---

### Phase 1 — Core infrastructure

- [x] **`config.py`**: `RunConfig` dataclass with all 7 flags + `launchd` property
  - [x] Test: `RunConfig.from_env()` sets `quiet=True` when `DRACULA_LAUNCHD=1`
  - [x] Test: `cfg.launchd` reflects env var independently of `quiet`
- [x] **`console.py`**: Dracula palette dict, `Theme`, shared `console`, `vampire_print`, `bat_warn`, `coffin_error`
  - [x] Test: `coffin_error` calls `console.bell()` (mock console)
- [x] **`logging_setup.py`**: `configure_logging()` — monthly log files, prune to 2 max
  - [x] Test: calling `configure_logging()` twice in different months leaves exactly 2 log files
  - [x] Test: third month prunes the oldest (use `freezegun` to control `datetime.now()`)
- [x] 🔲 **Linter gate**

---

### Phase 2 — Discovery (`discovery.py`)

- [x] `DraculaApp` dataclass (all fields including `synonyms`, `categories`, `updated_at`)
- [x] `fetch_github_repos(token)` — paginated org listing, anonymous-safe, `@retry` decorated
  - [x] Test: mock `Github.get_organization` — verify `DraculaApp` fields populated correctly
  - [x] Test: retry fires on exception; succeeds on second attempt (mock tenacity + exception)
- [x] `_parse_paths_ts(source)` — json5 parser; extract array literal, parse entries
  - [x] Test: parses a minimal valid entry correctly (all fields)
  - [x] Test: entries missing `repo` key are silently skipped
  - [x] Test: no array in source returns `{}`
  - [x] Test: `platform` key (singular) is mapped to `platforms` field
- [x] `fetch_website_metadata()` — shallow-clone `draculatheme.com` into tmpdir, parse paths.ts
  - [x] Verify the regex that extracts the array literal works against the live file (manual smoke test)
  - [x] Confirm field name in the live file is `platform` (singular) not `platforms`
  - [x] Test: mock `git.Repo.clone_from`; assert `_parse_paths_ts` called with file contents
  - [x] Test: missing `paths.ts` returns `{}`
- [x] `enrich_with_website_metadata(apps)` — merge; leave `updated_at` from GitHub API untouched
  - [x] Test: enrichment populates `title`, `platforms`, `synonyms`, `categories`
  - [x] Test: `updated_at` is not overwritten by enrichment (it has no such field in paths.ts)
- [x] Manual smoke test: print first 10 enriched apps; confirm data looks right
- [x] 🔲 **Linter gate**

---

### Phase 3 — Detection (`detection.py`)

- [x] `_normalise(name)` — lowercase, strip `.app`, replace spaces with `-`
  - [x] Test: `"Visual Studio Code.app"` → `"visual-studio-code"`
  - [x] Test: `"iTerm2"` → `"iterm2"`
  - [x] Test: already-normalised input is idempotent
- [x] `_from_applications_dir()` — `/Applications` + `~/Applications`
  - [x] Test: mock filesystem with `tmp_path`; assert `.app` dirs are found and normalised
- [x] `_from_brew()` — `shutil.which` guard, then `brew list --formula`
  - [x] Test: `shutil.which("brew")` returns `None` → empty set, no subprocess call
  - [x] Test: mock subprocess output; assert names normalised correctly
- [x] `_from_brew_cask()` — same pattern as `_from_brew`
  - [x] Test: same two cases
- [x] `_from_mas()` — `shutil.which("mas")` guard, then `mas list`; parse `id name` lines
  - [x] Test: `mas` absent → empty set
  - [x] Test: mock multi-line output; assert app names extracted (not IDs)
- [x] `_from_config_hints()` — static map of known config paths
  - [x] Test: mock `Path.exists`; assert only present paths contribute
- [x] `_from_library_app_support()` — scan `~/Library/Application Support`
  - [x] Test: mock dir with known subdirs; assert normalised names returned
- [x] `get_installed_apps()` — union of all sources
  - [x] Test: all sources return disjoint sets; union is their sum
- [x] `match_installed_to_themes(installed, themes)` — set intersection via slug + synonyms
  - [x] Test: slug match hits
  - [x] Test: synonym match hits (e.g. `"iterm2"` matches `DraculaApp(repo_name="iterm", synonyms=["iterm2"])`)
  - [x] Test: no overlap → empty list
  - [x] Test: no duplicates when both slug and synonym match
- [x] Manual smoke test: print detected apps and matched themes on the current machine
- [x] 🔲 **Linter gate**

---

### Phase 4 — Theme management (`themes.py`)

- [x] `ensure_theme(app, cfg)` — clone if absent, pull if present; dry-run aware
  - [x] Test: dest absent → `clone_from` called; status `"cloned"` (mock `git.Repo.clone_from`)
  - [x] Test: dest present, HEAD unchanged → status `"current"`
  - [x] Test: dest present, HEAD changed after pull → status `"updated"`
  - [x] Test: `cfg.dry_run=True` → no clone/pull, returns `"would-clone"` or `"current"`
  - [x] Test: `git.GitCommandError` → status `"error"`, error key populated
- [x] `needs_processing(app, existing_manifest)` — compare ISO timestamps
  - [x] Test: app not in manifest → `True`
  - [x] Test: manifest present, `app.updated_at` newer than `last_updated` → `True`
  - [x] Test: manifest present, same timestamp → `False`
  - [x] Test: either timestamp empty → `True` (safe default)
- [x] `ensure_all_themes(apps, cfg, existing_manifest)` — parallel, Rich progress bar
  - [x] Test: `cfg.force=True` → all apps processed regardless of manifest
  - [x] Test: `cfg.force=False` → unchanged apps skipped; skipped count correct
  - [x] Test: results contain one entry per input app
- [x] 🔲 **Linter gate**

---

### Phase 5 — Apply (`apply.py`)

- [x] **`_set_shell_alias(cmd, inject_flags, replace_pattern, cfg)`**
  - [x] Test: no existing alias → new `if command -v … fi` block appended to `DRACULA_ALIASES_FILE`
  - [x] Test: alias exists in `aliases/dracula` → block rewritten in-place, existing flags preserved, old `replace_pattern` flag removed
  - [x] Test: alias exists in a different file (`aliases/main`) → that file rewritten; `DRACULA_ALIASES_FILE` not touched
  - [x] Test: call twice with same args → file identical after second call (idempotent)
  - [x] Test: `cfg.dry_run=True` → no files written; returns correct status string
- [x] **`apply_xcode(cfg)`**
  - [x] Test: source `.xccolortheme` absent → `"skipped"`
  - [x] Test: dest absent → file copied, returns `"applied"`
  - [x] Test: dest present → file overwritten, returns `"updated"`
  - [x] Test: `cfg.dry_run=True` → no copy performed
- [x] **`apply_terminal_app(cfg)`**
  - [x] Test: profile absent → `"skipped"`
  - [x] Test: `cfg.dry_run=True` → no subprocess calls
  - [x] Test: profile present → `open` and two `defaults write` calls made (mock subprocess)
- [x] **`apply_bat(cfg)`**
  - [x] Test: `shutil.which("bat")` is `None` → `"skipped"`, no further calls
  - [x] Test: bat config dir is a git repo (mock `git.Repo`) → `"skipped"`
  - [x] Test: bat available, config not a repo → delegates to `_set_shell_alias`
- [x] **`apply_delta(cfg)`**
  - [x] Test: `shutil.which("delta")` is `None` → `"skipped"`
  - [x] Test: `cfg.dry_run=True` → no config write, returns `"applied"`
  - [x] Test: gitconfig not in a repo → `GitConfigParser.set_value` called; no git add/commit
  - [x] Test: gitconfig in dotfiles repo, interactive → add + commit + push called (mock gitpython)
  - [x] Test: gitconfig in dotfiles repo, launchd → add only; commit and push NOT called
- [x] `APPLY_FUNCS` registry — all implemented functions registered
- [x] `apply_if_possible` — returns `"manual"` for unregistered repo names
- [x] Audit 400+ dracula repos; document additional `apply_*` candidates in a comment block
- [x] Implement additional `apply_*` functions for identified candidates (each with tests)
- [x] 🔲 **Linter gate**

---

### Phase 6 — Manifest (`manifest.py`)

- [x] `AppEntry` Pydantic model (all fields)
- [x] `Manifest` Pydantic model
- [x] `manifest_path(hostname)` — `hostname -s` equivalent via `socket`
- [x] `load_manifest(hostname)` — returns `None` gracefully if absent
- [x] `save_manifest(entries, hostname)` — writes indented JSON
  - [x] Test: round-trip `save_manifest` → `load_manifest` returns identical data
  - [x] Test: missing manifest file → `load_manifest` returns `None` (not an exception)
  - [x] Test: `manifest_path` uses short hostname (no domain suffix)
  - [x] Test: `save_manifest` creates parent directory if absent
- [x] 🔲 **Linter gate**

---

### Phase 7 — Instructions (`instructions.py`)

- [x] `MANUAL_INSTRUCTIONS` dict — populate for all known manual-only apps
- [x] `BROWSER_SYNC_APPS` set — all browser-extension themes
- [x] `get_instructions(repo_name)`
  - [x] Test: known repo → returns correct steps list
  - [x] Test: unknown repo → returns `[]`
- [x] `open_for_manual(repo_name)` — ring bell, open relevant app
  - [x] Test: `console.bell()` called for any repo with instructions (mock console)
  - [x] Test: known opener → correct subprocess command issued (mock subprocess)
  - [x] Test: unknown repo → no subprocess call, no exception
- [x] Audit all matched apps on the current machine; add any missing entries
- [x] 🔲 **Linter gate**

---

### Phase 8 — Launchd (`launchd.py`)

- [x] `_dracula_bin()` — absolute path to venv binary
  - [x] Test: returned path ends with `dracula.venv/bin/dracula`
- [x] `install_agent(hour, minute)` — write plist, load with `launchctl`
  - [x] Test: plist written to correct path; contains `StartCalendarInterval` with given hour/minute
  - [x] Test: `DRACULA_LAUNCHD=1` present in `EnvironmentVariables`
  - [x] Test: `launchctl load -w` called with plist path (mock subprocess)
  - [x] Test: `plutil -lint` passes on the written plist (integration — run against real file)
- [x] `uninstall_agent()` — unload + delete
  - [x] Test: plist absent → no error
  - [x] Test: plist present → `launchctl unload` called, file deleted
- [x] Manually install agent; verify it fires at configured time and log line appears
- [x] 🔲 **Linter gate**

---

### Phase 9 — CLI (`cli.py`)

- [x] App/Typer setup with `rich_markup_mode="rich"`
- [x] `_resolve_github_token(token)`
  - [x] Test: explicit `token` arg → returned directly, no `op` call
  - [x] Test: `GITHUB_TOKEN` env var set → used (mock env)
  - [x] Test: `op` on PATH, returns token → used (mock subprocess)
  - [x] Test: `op` absent (`FileNotFoundError`) → returns `None`
  - [x] Test: `op` times out → returns `None`
- [x] **`sync` command** (use `typer.testing.CliRunner` for all CLI tests)
  - [x] Test: `--dry-run` → no files written, exit 0, summary printed
  - [x] Test: `--quiet` → no output except errors
  - [x] Test: `--update-only` → only manifest-known apps processed
  - [x] Test: `--show-new` → second table present in output
  - [x] Test: `--force` → `needs_processing` bypassed (all apps processed)
  - [x] Test: `DRACULA_LAUNCHD=1` → quiet mode, push skipped in `_commit_manifest`
- [x] **`status` command**
  - [x] Test: no manifest → exit 1, warning printed
  - [x] Test: manifest present → table rendered, exit 0
- [x] **`install-launchd` / `uninstall-launchd` commands**
  - [x] Test: `install-launchd --hour 9 --minute 30` → `install_agent(9, 30)` called
  - [x] Test: `uninstall-launchd` → `uninstall_agent()` called
- [x] `_commit_manifest`: already tested via `sync --dry-run`; add:
  - [x] Test: interactive mode → push called
  - [x] Test: launchd mode → push not called, commit still made
- [x] `_print_summary` — correct emoji per status; bell rings when manual entries present
  - [x] Test: all status values represented; verify correct emoji in output string
- [x] 🔲 **Linter gate**

---

### Phase 10 — Integration & final validation

- [x] `uv run pytest --cov=dracula_manager --cov-report=term-missing` — all tests pass, coverage ≥ 80%
- [x] `uv run pre-commit run --all-files` — fully clean
- [x] `dracula sync --dry-run --verbose` on the current machine — review output, no errors
- [x] `dracula sync` for real — themes cloned and applied correctly
- [x] Verify manifest written and auto-committed/pushed to GitHub
- [x] Install launchd agent; confirm it fires and log appears in `logs/YYYY-MM.log`
- [x] Rebuild from scratch on a second machine (or VM) using only the repo + first-run checklist
