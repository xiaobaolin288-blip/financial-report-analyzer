"""A股财报桌面应用入口。"""

from __future__ import annotations

import faulthandler
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from src.core.logging_config import LOG_FILE, install_excepthook, setup_logging
from src.db.session import init_db
from src.ui.main_window import MainWindow

logger = __import__("logging").getLogger("app")


def main() -> int:
    log_path = setup_logging()
    install_excepthook()
    faulthandler.enable(open(log_path.parent / "crash_dump.txt", "w", encoding="utf-8"), all_threads=True)

    logger.info("应用启动，日志文件: %s", log_path)
    init_db()
    app = QApplication(sys.argv)
    app.setApplicationName("StockFinance")
    try:
        window = MainWindow()
        window.show()
        return app.exec()
    except Exception:
        logger.exception("主窗口启动失败")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
