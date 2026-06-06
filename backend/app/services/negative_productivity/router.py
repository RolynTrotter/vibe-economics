"""FastAPI router for the negative-productivity service (ticket 0010).

Thin layer: load the tidy CPI table -> call pure model functions -> JSON. First
lens is localized-inflation / relative-price dispersion; future lenses (zombie
firms, value subtraction) attach more endpoints under the same prefix.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import model
from . import zombie_model
from .data import CATEGORIES, HEADLINE_LABEL, load_cpi
from .zombie_data import load_panel

router = APIRouter(prefix="/api/negative-productivity", tags=["negative-productivity"])

_SOURCE = (
    "BLS CPI-U, U.S. city average, NSA (six major groups with continuous history "
    "since 1967 + All items). 12-month changes."
)


@router.get("/inflation/meta")
def inflation_meta() -> dict:
    df = load_cpi()
    series = model.dispersion_series(df)
    return {
        "lens": "localized_inflation",
        "source": _SOURCE,
        "headline_label": HEADLINE_LABEL,
        "categories": list(CATEGORIES.values()),
        "first": f"{series[0]['year']:04d}-{series[0]['month']:02d}" if series else None,
        "last": f"{series[-1]['year']:04d}-{series[-1]['month']:02d}" if series else None,
        "definition": (
            "dispersion = cross-sectional std dev of the six groups' 12-month % "
            "changes; spread = hottest − coldest; skew = Pearson moment skewness "
            "(Ball & Mankiw 1995: positive skew ↔ adverse supply shock)."
        ),
        "episodes": [{"start": s, "end": e, "label": lab} for s, e, lab in model.EPISODES],
    }


@router.get("/inflation/dispersion")
def inflation_dispersion() -> dict:
    df = load_cpi()
    return {"source": _SOURCE, "series": model.dispersion_series(df)}


@router.get("/inflation/breakdown")
def inflation_breakdown() -> dict:
    df = load_cpi()
    return {"source": _SOURCE, "by_month": model.category_breakdown(df)}


@router.get("/inflation/latest")
def inflation_latest() -> dict:
    df = load_cpi()
    return {"source": _SOURCE, **model.latest_snapshot(df)}


# --------------------------------------------------------------------------- #
# Lens 2 — zombie firms (interest coverage < 1 for ≥3 years)
# --------------------------------------------------------------------------- #
_ZOMBIE_SOURCE = (
    "SEC EDGAR XBRL frames (data.sec.gov), public domain: OperatingIncomeLoss "
    "(EBIT) ÷ InterestExpense, US-listed firms 2009–present."
)


@router.get("/zombies/meta")
def zombies_meta() -> dict:
    return {"lens": "zombie_firms", "source": _ZOMBIE_SOURCE, **zombie_model.meta_summary(load_panel())}


@router.get("/zombies/share")
def zombies_share() -> dict:
    return {"source": _ZOMBIE_SOURCE, "series": zombie_model.zombie_share_series(load_panel())}


@router.get("/zombies/latest")
def zombies_latest(top: int = 25, mature_only: bool = True) -> dict:
    return {"source": _ZOMBIE_SOURCE, **zombie_model.latest_zombies(load_panel(), top, mature_only)}
