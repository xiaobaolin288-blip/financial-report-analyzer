from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.db.session import get_session
from src.repositories.company_repo import CompanyRepository
from src.services.compare_service import METRIC_LABELS, CompareService
from src.ui.charts.chart_bridge import ChartWidget


class CompareView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("多公司对比")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self._codes = QListWidget()
        self._codes.setMaximumHeight(120)

        bar = QHBoxLayout()
        self._code_input = QLineEdit()
        self._code_input.setPlaceholderText("输入代码后回车添加")
        self._code_input.returnPressed.connect(self._add_code)
        btn_add = QPushButton("添加")
        btn_add.clicked.connect(self._add_code)
        btn_watchlist = QPushButton("载入自选")
        btn_watchlist.clicked.connect(self._load_watchlist)
        btn_clear = QPushButton("清空")
        btn_clear.setObjectName("dangerBtn")
        btn_clear.clicked.connect(self._codes.clear)
        bar.addWidget(self._code_input)
        bar.addWidget(btn_add)
        bar.addWidget(btn_watchlist)
        bar.addWidget(btn_clear)
        layout.addLayout(bar)
        layout.addWidget(self._codes)

        ctrl = QHBoxLayout()
        self._metric = QComboBox()
        for key, label in METRIC_LABELS.items():
            self._metric.addItem(label, key)
        self._report_type = QComboBox()
        self._report_type.addItem("年报", "annual")
        self._report_type.addItem("季报", "quarterly")
        btn_refresh = QPushButton("刷新图表")
        btn_refresh.setObjectName("primaryBtn")
        btn_refresh.clicked.connect(self.refresh_chart)
        self._metric.currentIndexChanged.connect(self.refresh_chart)
        ctrl.addWidget(QLabel("指标"))
        ctrl.addWidget(self._metric)
        ctrl.addWidget(QLabel("报告"))
        ctrl.addWidget(self._report_type)
        ctrl.addStretch()
        ctrl.addWidget(btn_refresh)
        layout.addLayout(ctrl)

        self._chart = ChartWidget()
        self._chart.setMinimumHeight(400)
        layout.addWidget(self._chart, stretch=1)

    def _add_code(self) -> None:
        code = self._code_input.text().strip().zfill(6)
        if not code:
            return
        for i in range(self._codes.count()):
            if self._codes.item(i).text() == code:
                return
        self._codes.addItem(code)
        self._code_input.clear()

    def _load_watchlist(self) -> None:
        self._codes.clear()
        with get_session() as session:
            companies = CompanyRepository(session).watchlist()
        for c in companies:
            self._codes.addItem(c.stock_code)

    def refresh_chart(self) -> None:
        codes = [self._codes.item(i).text() for i in range(self._codes.count())]
        if not codes:
            self._chart.render("bar", {"title": "请先添加公司代码", "categories": [], "values": []})
            return
        metric = self._metric.currentData()
        report_type = self._report_type.currentData()
        with get_session() as session:
            payload = CompareService(session).multi_company_bar(
                codes, metric, report_type=report_type
            )
        self._chart.render("bar", payload)
