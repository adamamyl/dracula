# Dracula Manager — Project Memory

## What this is
A Python CLI tool (`dracula`) that keeps every app on a macOS machine themed with
[Dracula](https://draculatheme.com/). Full spec in `/Users/adam/projects/dracula/plan.md`.

## Key facts
- **Repo**: `~/projects/dracula/` — git repo, push to `github.com/<you>/dracula`
- **Venv**: `dracula.venv/` (fixed path, managed by `uv`)
- **Entry point**: `uv run dracula` → `dracula_manager.cli:app`
- **Python**: 3.12
- **All implementation detail is in `plan.md`** — source of truth; do not contradict it

## Project structure
```
src/dracula_manager/
  __init__.py / __main__.py
  cli.py           — Typer CLI, all commands
  config.py        — RunConfig dataclass (flags)
  console.py       — Rich console, Dracula palette, helpers
  discovery.py     — GitHub API + draculatheme.com repo parsing
  detection.py     — detect installed apps on macOS
  themes.py        — git clone/pull theme repos
  apply.py         — automate theme application
  manifest.py      — per-machine JSON manifest
  instructions.py  — manual steps + bell
  launchd.py       — launchd agent install/uninstall
  logging_setup.py — monthly rotating logs
tests/
  conftest.py      — shared fixtures
  test_*.py        — one file per module
```

## Runtime dependencies
```
typer[all]>=0.12   rich>=13   PyGithub>=2.3   gitpython>=3.1
pydantic>=2        json5>=0.9  tenacity>=8
```

## Dev dependencies
```
ruff>=0.4   mypy>=1.10   bandit>=1.7   pre-commit>=3
pytest>=8   pytest-mock>=3   pytest-cov>=5   freezegun>=1
```

## Architecture decisions
- **`RunConfig`** dataclass carries all 7 flags (`--dry-run`, `--verbose`, `--debug`,
  `--quiet`, `--force`, `--update-only`, `--show-new`) through every function call
- **`DRACULA_LAUNCHD=1`** env var → `cfg.quiet=True` + skip git push (add+commit only)
- **Discovery**: GitHub org API (PyGitHub) + shallow-clone `github.com/dracula/draculatheme.com`
  → parse `src/lib/paths.ts` with `json5` (not regex, not live scraping)
- **Detection**: `shutil.which()` guard before every subprocess call (brew, mas, bat)
- **`_set_shell_alias(cmd, inject_flags, replace_pattern, cfg)`** — shared helper in apply.py;
  scans ALL `~/pseudohome/dotfiles/aliases/*` for existing alias, preserves flags, writes to
  `aliases/dracula`; every `apply_*` that writes a shell alias uses this
- **`apply_delta`**: uses gitpython `GitConfigParser` + `repo.index` throughout — NO subprocess
  git calls (mixing causes index corruption)
- **Retry**: `@retry` from `tenacity` on `fetch_github_repos` and `fetch_website_metadata`
- **Smart sync**: `needs_processing()` compares `app.updated_at` (GitHub API) vs manifest
  `last_updated`; skips unchanged themes unless `--force`
- **launchd**: `StartCalendarInterval` (fixed 15:00) not `StartInterval`; label `com.adamamyl.draculamanager`
- **Manifest**: auto-committed after every sync; pushed in interactive mode, not in launchd mode
- **Logs**: monthly files (`YYYY-MM.log`), keep last 2 only

## Status emoji (output table)
✔ applied  ⬆ updated  ⬇ cloned  — current  ⏭ skipped  ⚰️ error  🧄 manual

## 1Password integration
`op read "op://Private/GitHub Dracula PAT/credential"` — tried silently if `op` on PATH

## TODO phases (see plan.md for full detail)
- Phase 0: Scaffolding (repo, pyproject, venv, pre-commit, conftest)
- Phase 1: config.py, console.py, logging_setup.py
- Phase 2: discovery.py
- Phase 3: detection.py
- Phase 4: themes.py
- Phase 5: apply.py (_set_shell_alias first, then apply_* functions)
- Phase 6: manifest.py
- Phase 7: instructions.py
- Phase 8: launchd.py
- Phase 9: cli.py
- Phase 10: Integration & final validation
Each phase: write tests alongside code, end with ruff+mypy+bandit gate.
