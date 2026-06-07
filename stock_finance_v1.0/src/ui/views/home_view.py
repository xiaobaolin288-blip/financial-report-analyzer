from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget

from src.db.session import get_session
from src.repositories.company_repo import CompanyRepository


class HomeView(QWidget):
    open_company = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("首页 · 自选与快捷入口")
        title.setObjectName("titleLabel")
        subtitle = QLabel(
            "① 公司库加自选 → ②「从外网更新」选「自选公司的财报指标」\n"
            "③ 单公司页查看图表（名录只有代码/名称，财报需单独同步）"
        )
        subtitle.setObjectName("subtitleLabel")
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._list)

    def refresh(self) -> None:
        self._list.clear()
        with get_session() as session:
            rows = [
                (c.stock_code, c.name)
                for c in CompanyRepository(session).watchlist()
            ]
        if not rows:
            self._list.addItem("暂无自选 — 请到「公司库」添加")
            return
        for code, name in rows:
            self._list.addItem(f"{code}  {name}")

    def _on_double_click(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        text = item.text()
        if text.startswith("暂无"):
            return
        code = text.split()[0]
        self.open_company.emit(code)
