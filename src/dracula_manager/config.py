import os
from dataclasses import dataclass


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
        return cls(quiet=bool(os.getenv("DRACULA_LAUNCHD")))

    @property
    def launchd(self) -> bool:
        return bool(os.getenv("DRACULA_LAUNCHD"))
