#!/usr/bin/env python3
from __future__ import annotations

import duckdb

from quantum_trade.paths import DB_DIR, RAW_DIR

DB_PATH = DB_DIR / "quant.duckdb"

VIEWS = {
    "stock_daily": RAW_DIR / "stock_daily" / "**" / "*.parquet",
    "sector_daily": RAW_DIR / "sector_daily" / "**" / "*.parquet",
    "sector_members": RAW_DIR / "sector_members" / "**" / "*.parquet",
}


def main() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))

    for view_name, parquet_glob in VIEWS.items():
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
