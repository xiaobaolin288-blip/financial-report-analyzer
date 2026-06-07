from __future__ import annotations

import logging

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.config import assets_path, load_settings
from src.ui.dialogs.sync_dialog import SyncDialog
from src.ui.views.company_detail_view import CompanyDetailView
from src.ui.views.company_list_view import CompanyListView
from src.ui.views.compare_view import CompareView
from src.ui.views.home_view import HomeView
from src.ui.views.query_view import QueryView
from src.ui.views.settings_view import SettingsView

logger = logging.getLogger(__name__)

NAV_ITEMS = [
    ("首页", "home"),
    ("公司库", "companies"),
    ("单公司", "detail"),
    ("多公司对比", "compare"),
    ("高级查询", "query"),
    ("设置", "settings"),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        settings = load_settings()
        ui_cfg = settings.get("ui", {})
        self.setWindowTitle("A股财报分析")
        self.resize(ui_cfg.get("window_width", 1280), ui_cfg.get("window_height", 800))

        qss_path = assets_path("themes", "app.qss")
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QVBoxLayout()
        brand = QLabel("Stock Finance")
        brand.setStyleSheet("font-size: 18px; font-weight: 700; padding: 16px 12px; color: #6eb6ff;")
        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        for label, _key in NAV_ITEMS:
            QListWidgetItem(label, self._nav)
        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._on_nav_changed)

        self._sync_btn = QPushButton("从外网更新")
        self._sync_btn.setObjectName("primaryBtn")
        self._sync_btn.clicked.connect(self._open_sync)

        side.addWidget(brand)
        side.addWidget(self._nav, stretch=1)
        side.addWidget(self._sync_btn)

        self._stack = QStackedWidget()
        self._home = HomeView()
        self._companies = CompanyListView()
        self._detail = CompanyDetailView()
        self._compare = CompareView()
        self._query = QueryView()
        self._settings = SettingsView()

        self._stack.addWidget(self._home)
        self._stack.addWidget(self._companies)
        self._stack.addWidget(self._detail)
        self._stack.addWidget(self._compare)
        self._stack.addWidget(self._query)
        self._stack.addWidget(self._settings)

        root.addLayout(side)
        root.addWidget(self._stack, stretch=1)

        self._home.open_company.connect(self._go_detail)
        self._companies.open_company.connect(self._go_detail)
        self._query.open_company.connect(self._go_detail)
        self._detail.sync_requested.connect(self._open_sync_for)

        self._home.refresh()

    def _on_nav_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        key = NAV_ITEMS[index][1]
        if key == "home":
            self._home.refresh()
        elif key == "companies":
            try:
                self._companies.refresh()
            except Exception:
                logger.exception("公司库刷新失败")
        elif key == "compare":
            self._compare.refresh_chart()

    def _go_detail(self, code: str) -> None:
        self._detail.set_stock_code(code)
        self._nav.setCurrentRow(2)
        self._stack.setCurrentIndex(2)

    def _open_sync(self) -> None:
        code = self._detail._current_code or self._detail._code_input.text().strip()
        self._open_sync_for(code or "")

    def _open_sync_for(self, code: str) -> None:
        dlg = SyncDialog(self, current_code=code.strip() or None)
        if dlg.exec() == SyncDialog.DialogCode.Accepted:
            QTimer.singleShot(0, self._after_sync)

    def _after_sync(self) -> None:
        try:
            self._home.refresh()
        except Exception:
            logger.exception("首页刷新失败")
        if self._stack.currentIndex() == 1:
            try:
                self._companies.refresh()
            except Exception:
                logger.exception("公司库刷新失败")
        code = self._detail._current_code or self._detail._code_input.text().strip()
        if code:
            self._detail.load_company()
        if self._stack.currentIndex() == 3:
            self._compare.refresh_chart()
