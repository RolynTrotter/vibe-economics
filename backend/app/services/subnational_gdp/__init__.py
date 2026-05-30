"""Subnational-GDP comparison (ticket 0002).

Places US states and whole countries on a single ranked ladder on a chosen basis
(total nominal GDP, total PPP GDP, or GDP-per-capita PPP), so you can answer
"this US state ≈ that country" and watch the ranking reshuffle by basis.

Data: BEA Regional (US state GDP + derived population) + World Bank WDI (country
GDP, GDP PPP, population). See data.py for the acquire/compile flow.
"""
