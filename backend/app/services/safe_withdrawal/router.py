"""FastAPI router for the safe-withdrawal backtester.

Thin layer: parse/validate params -> call pure model functions -> return JSON.
Allocations are three-asset (us / intl equity / bond); callers pass either a
named `preset` or explicit `us` and `intl` weights (bond = 1 - us - intl).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from . import model
from .data import load_returns

router = APIRouter(prefix="/api/safe-withdrawal", tags=["safe-withdrawal"])


def _resolve_weights(
    preset: Optional[str], us: Optional[float], intl: Optional[float]
) -> dict[str, float]:
    if preset is not None:
        if preset not in model.PRESETS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown preset '{preset}'. Options: {list(model.PRESETS)}",
            )
        return model.PRESETS[preset]
    if us is None and intl is None:
        return model.PRESETS["sixty_forty"]
    us_w = 0.0 if us is None else float(us)
    intl_w = 0.0 if intl is None else float(intl)
    bond_w = 1.0 - us_w - intl_w
    if us_w < 0 or intl_w < 0 or bond_w < -1e-9:
        raise HTTPException(
            status_code=400, detail="us + intl must be in [0, 1] and each non-negative"
        )
    try:
        return model.normalize_weights({"us": us_w, "intl": intl_w, "bond": bond_w})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/presets")
def presets() -> dict:
    return {"presets": model.PRESETS, "baseline_4pct_rule": model.RULE_OF_THUMB}


@router.get("/meta")
def meta() -> dict:
    df = load_returns()
    return {
        "dataset": "jst_returns",
        "source": "Jordà-Schularick-Taylor Macrohistory (Rate of Return on Everything, 1870-2015)",
        "first_year": int(df["year"].min()),
        "last_year": int(df["year"].max()),
        "n_years": int(len(df)),
        "units": "real (CPI-adjusted); withdrawals constant in real terms",
        "definition": "SWR = upper bound on the 4% rule: max constant real "
        "withdrawal that depletes the portfolio to exactly $0 at the horizon.",
        "notes": "US & bond from JST USA series; intl = GDP-weighted developed-ex-US "
        "equity converted to USD. Three-fund = 60/40 equity/bond with equity split "
        "60/40 US/intl, so it differs from 60-40 only by real international diversification.",
    }


@router.get("/by-year")
def by_year(
    horizon: int = Query(30, ge=1, le=100),
    preset: Optional[str] = None,
    us: Optional[float] = Query(None, ge=0.0, le=1.0),
    intl: Optional[float] = Query(None, ge=0.0, le=1.0),
) -> dict:
    w = _resolve_weights(preset, us, intl)
    result = model.swr_by_start_year(load_returns(), horizon, w)
    return {"weights": w, "horizon": horizon, "points": result.to_dict(orient="records")}


@router.get("/summary")
def summary(
    horizon: int = Query(30, ge=1, le=100),
    preset: Optional[str] = None,
    us: Optional[float] = Query(None, ge=0.0, le=1.0),
    intl: Optional[float] = Query(None, ge=0.0, le=1.0),
) -> dict:
    w = _resolve_weights(preset, us, intl)
    return model.summary(load_returns(), horizon, w)


@router.get("/path")
def path(
    start_year: int,
    horizon: int = Query(30, ge=1, le=100),
    preset: Optional[str] = None,
    us: Optional[float] = Query(None, ge=0.0, le=1.0),
    intl: Optional[float] = Query(None, ge=0.0, le=1.0),
    rate: float = Query(0.04, ge=0.0, le=1.0),
) -> dict:
    w = _resolve_weights(preset, us, intl)
    try:
        result = model.portfolio_path(load_returns(), start_year, horizon, w, rate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "weights": w,
        "horizon": horizon,
        "start_year": start_year,
        "rate": rate,
        "path": result.to_dict(orient="records"),
    }
