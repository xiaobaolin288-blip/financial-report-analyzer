from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

COMPANY_LIST_BATCH = 200

from src.db.models import Company, FinancialIndicator, FinancialReport, SyncLog, Watchlist
from src.providers import get_provider
from src.providers.base import CompanyDTO, IndicatorRowDTO


class SyncScope(str, Enum):
    CURRENT = "current"
    WATCHLIST = "watchlist"
    ALL = "all"
    CODES = "codes"


@dataclass
class SyncProgress:
    current: int
    total: int
    stock_code: str
    message: str


ProgressCallback = Callable[[SyncProgress], None]


def _scope_key(scope: SyncScope | str) -> str:
    """QComboBox 可能把 SyncScope 存成 str，统一转成 scope 字符串。"""
    if isinstance(scope, SyncScope):
        return scope.value
    return str(scope)


class SyncService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._provider = get_provider()

    def sync(
        self,
        scope: SyncScope | str,
        *,
        stock_codes: list[str] | None = None,
        current_code: str | None = None,
        include_company_list: bool = False,
        progress: ProgressCallback | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> SyncLog:
        scope_key = _scope_key(scope)
        log = SyncLog(scope=scope_key, status="running", started_at=datetime.utcnow())
        self._session.add(log)
        self._session.flush()

        company_list_count = 0
        try:
            if include_company_list or scope_key == SyncScope.ALL.value:
                company_list_count = self._sync_company_list(progress, cancel_check)

            codes = self._resolve_codes(scope, stock_codes, current_code)
            total = len(codes)
            count = 0

            for idx, code in enumerate(codes, start=1):
                if cancel_check and cancel_check():
                    log.status = "cancelled"
                    log.message = "用户取消同步"
                    break
                if progress:
                    progress(
                        SyncProgress(
                            current=idx,
                            total=total,
                            stock_code=code,
                            message=f"正在同步 {code}",
                        )
                    )
                count += self._sync_one_company(code)
            else:
                log.status = "success"
                if total > 0:
                    log.message = f"同步完成，财务数据 {total} 家"
                elif company_list_count > 0:
                    log.message = f"公司列表已更新，共 {company_list_count} 家"
                else:
                    log.message = "同步完成（无待更新项）"

            log.records_count = count + company_list_count
        except Exception as exc:  # noqa: BLE001
            log.status = "failed"
            log.message = str(exc)
            logger.exception("同步失败 scope=%s", scope_key)
            raise
        finally:
            log.finished_at = datetime.utcnow()
            self._session.flush()

        return log

    def _resolve_codes(
        self,
        scope: SyncScope | str,
        stock_codes: list[str] | None,
        current_code: str | None,
    ) -> list[str]:
        scope_key = _scope_key(scope)
        if scope_key == SyncScope.CODES.value and stock_codes:
            return [c.zfill(6) for c in stock_codes]
        if scope_key == SyncScope.CURRENT.value and current_code:
            return [current_code.zfill(6)]
        if scope_key == SyncScope.WATCHLIST.value:
            rows = self._session.scalars(
                select(Company.stock_code)
                .join(Watchlist, Watchlist.company_id == Company.id)
                .order_by(Company.stock_code)
            ).all()
            return list(rows)
        if scope_key == SyncScope.ALL.value:
            return list(self._session.scalars(select(Company.stock_code).order_by(Company.stock_code)).all())
        return []

    def _sync_company_list(
        self,
        progress: ProgressCallback | None,
        cancel_check: Callable[[], bool] | None,
    ) -> int:
        if progress:
            progress(
                SyncProgress(current=0, total=0, stock_code="", message="正在从外网拉取 A 股公司列表…")
            )
        companies = self._provider.fetch_company_list()
        total = len(companies)
        logger.info("拉取到公司 %s 家", total)
        saved = 0

        for idx, dto in enumerate(companies, start=1):
            if cancel_check and cancel_check():
                logger.info("公司列表同步已取消，已写入 %s 家", saved)
                return saved
            self._upsert_company(dto)
            saved += 1

            if idx % COMPANY_LIST_BATCH == 0:
                self._session.flush()
                logger.debug("公司列表已写入缓存 %s/%s", idx, total)

            if progress and (idx % 100 == 0 or idx == total):
                progress(
                    SyncProgress(
                        current=idx,
                        total=total,
                        stock_code=dto.stock_code,
                        message=f"写入公司库 {idx}/{total}",
                    )
                )

        self._session.flush()
        logger.info("公司列表同步完成，共 %s 家", saved)
        return saved

    def _sync_one_company(self, stock_code: str) -> int:
        company = self._get_or_create_company(stock_code)
        rows = self._provider.fetch_indicators(stock_code)
        saved = 0
        for row in rows:
            self._upsert_indicator(company.id, row)
            saved += 1
        return saved

    def _get_or_create_company(self, stock_code: str) -> Company:
        code = stock_code.zfill(6)
        company = self._session.scalar(select(Company).where(Company.stock_code == code))
        if company:
            return company
        company = Company(stock_code=code, name=code, market=_market(code))
        self._session.add(company)
        self._session.flush()
        return company

    def _upsert_company(self, dto: CompanyDTO) -> Company:
        company = self._session.scalar(select(Company).where(Company.stock_code == dto.stock_code))
        if company:
            company.name = dto.name
            if dto.market:
                company.market = dto.market
        else:
            company = Company(
                stock_code=dto.stock_code,
                name=dto.name,
                market=dto.market or _market(dto.stock_code),
            )
            self._session.add(company)
        return company

    def _upsert_indicator(self, company_id: int, row: IndicatorRowDTO) -> None:
        report = self._session.scalar(
            select(FinancialReport).where(
                FinancialReport.company_id == company_id,
                FinancialReport.report_period == row.report_period,
                FinancialReport.report_type == row.report_type,
            )
        )
        if not report:
            report = FinancialReport(
                company_id=company_id,
                report_period=row.report_period,
                report_type=row.report_type,
            )
            self._session.add(report)
            self._session.flush()

        indicator = report.indicator
        if not indicator:
            indicator = FinancialIndicator(report_id=report.id)
            self._session.add(indicator)

        indicator.revenue = row.revenue
        indicator.net_profit = row.net_profit
        indicator.gross_profit_margin = row.gross_profit_margin
        indicator.roe = row.roe
        indicator.debt_asset_ratio = row.debt_asset_ratio
        indicator.eps = row.eps
        indicator.bps = row.bps
        indicator.operating_cash_flow = row.operating_cash_flow


def _market(code: str) -> str:
    if code.startswith(("6", "5")):
        return "SH"
    if code.startswith(("0", "3")):
        return "SZ"
    if code.startswith(("8", "4")):
        return "BJ"
    return ""
