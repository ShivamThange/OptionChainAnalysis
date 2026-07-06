"""IV analytics — skew curve around ATM, IV squeeze, and IV-diff signal.

Mirrors the IV sheet: per-strike CE/PE IV around ATM (±step, ±2·step), the
ATM-IV vs baseline "squeeze", and the call/put IV diff signal (AD4 = AC4-AB4).
"""
from __future__ import annotations

import numpy as np


def iv_at(strikes, ivs, target) -> float | None:
    strikes = np.asarray(strikes, dtype=float)
    ivs = np.asarray(ivs, dtype=float)
    if strikes.size == 0:
        return None
    i = int(np.argmin(np.abs(strikes - target)))
    v = ivs[i]
    return float(v) if v is not None and not np.isnan(v) else None


def skew_curve(strikes, ce_iv, pe_iv, atm, step, span: int = 2) -> list[dict]:
    """CE/PE IV at ATM and ±span steps (the IV sheet's small skew table)."""
    out = []
    for k in range(-span, span + 1):
        target = atm + k * step
        out.append({
            "strike": float(target),
            "offset": k,
            "ce_iv": iv_at(strikes, ce_iv, target),
            "pe_iv": iv_at(strikes, pe_iv, target),
        })
    return out


def atm_iv(strikes, ce_iv, pe_iv, atm, step, n: int = 3) -> dict:
    """Average IV over the n strikes nearest ATM (Greeks K36 uses ~3)."""
    strikes = np.asarray(strikes, dtype=float)
    order = np.argsort(np.abs(strikes - atm))[:n]
    ce = np.asarray(ce_iv, dtype=float)[order]
    pe = np.asarray(pe_iv, dtype=float)[order]
    ce_m = float(np.nanmean(ce)) if np.any(~np.isnan(ce)) else None
    pe_m = float(np.nanmean(pe)) if np.any(~np.isnan(pe)) else None
    both = [v for v in (ce_m, pe_m) if v is not None]
    return {
        "atm_ce_iv": ce_m,
        "atm_pe_iv": pe_m,
        "atm_iv": float(np.mean(both)) if both else None,
    }


def iv_signals(atm_ce_iv, atm_pe_iv, baseline_ce_iv=None,
               baseline_pe_iv=None) -> dict:
    """Call/put IV diff + squeeze vs stored baseline (IV sheet W3/Z3/AD4)."""
    iv_diff = None
    if atm_ce_iv is not None and atm_pe_iv is not None:
        iv_diff = atm_ce_iv - atm_pe_iv
    squeeze_ce = (atm_ce_iv - baseline_ce_iv
                  if atm_ce_iv is not None and baseline_ce_iv is not None else None)
    squeeze_pe = (atm_pe_iv - baseline_pe_iv
                  if atm_pe_iv is not None and baseline_pe_iv is not None else None)
    # IV skew sentiment: call IV richer than put IV => bullish call demand
    if iv_diff is None:
        skew = "NEUTRAL"
    elif iv_diff > 0:
        skew = "CALL IV RICH"
    elif iv_diff < 0:
        skew = "PUT IV RICH"
    else:
        skew = "NEUTRAL"
    return {
        "iv_diff": iv_diff,
        "iv_squeeze_ce": squeeze_ce,
        "iv_squeeze_pe": squeeze_pe,
        "iv_skew_signal": skew,
    }
