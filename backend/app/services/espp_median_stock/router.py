"""FastAPI router for the ESPP / median-stock service.

Thin layer: parse params -> call pure model functions -> return JSON. The
single-stock panel and the index live in `sp500_constituent_returns`; the model
turns them into per-year median-vs-index stats and an ESPP discount evaluation.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from . import model
from .data import load_panel

router = APIRouter(prefix="/api/espp-median-stock", tags=["espp-median-stock"])


@router.get("/meta")
def meta() -> dict:
    panel = load_panel()
    years = model.available_years(panel)
    return {
        "dataset": "sp500_constituent_returns",
        "source": "Yahoo Finance (monthly adjusted close; SPY = total-return S&P 500) "
        "+ GitHub S&P 500 constituent list",
        "first_year": int(min(years)),
        "last_year": int(max(years)),
        "n_years": len(years),
        "min_stocks_per_year": model.MIN_STOCKS_PER_YEAR,
        "units": "annual total return (dividends reinvested), Dec(t-1)->Dec(t), decimal",
        "definition": "Median stock = cross-sectional median of single-stock one-year "
        "total returns among S&P 500 members that year; index = SPY total return.",
        "caveat": "Universe is today's S&P 500 members -> survivorship-biased upward. "
        "The true median stock did worse and the left tail is fatter.",
    }


@router.get("/by-year")
def by_year(
    discount: float = Query(model.DEFAULT_DISCOUNT, ge=0.0, lt=1.0),
) -> dict:
    panel = load_panel()
    df = model.by_year(panel, discount=discount)
    return {"discount": discount, "points": df.to_dict(orient="records")}


@router.get("/distribution")
def distribution(
    discount: float = Query(model.DEFAULT_DISCOUNT, ge=0.0, lt=1.0),
) -> dict:
    return model.pooled_distribution(load_panel(), discount=discount)


@router.get("/espp-curve")
def espp_curve() -> dict:
    panel = load_panel()
    discounts = [round(0.05 * i, 2) for i in range(0, 7)]  # 0%, 5%, ..., 30%
    df = model.espp_curve(panel, discounts)
    return {"points": df.to_dict(orient="records")}


@router.get("/summary")
def summary(
    discount: float = Query(model.DEFAULT_DISCOUNT, ge=0.0, lt=1.0),
) -> dict:
    return model.summary(load_panel(), discount=discount)
