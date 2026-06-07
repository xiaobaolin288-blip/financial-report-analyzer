from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.db.models import Company, FinancialIndicator, FinancialReport


class IndicatorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def series_for_company(
        self,
        stock_code: str,
        *,
        report_type: str | None = None,
        years: int | None = None,
    ) -> list[tuple[FinancialReport, FinancialIndicator]]:
        company = self._session.scalar(
            select(Company).where(Company.stock_code == stock_code.zfill(6))
        )
        if not company:
            return []

        stmt = (
            select(FinancialReport, FinancialIndicator)
            .join(FinancialIndicator, FinancialIndicator.report_id == FinancialReport.id)
            .where(FinancialReport.company_id == company.id)
            .order_by(FinancialReport.report_period)
        )
        if report_type:
            stmt = stmt.where(FinancialReport.report_type == report_type)

        rows = list(self._session.execute(stmt).all())
        if years and rows:
            latest = rows[-1][0].report_period
            cutoff_year = latest.year - years + 1
            rows = [(r, i) for r, i in rows if r.report_period.year >= cutoff_year]
        return rows

    def latest_snapshot(self, stock_codes: list[str], report_type: str = "annual") -> list[dict]:
        result: list[dict] = []
        for code in stock_codes:
            company = self._session.scalar(
                select(Company).where(Company.stock_code == code.zfill(6))
            )
            if not company:
                continue
            report = self._session.scalar(
                select(FinancialReport)
                .options(joinedload(FinancialReport.indicator))
                .where(
                    FinancialReport.company_id == company.id,
                    FinancialReport.report_type == report_type,
                )
                .order_by(FinancialReport.report_period.desc())
                .limit(1)
            )
            if not report or not report.indicator:
                continue
            ind = report.indicator
            result.append(
                {
                    "stock_code": company.stock_code,
                    "name": company.name,
                    "report_period": report.report_period.isoformat(),
                    "revenue": ind.revenue,
                    "net_profit": ind.net_profit,
                    "roe": ind.roe,
                    "gross_profit_margin": ind.gross_profit_margin,
                    "debt_asset_ratio": ind.debt_asset_ratio,
                    "eps": ind.eps,
                }
            )
        return result

    def distinct_periods(self, stock_code: str) -> list[date]:
        company = self._session.scalar(
            select(Company).where(Company.stock_code == stock_code.zfill(6))
        )
        if not company:
            return []
        return list(
            self._session.scalars(
                select(FinancialReport.report_period)
                .where(FinancialReport.company_id == company.id)
                .order_by(FinancialReport.report_period)
            ).all()
        )
