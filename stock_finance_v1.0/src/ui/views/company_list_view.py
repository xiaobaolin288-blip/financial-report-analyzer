from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db.session import get_session
from src.repositories.company_repo import CompanyRepository

PAGE_SIZE = 200

logger = logging.getLogger(__name__)


class CompanyListView(QWidget):
    open_company = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._page = 0
        self._total = 0
        self._watch_ids: set[int] = set()

        layout = QVBoxLayout(self)
        title = QLabel("公司库")
        title.setObjectName("titleLabel")

        bar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索代码或名称…")
        btn_search = QPushButton("搜索")
        btn_search.clicked.connect(self._search_reset)
        self._search.returnPressed.connect(self._search_reset)
        bar.addWidget(self._search)
        bar.addWidget(btn_search)

        action_bar = QHBoxLayout()
        self._status = QLabel("")
        self._status.setObjectName("subtitleLabel")
        btn_watch = QPushButton("加入自选")
        btn_watch.clicked.connect(self._add_selected)
        btn_unwatch = QPushButton("移出自选")
        btn_unwatch.setObjectName("dangerBtn")
        btn_unwatch.clicked.connect(self._remove_selected)
        btn_prev = QPushButton("上一页")
        btn_prev.clicked.connect(self._prev_page)
        btn_next = QPushButton("下一页")
        btn_next.clicked.connect(self._next_page)
        self._btn_prev = btn_prev
        self._btn_next = btn_next
        action_bar.addWidget(self._status)
        action_bar.addStretch()
        action_bar.addWidget(btn_watch)
        action_bar.addWidget(btn_unwatch)
        action_bar.addWidget(btn_prev)
        action_bar.addWidget(btn_next)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["代码", "名称", "市场", "自选"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.cellDoubleClicked.connect(self._on_double_click)

        layout.addWidget(title)
        layout.addLayout(bar)
        layout.addLayout(action_bar)
        layout.addWidget(self._table)

    def _search_reset(self) -> None:
        self._page = 0
        self.refresh()

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self.refresh()

    def _next_page(self) -> None:
        max_page = max(0, (self._total - 1) // PAGE_SIZE)
        if self._page < max_page:
            self._page += 1
            self.refresh()

    def refresh(self) -> None:
        try:
            self._refresh_impl()
        except Exception:
            logger.exception("公司库加载失败")
            self._reset_table()
            self._table.setRowCount(1)
            hint = QTableWidgetItem("加载失败，请查看 logs/app.log")
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            self._table.setItem(0, 0, hint)
            self._table.setSpan(0, 0, 1, 4)

    def _refresh_impl(self) -> None:
        keyword = self._search.text().strip()
        offset = self._page * PAGE_SIZE

        with get_session() as session:
            repo = CompanyRepository(session)
            self._total = repo.count(keyword)
            if self._total == 0 and not keyword:
                self._total = repo.count("")
            rows = [
                (c.id, c.stock_code or "", c.name or "", c.market or "")
                for c in repo.search(keyword, limit=PAGE_SIZE, offset=offset)
            ]
            self._watch_ids = repo.watchlist_ids()

        self._reset_table()
        max_page = max(1, (self._total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._status.setText(
            f"共 {self._total} 家 · 第 {self._page + 1}/{max_page} 页（每页 {PAGE_SIZE} 条）"
        )
        self._btn_prev.setEnabled(self._page > 0)
        self._btn_next.setEnabled((self._page + 1) * PAGE_SIZE < self._total)

        if self._total == 0:
            self._table.setRowCount(1)
            hint = QTableWidgetItem("暂无数据：请点击「从外网更新」→「仅同步 A 股公司列表」")
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            self._table.setItem(0, 0, hint)
            self._table.setSpan(0, 0, 1, 4)
            return

        self._table.setRowCount(len(rows))
        for row, (company_id, stock_code, name, market) in enumerate(rows):
            code_item = QTableWidgetItem(stock_code)
            code_item.setData(Qt.ItemDataRole.UserRole, stock_code)
            self._table.setItem(row, 0, code_item)
            self._table.setItem(row, 1, QTableWidgetItem(name))
            self._table.setItem(row, 2, QTableWidgetItem(market))
            in_watch = company_id in self._watch_ids
            watch_item = QTableWidgetItem("★ 已关注" if in_watch else "")
            watch_item.setData(Qt.ItemDataRole.UserRole, company_id)
            watch_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row, 3, watch_item)

    def _reset_table(self) -> None:
        self._table.clearSpans()
        self._table.clearContents()
        self._table.setRowCount(0)

    def _selected_code(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole) or item.text()

    def _add_selected(self) -> None:
        code = self._selected_code()
        if not code:
            return
        with get_session() as session:
            repo = CompanyRepository(session)
            company = repo.get_by_code(code)
            if company:
                repo.add_watchlist(company)
        self.refresh()

    def _remove_selected(self) -> None:
        code = self._selected_code()
        if not code:
            return
        with get_session() as session:
            repo = CompanyRepository(session)
            company = repo.get_by_code(code)
            if company:
                repo.remove_watchlist(company)
        self.refresh()

    def _on_double_click(self, row: int, _col: int) -> None:
        item = self._table.item(row, 0)
        if not item:
            return
        code = item.data(Qt.ItemDataRole.UserRole) or item.text()
        if code and not code.startswith("暂无"):
            self.open_company.emit(code)
