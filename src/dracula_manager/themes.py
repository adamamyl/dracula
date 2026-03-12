from pathlib import Path
from typing import Any

import git

from .config import RunConfig
from .console import coffin_error, console
from .discovery import DraculaApp

THEMES_DIR = Path("~/projects/dracula/themes").expanduser()


def ensure_theme(app: DraculaApp, cfg: RunConfig, *, progress: Any = None) -> dict[str, str]:
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
            changed = not cfg.dry_run and repo.head.commit.hexsha != old_head
            status = "updated" if changed else "current"
        return {"repo": app.repo_name, "status": status, "path": str(dest)}
    except git.GitCommandError as exc:
        coffin_error(f"Git error for {app.repo_name}: {exc}")
        return {"repo": app.repo_name, "status": "error", "error": str(exc)}


def needs_processing(app: DraculaApp, existing_manifest: Any) -> bool:
    if existing_manifest is None:
        return True
    entry = next((e for e in existing_manifest.apps if e.repo_name == app.repo_name), None)
    if entry is None:
        return True
    if not entry.last_updated or not app.updated_at:
        return True
    return bool(app.updated_at > entry.last_updated)


def ensure_all_themes(
    apps: list[DraculaApp],
    cfg: RunConfig,
    existing_manifest: Any = None,
) -> list[dict[str, str]]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

    to_process = apps if cfg.force else [a for a in apps if needs_processing(a, existing_manifest)]
    skipped = [
        {"repo": a.repo_name, "status": "current", "path": str(THEMES_DIR / a.repo_name)}
        for a in apps if a not in to_process
    ]

    if cfg.verbose and skipped:
        n = len(skipped)
        console.print(f"  [muted]Skipping {n} unchanged themes (use --force to override)[/]")

    results: list[dict[str, str]] = list(skipped)
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
