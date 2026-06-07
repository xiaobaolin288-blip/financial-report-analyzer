from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Property
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


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
        self._title = QLabel(title)
        self._title.setStyleSheet("color: #8b9cb3; font-size: 12px;")
        self._value = _AnimatedLabel()
        self._value.setStyleSheet("color: #6eb6ff; font-size: 22px; font-weight: 700;")
        self._value.setText("—")
        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def animate_number(self, value: float | None, *, suffix: str = "", formatter=None) -> None:
        if value is None:
            self._value.setText("—")
            return
        self._value.animate_to(float(value), suffix=suffix, formatter=formatter)
