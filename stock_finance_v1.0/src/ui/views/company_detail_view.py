from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
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
from src.repositories.company_repo import CompanyRepository
from src.repositories.indicator_repo import IndicatorRepository
from src.services.compare_service import METRIC_LABELS, CompareService
from src.ui.charts.chart_bridge import ChartWidget
from src.ui.widgets.kpi_card import KpiCard

_log = logging.getLogger(__name__)

# 表格中需要颜色标记的数值列索引（0-based）
_NUMERIC_COLS = {2, 3, 4, 5, 6, 7}

# 颜色常量
_COLOR_POSITIVE = QColor("#5ad8a6")   # 绿色：盈利/正值
_COLOR_NEGATIVE = QColor("#f56c6c")   # 红色：亏损/负值
_COLOR_MUTED = QColor("#5a6a7a")      # 灰色：N/A
_COLOR_DEFAULT = QColor("#c5d0de")    # 白/浅灰：零值或普通


class CompanyDetailView(QWidget):
    sync_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_code = ""
        self._current_name = ""  # 当前公司名称

        root = QVBoxLayout(self)

        # ── 顶栏：标题 + 代码输入 + 按钮 ──
        header = QHBoxLayout()
        title = QLabel("单公司分析")
        title.setObjectName("titleLabel")
        self._company_name = QLabel("")
        self._company_name.setStyleSheet(
            "color: #6eb6ff; font-size: 14px; font-weight: 600; margin-left: 8px;"
        )
        self._code_input = QLineEdit()
        self._code_input.setPlaceholderText("股票代码，如 600519")
        self._code_input.setMaximumWidth(140)
        btn_load = QPushButton("加载")
        btn_load.setObjectName("primaryBtn")
        btn_load.clicked.connect(self.load_company)
        btn_sync = QPushButton("同步该公司财报")
        btn_sync.setObjectName("primaryBtn")
        btn_sync.clicked.connect(self._request_sync)
        header.addWidget(title)
        header.addWidget(self._company_name)
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

        # ── 控制栏 ──
        controls = QHBoxLayout()
        self._metric = QComboBox()
        for key, label in METRIC_LABELS.items():
            self._metric.addItem(label, key)
        self._report_type = QComboBox()
        self._report_type.addItem("年报", "annual")
        self._report_type.addItem("季报", "quarterly")
        self._metric.currentIndexChanged.connect(self._refresh_chart)
        self._report_type.currentIndexChanged.connect(self._on_report_type_changed)
        controls.addWidget(QLabel("指标"))
        controls.addWidget(self._metric)
        controls.addWidget(QLabel("报告类型"))
        controls.addWidget(self._report_type)
        controls.addStretch()

        # ── KPI 卡片：2 行 × 4 列 ──
        kpi_row = QGridLayout()
        kpi_row.setSpacing(10)
        self._kpi_revenue = KpiCard("营业收入")
        self._kpi_profit = KpiCard("净利润")
        self._kpi_roe = KpiCard("ROE")
        self._kpi_margin = KpiCard("毛利率")
        self._kpi_debt = KpiCard("资产负债率")
        self._kpi_eps = KpiCard("每股收益")
        self._kpi_bps = KpiCard("每股净资产")
        self._kpi_ocf = KpiCard("经营现金流")
        # 第一行
        kpi_row.addWidget(self._kpi_revenue, 0, 0)
        kpi_row.addWidget(self._kpi_profit, 0, 1)
        kpi_row.addWidget(self._kpi_roe, 0, 2)
        kpi_row.addWidget(self._kpi_margin, 0, 3)
        # 第二行
        kpi_row.addWidget(self._kpi_debt, 1, 0)
        kpi_row.addWidget(self._kpi_eps, 1, 1)
        kpi_row.addWidget(self._kpi_bps, 1, 2)
        kpi_row.addWidget(self._kpi_ocf, 1, 3)

        self._all_kpis = [
            self._kpi_revenue, self._kpi_profit, self._kpi_roe,
            self._kpi_margin, self._kpi_debt, self._kpi_eps,
            self._kpi_bps, self._kpi_ocf,
        ]

        self._chart = ChartWidget()
        self._chart.setMinimumHeight(320)

        # ── 表格 ──
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

    # ── 公开方法 ──

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
        # 获取公司名称
        self._load_company_name()
        for step_name, step in [
            ("fill_table", self._fill_table),
            ("refresh_kpis", self._refresh_kpis),
            ("refresh_chart", self._refresh_chart),
        ]:
            try:
                step()
            except Exception:
                _log.exception("load_company(%s) %s 失败", code, step_name)

    # ── 内部方法 ──

    def _load_company_name(self) -> None:
        try:
            with get_session() as session:
                c = CompanyRepository(session).get_by_code(self._current_code)
                if c and c.name:
                    self._current_name = c.name
                    self._company_name.setText(f"· {c.name}")
                    return
        except Exception:
            _log.exception("获取公司名称失败")
        self._current_name = ""
        self._company_name.setText("")

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
                    ind.bps,
                    ind.operating_cash_flow,
                )
                for report, ind in pairs
            ]

    @staticmethod
    def _calc_trend(current_period: str, current_value: float | None, rows: list[tuple]) -> float | None:
        """计算同比变化率。

        找到与 current_period 同年上期（季报）或上年同期（年报）的数据，
        返回 (current - prev) / abs(prev) * 100，无数据则返回 None。
        """
        if current_value is None or current_value == 0:
            return None
        # 从 current_period 解析年份和月份
        parts = current_period.split("-")
        if len(parts) < 2:
            return None
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 12
        # 年报 (12-31) → 找上年年报
        if month == 12:
            target_year = year - 1
            target_month = 12
        else:
            target_year = year - 1
            target_month = month

        prev_value = None
        for row in rows:
            rp = row[0]  # report_period str
            try:
                rp_parts = rp.split("-")
                rp_year = int(rp_parts[0])
                rp_month = int(rp_parts[1]) if len(rp_parts) > 1 else 12
            except (ValueError, IndexError):
                continue
            if rp_year == target_year and rp_month == target_month:
                prev_value = row[2]  # revenue 在索引2，但这取决于我们比较的字段...
                break

        # 注意：row[2] 是 revenue，需要根据当前字段重新取值
        # 这里简化处理：重新从 rows 找到对应字段的值
        # 实际在 _refresh_kpis 中根据不同字段分别处理
        return None  # 由调用方根据具体字段计算

    def _find_prev_value(self, rows: list[tuple], current_period: str, field_idx: int) -> float | None:
        """在 rows 中找到同一字段上年同期的值。"""
        parts = current_period.split("-")
        if len(parts) < 2:
            return None
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 12
        target_year = year - 1
        target_month = month

        for row in rows:
            rp = row[0]
            try:
                rp_parts = rp.split("-")
                rp_year = int(rp_parts[0])
                rp_month = int(rp_parts[1]) if len(rp_parts) > 1 else 12
            except (ValueError, IndexError):
                continue
            if rp_year == target_year and rp_month == target_month:
                return row[field_idx]
        return None

    def _report_type_label(self) -> str:
        rt = self._report_type.currentData()
        return "年报" if rt == "annual" else "季报"

    def _period_label(self, period_str: str) -> str:
        """从 '2025-12-31' 生成 '2025年报' 或 '2026Q1'。"""
        parts = period_str.split("-")
        if len(parts) < 2:
            return period_str
        year = parts[0]
        month = int(parts[1])
        if month == 12:
            return f"{year}年报"
        q = (month - 1) // 3 + 1
        return f"{year}Q{q}"

    # ── 表格 ──

    def _fill_table(self) -> None:
        report_type = self._report_type.currentData()
        rows = self._load_rows(report_type)
        self._hint.setVisible(len(rows) == 0)

        self._table.setRowCount(len(rows))
        for i, (period, rtype, rev, profit, roe, margin, debt, eps, _bps, _ocf) in enumerate(rows):
            items = [
                period,
                rtype,
                _fmt(rev), _fmt(profit), _fmt(roe),
                _fmt(margin), _fmt(debt), _fmt(eps),
            ]
            for j, text in enumerate(items):
                item = QTableWidgetItem(text)
                # 数值列颜色标记
                if j in _NUMERIC_COLS:
                    raw = [rev, profit, roe, margin, debt, eps][j - 2] if j >= 2 else 0
                    item.setForeground(_color_for(raw))
                else:
                    item.setForeground(_COLOR_DEFAULT)
                self._table.setItem(i, j, item)

    # ── KPI ──

    def _refresh_kpis(self) -> None:
        report_type = self._report_type.currentData()
        rows = self._load_rows(report_type)
        if not rows:
            for card in self._all_kpis:
                card.set_value("—")
                card.set_period("")
                card.set_trend(None)
            return

        latest = rows[-1]  # (period, rtype, rev, profit, roe, margin, debt, eps, bps, ocf)
        period, _, rev, profit, roe, margin, debt, eps, bps, ocf = latest
        period_label = self._period_label(period)

        # KPI 字段配置: (card, field_idx, title, suffix, formatter)
        kpi_config = [
            (self._kpi_revenue, 2, rev, "", _fmt_kpi),
            (self._kpi_profit, 3, profit, "", _fmt_kpi),
            (self._kpi_roe, 4, roe, "%", None),
            (self._kpi_margin, 5, margin, "%", None),
            (self._kpi_debt, 6, debt, "%", None),
            (self._kpi_eps, 7, eps, "", None),
            (self._kpi_bps, 8, bps, "", None),
            (self._kpi_ocf, 9, ocf, "", _fmt_kpi),
        ]

        for card, field_idx, value, suffix, formatter in kpi_config:
            card.animate_number(value, suffix=suffix, formatter=formatter)
            card.set_period(period_label)
            prev = self._find_prev_value(rows, period, field_idx)
            if value is not None and prev is not None and prev != 0:
                delta = (value - prev) / abs(prev) * 100
                card.set_trend(delta)
            else:
                card.set_trend(None)

    def _on_report_type_changed(self) -> None:
        """报告类型切换时刷新表格、KPI 和图表。"""
        self._fill_table()
        self._refresh_kpis()
        self._refresh_chart()

    # ── 图表 ──

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


# ── 格式化 ──

def _fmt(v) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.2f}万"
    return f"{v:.2f}"


def _fmt_kpi(v: float) -> str:
    """KPI 卡片数值格式化（紧凑）。"""
    if abs(v) >= 1e8:
        return f"{v / 1e8:.1f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.0f}万"
    return f"{v:,.2f}"


def _color_for(v) -> QColor:
    if v is None:
        return _COLOR_MUTED
    if isinstance(v, (int, float)):
        if v > 0:
            return _COLOR_POSITIVE
        if v < 0:
            return _COLOR_NEGATIVE
    return _COLOR_DEFAULT
