"""OI-based analytics: side totals, PCR, support/resistance, OI-buildup.

Covers the workbook's OCI / New OCI / OBS aggregations and the AU/AX/AY
support-resistance blocks, plus the standard OI-buildup classification
(rigorous version of the sheet's decay/buildup intent — **[IMPROVED]**).
"""
from __future__ import annotations

import numpy as np


def side_totals(ce_oi, pe_oi, ce_vol, pe_vol, ce_chg, pe_chg) -> dict:
    return {
        "ce_oi": float(np.nansum(ce_oi)),
        "pe_oi": float(np.nansum(pe_oi)),
        "ce_volume": float(np.nansum(ce_vol)),
        "pe_volume": float(np.nansum(pe_vol)),
        "ce_oi_change": float(np.nansum(ce_chg)),
        "pe_oi_change": float(np.nansum(pe_chg)),
    }


def pcr(totals: dict) -> dict:
    def _r(n, d):
        return float(n / d) if d else None
    return {
        "pcr_oi": _r(totals["pe_oi"], totals["ce_oi"]),
        "pcr_volume": _r(totals["pe_volume"], totals["ce_volume"]),
        "pcr_oi_change": _r(totals["pe_oi_change"], totals["ce_oi_change"]),
    }


def _top2(strikes, values):
    """Strike of largest and 2nd-largest value (workbook MAX + LARGE(,2))."""
    strikes = np.asarray(strikes, dtype=float)
    values = np.asarray(values, dtype=float)
    if strikes.size == 0 or np.all(np.isnan(values)):
        return None, None
    order = np.argsort(np.nan_to_num(values, nan=-np.inf))[::-1]
    first = float(strikes[order[0]])
    second = float(strikes[order[1]]) if strikes.size > 1 else None
    return first, second


def support_resistance(strikes, ce_oi, pe_oi, ce_chg, pe_chg) -> dict:
    r1, r2 = _top2(strikes, ce_oi)      # calls => resistance
    s1, s2 = _top2(strikes, pe_oi)      # puts  => support
    r_fresh, _ = _top2(strikes, ce_chg)
    s_fresh, _ = _top2(strikes, pe_chg)
    return {
        "resistance_1": r1, "resistance_2": r2,
        "support_1": s1, "support_2": s2,
        "resistance_fresh": r_fresh, "support_fresh": s_fresh,
    }


def classify_buildup(price_change: float, oi_change: float,
                     eps: float = 0.0) -> str:
    """price↑OI↑=Long buildup, price↓OI↑=Short buildup,
    price↑OI↓=Short covering, price↓OI↓=Long unwinding."""
    if oi_change > eps and price_change > eps:
        return "Long Buildup"
    if oi_change > eps and price_change < -eps:
        return "Short Buildup"
    if oi_change < -eps and price_change > eps:
        return "Short Covering"
    if oi_change < -eps and price_change < -eps:
        return "Long Unwinding"
    return "Neutral"
