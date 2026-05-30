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


@router.get("/meta")
def meta() -> dict:
    df = load_entities()
    return {
        "dataset": DATASET_ID,
        "sources": [
            "BEA Regional (US state GDP; population derived from personal income / "
            "per-capita personal income). U.S. Government work, public domain.",
            "World Bank WDI (country GDP, GDP PPP, population). CC BY 4.0.",
        ],
        "n_states": int((df["kind"] == "state").sum()),
        "n_countries": int((df["kind"] == "country").sum()),
        "bases": {k: {"label": v["label"], "blurb": v["blurb"]} for k, v in model.BASES.items()},
        "caveats": [
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
) -> dict:
    kind_tuple = None
    if kinds:
        parts = tuple(k.strip() for k in kinds.split(",") if k.strip())
        bad = [k for k in parts if k not in {"state", "country"}]
        if bad:
            raise HTTPException(400, f"Unknown kind(s): {bad}")
        kind_tuple = parts
    try:
        table = model.ranked_table(load_entities(), basis, kind_tuple)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"basis": basis, "n": len(table), "rows": table.to_dict(orient="records")}


@router.get("/compare")
def compare(
    entities: str = Query(..., description="comma-separated entity ids, e.g. US-CA,DEU,FRA"),
    basis: str = Query("nominal"),
) -> dict:
    ids = [e.strip() for e in entities.split(",") if e.strip()]
    if not ids:
        raise HTTPException(400, "Provide at least one entity id.")
    try:
        rows = model.compare(load_entities(), ids, basis)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"basis": basis, "entities": ids, "rows": rows}


@router.get("/rank")
def rank(
    entity: str = Query(..., description="entity id, e.g. US-VA"),
    basis: str = Query("nominal"),
    among: str = Query("country"),
    n: int = Query(3, ge=1, le=20),
) -> dict:
    if among not in _KIND_OPTS:
        raise HTTPException(400, f"among must be one of {_KIND_OPTS}")
    try:
        return model.nearest(load_entities(), entity, basis, n=n, among=among)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
