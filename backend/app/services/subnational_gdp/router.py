"""FastAPI router for the subnational-GDP comparison.

Thin layer: parse/validate params -> pure model functions -> JSON. The deployed
web app is static and computes the same ranking client-side from a JSON snapshot;
this backend is the tested source of truth for local dev.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from . import model
from .data import DATASET_ID, load_entities

router = APIRouter(prefix="/api/subnational-gdp", tags=["subnational-gdp"])

_KIND_OPTS = {"state", "country", "any"}


def _entities(year: Optional[int]):
    """Entities frame for a target `year` (smoothed/imputed via the time series), or
    the latest-snapshot frame when no year is given / the time series isn't built."""
    if year is None:
        return load_entities()
    from . import estimate
    lo, hi = estimate.available_years()
    if not (lo <= year <= hi):
        raise HTTPException(400, f"year must be in [{lo}, {hi}]")
    return estimate.load_entities_for_year(year)


@router.get("/meta")
def meta() -> dict:
    df = load_entities()
    year_range = None
    try:
        from . import estimate
        lo, hi = estimate.available_years()
        year_range = {"min": lo, "max": hi, "default": hi}
    except (FileNotFoundError, ValueError, KeyError):
        pass
    return {
        "dataset": DATASET_ID,
        "sources": [
            "BEA Regional (US state GDP; population derived from personal income / "
            "per-capita personal income). U.S. Government work, public domain.",
            "World Bank WDI (country GDP, GDP PPP, population). CC BY 4.0.",
            "IMF DataMapper / WEO (near-term growth used to carry the latest actual "
            "to the chosen year). IMF terms.",
        ],
        "years": year_range,
        "n_states": int((df["kind"] == "state").sum()),
        "n_countries": int((df["kind"] == "country").sum()),
        "bases": {k: {"label": v["label"], "blurb": v["blurb"]} for k, v in model.BASES.items()},
        "caveats": [
            "Year alignment: each place is shown at the chosen year. Figures past a "
            "source's latest release are interpolated between actuals or carried "
            "forward (≤2 yrs) by IMF WEO growth, and marked with an asterisk (*).",
            "US-state PPP uses nominal USD as a proxy (US ≈ PPP reference economy; "
            "US PPP/nominal ≈ 1.01 per World Bank).",
            "State population is derived (personal income ÷ per-capita personal income).",
            "DC is excluded from the per-capita ranking: its GDP/capita is a commuter "
            "artifact (metro-wide output divided by DC residents only).",
            "Source release lags differ; each entity carries the year of its GDP figure.",
        ],
    }


@router.get("/ranking")
def ranking(
    basis: str = Query("nominal"),
    kinds: Optional[str] = Query(None, description="comma list of state,country"),
    year: Optional[int] = Query(None, description="align all places to this year (smoothed/imputed)"),
) -> dict:
    kind_tuple = None
    if kinds:
        parts = tuple(k.strip() for k in kinds.split(",") if k.strip())
        bad = [k for k in parts if k not in {"state", "country"}]
        if bad:
            raise HTTPException(400, f"Unknown kind(s): {bad}")
        kind_tuple = parts
    try:
        table = model.ranked_table(_entities(year), basis, kind_tuple)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"basis": basis, "year": year, "n": len(table), "rows": table.to_dict(orient="records")}


@router.get("/compare")
def compare(
    entities: str = Query(..., description="comma-separated entity ids, e.g. US-CA,DEU,FRA"),
    basis: str = Query("nominal"),
    year: Optional[int] = Query(None, description="align all places to this year"),
) -> dict:
    ids = [e.strip() for e in entities.split(",") if e.strip()]
    if not ids:
        raise HTTPException(400, "Provide at least one entity id.")
    try:
        rows = model.compare(_entities(year), ids, basis)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"basis": basis, "entities": ids, "rows": rows}


@router.get("/hinterland")
def hinterland(
    basis: str = Query("per_capita"),
    remove_capital: bool = Query(False),
    remove_largest: bool = Query(False),
    remove_richest: bool = Query(False),
    include: str = Query("all", description="all | states | countries"),
) -> dict:
    """Ladder of countries (OECD FUA) and/or US states (CSA county footprint) with
    each place's capital / largest / richest metro punched out — the 'hinterland' view."""
    from .metros import load_metros
    from .us_metros import load_us_metros

    df = load_entities()
    names = {r.entity_id: r.name for r in df[df["kind"] == "country"].itertuples()}
    names["USA"] = "United States"
    places = []
    if include in ("all", "countries"):
        places += model.country_places(load_metros(), names)
    if include in ("all", "states"):
        places += model.state_places(load_us_metros(), df)
    try:
        table = model.hinterland_table(places, basis, remove_capital, remove_largest, remove_richest)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {
        "basis": basis, "remove_capital": remove_capital, "remove_largest": remove_largest,
        "remove_richest": remove_richest, "include": include,
        "n": len(table), "rows": table.to_dict(orient="records"),
    }


@router.get("/rank")
def rank(
    entity: str = Query(..., description="entity id, e.g. US-VA"),
    basis: str = Query("nominal"),
    among: str = Query("country"),
    n: int = Query(3, ge=1, le=20),
    year: Optional[int] = Query(None, description="align all places to this year"),
) -> dict:
    if among not in _KIND_OPTS:
        raise HTTPException(400, f"among must be one of {_KIND_OPTS}")
    try:
        return model.nearest(_entities(year), entity, basis, n=n, among=among)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
