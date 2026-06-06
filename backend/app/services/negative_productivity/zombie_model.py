"""Pure zombie-firm analysis (ticket 0010, lens 2).

No I/O: every function takes the tidy panel (cik, name, loc, year, ebit, interest,
icr) from zombie_data.py and returns plain Python.

Zombie test (BIS — Banerjee & Hofmann 2018): interest-coverage ratio (EBIT ÷
interest) **< 1 for THRESHOLD_YEARS consecutive years**. We additionally report a
**mature** subset (firm observed in the panel for ≥ MATURE_YEARS years), a tractable
proxy for the BIS "age ≥ 10 years" screen that excludes young loss-making growth
firms. (True incorporation age isn't in the XBRL frames; reporting-age is the
public-data stand-in, surfaced as a caveat.)

`zombie_share_series` returns one record per year with the broad and mature shares.
The most recent year(s) can be incomplete (filings still arriving), so each record
carries `provisional` based on cross-sectional coverage vs the trailing norm.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ICR_THRESHOLD = 1.0
CONSECUTIVE_YEARS = 3
MATURE_YEARS = 10
# A year is flagged provisional if its firm count falls below this fraction of the
# trailing-median count (i.e. filings for that year are still coming in).
COVERAGE_FLOOR = 0.7


def _by_firm(df: pd.DataFrame) -> tuple[dict[int, dict[int, float]], dict[int, int], dict[int, dict]]:
    """Return (icr[cik][year], first_year[cik], meta[cik]={name,loc})."""
    icr: dict[int, dict[int, float]] = {}
    meta: dict[int, dict] = {}
    for r in df.itertuples():
        icr.setdefault(r.cik, {})[int(r.year)] = float(r.icr)
        meta[r.cik] = {"name": r.name, "loc": r.loc}
    first_year = {cik: min(ys) for cik, ys in icr.items()}
    return icr, first_year, meta


def _is_zombie(years_icr: dict[int, float], t: int) -> bool:
    """ICR < threshold in each of the CONSECUTIVE_YEARS ending at t (all must exist)."""
    window = [t - k for k in range(CONSECUTIVE_YEARS)]
    if any(y not in years_icr for y in window):
        return False
    return all(years_icr[y] < ICR_THRESHOLD for y in window)


def zombie_share_series(df: pd.DataFrame) -> list[dict]:
    """Per-year zombie share — broad universe and the mature (≥10y reporting) subset."""
    icr, first_year, _ = _by_firm(df)
    years = sorted({y for m in icr.values() for y in m})
    if not years:
        return []
    # cross-sectional firm count per year (for the provisional flag)
    count_by_year = {y: sum(1 for m in icr.values() if y in m) for y in years}

    raw: list[dict] = []
    start = years[0] + CONSECUTIVE_YEARS - 1  # first year with a full window
    for t in range(start, years[-1] + 1):
        n = nz = mat = matz = 0
        for cik, m in icr.items():
            if any((t - k) not in m for k in range(CONSECUTIVE_YEARS)):
                continue
            n += 1
            z = _is_zombie(m, t)
            nz += z
            if first_year[cik] <= t - (MATURE_YEARS - 1):
                mat += 1
                matz += z
        if n == 0:
            continue
        raw.append(
            {
                "year": t,
                "n_firms": n,
                "n_zombies": nz,
                "share": round(100 * nz / n, 2),
                "n_mature": mat,
                "n_mature_zombies": matz,
                "mature_share": round(100 * matz / mat, 2) if mat else None,
                "_window_count": count_by_year[t],
            }
        )
    # provisional flag: compare each year's cross-section count to the trailing median
    counts = [r["_window_count"] for r in raw]
    for i, r in enumerate(raw):
        ref = np.median(counts[max(0, i - 5):i]) if i >= 3 else None
        r["provisional"] = bool(ref and r["_window_count"] < COVERAGE_FLOOR * ref)
        del r["_window_count"]
    return raw


def latest_zombies(df: pd.DataFrame, top_n: int = 25, mature_only: bool = True) -> dict:
    """The most recent complete year's zombie roster, ranked by interest burden.

    Ranked by interest expense (the size of the debt service these firms can't cover),
    so recognisable large names surface rather than micro-caps."""
    series = zombie_share_series(df)
    if not series:
        return {}
    complete = [s for s in series if not s["provisional"]]
    if not complete:
        complete = series
    year = complete[-1]["year"]

    icr, first_year, meta = _by_firm(df)
    latest_val = {r.cik: r for r in df[df["year"] == year].itertuples()}

    rows = []
    for cik, m in icr.items():
        if not _is_zombie(m, year):
            continue
        if mature_only and first_year[cik] > year - (MATURE_YEARS - 1):
            continue
        rec = latest_val.get(cik)
        if rec is None:
            continue
        rows.append(
            {
                "name": meta[cik]["name"],
                "loc": meta[cik]["loc"],
                "icr": round(float(rec.icr), 2),
                "ebit": float(rec.ebit),
                "interest": float(rec.interest),
                "since": int(first_year[cik]),
            }
        )
    rows.sort(key=lambda r: r["interest"], reverse=True)
    return {"year": year, "mature_only": mature_only, "firms": rows[:top_n]}


def meta_summary(df: pd.DataFrame) -> dict:
    series = zombie_share_series(df)
    complete = [s for s in series if not s["provisional"]]
    latest = (complete or series)[-1] if series else None
    return {
        "first_year": series[0]["year"] if series else None,
        "last_complete_year": complete[-1]["year"] if complete else None,
        "latest": latest,
        "definition": (
            f"Zombie = interest-coverage ratio (EBIT ÷ interest) < {ICR_THRESHOLD:g} "
            f"for {CONSECUTIVE_YEARS} consecutive years. 'Mature' = ≥{MATURE_YEARS} "
            "years of reporting history (proxy for the BIS age≥10 screen)."
        ),
    }
