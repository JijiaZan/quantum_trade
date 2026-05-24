#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb

from quantum_trade.paths import RAW_DIR

DEFAULT_DB = ":memory:"

VIEWS = {
    "stock_daily": RAW_DIR / "stock_daily" / "trade_date=*" / "part.parquet",
    "sector_daily": RAW_DIR / "sector_daily" / "trade_date=*" / "part.parquet",
    "sector_members": RAW_DIR / "sector_members" / "trade_date=*" / "part.parquet",
}


def _sql_literal(path: Path) -> str:
    return str(path).replace("'", "''")


def register_views(conn: duckdb.DuckDBPyConnection) -> None:
    for view_name, parquet_glob in VIEWS.items():
        matches = glob.glob(str(parquet_glob))
        if not matches:
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
            SELECT *
            FROM read_parquet('{_sql_literal(parquet_glob)}', union_by_name = true, hive_partitioning = true)
            """
        )


def print_relation(conn: duckdb.DuckDBPyConnection, sql: str, limit: int | None) -> None:
    query = sql.strip().rstrip(";")
    if not query:
        return

    df = conn.sql(query).df()
    if limit is not None:
        df = df.head(limit)

    if df.empty:
        print("<empty>")
    else:
        print(df.to_string(index=False))


def run_script(conn: duckdb.DuckDBPyConnection, sql: str, limit: int | None) -> None:
    # Keep this simple: one SQL statement for result printing. For multiple DDL/DML
    # statements, use DuckDB CLI later or split them manually in a .sql file.
    print_relation(conn, sql, limit)


def repl(conn: duckdb.DuckDBPyConnection, limit: int | None) -> None:
    print("DuckDB SQL shell. Registered views: " + ", ".join(VIEWS))
    print("Type .tables to list views, .schema <view> to describe, .quit to exit.")
    buffer: list[str] = []

    while True:
        prompt = "sql> " if not buffer else "...> "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break

        command = line.strip()
        if not buffer and command in {".quit", ".exit", "quit", "exit"}:
            break
        if not buffer and command == ".tables":
            for view_name in VIEWS:
                print(view_name)
            continue
        if not buffer and command.startswith(".schema"):
            parts = command.split(maxsplit=1)
            if len(parts) != 2:
                print("usage: .schema <view_name>")
                continue
            try:
                print_relation(conn, f"DESCRIBE {parts[1]}", limit=None)
            except Exception as exc:
                print(f"error: {exc}")
            continue

        buffer.append(line)
        sql = "\n".join(buffer)
        if ";" not in line:
            continue

        try:
            print_relation(conn, sql, limit)
        except Exception as exc:
            print(f"error: {exc}")
        finally:
            buffer = []


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SQL against local Quantum Trade DuckDB/Parquet data.")
    parser.add_argument("-c", "--command", help="SQL command to execute.")
    parser.add_argument("-f", "--file", type=Path, help="Path to a .sql file to execute.")
    parser.add_argument("--db", default=DEFAULT_DB, help="DuckDB database path. Defaults to in-memory ':memory:'.")
    parser.add_argument("--limit", type=int, default=None, help="Optional display row limit for query results.")
    args = parser.parse_args()

    if args.command and args.file:
        parser.error("use either --command or --file, not both")

    if args.db != ":memory:":
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(args.db)
    register_views(conn)

    try:
        if args.command:
            run_script(conn, args.command, args.limit)
        elif args.file:
            run_script(conn, args.file.read_text(), args.limit)
        else:
            repl(conn, args.limit)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
