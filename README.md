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

`fetch_stock_daily.py` supports resumable full-market fetching. It writes checkpoint batches under `_parts/`, records completed symbols in `_manifest.csv`, and writes the final merged file to `part.parquet`.

Useful examples:

```bash
# Quick smoke test
python scripts/fetch_stock_daily.py --date 20260522 --limit 100

# Full沪深A股日线
python scripts/fetch_stock_daily.py --date 20260522

# Smaller checkpoint batches
python scripts/fetch_stock_daily.py --date 20260522 --batch-size 50

# Ignore existing checkpoints and refetch selected stocks
python scripts/fetch_stock_daily.py --date 20260522 --limit 100 --no-resume
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

## View Parquet files

### Option 1: Python / Pandas

```bash
python - <<'PY'
import pandas as pd

path = 'data/raw/stock_daily/trade_date=20260522/part.parquet'
df = pd.read_parquet(path)

print(df.head(20))
print(df.dtypes)
print(df.describe())
PY
```

### Option 2: DuckDB CLI or Python

```bash
python - <<'PY'
import duckdb

path = 'data/raw/stock_daily/trade_date=20260522/part.parquet'
print(duckdb.sql(f"SELECT * FROM '{path}' LIMIT 20").df())
print(duckdb.sql(f"SELECT count(*) AS rows FROM '{path}'").df())
PY
```

You can also query all partition files:

```bash
python - <<'PY'
import duckdb

print(duckdb.sql("""
    SELECT trade_date, count(*) AS rows
    FROM read_parquet('data/raw/stock_daily/**/*.parquet', hive_partitioning = true)
    GROUP BY trade_date
    ORDER BY trade_date
""").df())
PY
```

### Option 3: Convert a small sample to CSV

```bash
python - <<'PY'
import pandas as pd

path = 'data/raw/stock_daily/trade_date=20260522/part.parquet'
df = pd.read_parquet(path)
df.head(100).to_csv('stock_daily_sample.csv', index=False)
print('wrote stock_daily_sample.csv')
PY
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
- `fetch_stock_daily.py` uses exchange code lists and Sina historical daily data. It runs sequentially because the upstream AkShare/Sina path is not thread-safe in this environment.
- Market data should be fetched on trading days after market close.
- Raw and processed data files are intentionally ignored by git.
