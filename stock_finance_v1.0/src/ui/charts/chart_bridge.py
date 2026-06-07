from __future__ import annotations

import math

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget


class ChartWidget(QWidget):
    """Matplotlib 图表 — 暗色主题 + 缩放工具栏 + 悬浮标注。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._figure = Figure(figsize=(8, 4), facecolor="#0f1419")
        self._canvas = FigureCanvasQTAgg(self._figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏（缩放/平移/复位）
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._toolbar.setStyleSheet(
            "QToolBar { background: #0f1419; border: none; spacing: 2px; }"
            "QToolButton { background: #151b24; color: #8b9cb3; border: 1px solid #1e2836;"
            "  border-radius: 4px; padding: 3px 6px; }"
            "QToolButton:hover { background: #1e2836; }"
            "QToolButton:checked { background: #2a3544; color: #6eb6ff; }"
        )
        # 工具栏按钮中文化（覆盖 Matplotlib 默认英文 tooltip）
        self._localize_toolbar()

        layout.addWidget(self._canvas)
        layout.addWidget(self._toolbar)

        # 悬浮标注状态
        self._annot = None
        self._last_cid = None
        self._current_data = {}  # 存储当前图表数据用于悬浮

    def _localize_toolbar(self) -> None:
        """将 Matplotlib 导航工具栏按钮提示改为中文。"""
        tips = {
            "Home": "复位",
            "Back": "后退",
            "Forward": "前进",
            "Pan": "拖动",
            "Zoom": "框选缩放",
            "Subplots": "子图设置",
            "Save": "保存图片",
            "Customize": "自定义",
        }
        from PySide6.QtWidgets import QToolButton
        for child in self._toolbar.findChildren(QToolButton):
            tt = child.toolTip()
            if tt in tips:
                child.setToolTip(tips[tt])
            bt = child.text()
            if bt in tips:
                child.setText(tips[bt])

    def render(self, chart_type: str, payload: dict) -> None:
        # 先断开旧悬浮事件，防止 stale callback 泄漏
        self._disconnect_hover()
        self._figure.clear()
        self._current_data = payload
        self._annot = None
        self._ax_for_hover = None

        ax = self._figure.add_subplot(111)
        ax.set_facecolor("#151b24")
        for spine in ax.spines.values():
            spine.set_color("#2a3544")
        ax.tick_params(colors="#8b9cb3", labelsize=9)
        ax.title.set_color("#e8edf4")
        ax.yaxis.label.set_color("#8b9cb3")
        ax.xaxis.label.set_color("#8b9cb3")

        categories = payload.get("categories") or []
        values = payload.get("values") or []
        title = payload.get("title") or ""
        series_name = payload.get("series_name") or ""

        if not categories or not values:
            ax.text(
                0.5, 0.5,
                title or "暂无数据",
                ha="center", va="center",
                transform=ax.transAxes,
                color="#8b9cb3", fontsize=14,
            )
            ax.set_xticks([])
            ax.set_yticks([])
        elif chart_type == "bar":
            ax.set_title(title, fontsize=13, pad=12, fontweight="bold")
            colors = ["#5ad8a6" if (v is not None and v >= 0) else "#f56c6c" for v in values]
            bars = ax.bar(range(len(categories)), [v or 0 for v in values],
                          color=colors, edgecolor="none")
            ax.set_xticks(range(len(categories)))
            short = [self._short_label(c) for c in categories]
            ax.set_xticklabels(short, rotation=25, ha="right")
            ax.grid(axis="y", color="#1e2836", linestyle="--", alpha=0.6)
            for bar, val in zip(bars, values):
                if val is not None:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height(),
                        self._format_value(val),
                        ha="center", va="bottom",
                        color="#c5d0de", fontsize=8,
                    )
        else:
            ax.set_title(title, fontsize=13, pad=12, fontweight="bold")
            xs = list(range(len(categories)))
            ys = [v if v is not None else float("nan") for v in values]
            (line,) = ax.plot(xs, ys, color="#3d8bfd", linewidth=2.5,
                              marker="o", markersize=7, label=series_name)
            ax.fill_between(xs, ys, color="#3d8bfd", alpha=0.15)
            ax.set_xticks(xs)
            ax.set_xticklabels(categories, rotation=25, ha="right")
            ax.grid(color="#1e2836", linestyle="--", alpha=0.6)

            # 数据点引用（用于悬浮检测）
            self._line = line
            self._xs = xs
            self._ys = ys
            self._ax_for_hover = ax

            if series_name:
                leg = ax.legend(facecolor="#151b24", edgecolor="#2a3544", labelcolor="#e8edf4")
                leg.get_frame().set_alpha(0.9)

        self._figure.tight_layout()
        self._canvas.draw_idle()

        # 重新绑定悬浮事件（每次 render 后需要重新连接）
        if chart_type != "bar" and categories:
            self._setup_hover()

    def _disconnect_hover(self) -> None:
        """断开旧悬浮事件，避免 stale callback 在已销毁的 axes 上触发。"""
        if self._last_cid is not None:
            try:
                self._canvas.mpl_disconnect(self._last_cid)
            except Exception:
                pass
            self._last_cid = None

    def _setup_hover(self) -> None:

        self._annot = self._ax_for_hover.annotate(
            "", xy=(0, 0), xytext=(12, 12),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.4", fc="#1a2332", ec="#3d8bfd", alpha=0.95),
            fontsize=9, color="#e8edf4",
            visible=False,
        )

        self._last_cid = self._canvas.mpl_connect("motion_notify_event", self._on_hover)

    def _on_hover(self, event) -> None:
        if event.inaxes != getattr(self, "_ax_for_hover", None):
            if self._annot and self._annot.get_visible():
                self._annot.set_visible(False)
                self._canvas.draw_idle()
            self._canvas.setCursor(Qt.CursorShape.ArrowCursor)
            return

        xs = getattr(self, "_xs", [])
        ys = getattr(self, "_ys", [])
        if not len(xs):
            return

        # 找到最近的数据点
        x_data, y_data = event.xdata, event.ydata
        if x_data is None:
            return

        # 查找最近的 x 索引
        tol = max(abs(xs[-1] - xs[0]) * 0.03 if len(xs) > 1 else 0.5, 0.3)
        min_dist = float("inf")
        best_idx = -1

        for i, (xi, yi) in enumerate(zip(xs, ys)):
            if math.isnan(yi):
                continue
            dist = abs(xi - x_data)
            if dist < min_dist:
                min_dist = dist
                best_idx = i

        if best_idx >= 0 and min_dist < tol:
            xi, yi = xs[best_idx], ys[best_idx]
            self._canvas.setCursor(Qt.CursorShape.PointingHandCursor)

            # 更新标注内容
            categories = self._current_data.get("categories", [])
            label = categories[best_idx] if best_idx < len(categories) else str(xi)
            series_name = self._current_data.get("series_name", "")
            val_text = self._format_value(yi) if not math.isnan(yi) else "—"

            if series_name:
                text = f"{label}\n{series_name}：{val_text}"
            else:
                text = f"{label}\n{val_text}"

            self._annot.xy = (xi, yi)
            self._annot.set_text(text)
            self._annot.set_visible(True)
            self._canvas.draw_idle()
        else:
            self._canvas.setCursor(Qt.CursorShape.ArrowCursor)
            if self._annot and self._annot.get_visible():
                self._annot.set_visible(False)
                self._canvas.draw_idle()

    @staticmethod
    def _short_label(text: str, max_len: int = 12) -> str:
        text = str(text).replace("\n", " ")
        return text if len(text) <= max_len else text[: max_len - 1] + "…"

    @staticmethod
    def _format_value(v: float) -> str:
        if abs(v) >= 1e8:
            return f"{v / 1e8:.1f}亿"
        if abs(v) >= 1e4:
            return f"{v / 1e4:.1f}万"
        return f"{v:.2f}"
