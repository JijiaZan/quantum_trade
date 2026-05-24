#!/usr/bin/env python3
from __future__ import annotations

import duckdb
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quantum_trade.paths import DB_DIR, RAW_DIR

DB_PATH = DB_DIR / "quant.duckdb"

VIEWS = {
    "stock_daily": RAW_DIR / "stock_daily" / "trade_date=*" / "part.parquet",
    "sector_daily": RAW_DIR / "sector_daily" / "trade_date=*" / "part.parquet",
    "sector_members": RAW_DIR / "sector_members" / "trade_date=*" / "part.parquet",
}


def main() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))

    for view_name, parquet_glob in VIEWS.items():
        if not glob.glob(str(parquet_glob)):
            conn.execute(
                f"""
                CREATE OR REPLACE VIEW {view_name} AS
                SELECT CAST(NULL AS VARCHAR) AS trade_date
                WHERE false
                """
            )
            continue

        conn.execute(
            f"""
            CREATE OR REPLACE VIEW {view_name} AS
            SELECT * FROM read_parquet('{parquet_glob}', union_by_name = true, hive_partitioning = true)
            """
        )

    conn.close()
    print(f"initialized DuckDB database at {DB_PATH}")
    print("created views: " + ", ".join(VIEWS))


if __name__ == "__main__":
    main()
