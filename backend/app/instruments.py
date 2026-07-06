"""Kite instrument master.

Downloads Kite's instrument dump (refreshed daily) and builds, per underlying:
the near expiry, the option strikes with their CE/PE instrument tokens, the
lot size, the nearest future token (for Black-76 pricing), and the index spot
token. Kept independent of live state so it can be unit-reasoned in isolation.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

log = logging.getLogger("instruments")

# Underlying -> NSE index tradingsymbol for spot LTP
INDEX_SPOT_SYMBOL = {
    "NIFTY": "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK",
    "FINNIFTY": "NSE:NIFTY FIN SERVICE",
    "MIDCPNIFTY": "NSE:NIFTY MIDCAP SELECT",
}


@dataclass
class OptionLeg:
    token: int
    tradingsymbol: str
    strike: float
    side: str            # "ce" | "pe"


@dataclass
class UnderlyingInstruments:
    name: str
    expiry: dt.date
    step: float
    lot: float
    legs: list[OptionLeg] = field(default_factory=list)
    future_token: int | None = None
    index_symbol: str | None = None
    all_strikes: list[float] = field(default_factory=list)


def _nearest_expiry(expiries: list[dt.date], today: dt.date) -> dt.date | None:
    future = sorted(e for e in expiries if e >= today)
    return future[0] if future else None


def build_for_underlying(nfo_instruments: list[dict], name: str,
                         today: dt.date | None = None) -> UnderlyingInstruments | None:
    """Filter the NFO dump down to one underlying's near-expiry option chain."""
    today = today or dt.date.today()
    opts = [i for i in nfo_instruments
            if i.get("name") == name and i.get("instrument_type") in ("CE", "PE")
            and i.get("segment") == "NFO-OPT"]
    if not opts:
        log.warning("No NFO options found for %s", name)
        return None

    expiries = {i["expiry"] for i in opts if isinstance(i.get("expiry"), dt.date)}
    expiry = _nearest_expiry(list(expiries), today)
    if expiry is None:
        return None

    chain = [i for i in opts if i["expiry"] == expiry]
    strikes = sorted({float(i["strike"]) for i in chain})
    step = _infer_step(strikes) or 50.0
    lot = float(chain[0].get("lot_size") or 1)

    legs = [OptionLeg(token=int(i["instrument_token"]),
                      tradingsymbol=i["tradingsymbol"],
                      strike=float(i["strike"]),
                      side="ce" if i["instrument_type"] == "CE" else "pe")
            for i in chain]

    # nearest future (for Black-76 underlying price)
    futs = [i for i in nfo_instruments
            if i.get("name") == name and i.get("instrument_type") == "FUT"
            and isinstance(i.get("expiry"), dt.date) and i["expiry"] >= today]
    fut_token = int(sorted(futs, key=lambda x: x["expiry"])[0]["instrument_token"]) if futs else None

    return UnderlyingInstruments(
        name=name, expiry=expiry, step=step, lot=lot, legs=legs,
        future_token=fut_token, index_symbol=INDEX_SPOT_SYMBOL.get(name),
        all_strikes=strikes)


def window_tokens(ui: UnderlyingInstruments, atm: float, window: int) -> list[OptionLeg]:
    """Legs within ATM ± window·step (keeps tick load bounded)."""
    lo, hi = atm - window * ui.step, atm + window * ui.step
    return [leg for leg in ui.legs if lo <= leg.strike <= hi]


def _infer_step(strikes: list[float]) -> float | None:
    if len(strikes) < 2:
        return None
    diffs = sorted(strikes[i + 1] - strikes[i] for i in range(len(strikes) - 1))
    return diffs[len(diffs) // 2]
