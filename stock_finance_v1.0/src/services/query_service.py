from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.db.models import Company, FinancialIndicator, FinancialReport


@dataclass
class QueryCondition:
    field: str
    operator: str
    value: float


FIELD_MAP = {
    "roe": FinancialIndicator.roe,
    "gross_profit_margin": FinancialIndicator.gross_profit_margin,
    "debt_asset_ratio": FinancialIndicator.debt_asset_ratio,
    "eps": FinancialIndicator.eps,
    "revenue": FinancialIndicator.revenue,
    "net_profit": FinancialIndicator.net_profit,
}


class QueryService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def filter_companies(
        self,
        conditions: list[QueryCondition],
        *,
        report_type: str = "annual",
        limit: int = 200,
    ) -> list[dict]:
        if not conditions:
            return []

        filters = []
        for cond in conditions:
            column = FIELD_MAP.get(cond.field)
            if column is None:
                continue
            if cond.operator == ">=":
                filters.append(column >= cond.value)
            elif cond.operator == "<=":
                filters.append(column <= cond.value)
            elif cond.operator == ">":
                filters.append(column > cond.value)
            elif cond.operator == "<":
                filters.append(column < cond.value)
            elif cond.operator == "=":
                filters.append(column == cond.value)

        if not filters:
            return []

        latest = (
            select(
                FinancialReport.company_id.label("company_id"),
                func.max(FinancialReport.report_period).label("max_period"),
            )
            .where(FinancialReport.report_type == report_type)
            .group_by(FinancialReport.company_id)
            .subquery()
        )

        stmt = (
            select(Company, FinancialIndicator, FinancialReport)
            .join(FinancialReport, FinancialReport.company_id == Company.id)
            .join(
                latest,
                and_(
                    FinancialReport.company_id == latest.c.company_id,
                    FinancialReport.report_period == latest.c.max_period,
                ),
            )
            .join(FinancialIndicator, FinancialIndicator.report_id == FinancialReport.id)
            .where(FinancialReport.report_type == report_type)
            .where(and_(*filters))
            .order_by(Company.stock_code)
            .limit(limit)
        )

        results: list[dict] = []
        for company, indicator, report in self._session.execute(stmt):
            results.append(
                {
                    "stock_code": company.stock_code,
                    "name": company.name,
                    "report_period": report.report_period.isoformat(),
                    "roe": indicator.roe,
                    "gross_profit_margin": indicator.gross_profit_margin,
                    "debt_asset_ratio": indicator.debt_asset_ratio,
                    "eps": indicator.eps,
                    "revenue": indicator.revenue,
                    "net_profit": indicator.net_profit,
                }
            )
        return results
