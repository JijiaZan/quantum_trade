#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
    "换手率": "turnover_rate",
    "市盈率-动态": "pe_dynamic",
    "市净率": "pb",
}


def _fetch_board_members(
    boards: pd.DataFrame,
    sector_type: str,
    member_func: Callable[..., pd.DataFrame],
    trade_date: str,
    limit: int | None,
) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    board_names = boards["板块名称"].dropna().astype(str).tolist()
    if limit is not None:
        board_names = board_names[:limit]

    for sector_name in board_names:
        try:
            members = member_func(symbol=sector_name)
        except Exception as exc:  # keep one broken board from failing the whole job
            print(f"skip {sector_type} {sector_name}: {exc}")
            continue

        if members.empty:
            continue

        members = members.rename(columns=FIELD_MAP)
        members["trade_date"] = trade_date
        members["sector_type"] = sector_type
        members["sector_name"] = sector_name
        frames.append(members)

    return frames


def fetch_sector_members(trade_date: str, limit: int | None = None) -> pd.DataFrame:
    industry_boards = ak.stock_board_industry_name_em()
    concept_boards = ak.stock_board_concept_name_em()

    frames = []
    frames.extend(_fetch_board_members(industry_boards, "industry", ak.stock_board_industry_cons_em, trade_date, limit))
    frames.extend(_fetch_board_members(concept_boards, "concept", ak.stock_board_concept_cons_em, trade_date, limit))

    if not frames:
        return pd.DataFrame(columns=["trade_date", "sector_type", "sector_name", "symbol", "name"])

    df = pd.concat(frames, ignore_index=True)
    preferred = ["trade_date", "sector_type", "sector_name", "symbol", "name", "open", "high", "low", "close", "pre_close", "pct_chg", "chg", "volume", "amount", "turnover_rate"]
    existing = [col for col in preferred if col in df.columns]
    remaining = [col for col in df.columns if col not in existing]
    return df[existing + remaining]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch A-share industry and concept board constituent stocks.")
    parser.add_argument("--date", dest="trade_date", help="Trade date, YYYYMMDD or YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--limit", type=int, help="Optional board limit for quick smoke tests.")
    args = parser.parse_args()

    trade_date = normalize_trade_date(args.trade_date)
    df = fetch_sector_members(trade_date, args.limit)
    out_file = write_partitioned_parquet(df, RAW_DIR / "sector_members", trade_date)
    print(f"wrote {len(df)} rows to {out_file}")


if __name__ == "__main__":
    main()
