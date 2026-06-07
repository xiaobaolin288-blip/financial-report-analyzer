from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
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
from src.repositories.indicator_repo import IndicatorRepository
from src.services.compare_service import METRIC_LABELS, CompareService
from src.ui.charts.chart_bridge import ChartWidget
from src.ui.widgets.kpi_card import KpiCard


class CompanyDetailView(QWidget):
    sync_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_code = ""

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("单公司分析")
        title.setObjectName("titleLabel")
        self._code_input = QLineEdit()
        self._code_input.setPlaceholderText("股票代码，如 600519")
        self._code_input.setMaximumWidth(160)
        btn_load = QPushButton("加载")
        btn_load.setObjectName("primaryBtn")
        btn_load.clicked.connect(self.load_company)
        btn_sync = QPushButton("同步该公司财报")
        btn_sync.setObjectName("primaryBtn")
        btn_sync.clicked.connect(self._request_sync)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._code_input)
        header.addWidget(btn_load)
        header.addWidget(btn_sync)

        self._hint = QLabel(
            "当前只有公司名录（代码/名称）。要查看 ROE、利润、图表等，请点「同步该公司财报」"
            "或在左侧「从外网更新」中选择「自选列表」批量同步。"
        )
        self._hint.setObjectName("subtitleLabel")
        self._hint.setWordWrap(True)
        self._hint.setVisible(False)

        controls = QHBoxLayout()
        self._metric = QComboBox()
        for key, label in METRIC_LABELS.items():
            self._metric.addItem(label, key)
        self._report_type = QComboBox()
        self._report_type.addItem("年报", "annual")
        self._report_type.addItem("季报", "quarterly")
        self._metric.currentIndexChanged.connect(self._refresh_chart)
        self._report_type.currentIndexChanged.connect(self._refresh_chart)
        controls.addWidget(QLabel("指标"))
        controls.addWidget(self._metric)
        controls.addWidget(QLabel("报告类型"))
        controls.addWidget(self._report_type)
        controls.addStretch()

        kpi_row = QGridLayout()
        self._kpi_revenue = KpiCard("营业收入")
        self._kpi_profit = KpiCard("净利润")
        self._kpi_roe = KpiCard("ROE")
        self._kpi_debt = KpiCard("资产负债率")
        kpi_row.addWidget(self._kpi_revenue, 0, 0)
        kpi_row.addWidget(self._kpi_profit, 0, 1)
        kpi_row.addWidget(self._kpi_roe, 0, 2)
        kpi_row.addWidget(self._kpi_debt, 0, 3)

        self._chart = ChartWidget()
        self._chart.setMinimumHeight(320)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            ["报告期", "类型", "营收", "净利润", "ROE%", "毛利率%", "负债率%", "EPS"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        root.addLayout(header)
        root.addWidget(self._hint)
        root.addLayout(controls)
        root.addLayout(kpi_row)
        root.addWidget(self._chart, stretch=1)
        root.addWidget(self._table)

    def set_stock_code(self, code: str) -> None:
        self._code_input.setText(code)
        self.load_company()

    def _request_sync(self) -> None:
        code = self._code_input.text().strip().zfill(6)
        if code:
            self.sync_requested.emit(code)

    def load_company(self) -> None:
        code = self._code_input.text().strip().zfill(6)
        if not code:
            return
        self._current_code = code
        self._fill_table()
        self._refresh_kpis()
        self._refresh_chart()

    def _load_rows(self, report_type: str) -> list[tuple]:
        with get_session() as session:
            pairs = IndicatorRepository(session).series_for_company(
                self._current_code, report_type=report_type
            )
            return [
                (
                    report.report_period.isoformat(),
                    report.report_type,
                    ind.revenue,
                    ind.net_profit,
                    ind.roe,
                    ind.gross_profit_margin,
                    ind.debt_asset_ratio,
                    ind.eps,
                )
                for report, ind in pairs
            ]

    def _fill_table(self) -> None:
        report_type = self._report_type.currentData()
        rows = self._load_rows(report_type)
        self._hint.setVisible(len(rows) == 0)

        self._table.setRowCount(len(rows))
        for i, (period, rtype, rev, profit, roe, margin, debt, eps) in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(period))
            self._table.setItem(i, 1, QTableWidgetItem(rtype))
            self._table.setItem(i, 2, QTableWidgetItem(_fmt(rev)))
            self._table.setItem(i, 3, QTableWidgetItem(_fmt(profit)))
            self._table.setItem(i, 4, QTableWidgetItem(_fmt(roe)))
            self._table.setItem(i, 5, QTableWidgetItem(_fmt(margin)))
            self._table.setItem(i, 6, QTableWidgetItem(_fmt(debt)))
            self._table.setItem(i, 7, QTableWidgetItem(_fmt(eps)))

    def _refresh_kpis(self) -> None:
        report_type = self._report_type.currentData()
        rows = self._load_rows(report_type)
        if not rows:
            for card in (self._kpi_revenue, self._kpi_profit, self._kpi_roe, self._kpi_debt):
                card.set_value("—")
            return
        *_, latest = rows[-1]
        _, _, rev, profit, roe, _, debt, _ = latest
        self._kpi_revenue.animate_number(rev)
        self._kpi_profit.animate_number(profit)
        self._kpi_roe.animate_number(roe, suffix="%")
        self._kpi_debt.animate_number(debt, suffix="%")

    def _refresh_chart(self) -> None:
        if not self._current_code:
            return
        metric = self._metric.currentData()
        report_type = self._report_type.currentData()
        with get_session() as session:
            payload = CompareService(session).company_time_series(
                self._current_code, metric, report_type=report_type
            )
        self._chart.render("line", payload)


def _fmt(v) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.2f}万"
    return f"{v:.2f}"
