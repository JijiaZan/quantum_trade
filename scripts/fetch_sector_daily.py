#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import akshare as ak
import pandas as pd

from quantum_trade.calendar import normalize_trade_date
from quantum_trade.io import write_partitioned_parquet
from quantum_trade.paths import RAW_DIR

FIELD_MAP = {
    "排名": "rank",
    "板块名称": "sector_name",
    "板块代码": "sector_code",
    "最新价": "close",
    "涨跌额": "chg",
    "涨跌幅": "pct_chg",
    "总市值": "total_market_cap",
    "换手率": "turnover_rate",
    "上涨家数": "up_count",
    "下跌家数": "down_count",
    "领涨股票": "leading_stock",
    "领涨股票-涨跌幅": "leading_stock_pct_chg",
}


def _normalize(df: pd.DataFrame, trade_date: str, sector_type: str) -> pd.DataFrame:
    df = df.rename(columns=FIELD_MAP)
    df["trade_date"] = trade_date
    df["sector_type"] = sector_type
    preferred = [
        "trade_date",
        "sector_type",
        "sector_code",
        "sector_name",
        "close",
        "pct_chg",
        "chg",
        "turnover_rate",
        "total_market_cap",
        "up_count",
        "down_count",
        "leading_stock",
        "leading_stock_pct_chg",
    ]
    existing = [col for col in preferred if col in df.columns]
    remaining = [col for col in df.columns if col not in existing]
    return df[existing + remaining]


def fetch_sector_daily(trade_date: str) -> pd.DataFrame:
    industry = _normalize(ak.stock_board_industry_name_em(), trade_date, "industry")
    concept = _normalize(ak.stock_board_concept_name_em(), trade_date, "concept")
    return pd.concat([industry, concept], ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch A-share industry and concept board daily snapshot data.")
    parser.add_argument("--date", dest="trade_date", help="Trade date, YYYYMMDD or YYYY-MM-DD. Defaults to today.")
    args = parser.parse_args()

    trade_date = normalize_trade_date(args.trade_date)
    df = fetch_sector_daily(trade_date)
    out_file = write_partitioned_parquet(df, RAW_DIR / "sector_daily", trade_date)
    print(f"wrote {len(df)} rows to {out_file}")


if __name__ == "__main__":
    main()
