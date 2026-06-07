from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class _AnimatedLabel(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._anim: QPropertyAnimation | None = None

    def get_value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        self._value = v
        self.setText(f"{v:,.2f}")

    value = Property(float, get_value, set_value)

    def animate_to(self, target: float, *, suffix: str = "", formatter=None) -> None:
        if self._anim:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"value")
        self._anim.setDuration(800)
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _on_change(v: float) -> None:
            if formatter:
                self.setText(formatter(v))
            elif suffix:
                self.setText(f"{v:,.2f}{suffix}")
            else:
                self.setText(f"{v:,.2f}")

        self._anim.valueChanged.connect(_on_change)
        self._anim.start()


class KpiCard(QFrame):
    """KPI 数值卡片：标题 + 大数值 + 期间 + 同比趋势。"""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("kpiCard")
        self.setStyleSheet(
            """
            QFrame#kpiCard {
                background-color: #151b24;
                border: 1px solid #1e2836;
                border-radius: 12px;
                padding: 4px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(12, 8, 12, 8)

        self._title = QLabel(title)
        self._title.setStyleSheet("color: #8b9cb3; font-size: 12px;")

        self._value = _AnimatedLabel()
        self._value.setStyleSheet("color: #6eb6ff; font-size: 22px; font-weight: 700;")
        self._value.setText("—")

        # 底部行：期间 + 趋势
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)

        self._period = QLabel("")
        self._period.setStyleSheet("color: #5a6a7a; font-size: 11px;")

        self._trend = QLabel("")
        self._trend.setStyleSheet("font-size: 11px; font-weight: 600;")

        bottom.addWidget(self._period)
        bottom.addStretch()
        bottom.addWidget(self._trend)

        layout.addWidget(self._title)
        layout.addWidget(self._value)
        layout.addLayout(bottom)

    def set_value(self, text: str) -> None:
        """静态设置文本（无动画），用于空数据状态。"""
        self._value.setText(text)

    def animate_number(self, value: float | None, *, suffix: str = "", formatter=None) -> None:
        """带动画设置数值。"""
        if value is None:
            self._value.setText("—")
            return
        self._value.animate_to(float(value), suffix=suffix, formatter=formatter)

    def set_period(self, text: str) -> None:
        """设置数据期间标签（如 '2025年报'）。"""
        self._period.setText(text)

    def set_trend(self, delta: float | None, *, suffix: str = "%") -> None:
        """设置同比变化趋势。

        delta > 0 → 绿色 ▲
        delta < 0 → 红色 ▼
        delta is None → 不显示
        """
        if delta is None:
            self._trend.setText("")
            return
        arrow = "▲" if delta >= 0 else "▼"  # ▲ or ▼
        color = "#5ad8a6" if delta >= 0 else "#f56c6c"
        self._trend.setText(f"{arrow} {abs(delta):.1f}{suffix}")
        self._trend.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600;")
