"""FastAPI router for the safe-withdrawal backtester.

Thin layer: parse/validate params -> call pure model functions -> return JSON.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from . import model
from .data import load_returns

router = APIRouter(prefix="/api/safe-withdrawal", tags=["safe-withdrawal"])


def _resolve_stock_weight(preset: Optional[str], stock: Optional[float]) -> float:
    if preset is not None:
        if preset not in model.PRESETS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown preset '{preset}'. Options: {list(model.PRESETS)}",
            )
        return model.PRESETS[preset]
    if stock is None:
        return model.PRESETS["sixty_forty"]
    if not 0.0 <= stock <= 1.0:
        raise HTTPException(status_code=400, detail="stock weight must be in [0, 1]")
    return float(stock)


@router.get("/presets")
def presets() -> dict:
    return {"presets": model.PRESETS, "baseline_4pct_rule": model.RULE_OF_THUMB}


@router.get("/meta")
def meta() -> dict:
    df = load_returns()
    return {
        "dataset": "shiller_returns",
        "source": "Robert J. Shiller, Yale (CSV mirror datasets/s-and-p-500)",
        "first_year": int(df["year"].min()),
        "last_year": int(df["year"].max()),
        "n_years": int(len(df)),
        "units": "real (CPI-adjusted); withdrawals constant in real terms",
        "definition": "SWR = upper bound on the 4% rule: max constant real "
        "withdrawal that depletes the portfolio to exactly $0 at the horizon.",
        "notes": "Bond = 10yr Treasury par-bond proxy. 3-fund intl equity proxied by US equity.",
    }


@router.get("/by-year")
def by_year(
    horizon: int = Query(30, ge=1, le=100),
    preset: Optional[str] = None,
    stock: Optional[float] = Query(None, ge=0.0, le=1.0),
) -> dict:
    sw = _resolve_stock_weight(preset, stock)
    result = model.swr_by_start_year(load_returns(), horizon, sw)
    return {"stock_weight": sw, "horizon": horizon, "points": result.to_dict(orient="records")}


@router.get("/summary")
def summary(
    horizon: int = Query(30, ge=1, le=100),
    preset: Optional[str] = None,
    stock: Optional[float] = Query(None, ge=0.0, le=1.0),
) -> dict:
    sw = _resolve_stock_weight(preset, stock)
    return model.summary(load_returns(), horizon, sw)


@router.get("/path")
def path(
    start_year: int,
    horizon: int = Query(30, ge=1, le=100),
    preset: Optional[str] = None,
    stock: Optional[float] = Query(None, ge=0.0, le=1.0),
    rate: float = Query(0.04, ge=0.0, le=1.0),
) -> dict:
    sw = _resolve_stock_weight(preset, stock)
    try:
        result = model.portfolio_path(load_returns(), start_year, horizon, sw, rate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "stock_weight": sw,
        "horizon": horizon,
        "start_year": start_year,
        "rate": rate,
        "path": result.to_dict(orient="records"),
    }
