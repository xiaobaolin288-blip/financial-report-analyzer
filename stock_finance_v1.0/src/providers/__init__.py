from src.providers.akshare_provider import AkshareProvider
from src.providers.base import FinancialDataProvider

__all__ = ["FinancialDataProvider", "AkshareProvider"]


def get_provider(name: str | None = None) -> FinancialDataProvider:
    from src.core.config import load_settings

    settings = load_settings()
    name = name or settings.get("provider", {}).get("name", "akshare")
    if name == "akshare":
        interval = float(settings.get("provider", {}).get("request_interval_sec", 0.3))
        return AkshareProvider(request_interval_sec=interval)
    raise ValueError(f"未知数据源: {name}")
