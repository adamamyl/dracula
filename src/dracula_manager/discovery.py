import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import git
import json5
from github import Auth, Github
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

WEBSITE_REPO = "https://github.com/dracula/draculatheme.com.git"


@dataclass
class DraculaApp:
    repo_name: str
    full_name: str
    clone_url: str
    description: str
    title: str = ""
    platforms: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    updated_at: str = ""


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def fetch_github_repos(token: str | None = None) -> list[DraculaApp]:
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


def _parse_paths_ts(source: str) -> dict[str, dict[str, object]]:
    match = re.search(r'=\s*(\[.*\])', source, re.DOTALL)
    if not match:
        return {}
    entries = json5.loads(match.group(1))
    return {
        e["repo"]: {
            "title":      e.get("title", ""),
            "platforms":  e.get("platform", []),
            "synonyms":   e.get("synonyms", []),
            "categories": e.get("categories", []),
        }
        for e in entries
        if isinstance(e, dict) and "repo" in e
    }


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def fetch_website_metadata() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        git.Repo.clone_from(WEBSITE_REPO, tmp, depth=1)
        paths_ts = Path(tmp) / "src" / "lib" / "paths.ts"
        if not paths_ts.exists():
            return {}
        return _parse_paths_ts(paths_ts.read_text())


def enrich_with_website_metadata(apps: list[DraculaApp]) -> list[DraculaApp]:
    meta = fetch_website_metadata()
    for app in apps:
        if info := meta.get(app.repo_name):
            app.title      = str(info.get("title", ""))
            app.platforms  = [str(x) for x in cast(list[object], info.get("platforms", []))]
            app.synonyms   = [str(x) for x in cast(list[object], info.get("synonyms", []))]
            app.categories = [str(x) for x in cast(list[object], info.get("categories", []))]
    return apps
