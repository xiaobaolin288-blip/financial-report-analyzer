from __future__ import annotations

import re
import time
from datetime import date, datetime

import pandas as pd

from src.providers.base import CompanyDTO, FinancialDataProvider, IndicatorRowDTO

# 列名别名 -> 标准字段
_COLUMN_ALIASES: dict[str, list[str]] = {
    "report_period": ["报告期", "报告日期", "截止日期"],
    "revenue": ["营业总收入", "营业收入", "主营业务收入"],
    "net_profit": ["净利润", "归属于母公司所有者的净利润", "归母净利润"],
    "gross_profit_margin": ["销售毛利率", "毛利率", "主营毛利率"],
    "roe": ["净资产收益率", "加权净资产收益率", "ROE"],
    "debt_asset_ratio": ["资产负债率"],
    "eps": ["基本每股收益", "每股收益", "EPS"],
    "bps": ["每股净资产", "BPS"],
    "operating_cash_flow": [
        "经营活动产生的现金流量净额",
        "经营活动现金流量净额",
    ],
}


def _pick_column(df: pd.DataFrame, field: str) -> str | None:
    for name in _COLUMN_ALIASES.get(field, []):
        if name in df.columns:
            return name
    return None


def _to_float(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "-", "--", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_period(raw) -> date | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, date):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10].replace("/", "-"), fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _report_type_from_period(period: date) -> str:
    if period.month == 12 and period.day == 31:
        return "annual"
    return "quarterly"


def _normalize_stock_code(raw) -> str | None:
    text = str(raw).strip()
    if text.lower() in ("", "nan", "none", "null"):
        return None
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 4:
        return None
    return digits.zfill(6)[-6:]


def _market_from_code(code: str) -> str:
    if code.startswith(("6", "5")):
        return "SH"
    if code.startswith(("0", "3")):
        return "SZ"
    if code.startswith(("8", "4")):
        return "BJ"
    return ""


def _normalize_indicator_df(df: pd.DataFrame) -> list[IndicatorRowDTO]:
    period_col = _pick_column(df, "report_period")
    if not period_col:
        return []

    rows: list[IndicatorRowDTO] = []
    col_map = {field: _pick_column(df, field) for field in _COLUMN_ALIASES if field != "report_period"}

    for _, record in df.iterrows():
        period = _parse_period(record.get(period_col))
        if not period:
            continue
        rows.append(
            IndicatorRowDTO(
                report_period=period,
                report_type=_report_type_from_period(period),
                revenue=_to_float(record.get(col_map["revenue"])) if col_map.get("revenue") else None,
                net_profit=_to_float(record.get(col_map["net_profit"])) if col_map.get("net_profit") else None,
                gross_profit_margin=_to_float(record.get(col_map["gross_profit_margin"]))
                if col_map.get("gross_profit_margin")
                else None,
                roe=_to_float(record.get(col_map["roe"])) if col_map.get("roe") else None,
                debt_asset_ratio=_to_float(record.get(col_map["debt_asset_ratio"]))
                if col_map.get("debt_asset_ratio")
                else None,
                eps=_to_float(record.get(col_map["eps"])) if col_map.get("eps") else None,
                bps=_to_float(record.get(col_map["bps"])) if col_map.get("bps") else None,
                operating_cash_flow=_to_float(record.get(col_map["operating_cash_flow"]))
                if col_map.get("operating_cash_flow")
                else None,
            )
        )
    rows.sort(key=lambda r: r.report_period)
    return rows


class AkshareProvider(FinancialDataProvider):
    def __init__(self, request_interval_sec: float = 0.3) -> None:
        self._interval = request_interval_sec

    def _sleep(self) -> None:
        if self._interval > 0:
            time.sleep(self._interval)

    def fetch_company_list(self) -> list[CompanyDTO]:
        import akshare as ak

        self._sleep()
        df = ak.stock_info_a_code_name()
        code_col = "code" if "code" in df.columns else df.columns[0]
        name_col = "name" if "name" in df.columns else df.columns[1]

        companies: list[CompanyDTO] = []
        for _, row in df.iterrows():
            code = _normalize_stock_code(row[code_col])
            if not code:
                continue
            name = str(row[name_col]).strip()
            if name.lower() in ("nan", "none"):
                name = code
            companies.append(CompanyDTO(stock_code=code, name=name, market=_market_from_code(code)))
        return companies

    def fetch_indicators(self, stock_code: str) -> list[IndicatorRowDTO]:
        import akshare as ak

        code = stock_code.strip().zfill(6)
        errors: list[str] = []

        for fetcher in (
            lambda: ak.stock_financial_analysis_indicator(symbol=code),
            lambda: ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期"),
        ):
            try:
                self._sleep()
                df = fetcher()
                if df is not None and not df.empty:
                    rows = _normalize_indicator_df(df)
                    if rows:
                        return rows
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        if errors:
            raise RuntimeError(f"获取 {code} 财务指标失败: {'; '.join(errors[:2])}")
        return []
