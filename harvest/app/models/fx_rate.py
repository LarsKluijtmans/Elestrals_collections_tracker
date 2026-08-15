"""`fx_rates` — one row per day per currency pair.

Conversion uses **the rate for the observation's own day**, never today's. Using today's rate for
a year-old sale rewrites history every morning: the same past day's value moves because the euro
moved, and a portfolio chart then shows movement that never happened.

A missed day carries the previous rate forward and marks the conversion approximate rather than
failing — an approximate conversion over a weekend is fine, and one over a fortnight is a broken
job that the `is_carried_forward` flag makes visible.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class FxRate(Base):
    __tablename__ = "fx_rates"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    base: Mapped[str] = mapped_column(String(3), primary_key=True)
    quote: Mapped[str] = mapped_column(String(3), primary_key=True)
    rate: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    #: True when this row was copied from an earlier day because the provider was unreachable.
    #: Every figure converted through it is labelled approximate.
    is_carried_forward: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
