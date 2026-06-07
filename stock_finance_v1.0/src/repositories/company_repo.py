from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.db.models import Company, Watchlist

# ---- 内存缓存：避免每次搜索都扫全表 ----
_cache: list[dict] | None = None
_cache_by_code: dict[str, dict] | None = None


def _ensure_cache(session: Session) -> None:
    """首次访问时一次性加载全部公司到内存（约 5500 条，<1MB）。"""
    global _cache, _cache_by_code
    if _cache is not None:
        return
    rows = session.scalars(select(Company).order_by(Company.stock_code)).all()
    _cache = [
        {"id": c.id, "stock_code": c.stock_code, "name": c.name or "", "market": c.market or ""}
        for c in rows
    ]
    _cache_by_code = {c["stock_code"]: c for c in _cache}


def _invalidate_cache() -> None:
    """公司数据变更后清除缓存。"""
    global _cache, _cache_by_code
    _cache = None
    _cache_by_code = None


class CompanyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        _ensure_cache(session)

    def get_by_code(self, stock_code: str) -> Company | None:
        code = stock_code.zfill(6)
        # 内存查基本信息，DB 取 ORM 对象（需要时）
        return self._session.scalar(select(Company).where(Company.stock_code == code))

    def count(self, keyword: str = "") -> int:
        keyword = keyword.strip()
        if not keyword:
            return len(_cache)
        kw = keyword.lower()
        return sum(
            1 for c in _cache
            if kw in c["stock_code"] or kw in c["name"].lower()
        )

    def search(
        self,
        keyword: str = "",
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Company]:
        keyword = keyword.strip()
        if keyword:
            kw = keyword.lower()
            filtered = [
                c for c in _cache
                if kw in c["stock_code"] or kw in c["name"].lower()
            ]
        else:
            filtered = _cache[:]

        ids = [c["id"] for c in filtered[offset:offset + limit]]
        if not ids:
            return []
        # 批量取 ORM 对象（保持返回类型不变）
        companies = list(
            self._session.scalars(
                select(Company)
                .where(Company.id.in_(ids))
                .order_by(Company.stock_code)
            ).all()
        )
        return companies

    def watchlist_ids(self) -> set[int]:
        return set(self._session.scalars(select(Watchlist.company_id)).all())

    def watchlist(self) -> list[Company]:
        return list(
            self._session.scalars(
                select(Company)
                .join(Watchlist, Watchlist.company_id == Company.id)
                .order_by(Company.stock_code)
            ).all()
        )

    def add_watchlist(self, company: Company) -> None:
        exists = self._session.scalar(
            select(Watchlist).where(Watchlist.company_id == company.id)
        )
        if not exists:
            self._session.add(Watchlist(company_id=company.id))

    def remove_watchlist(self, company: Company) -> None:
        entry = self._session.scalar(
            select(Watchlist).where(Watchlist.company_id == company.id)
        )
        if entry:
            self._session.delete(entry)

    def is_watchlisted(self, company: Company) -> bool:
        return (
            self._session.scalar(
                select(Watchlist).where(Watchlist.company_id == company.id)
            )
            is not None
        )
