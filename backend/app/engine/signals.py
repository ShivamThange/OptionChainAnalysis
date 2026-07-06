"""Directional signals — CE/PE active, option buy/sell, writer strength.

Mirrors the workbook's signal cells (Option Chain AY13/AZ93, Greeks K36/L35,
L37). Thresholds are configurable but default to the sheet's values.
"""
from __future__ import annotations

import numpy as np


def ce_pe_active(ce_oi, pe_oi, ce_chg, pe_chg) -> str:
    """AY13/AZ93: which side is adding dominant OI (writers active).

    Sheet compares top-2 OI concentration + OI-change on each side. We reduce it
    to: the side whose total OI *and* fresh OI-change dominates is "active".
    """
    ce_oi_t = float(np.nansum(ce_oi)); pe_oi_t = float(np.nansum(pe_oi))
    ce_chg_t = float(np.nansum(ce_chg)); pe_chg_t = float(np.nansum(pe_chg))
    if ce_oi_t > pe_oi_t and ce_chg_t > pe_chg_t:
        return "CE ACTIVE"      # call writing dominant -> bearish/resistance
    if pe_oi_t > ce_oi_t and pe_chg_t > ce_chg_t:
        return "PE ACTIVE"      # put writing dominant -> bullish/support
    return ""


def option_buy_sell(atm_iv: float | None, threshold: float = 20.0) -> str:
    """Greeks K36/L35: avg ATM IV < thr => OPTION BUY, > thr => OPTION SELL."""
    if atm_iv is None:
        return ""
    if atm_iv < threshold:
        return "OPTION BUY"
    if atm_iv > threshold:
        return "OPTION SELL"
    return ""


def writer_strength(sum_ce_theta: float, sum_pe_theta: float) -> str:
    """Greeks L37: compare summed CE vs PE theta (decay each writer earns).

    Theta is negative for long options; the writer earns |theta|. The side with
    the larger absolute theta pool is where writing dominates.
    """
    ce = abs(sum_ce_theta)
    pe = abs(sum_pe_theta)
    if ce > pe:
        return "CALL WRITER STRONG"
    if pe > ce:
        return "PUT WRITER STRONG"
    return ""


def composite_bias(pcr_oi, max_pain_bias, ce_pe_active_signal) -> str:
    """Roll the independent tells into one headline bias.

    PCR>1 (heavy puts) is bullish; PCR<1 bearish. Combined with the max-pain
    ladder and the active-side signal via simple majority vote.
    """
    votes = 0
    if pcr_oi is not None:
        votes += 1 if pcr_oi > 1.0 else -1
    if max_pain_bias == "MAX PAIN BULLISH":
        votes += 1
    elif max_pain_bias == "MAX PAIN BEARISH":
        votes -= 1
    if ce_pe_active_signal == "PE ACTIVE":
        votes += 1
    elif ce_pe_active_signal == "CE ACTIVE":
        votes -= 1
    if votes > 0:
        return "BULLISH"
    if votes < 0:
        return "BEARISH"
    return "NEUTRAL"
