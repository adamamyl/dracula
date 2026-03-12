import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from .config import RunConfig

THEMES_DIR  = Path("~/projects/dracula/themes").expanduser()
ALIASES_DIR = Path("~/pseudohome/dotfiles/aliases").expanduser()
DRACULA_ALIASES_FILE = ALIASES_DIR / "dracula"


def _set_shell_alias(
    cmd: str,
    inject_flags: str,
    replace_pattern: str,
    cfg: RunConfig,
) -> str:
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
        with DRACULA_ALIASES_FILE.open("a") as fh:
            fh.write("\n" + new_block)
        return "applied"


def apply_xcode(cfg: RunConfig) -> str:
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
    if not shutil.which("bat"):
        return "skipped"
    try:
        import git
        bat_config_dir = subprocess.run(
            ["bat", "--config-dir"], capture_output=True, text=True, check=True
        ).stdout.strip()
        git.Repo(bat_config_dir)
        return "skipped"
    except (subprocess.CalledProcessError, Exception):
        pass

    return _set_shell_alias(
        cmd="bat",
        inject_flags="--theme=Dracula",
        replace_pattern=r"--theme=\S+",
        cfg=cfg,
    )


def apply_delta(cfg: RunConfig) -> str:
    if not shutil.which("delta"):
        return "skipped"

    if cfg.dry_run:
        return "applied"

    import git as _git
    with _git.GitConfigParser(
        [str(Path.home() / ".gitconfig")], read_only=False
    ) as gcw:
        gcw.set_value("delta", "syntax-theme", "Dracula")

    gitconfig = Path.home() / ".gitconfig"
    try:
        dotfiles_repo = _git.Repo(gitconfig.parent, search_parent_directories=True)
    except (_git.InvalidGitRepositoryError, _git.NoSuchPathError):
        return "applied"

    dotfiles_repo.index.add([str(gitconfig)])
    if not cfg.launchd:
        dotfiles_repo.index.commit("dracula: set delta syntax-theme")
        dotfiles_repo.remotes.origin.push().raise_if_error()

    return "applied"


APPLY_FUNCS: dict[str, Callable[[RunConfig], str]] = {
    "xcode":        apply_xcode,
    "terminal-app": apply_terminal_app,
    "bat":          apply_bat,
    "delta":        apply_delta,
}


def apply_if_possible(repo_name: str, cfg: RunConfig) -> str:
    fn = APPLY_FUNCS.get(repo_name)
    if fn is None:
        return "manual"
    return fn(cfg)
