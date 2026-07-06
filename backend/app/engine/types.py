"""Domain types shared across the analytics engine.

These are plain dataclasses (not pydantic) so the hot recompute path stays
allocation-cheap. Serialization to the frontend happens once per push in the
API layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"


@dataclass(slots=True)
class Quote:
    """A single instrument's latest values (option leg, future, or index)."""
    ltp: float = 0.0
    oi: float = 0.0
    oi_change: float = 0.0
    volume: float = 0.0          # traded qty / no. of contracts (NOC)
    atp: float = 0.0             # average traded price
    iv_feed: float | None = None  # IV from the provider, if any (may be absent)
    bid: float = 0.0
    ask: float = 0.0
    prev_close: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0


@dataclass(slots=True)
class StrikeRow:
    """One strike with both legs and computed per-strike metrics."""
    strike: float
    ce: Quote = field(default_factory=Quote)
    pe: Quote = field(default_factory=Quote)
    # computed (filled by the engine)
    ce_iv: float | None = None
    pe_iv: float | None = None
    ce_greeks: "Greeks | None" = None
    pe_greeks: "Greeks | None" = None
    ce_buildup: str = ""
    pe_buildup: str = ""
    total_oi: float = 0.0        # ce.oi + pe.oi  (workbook BA = X + X)


@dataclass(slots=True)
class Greeks:
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    price: float = 0.0           # theoretical price at the used IV
    d1: float = 0.0
    d2: float = 0.0


@dataclass(slots=True)
class ChainInputs:
    """Everything the engine needs to compute a full snapshot for one expiry."""
    underlying: str
    spot: float                  # index/future price used as S
    strikes: list[StrikeRow]
    r: float                     # risk-free rate (fraction)
    q: float                     # dividend yield (fraction)
    t_years: float               # time to expiry in years
    step: float                  # strike step
    atm: float                   # ATM strike
    india_vix: float | None = None
    lot_size: float = 1.0
    is_future_underlying: bool = True  # use Black-76 when priced off the future
