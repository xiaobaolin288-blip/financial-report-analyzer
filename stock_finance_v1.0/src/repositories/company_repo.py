from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.db.models import Company, Watchlist


class CompanyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_code(self, stock_code: str) -> Company | None:
        return self._session.scalar(
            select(Company).where(Company.stock_code == stock_code.zfill(6))
        )

    def count(self, keyword: str = "") -> int:
        stmt = select(func.count()).select_from(Company)
        keyword = keyword.strip()
        if keyword:
            stmt = stmt.where(
                or_(
                    Company.stock_code.contains(keyword),
                    Company.name.contains(keyword),
                )
            )
        return int(self._session.scalar(stmt) or 0)

    def search(
        self,
        keyword: str = "",
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Company]:
        stmt = select(Company).order_by(Company.stock_code)
        keyword = keyword.strip()
        if keyword:
            stmt = stmt.where(
                or_(
                    Company.stock_code.contains(keyword),
                    Company.name.contains(keyword),
                )
            )
        stmt = stmt.limit(limit).offset(offset)
        return list(self._session.scalars(stmt).all())

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
        entry = self._session.scalar(select(Watchlist).where(Watchlist.company_id == company.id))
        if entry:
            self._session.delete(entry)

    def is_watchlisted(self, company: Company) -> bool:
        return (
            self._session.scalar(select(Watchlist).where(Watchlist.company_id == company.id))
            is not None
        )
