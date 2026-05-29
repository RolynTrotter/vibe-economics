"""FastAPI application entry point.

Auto-discovers service routers: any `app/services/<name>/router.py` that defines
a module-level `router` (an APIRouter) is mounted. Add a service by dropping in a
package — no edits here required.
"""
from __future__ import annotations

import importlib
import pkgutil

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import services

app = FastAPI(
    title="vibe-economics API",
    version="0.1.0",
    description="Economics utilities: backtesting, GDP comparisons, cost of living, and more.",
)

# Allow the local Vite dev server (and any origin in this personal/local setup).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _mount_service_routers() -> list[str]:
    """Import every services/<name>/router.py and include its `router`."""
    mounted: list[str] = []
    for mod in pkgutil.iter_modules(services.__path__):
        if not mod.ispkg:
            continue
        try:
            router_mod = importlib.import_module(f"{services.__name__}.{mod.name}.router")
        except ModuleNotFoundError:
            continue
        router = getattr(router_mod, "router", None)
        if router is not None:
            app.include_router(router)
            mounted.append(mod.name)
    return mounted


MOUNTED_SERVICES = _mount_service_routers()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "services": MOUNTED_SERVICES}
