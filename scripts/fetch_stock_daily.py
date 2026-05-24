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
    "代码": "symbol",
    "名称": "name",
    "日期": "trade_date",
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
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_chg",
    "涨跌额": "chg",
    "换手率": "turnover_rate",
}


def _fetch_stock_codes(limit: int | None) -> pd.DataFrame:
    # Use exchange official code lists instead of Eastmoney spot list, because the
    # spot endpoint can be unstable in some network environments. BSE can be added
    # later once its upstream endpoint is stable enough for this project.
    sh = ak.stock_info_sh_name_code().rename(columns={"证券代码": "symbol", "证券简称": "name"})
    sz = ak.stock_info_sz_name_code().rename(columns={"A股代码": "symbol", "A股简称": "name"})
    codes = pd.concat([sh[["symbol", "name"]], sz[["symbol", "name"]]], ignore_index=True)
    if "symbol" not in codes.columns:
        raise RuntimeError(f"Unexpected stock code columns: {list(codes.columns)}")
    codes["symbol"] = codes["symbol"].astype(str).str.zfill(6)
    if limit is not None:
        codes = codes.head(limit)
    return codes


def _to_sina_symbol(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _fetch_one_stock(symbol: str, trade_date: str) -> pd.DataFrame:
    # Sina historical daily API is currently more reachable from this environment
    # than Eastmoney's kline endpoint. It returns a strict date range for one stock.
    df = ak.stock_zh_a_daily(
        symbol=_to_sina_symbol(symbol),
        start_date=trade_date,
        end_date=trade_date,
        adjust="",
    )
    if df.empty:
        return df

    df = df.rename(columns=FIELD_MAP)
    if "date" in df.columns:
        df = df.drop(columns=["date"])
    df["trade_date"] = trade_date
    df["symbol"] = symbol
    return df


def fetch_stock_daily(trade_date: str, limit: int | None = None) -> pd.DataFrame:
    codes = _fetch_stock_codes(limit)
    frames: list[pd.DataFrame] = []
    total = len(codes)

    for idx, row in codes.iterrows():
        symbol = row["symbol"]
        name = row.get("name")
        try:
            df = _fetch_one_stock(symbol, trade_date)
        except Exception as exc:
            print(f"skip {symbol}: {exc}", flush=True)
            continue

        if df.empty:
            continue

        df["name"] = name
        frames.append(df)

        if (idx + 1) % 100 == 0 or (idx + 1) == total:
            print(f"processed {idx + 1}/{total}, rows={len(frames)}", flush=True)

    if not frames:
        return pd.DataFrame(columns=["trade_date", "symbol", "name", "open", "high", "low", "close"])

    df = pd.concat(frames, ignore_index=True)

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
    parser = argparse.ArgumentParser(description="Fetch A-share stock daily historical data for one trade date.")
    parser.add_argument("--date", dest="trade_date", help="Trade date, YYYYMMDD or YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--limit", type=int, help="Optional stock limit for quick smoke tests.")
    args = parser.parse_args()

    trade_date = normalize_trade_date(args.trade_date)
    df = fetch_stock_daily(trade_date, args.limit)
    out_file = write_partitioned_parquet(df, RAW_DIR / "stock_daily", trade_date)
    print(f"wrote {len(df)} rows to {out_file}")


if __name__ == "__main__":
    main()
