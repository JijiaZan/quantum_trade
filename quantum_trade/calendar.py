from __future__ import annotations

from datetime import date, datetime


def normalize_trade_date(value: str | None) -> str:
    """Normalize YYYYMMDD / YYYY-MM-DD / None into YYYYMMDD."""
    if value is None:
        return date.today().strftime("%Y%m%d")

    raw = value.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y%m%d")
        except ValueError:
            pass

    raise ValueError(f"Invalid trade date: {value!r}. Use YYYYMMDD or YYYY-MM-DD.")
