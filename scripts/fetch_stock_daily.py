#!/usr/bin/env python3
from __future__ import annotations

import argparse

import akshare as ak
import pandas as pd

from quantum_trade.calendar import normalize_trade_date
from quantum_trade.io import write_partitioned_parquet
from quantum_trade.paths import RAW_DIR

FIELD_MAP = {
    "代码": "symbol",
    "名称": "name",
    "最新价": "close",
    "涨跌幅": "pct_chg",
    "涨跌额": "chg",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "最高": "high",
    "最低": "low",
    "今开": "open",
    "昨收": "pre_close",
    "量比": "volume_ratio",
    "换手率": "turnover_rate",
    "市盈率-动态": "pe_dynamic",
    "市净率": "pb",
    "总市值": "total_market_cap",
    "流通市值": "float_market_cap",
    "涨速": "rise_speed",
    "5分钟涨跌": "pct_chg_5m",
    "60日涨跌幅": "pct_chg_60d",
    "年初至今涨跌幅": "pct_chg_ytd",
}


def fetch_stock_daily(trade_date: str) -> pd.DataFrame:
    # Eastmoney spot API returns latest daily snapshot for all A-share stocks.
    # trade_date is attached by this project so downstream files are partitioned consistently.
    df = ak.stock_zh_a_spot_em()
    df = df.rename(columns=FIELD_MAP)
    df["trade_date"] = trade_date

    preferred = [
        "trade_date",
        "symbol",
        "name",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "pct_chg",
        "chg",
        "volume",
        "amount",
        "turnover_rate",
        "amplitude",
        "volume_ratio",
        "pe_dynamic",
        "pb",
        "total_market_cap",
        "float_market_cap",
    ]
    existing = [col for col in preferred if col in df.columns]
    remaining = [col for col in df.columns if col not in existing]
    return df[existing + remaining]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch A-share stock daily snapshot data.")
    parser.add_argument("--date", dest="trade_date", help="Trade date, YYYYMMDD or YYYY-MM-DD. Defaults to today.")
    args = parser.parse_args()

    trade_date = normalize_trade_date(args.trade_date)
    df = fetch_stock_daily(trade_date)
    out_file = write_partitioned_parquet(df, RAW_DIR / "stock_daily", trade_date)
    print(f"wrote {len(df)} rows to {out_file}")


if __name__ == "__main__":
    main()
