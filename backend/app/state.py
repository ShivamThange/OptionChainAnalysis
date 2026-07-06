"""In-memory live market state.

Providers write raw quotes here (hot path, cheap). The recompute pipeline reads
a consistent view via `build_inputs()` to produce metric snapshots. One
`UnderlyingState` per tracked underlying+expiry.
"""
from __future__ import annotations

import datetime as dt
import threading

from .engine.index_calc import atm_strike, time_to_expiry_years
from .engine.types import ChainInputs, Quote, StrikeRow

# staleness threshold — if no update within this many seconds, mark stale
STALE_AFTER_SEC = 15.0


class UnderlyingState:
    def __init__(self, name: str, step: float, lot: float,
                 is_future_underlying: bool = False):
        self.name = name
        self.step = step
        self.lot = lot
        self.is_future_underlying = is_future_underlying
        self.spot: float = 0.0             # index/underlying value (S)
        self.future_ltp: float = 0.0
        self.expiry: dt.date | None = None
        self.india_vix: float | None = None
        self.strikes: dict[float, StrikeRow] = {}
        # token -> (strike, side) for O(1) tick routing
        self.route: dict[int, tuple[float, str]] = {}
        self.last_update: float = 0.0
        self.source: str = ""

    def ensure_strike(self, strike: float) -> StrikeRow:
        row = self.strikes.get(strike)
        if row is None:
            row = StrikeRow(strike=strike)
            self.strikes[strike] = row
        return row

    def register_token(self, token: int, strike: float, side: str):
        self.route[token] = (strike, side)
        self.ensure_strike(strike)

    def apply_tick(self, token: int, *, ltp=None, oi=None, oi_change=None,
                   volume=None, atp=None, iv=None, bid=None, ask=None,
                   prev_close=None, now: float | None = None):
        loc = self.route.get(token)
        if loc is None:
            return
        strike, side = loc
        q: Quote = getattr(self.ensure_strike(strike), side)
        if ltp is not None: q.ltp = ltp
        if oi is not None: q.oi = oi
        if oi_change is not None: q.oi_change = oi_change
        if volume is not None: q.volume = volume
        if atp is not None: q.atp = atp
        if iv is not None: q.iv_feed = iv
        if bid is not None: q.bid = bid
        if ask is not None: q.ask = ask
        if prev_close is not None: q.prev_close = prev_close
        if now is not None:
            self.last_update = now

    def is_stale(self, now: float) -> bool:
        return self.last_update == 0.0 or (now - self.last_update) > STALE_AFTER_SEC

    def build_inputs(self, r: float, q: float,
                     today: dt.date | None = None) -> ChainInputs | None:
        if not self.spot or not self.strikes or self.expiry is None:
            return None
        today = today or dt.date.today()
        t = time_to_expiry_years(today, self.expiry)
        s = self.future_ltp if (self.is_future_underlying and self.future_ltp) else self.spot
        atm = atm_strike(self.spot, self.step)
        rows = [self.strikes[k] for k in sorted(self.strikes)]
        return ChainInputs(
            underlying=self.name, spot=s, strikes=rows, r=r, q=q, t_years=t,
            step=self.step, atm=atm, india_vix=self.india_vix, lot_size=self.lot,
            is_future_underlying=self.is_future_underlying)


class LiveStore:
    """Thread-safe container of all underlying states."""

    def __init__(self):
        self._lock = threading.RLock()
        self.underlyings: dict[str, UnderlyingState] = {}

    def get_or_create(self, name: str, step: float, lot: float,
                      is_future_underlying: bool = False) -> UnderlyingState:
        with self._lock:
            st = self.underlyings.get(name)
            if st is None:
                st = UnderlyingState(name, step, lot, is_future_underlying)
                self.underlyings[name] = st
            return st

    def get(self, name: str) -> UnderlyingState | None:
        return self.underlyings.get(name)

    def names(self) -> list[str]:
        return list(self.underlyings)
