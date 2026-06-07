from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.db.session import get_session
from src.services.query_service import FIELD_MAP, QueryCondition, QueryService


class QueryView(QWidget):
    open_company = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("高级查询"))
        self._rows: list[tuple[QComboBox, QComboBox, QDoubleSpinBox]] = []
        for _ in range(3):
            layout.addLayout(self._make_condition_row())
        btn = QPushButton("执行查询")
        btn.setObjectName("primaryBtn")
        btn.clicked.connect(self.run_query)
        layout.addWidget(btn)
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["代码", "名称", "报告期", "ROE%", "毛利率%", "负债率%", "EPS"]
        )
        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

    def _make_condition_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        field = QComboBox()
        labels = {
            "roe": "ROE",
            "gross_profit_margin": "毛利率",
            "debt_asset_ratio": "资产负债率",
            "eps": "每股收益",
            "revenue": "营业收入",
            "net_profit": "净利润",
        }
        for key, label in labels.items():
            if key in FIELD_MAP:
                field.addItem(label, key)
        op = QComboBox()
        op.addItem("≥", ">=")
        op.addItem("≤", "<=")
        op.addItem(">", ">")
        op.addItem("<", "<")
        op.addItem("=", "=")
        val = QDoubleSpinBox()
        val.setRange(-1e12, 1e12)
        val.setDecimals(2)
        val.setValue(15)
        row.addWidget(field)
        row.addWidget(op)
        row.addWidget(val)
        self._rows.append((field, op, val))
        return row

    def run_query(self) -> None:
        conditions: list[QueryCondition] = []
        for field, op, val in self._rows:
            conditions.append(
                QueryCondition(
                    field=field.currentData(),
                    operator=op.currentData(),
                    value=val.value(),
                )
            )
        with get_session() as session:
            results = QueryService(session).filter_companies(conditions)

        self._table.setRowCount(len(results))
        for i, r in enumerate(results):
            self._table.setItem(i, 0, QTableWidgetItem(r["stock_code"]))
            self._table.setItem(i, 1, QTableWidgetItem(r["name"]))
            self._table.setItem(i, 2, QTableWidgetItem(r["report_period"]))
            self._table.setItem(i, 3, QTableWidgetItem(_s(r.get("roe"))))
            self._table.setItem(i, 4, QTableWidgetItem(_s(r.get("gross_profit_margin"))))
            self._table.setItem(i, 5, QTableWidgetItem(_s(r.get("debt_asset_ratio"))))
            self._table.setItem(i, 6, QTableWidgetItem(_s(r.get("eps"))))

    def _on_double_click(self, row: int, _col: int) -> None:
        item = self._table.item(row, 0)
        if item:
            self.open_company.emit(item.text())


def _s(v) -> str:
    return "—" if v is None else f"{v:.2f}"
