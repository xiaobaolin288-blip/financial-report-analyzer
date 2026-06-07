from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    market: Mapped[str | None] = mapped_column(String(8), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    list_status: Mapped[str] = mapped_column(String(16), default="listed")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reports: Mapped[list[FinancialReport]] = relationship(back_populates="company", cascade="all, delete-orphan")
    watchlist_entries: Mapped[list[Watchlist]] = relationship(back_populates="company", cascade="all, delete-orphan")


class FinancialReport(Base):
    __tablename__ = "financial_report"
    __table_args__ = (UniqueConstraint("company_id", "report_period", "report_type", name="uq_report"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"), index=True)
    report_period: Mapped[date] = mapped_column(Date, index=True)
    report_type: Mapped[str] = mapped_column(String(16), default="annual")
    disclose_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    company: Mapped[Company] = relationship(back_populates="reports")
    indicator: Mapped[FinancialIndicator | None] = relationship(
        back_populates="report", uselist=False, cascade="all, delete-orphan"
    )


class FinancialIndicator(Base):
    """主要财务指标（宽表，金额单位：元）。"""

    __tablename__ = "financial_indicator"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("financial_report.id"), unique=True)

    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_profit_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_asset_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)

    report: Mapped[FinancialReport] = relationship(back_populates="indicator")


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("company_id", name="uq_watchlist_company"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("company.id"))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped[Company] = relationship(back_populates="watchlist_entries")


class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    scope: Mapped[str] = mapped_column(String(32))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_count: Mapped[int] = mapped_column(Integer, default=0)
