from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

from src.core.config import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"


def setup_logging() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return LOG_FILE

    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)

    root.addHandler(file_handler)
    root.addHandler(console)

    for name in ("urllib3", "akshare", "charset_normalizer", "matplotlib"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return LOG_FILE


def install_excepthook() -> None:
    log = logging.getLogger("app.crash")

    def _hook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.critical("未捕获异常:\n%s", text)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook

    try:
        import threading

        def _thread_hook(args) -> None:
            log.critical(
                "线程未捕获异常: %s",
                "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
            )

        threading.excepthook = _thread_hook
    except AttributeError:
        pass
