import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.table import Table

from . import apply, detection, discovery, instructions, launchd, manifest, themes
from .config import RunConfig
from .console import bat_warn, console, vampire_print
from .manifest import AppEntry

app = typer.Typer(
    name="dracula",
    help="🧛🏻 Keep your whole machine Dracula-themed.",
    rich_markup_mode="rich",
)


def _resolve_github_token(token: str | None) -> str | None:
    if token:
        return token
    try:
        result = subprocess.run(
            ["op", "read", "op://Private/GitHub Dracula PAT/credential"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        pass
    return None


@app.command()
def sync(
    token: str = typer.Option(  # noqa: E501
        None, envvar="GITHUB_TOKEN", help="GitHub PAT (falls back to 1Password, then anonymous)"
    ),
    dry_run:     bool = typer.Option(False, "--dry-run",     help="Show what would be done; make no changes"),  # noqa: E501
    verbose:     bool = typer.Option(False, "--verbose",     help="Extra output"),
    debug:       bool = typer.Option(False, "--debug",       help="Developer-level output"),
    quiet:       bool = typer.Option(False, "--quiet", "-q", help="Errors only"),
    force:       bool = typer.Option(False, "--force",       help="Re-process all themes, even unchanged ones"),  # noqa: E501
    update_only: bool = typer.Option(False, "--update-only", help="Only update themes already in the manifest"),  # noqa: E501
    show_new:    bool = typer.Option(False, "--show-new",    help="Show newly available themes for detected apps"),  # noqa: E501
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
            last_updated=datetime.now(UTC).isoformat(),
        ))

    saved: Path | None = None
    if not cfg.dry_run:
        saved = manifest.save_manifest(entries)
        _commit_manifest(saved, cfg)

    if not cfg.quiet:
        _print_summary(entries, cfg)
        if not cfg.dry_run and saved is not None:
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
    try:
        import git
        repo = git.Repo(Path("~/projects/dracula").expanduser())
        rel = str(saved.relative_to(repo.working_dir))
        repo.index.add([rel])
        if repo.is_dirty(index=True):
            host = saved.parent.name
            repo.index.commit(f"manifest: {host} {datetime.now(UTC):%Y-%m-%d}")
            if not cfg.launchd:
                repo.remotes.origin.push()
    except Exception:
        pass


def _print_summary(entries: list[AppEntry], cfg: RunConfig) -> None:
    STATUS_STYLE: dict[str, tuple[str, str]] = {
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


def _print_new_themes(
    matched: list[discovery.DraculaApp],
    all_themes: list[discovery.DraculaApp],
    installed: set[str],
) -> None:
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
