#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import akshare as ak
import pandas as pd

from quantum_trade.calendar import normalize_trade_date
from quantum_trade.io import ensure_dir
from quantum_trade.paths import LOG_DIR, RAW_DIR

FIELD_MAP = {
    "日期": "trade_date",
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

PREFERRED_COLUMNS = [
    "trade_date",
    "symbol",
    "name",
    "open",
    "high",
    "low",
    "close",
    "pct_chg",
    "chg",
    "volume",
    "amount",
    "turnover_rate",
    "amplitude",
    "outstanding_share",
    "turnover",
]

EMPTY_COLUMNS = ["trade_date", "symbol", "name", "open", "high", "low", "close"]


@dataclass(frozen=True)
class StockInfo:
    symbol: str
    name: str


@dataclass(frozen=True)
class FetchResult:
    symbol: str
    name: str
    status: str
    rows: int
    error: str = ""
    df: pd.DataFrame | None = None


def _fetch_stock_codes(limit: int | None) -> list[StockInfo]:
    # Use exchange official code lists instead of Eastmoney spot list, because the
    # Eastmoney spot endpoint can be unstable in some network environments. BSE can
    # be added later once its upstream endpoint is stable enough for this project.
    sh = ak.stock_info_sh_name_code().rename(columns={"证券代码": "symbol", "证券简称": "name"})
    sz = ak.stock_info_sz_name_code().rename(columns={"A股代码": "symbol", "A股简称": "name"})
    codes = pd.concat([sh[["symbol", "name"]], sz[["symbol", "name"]]], ignore_index=True)
    codes["symbol"] = codes["symbol"].astype(str).str.zfill(6)
    codes["name"] = codes["name"].astype(str)
    codes = codes.drop_duplicates(subset=["symbol"]).sort_values("symbol").reset_index(drop=True)
    if limit is not None:
        codes = codes.head(limit)
    return [StockInfo(symbol=row.symbol, name=row.name) for row in codes.itertuples(index=False)]


def _to_sina_symbol(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _normalize_stock_df(df: pd.DataFrame, stock: StockInfo, trade_date: str) -> pd.DataFrame:
    df = df.rename(columns=FIELD_MAP)
    if "date" in df.columns:
        df = df.drop(columns=["date"])
    df["trade_date"] = trade_date
    df["symbol"] = stock.symbol
    df["name"] = stock.name

    existing = [col for col in PREFERRED_COLUMNS if col in df.columns]
    remaining = [col for col in df.columns if col not in existing]
    return df[existing + remaining]


def _fetch_one_stock(stock: StockInfo, trade_date: str) -> FetchResult:
    try:
        # Sina historical daily API is currently more reachable from this environment
        # than Eastmoney's kline endpoint. It returns a strict date range for one stock.
        df = ak.stock_zh_a_daily(
            symbol=_to_sina_symbol(stock.symbol),
            start_date=trade_date,
            end_date=trade_date,
            adjust="",
        )
    except Exception as exc:
        return FetchResult(stock.symbol, stock.name, "error", 0, str(exc))

    if df.empty:
        return FetchResult(stock.symbol, stock.name, "empty", 0)

    df = _normalize_stock_df(df, stock, trade_date)
    return FetchResult(stock.symbol, stock.name, "ok", len(df), df=df)


def _partition_dir(trade_date: str) -> Path:
    return RAW_DIR / "stock_daily" / f"trade_date={trade_date}"


def _parts_dir(trade_date: str) -> Path:
    return _partition_dir(trade_date) / "_parts"


def _manifest_path(trade_date: str) -> Path:
    return _partition_dir(trade_date) / "_manifest.csv"


def _load_done_symbols(trade_date: str) -> set[str]:
    path = _manifest_path(trade_date)
    if not path.exists():
        return set()

    done: set[str] = set()
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status") in {"ok", "empty"}:
                done.add(row["symbol"])
    return done


def _append_manifest(trade_date: str, results: list[FetchResult]) -> None:
    path = _manifest_path(trade_date)
    ensure_dir(path.parent)
    exists = path.exists()
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name", "status", "rows", "error"])
        if not exists:
            writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "symbol": result.symbol,
                    "name": result.name,
                    "status": result.status,
                    "rows": result.rows,
                    "error": result.error,
                }
            )


def _write_failure_log(trade_date: str, results: list[FetchResult]) -> None:
    failures = [result for result in results if result.status == "error"]
    if not failures:
        return

    ensure_dir(LOG_DIR)
    path = LOG_DIR / f"fetch_stock_daily_{trade_date}_failed.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name", "status", "rows", "error"])
        writer.writeheader()
        for result in failures:
            writer.writerow(
                {
                    "symbol": result.symbol,
                    "name": result.name,
                    "status": result.status,
                    "rows": result.rows,
                    "error": result.error,
                }
            )
    print(f"wrote failure log to {path}", flush=True)


def _write_batch(trade_date: str, batch_index: int, results: list[FetchResult]) -> Path | None:
    frames = [result.df for result in results if result.df is not None and not result.df.empty]
    if not frames:
        _append_manifest(trade_date, results)
        return None

    part_dir = _parts_dir(trade_date)
    ensure_dir(part_dir)
    out_file = part_dir / f"part-{batch_index:05d}.parquet"
    df = pd.concat(frames, ignore_index=True)
    df.to_parquet(out_file, index=False)
    _append_manifest(trade_date, results)
    return out_file


def _write_final_file(trade_date: str) -> Path:
    part_dir = _parts_dir(trade_date)
    out_file = _partition_dir(trade_date) / "part.parquet"
    ensure_dir(out_file.parent)

    part_files = sorted(part_dir.glob("part-*.parquet"))
    if not part_files:
        pd.DataFrame(columns=EMPTY_COLUMNS).to_parquet(out_file, index=False)
        return out_file

    df = pd.concat((pd.read_parquet(path) for path in part_files), ignore_index=True)
    df = df.drop_duplicates(subset=["trade_date", "symbol"], keep="last")
    df = df.sort_values("symbol").reset_index(drop=True)
    df.to_parquet(out_file, index=False)
    return out_file


def fetch_stock_daily(
    trade_date: str,
    limit: int | None = None,
    batch_size: int = 100,
    workers: int = 1,
    resume: bool = True,
) -> pd.DataFrame:
    stocks = _fetch_stock_codes(limit)
    done_symbols = _load_done_symbols(trade_date) if resume else set()
    pending = [stock for stock in stocks if stock.symbol not in done_symbols]
    total = len(stocks)

    print(
        f"stocks={total}, done={len(done_symbols)}, pending={len(pending)}, "
        f"workers={workers}, batch_size={batch_size}",
        flush=True,
    )

    if workers != 1:
        print(
            "warning: AkShare/Sina daily fetch is not thread-safe in this environment; "
            "running sequentially with workers=1",
            flush=True,
        )

    if not pending:
        out_file = _write_final_file(trade_date)
        print(f"nothing to fetch; final file is {out_file}", flush=True)
        return pd.read_parquet(out_file)

    completed = len(done_symbols)
    batch_index = len(list(_parts_dir(trade_date).glob("part-*.parquet"))) + 1
    batch_results: list[FetchResult] = []
    all_results: list[FetchResult] = []

    for stock in pending:
        result = _fetch_one_stock(stock, trade_date)
        completed += 1
        batch_results.append(result)
        all_results.append(result)

        if completed % 100 == 0 or completed == total:
            ok_count = sum(1 for item in all_results if item.status == "ok")
            error_count = sum(1 for item in all_results if item.status == "error")
            print(f"processed {completed}/{total}, new_ok={ok_count}, new_errors={error_count}", flush=True)

        if len(batch_results) >= batch_size:
            part_file = _write_batch(trade_date, batch_index, batch_results)
            if part_file is not None:
                print(f"wrote batch {batch_index} to {part_file}", flush=True)
            batch_index += 1
            batch_results = []

    if batch_results:
        part_file = _write_batch(trade_date, batch_index, batch_results)
        if part_file is not None:
            print(f"wrote batch {batch_index} to {part_file}", flush=True)

    _write_failure_log(trade_date, all_results)
    out_file = _write_final_file(trade_date)
    print(f"wrote final file to {out_file}", flush=True)
    return pd.read_parquet(out_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch A-share stock daily historical data for one trade date.")
    parser.add_argument("--date", dest="trade_date", help="Trade date, YYYYMMDD or YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--limit", type=int, help="Optional stock limit for quick smoke tests.")
    parser.add_argument("--batch-size", type=int, default=100, help="Rows to write per checkpoint batch. Defaults to 100.")
    parser.add_argument("--workers", type=int, default=1, help="Reserved for future use. Current Sina fetch runs sequentially.")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing manifest and refetch all selected stocks.")
    args = parser.parse_args()

    trade_date = normalize_trade_date(args.trade_date)
    df = fetch_stock_daily(
        trade_date,
        limit=args.limit,
        batch_size=args.batch_size,
        workers=args.workers,
        resume=not args.no_resume,
    )
    print(f"wrote {len(df)} rows to {_partition_dir(trade_date) / 'part.parquet'}")


if __name__ == "__main__":
    main()
