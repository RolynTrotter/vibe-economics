"""Cached loading of processed (tidy) datasets.

Services call `load_processed("shiller_returns")` to get a DataFrame without
worrying about paths. Results are cached so repeated API calls are cheap.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .catalog import get_dataset


@lru_cache(maxsize=32)
def load_processed(ds_id: str) -> pd.DataFrame:
    """Load a dataset's processed parquet/csv from data/processed/.

    Raises a clear error (with the rebuild command) if it hasn't been compiled yet.
    """
    entry = get_dataset(ds_id)
    path = entry.processed_path
    if path is None:
        raise ValueError(
            f"Dataset '{ds_id}' has no processed file configured in catalog.yaml."
        )
    if not path.exists():
        raise FileNotFoundError(
            f"Processed file for '{ds_id}' not found at {path}. "
            f"Build it with:  python -m app.cli acquire {ds_id} && python -m app.cli compile {ds_id}"
        )
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported processed file type: {path.suffix}")
