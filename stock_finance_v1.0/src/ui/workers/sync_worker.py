from __future__ import annotations

import logging
import os

from PySide6.QtCore import QObject, QThread, Signal

from src.db.session import get_session
from src.sync.sync_service import SyncProgress, SyncScope, SyncService

logger = logging.getLogger(__name__)


class SyncWorker(QObject):
    progress = Signal(object)
    finished = Signal(bool, str)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._cancelled = False
        self.scope = SyncScope.WATCHLIST
        self.stock_codes: list[str] | None = None
        self.current_code: str | None = None
        self.include_company_list = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        os.environ["TQDM_DISABLE"] = "1"
        os.environ["PYTHONWARNINGS"] = "ignore"
        try:
            logger.info(
                "开始同步 scope=%s include_list=%s",
                self.scope,
                self.include_company_list,
            )
            with get_session() as session:
                service = SyncService(session)
                log = service.sync(
                    self.scope,
                    stock_codes=self.stock_codes,
                    current_code=self.current_code,
                    include_company_list=self.include_company_list,
                    progress=lambda p: self.progress.emit(p),
                    cancel_check=lambda: self._cancelled,
                )
                ok = log.status in ("success", "cancelled")
                msg = log.message or log.status
                logger.info("同步结束 status=%s msg=%s", log.status, msg)
                self.finished.emit(ok, msg)
        except Exception as exc:  # noqa: BLE001
            logger.exception("同步线程异常")
            self.failed.emit(str(exc))


class SyncThread(QThread):
    def __init__(self, worker: SyncWorker) -> None:
        super().__init__()
        self.worker = worker
        worker.moveToThread(self)
        self.started.connect(worker.run)
