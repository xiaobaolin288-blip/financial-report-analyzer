from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.core.config import CONFIG_PATH, database_url, load_settings


class SettingsView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("设置")
        title.setObjectName("titleLabel")
        settings = load_settings()
        info = QLabel(
            f"配置文件: {CONFIG_PATH}\n"
            f"数据库: {database_url(settings)}\n"
            f"数据源: {settings.get('provider', {}).get('name', 'akshare')}\n\n"
            "未来切换 PostgreSQL：修改 config/settings.yaml 中的 database.url 即可。"
        )
        info.setWordWrap(True)
        info.setObjectName("subtitleLabel")
        layout.addWidget(title)
        layout.addWidget(info)
        layout.addStretch()
