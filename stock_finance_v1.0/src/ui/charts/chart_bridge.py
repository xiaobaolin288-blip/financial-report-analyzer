from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget


class ChartWidget(QWidget):
    """Matplotlib 图表（无需 PySide6-WebEngine）。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._figure = Figure(figsize=(8, 4), facecolor="#0f1419")
        self._canvas = FigureCanvasQTAgg(self._figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def render(self, chart_type: str, payload: dict) -> None:
        self._figure.clear()
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
                0.5,
                0.5,
                title or "暂无数据",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color="#8b9cb3",
                fontsize=14,
            )
            ax.set_xticks([])
            ax.set_yticks([])
        elif chart_type == "bar":
            ax.set_title(title, fontsize=13, pad=12, fontweight="bold")
            colors = ["#5ad8a6" if (v is not None and v >= 0) else "#f56c6c" for v in values]
            bars = ax.bar(range(len(categories)), [v or 0 for v in values], color=colors, edgecolor="none")
            ax.set_xticks(range(len(categories)))
            short_labels = [_short_label(c) for c in categories]
            ax.set_xticklabels(short_labels, rotation=25, ha="right")
            ax.grid(axis="y", color="#1e2836", linestyle="--", alpha=0.6)
            for bar, val in zip(bars, values):
                if val is not None:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height(),
                        _format_value(val),
                        ha="center",
                        va="bottom",
                        color="#c5d0de",
                        fontsize=8,
                    )
        else:
            ax.set_title(title, fontsize=13, pad=12, fontweight="bold")
            xs = list(range(len(categories)))
            ys = [v if v is not None else float("nan") for v in values]
            ax.plot(xs, ys, color="#3d8bfd", linewidth=2.5, marker="o", markersize=6, label=series_name)
            ax.fill_between(xs, ys, color="#3d8bfd", alpha=0.15)
            ax.set_xticks(xs)
            ax.set_xticklabels(categories, rotation=25, ha="right")
            ax.grid(color="#1e2836", linestyle="--", alpha=0.6)
            if series_name:
                leg = ax.legend(facecolor="#151b24", edgecolor="#2a3544", labelcolor="#e8edf4")
                leg.get_frame().set_alpha(0.9)

        self._figure.tight_layout()
        self._canvas.draw_idle()


def _short_label(text: str, max_len: int = 12) -> str:
    text = str(text).replace("\n", " ")
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _format_value(v: float) -> str:
    if abs(v) >= 1e8:
        return f"{v / 1e8:.1f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.1f}万"
    return f"{v:.2f}"
