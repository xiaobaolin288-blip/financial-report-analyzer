from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class CompanyDTO:
    stock_code: str
    name: str
    market: str | None = None


@dataclass
class IndicatorRowDTO:
    report_period: date
    report_type: str
    revenue: float | None = None
    net_profit: float | None = None
    gross_profit_margin: float | None = None
    roe: float | None = None
    debt_asset_ratio: float | None = None
    eps: float | None = None
    bps: float | None = None
    operating_cash_flow: float | None = None


class FinancialDataProvider(ABC):
    @abstractmethod
    def fetch_company_list(self) -> list[CompanyDTO]:
        pass

    @abstractmethod
    def fetch_indicators(self, stock_code: str) -> list[IndicatorRowDTO]:
        pass
