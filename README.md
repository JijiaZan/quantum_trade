# Quantum Trade

A small local data project for quantitative trading research.

The first milestone is to collect daily A-share stock, industry board, and concept board data, store the raw snapshots as Parquet files, and query them locally with DuckDB.

## Why Parquet + DuckDB

- Parquet stores large table-like market data compactly and preserves column types.
- DuckDB lets you query local Parquet files with SQL without running a database server.
- MySQL/PostgreSQL can be added later for live trading state, orders, users, or strategy task metadata.

## Project layout

```text
quantum_trade/
  calendar.py
  io.py
  paths.py
scripts/
  fetch_stock_daily.py
  fetch_sector_daily.py
  fetch_sector_members.py
  init_db.py
data/
  raw/
    stock_daily/
    sector_daily/
    sector_members/
  processed/
db/
notebooks/
logs/
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Fetch data

Use a real trading date. For example:

```bash
python scripts/fetch_stock_daily.py --date 20260522
python scripts/fetch_sector_daily.py --date 20260522
python scripts/fetch_sector_members.py --date 20260522
```

For a quick smoke test of sector members:

```bash
python scripts/fetch_sector_members.py --date 20260522 --limit 3
```

The files are written to partitioned folders such as:

```text
data/raw/stock_daily/trade_date=20260522/part.parquet
data/raw/sector_daily/trade_date=20260522/part.parquet
data/raw/sector_members/trade_date=20260522/part.parquet
```

## Initialize DuckDB views

After data files exist:

```bash
python scripts/init_db.py
```

Then query with DuckDB:

```sql
SELECT *
FROM stock_daily
WHERE trade_date = '20260522'
ORDER BY pct_chg DESC
LIMIT 20;
```

Or directly query Parquet without creating a database file:

```sql
SELECT *
FROM read_parquet('data/raw/stock_daily/**/*.parquet', union_by_name = true, hive_partitioning = true)
LIMIT 10;
```

## Notes

- The current data fetchers use AkShare and Eastmoney public endpoints.
- Market data should be fetched on trading days after market close.
- Raw and processed data files are intentionally ignored by git.
