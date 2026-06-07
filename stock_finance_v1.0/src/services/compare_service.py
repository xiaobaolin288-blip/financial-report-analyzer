from __future__ import annotations

from sqlalchemy.orm import Session

from src.repositories.indicator_repo import IndicatorRepository

METRIC_LABELS = {
    "revenue": "营业收入（元）",
    "net_profit": "净利润（元）",
    "roe": "ROE（%）",
    "gross_profit_margin": "毛利率（%）",
    "debt_asset_ratio": "资产负债率（%）",
    "eps": "每股收益",
    "operating_cash_flow": "经营现金流（元）",
}


class CompareService:
    def __init__(self, session: Session) -> None:
        self._repo = IndicatorRepository(session)

    def company_time_series(
        self,
        stock_code: str,
        metric: str,
        *,
        report_type: str | None = "annual",
        years: int = 10,
    ) -> dict:
        rows = self._repo.series_for_company(stock_code, report_type=report_type, years=years)
        periods: list[str] = []
        values: list[float | None] = []
        for report, indicator in rows:
            value = getattr(indicator, metric, None)
            periods.append(report.report_period.strftime("%Y-%m-%d"))
            values.append(value)
        return {
            "title": f"{stock_code} · {METRIC_LABELS.get(metric, metric)}",
            "categories": periods,
            "series_name": METRIC_LABELS.get(metric, metric),
            "values": values,
        }

    def multi_company_bar(
        self,
        stock_codes: list[str],
        metric: str,
        *,
        report_type: str = "annual",
    ) -> dict:
        snapshots = self._repo.latest_snapshot(stock_codes, report_type=report_type)
        names = [f"{s['name']}\n{s['stock_code']}" for s in snapshots]
        values = [s.get(metric) for s in snapshots]
        return {
            "title": f"多公司对比 · {METRIC_LABELS.get(metric, metric)}",
            "categories": names,
            "series_name": METRIC_LABELS.get(metric, metric),
            "values": values,
        }
