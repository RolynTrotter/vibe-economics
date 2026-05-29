"""Generic data-source fetchers used by the acquire stage.

Start with a plain HTTP downloader; add source-specific helpers (World Bank,
Eurostat, OECD, FRED, BEA ...) here as services need them, so acquisition logic
stays out of individual services.
"""
from .http import download

__all__ = ["download"]
