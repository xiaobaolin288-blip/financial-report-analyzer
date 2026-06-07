from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
)

from src.db.session import get_session
from src.repositories.company_repo import CompanyRepository
from src.sync.sync_service import SyncScope
from src.ui.workers.sync_worker import SyncThread, SyncWorker

logger = logging.getLogger(__name__)


class SyncDialog(QDialog):
    def __init__(self, parent=None, *, current_code: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("从外网更新数据")
        self.setMinimumWidth(420)
        self._current_code = current_code
        self._thread: SyncThread | None = None
        self._last_progress_at = 0

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("选择要同步的内容（需联网）："))

        self._scope = QComboBox()
        self._scope.addItem("自选公司的财报指标（ROE/利润等）", SyncScope.WATCHLIST)
        if current_code:
            self._scope.addItem(f"当前公司财报（{current_code}）", SyncScope.CURRENT)
        self._scope.addItem("全部已入库公司的财报", SyncScope.ALL)
        self._scope.addItem("仅更新 A 股公司名录（代码+名称）", "company_list")

        self._include_list = QCheckBox("同时更新 A 股公司名录（仅首次需要）")
        self._include_list.setChecked(self._should_default_sync_list())

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._status = QLabel("")
        self._status.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("开始同步")
        buttons.accepted.connect(self._start)
        buttons.rejected.connect(self._on_cancel)

        layout.addWidget(self._scope)
        layout.addWidget(self._include_list)
        layout.addWidget(self._progress)
        layout.addWidget(self._status)
        layout.addWidget(buttons)
        self._buttons = buttons

        if current_code:
            for i in range(self._scope.count()):
                if self._scope.itemData(i) == SyncScope.CURRENT:
                    self._scope.setCurrentIndex(i)
                    break

    def _should_default_sync_list(self) -> bool:
        try:
            with get_session() as session:
                return CompanyRepository(session).count() < 100
        except Exception:
            logger.exception("读取公司数量失败")
            return True

    def _start(self) -> None:
        scope_data = self._scope.currentData()
        worker = SyncWorker()
        if scope_data == "company_list":
            worker.scope = SyncScope.WATCHLIST
            worker.include_company_list = True
            worker.stock_codes = []
        else:
            if isinstance(scope_data, SyncScope):
                worker.scope = scope_data
            elif scope_data:
                worker.scope = SyncScope(str(scope_data))
            worker.include_company_list = self._include_list.isChecked()
            worker.current_code = self._current_code

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self._status.setText("同步进行中…")

        self._thread = SyncThread(worker)
        worker.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._on_failed, Qt.ConnectionType.QueuedConnection)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_progress(self, p) -> None:
        import time

        now = time.monotonic()
        if p.total > 0 and (now - self._last_progress_at >= 0.15 or p.current >= p.total):
            self._last_progress_at = now
            self._progress.setRange(0, p.total)
            self._progress.setValue(min(p.current, p.total))
        self._status.setText(p.message + (f" ({p.stock_code})" if p.stock_code else ""))

    def _on_finished(self, ok: bool, msg: str) -> None:
        self._progress.setVisible(False)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._status.setText(msg)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)
        if ok:
            QMessageBox.information(self, "同步完成", msg)
            QTimer.singleShot(0, self.accept)

    def _on_failed(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._status.setText(f"失败: {msg}")
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)
        QMessageBox.warning(self, "同步失败", msg)

    def _on_cancel(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.worker.cancel()
            self._thread.quit()
            self._thread.wait(3000)
        self.reject()
