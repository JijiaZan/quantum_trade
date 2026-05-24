from __future__ import annotations

from pathlib import Path

import pandas as pd


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_partitioned_parquet(df: pd.DataFrame, base_dir: Path, trade_date: str) -> Path:
    """Write a daily dataframe into data-set style partition folder."""
    out_dir = base_dir / f"trade_date={trade_date}"
    ensure_dir(out_dir)
    out_file = out_dir / "part.parquet"
    df.to_parquet(out_file, index=False)
    return out_file
