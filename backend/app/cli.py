"""Dataset CLI: acquire (download raw) and compile (raw -> tidy processed).

Usage (run from backend/ with the venv active):

    python -m app.cli list
    python -m app.cli acquire <dataset_id>
    python -m app.cli compile <dataset_id>

`acquire` downloads the catalog `url` into data/raw/<...>. `compile` imports the
catalog `compiler` ("module:function"), runs it on the raw path, and writes the
tidy result to data/processed/<...>.
"""
from __future__ import annotations

import argparse
import importlib
import sys

import pandas as pd

from .core.catalog import all_datasets, get_dataset
from .core.sources import download


def _cmd_list(_args) -> int:
    for ds_id, e in sorted(all_datasets().items()):
        key = f" (needs {e.api_key})" if e.api_key else ""
        proc = "compiled" if (e.processed_path and e.processed_path.exists()) else "—"
        print(f"{ds_id:28s} {proc:9s}{key}  {e.title}")
    return 0


def _cmd_acquire(args) -> int:
    e = get_dataset(args.dataset)
    if e.raw_path is None:
        print(f"Dataset '{e.id}' has no `raw` path configured.", file=sys.stderr)
        return 1
    url = e.url
    if e.api_key and e.resolved_api_key() is None:
        print(
            f"Dataset '{e.id}' needs env var {e.api_key} to build its URL; not set.",
            file=sys.stderr,
        )
        return 1
    print(f"Downloading {url}\n        -> {e.raw_path}")
    download(url, e.raw_path)
    print(f"OK ({e.raw_path.stat().st_size} bytes)")
    return 0


def _load_compiler(spec: str):
    module_name, func_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


def _cmd_compile(args) -> int:
    e = get_dataset(args.dataset)
    if not e.compiler:
        print(f"Dataset '{e.id}' has no `compiler` configured.", file=sys.stderr)
        return 1
    if e.raw_path is None or not e.raw_path.exists():
        print(
            f"Raw file for '{e.id}' missing. Run: python -m app.cli acquire {e.id}",
            file=sys.stderr,
        )
        return 1
    compiler = _load_compiler(e.compiler)
    df: pd.DataFrame = compiler(e.raw_path)
    out = e.processed_path
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".parquet":
        df.to_parquet(out, index=False)
    else:
        df.to_csv(out, index=False)
    print(f"Compiled {e.id}: {len(df)} rows -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="vibe-economics dataset CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list datasets and compile status")

    p_acq = sub.add_parser("acquire", help="download a dataset's raw file")
    p_acq.add_argument("dataset")

    p_comp = sub.add_parser("compile", help="compile raw -> tidy processed")
    p_comp.add_argument("dataset")

    args = parser.parse_args(argv)
    return {
        "list": _cmd_list,
        "acquire": _cmd_acquire,
        "compile": _cmd_compile,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
