"""Max Pain.

The workbook eyeballs `CE_OI + PE_OI` per strike (`BA = X + X`). We compute the
textbook total-loss-minimisation max pain (the strike where option WRITERS lose
the least at expiry), and also return the sheet's per-strike total-OI series for
parity/plotting.
"""
from __future__ import annotations

import numpy as np


def max_pain(strikes, ce_oi, pe_oi, lot_size: float = 1.0) -> dict:
    """Return max-pain strike + pain curve.

    pain(E) = Σ_K CE_OI[K]·max(E-K,0) + Σ_K PE_OI[K]·max(K-E,0)   (× lot)
    evaluated at every listed strike E; min => max-pain.
    """
    strikes = np.asarray(strikes, dtype=float)
    ce_oi = np.asarray(ce_oi, dtype=float)
    pe_oi = np.asarray(pe_oi, dtype=float)
    if strikes.size == 0:
        return {"max_pain": None, "pain_curve": [], "total_oi_curve": []}

    # broadcast: rows = candidate expiry E, cols = strike K
    E = strikes[:, None]
    K = strikes[None, :]
    call_pain = np.maximum(E - K, 0.0) * ce_oi[None, :]
    put_pain = np.maximum(K - E, 0.0) * pe_oi[None, :]
    pain = (call_pain + put_pain).sum(axis=1) * lot_size

    idx = int(np.argmin(pain))
    total_oi = ce_oi + pe_oi
    return {
        "max_pain": float(strikes[idx]),
        "pain_curve": [
            {"strike": float(s), "pain": float(p)} for s, p in zip(strikes, pain)
        ],
        "total_oi_curve": [
            {"strike": float(s), "total_oi": float(o)}
            for s, o in zip(strikes, total_oi)
        ],
    }


def max_pain_bias(strikes, ce_oi, pe_oi, atm: float) -> str:
    """Workbook's monotonic-ladder bias (AZ17 / BA98) around ATM.

    Looks at total OI at ATM-step, ATM, ATM+step: strictly decreasing =>
    BEARISH, strictly increasing => BULLISH, else NO SIGNAL.
    """
    strikes = np.asarray(strikes, dtype=float)
    total = np.asarray(ce_oi, dtype=float) + np.asarray(pe_oi, dtype=float)
    if strikes.size < 3:
        return "NO SIGNAL"
    i = int(np.argmin(np.abs(strikes - atm)))
    if i == 0 or i == strikes.size - 1:
        return "NO SIGNAL"
    v1, v2, v3 = total[i - 1], total[i], total[i + 1]
    if v3 < v2 < v1:
        return "MAX PAIN BEARISH"
    if v3 > v2 > v1:
        return "MAX PAIN BULLISH"
    return "NO SIGNAL"
