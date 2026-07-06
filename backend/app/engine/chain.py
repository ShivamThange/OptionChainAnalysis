"""Per-strike enrichment: compute IV (Newton-Raphson) and Greeks for each leg.

Takes the raw ingested StrikeRows in a ChainInputs and fills ce_iv/pe_iv,
ce_greeks/pe_greeks, buildup labels, and total_oi. This is the compute-heavy
step; it runs on the debounced recompute cadence, not per tick.
"""
from __future__ import annotations

from . import greeks as gk
from .oi_buildup import classify_buildup
from .types import ChainInputs, OptionType


def enrich_chain(inp: ChainInputs) -> None:
    """Mutates inp.strikes in place with computed IV / Greeks / buildup."""
    s = inp.spot
    r, q, t = inp.r, inp.q, inp.t_years
    # Black-76 on a future => set q = r (drift cancels), keep s = future price.
    q_eff = r if inp.is_future_underlying else q

    for row in inp.strikes:
        row.total_oi = (row.ce.oi or 0.0) + (row.pe.oi or 0.0)

        # ---- CE leg ----
        if row.ce.ltp and row.ce.ltp > 0:
            iv = gk.implied_vol(row.ce.ltp, s, row.strike, r, q_eff, t, OptionType.CE)
            # prefer computed IV; fall back to feed IV only if solver failed
            if iv is None and row.ce.iv_feed:
                iv = row.ce.iv_feed / 100.0
            row.ce_iv = iv * 100.0 if iv is not None else None
            if iv is not None:
                row.ce_greeks = gk.greeks(s, row.strike, iv, r, q_eff, t, OptionType.CE)
        row.ce_buildup = classify_buildup(
            (row.ce.ltp or 0.0) - (row.ce.prev_close or 0.0), row.ce.oi_change or 0.0)

        # ---- PE leg ----
        if row.pe.ltp and row.pe.ltp > 0:
            iv = gk.implied_vol(row.pe.ltp, s, row.strike, r, q_eff, t, OptionType.PE)
            if iv is None and row.pe.iv_feed:
                iv = row.pe.iv_feed / 100.0
            row.pe_iv = iv * 100.0 if iv is not None else None
            if iv is not None:
                row.pe_greeks = gk.greeks(s, row.strike, iv, r, q_eff, t, OptionType.PE)
        row.pe_buildup = classify_buildup(
            (row.pe.ltp or 0.0) - (row.pe.prev_close or 0.0), row.pe.oi_change or 0.0)
