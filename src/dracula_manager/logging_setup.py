import logging
from datetime import UTC, datetime
from pathlib import Path

LOG_DIR = Path("~/projects/dracula/logs").expanduser()


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    current = LOG_DIR / f"{now:%Y-%m}.log"

    logging.basicConfig(
        filename=current,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    all_logs = sorted(LOG_DIR.glob("*.log"))
    for old_log in all_logs[:-2]:
        old_log.unlink()
