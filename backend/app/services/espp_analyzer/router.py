"""FastAPI router for the ESPP Analyzer.

Thin layer: parse params -> call the pure model on the monthly total-return
levels -> return JSON. Monthly levels come from the shared sp500_monthly_levels
dataset (built by the espp_median_stock service's data module).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.espp_median_stock.data import load_monthly

from . import model

router = APIRouter(prefix="/api/espp-analyzer", tags=["espp-analyzer"])


@router.get("/meta")
def meta() -> dict:
    monthly = load_monthly()
    stocks = monthly[monthly["kind"] == "stock"]
    return {
        "dataset": "sp500_monthly_levels",
        "source": "Yahoo Finance monthly adjusted close (total return); index = SPY. "
        "Universe = current S&P 500 members.",
        "term_options": model.TERM_OPTIONS,
        "hold_options": model.HOLD_OPTIONS,
        "n_tickers": int(stocks["ticker"].nunique()),
        "first_year": int(stocks["year"].min()),
        "last_year": int(stocks["year"].max()),
        "definition": "APY on the average invested dollar (committed term/2 + hold "
        "months), ESPP vs index, at p25/median/p75 of (stock, start-month) windows.",
        "caveat": "Survivorship-biased upward (today's members only); windows overlap "
        "(monthly starts); lookback compares actual split-adjusted share prices, "
        "holding gain earns total return.",
    }


@router.get("/analyze")
def analyze(
    term: int = Query(model.DEFAULT_TERM),
    hold: int = Query(model.DEFAULT_HOLD, ge=0),
    lookback: bool = Query(model.DEFAULT_LOOKBACK),
    discount: float = Query(model.DEFAULT_DISCOUNT, ge=0.0, lt=1.0),
) -> dict:
    if term not in model.TERM_OPTIONS:
        raise HTTPException(400, f"term must be one of {model.TERM_OPTIONS}")
    return model.analyze(load_monthly(), term, hold, lookback, discount)
