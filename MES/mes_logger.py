import logging
import sys
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent / "mes_debug.log"
_initialized = False


def setup_logger(name: str = "MES", console_only: bool = False) -> logging.Logger:
    global _initialized

    if not _initialized:
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)

        for h in root.handlers[:]:
            root.removeHandler(h)

        if not console_only:
            fh = logging.FileHandler(str(LOG_FILE), mode="w", encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            root.addHandler(fh)

        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)
        sh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(sh)

        for noisy in ("asyncua", "psycopg2"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

        _initialized = True

    return logging.getLogger(name)
