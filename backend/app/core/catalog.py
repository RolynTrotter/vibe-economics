"""Load and resolve entries from data/catalog.yaml.

The catalog is the single source of truth for every dataset: where the raw file
comes from, where the tidy processed file lives, and which function compiles one
into the other. Both the CLI and service data loaders go through here so paths
stay consistent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

# Repo layout: this file is backend/app/core/catalog.py -> repo root is 3 parents up.
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CATALOG_PATH = DATA_DIR / "catalog.yaml"


@dataclass(frozen=True)
class DatasetEntry:
    id: str
    title: str
    source: str
    homepage: str
    url: str
    license: str
    api_key: Optional[str]
    raw: Optional[str]
    processed: Optional[str]
    compiler: Optional[str]
    notes: str

    @property
    def raw_path(self) -> Optional[Path]:
        return (RAW_DIR / self.raw) if self.raw else None

    @property
    def processed_path(self) -> Optional[Path]:
        return (PROCESSED_DIR / self.processed) if self.processed else None

    def resolved_api_key(self) -> Optional[str]:
        """Return the API key value from the environment, if this dataset needs one."""
        if not self.api_key:
            return None
        return os.environ.get(self.api_key)


@lru_cache(maxsize=1)
def _load_raw_catalog() -> dict:
    with CATALOG_PATH.open() as fh:
        return yaml.safe_load(fh) or {}


def all_datasets() -> dict[str, DatasetEntry]:
    raw = _load_raw_catalog().get("datasets", {}) or {}
    out: dict[str, DatasetEntry] = {}
    for ds_id, fields in raw.items():
        fields = fields or {}
        out[ds_id] = DatasetEntry(
            id=ds_id,
            title=fields.get("title", ds_id),
            source=fields.get("source", ""),
            homepage=fields.get("homepage", ""),
            url=fields.get("url", ""),
            license=fields.get("license", ""),
            api_key=fields.get("api_key"),
            raw=fields.get("raw"),
            processed=fields.get("processed"),
            compiler=fields.get("compiler"),
            notes=fields.get("notes", "") or "",
        )
    return out


def get_dataset(ds_id: str) -> DatasetEntry:
    datasets = all_datasets()
    if ds_id not in datasets:
        raise KeyError(
            f"Unknown dataset id '{ds_id}'. Known: {', '.join(sorted(datasets))}"
        )
    return datasets[ds_id]
