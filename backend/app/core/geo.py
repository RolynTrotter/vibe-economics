"""Shared geographic-entity handling.

First consumer is the subnational-GDP service (ticket 0002); the cost-of-living
service (ticket 0005) is expected to reuse it. The job here is small but central:
give every place a **stable entity id** and the metadata a UI needs to render it
consistently — its display name, whether it's a country or a subnational region,
and its *parent nation* (so a widget can colour a US state the same as the USA).

Entity id conventions
----------------------
- Countries:        ISO 3166-1 alpha-3, e.g. ``DE``→``DEU`` is *not* used; we use
                    the 3-letter code directly: ``DEU``, ``FRA``, ``GBR``.
                    A 2-letter alias (``DE``) resolves to the alpha-3 too.
- US states:        ``US-XX`` with the USPS 2-letter code, e.g. ``US-CA``.

Keeping this in one place means the subnational and cost-of-living services agree
on what ``US-CA`` or ``FRA`` means without re-deriving it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Parent-nation id used to colour subnational entities by their country.
USA = "USA"


@dataclass(frozen=True)
class Entity:
    id: str               # stable id: "US-CA" or "FRA"
    name: str             # display name: "California", "Germany"
    kind: str             # "state" | "country"
    parent: str           # parent-nation id; a country is its own parent

    @property
    def is_subnational(self) -> bool:
        return self.kind != "country"


# USPS code -> full state name. 50 states + DC (DC is included as a state-like
# region because BEA reports it alongside the states).
US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# BEA Regional reports states by 2-digit FIPS GeoFips ("06000" for California).
# Map FIPS state code -> USPS so we can build "US-XX" ids from BEA rows.
FIPS_TO_USPS: dict[str, str] = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}


def state_entity(usps: str) -> Entity:
    usps = usps.upper()
    return Entity(id=f"US-{usps}", name=US_STATES[usps], kind="state", parent=USA)


def country_entity(iso3: str, name: str) -> Entity:
    iso3 = iso3.upper()
    return Entity(id=iso3, name=name, kind="country", parent=iso3)


def fips_to_state_entity(geofips: str) -> Optional[Entity]:
    """Map a BEA GeoFips ("06000" / "06") to a state Entity, or None if not a state."""
    code = str(geofips)[:2]
    usps = FIPS_TO_USPS.get(code)
    return state_entity(usps) if usps else None
