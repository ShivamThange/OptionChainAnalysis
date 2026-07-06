"""Recompute orchestrator — assembles the full metric snapshot for one expiry.

`compute_snapshot(inputs, prev)` runs every engine module and returns a plain
dict ready to serialize to the frontend. `prev` carries cross-snapshot state
(baseline IV for squeeze, previous straddle for decay).
"""
from __future__ import annotations

import numpy as np

from . import iv as iv_mod
from . import maxpain as mp
from . import oi_buildup as oib
from . import signals as sig
from .chain import enrich_chain
from .decay import coi_per_volume, decay_step, straddle_premium
from .index_calc import expected_move
from .types import ChainInputs


def _arr(strikes, pick):
    return np.array([pick(r) for r in strikes], dtype=float)


def compute_snapshot(inp: ChainInputs, prev: dict | None = None,
                     iv_threshold: float = 20.0) -> dict:
    prev = prev or {}
    enrich_chain(inp)

    rows = inp.strikes
    strikes = _arr(rows, lambda r: r.strike)
    ce_oi = _arr(rows, lambda r: r.ce.oi or 0.0)
    pe_oi = _arr(rows, lambda r: r.pe.oi or 0.0)
    ce_vol = _arr(rows, lambda r: r.ce.volume or 0.0)
    pe_vol = _arr(rows, lambda r: r.pe.volume or 0.0)
    ce_chg = _arr(rows, lambda r: r.ce.oi_change or 0.0)
    pe_chg = _arr(rows, lambda r: r.pe.oi_change or 0.0)
    ce_iv = _arr(rows, lambda r: r.ce_iv if r.ce_iv is not None else np.nan)
    pe_iv = _arr(rows, lambda r: r.pe_iv if r.pe_iv is not None else np.nan)

    totals = oib.side_totals(ce_oi, pe_oi, ce_vol, pe_vol, ce_chg, pe_chg)
    pcr = oib.pcr(totals)
    sr = oib.support_resistance(strikes, ce_oi, pe_oi, ce_chg, pe_chg)
    maxpain = mp.max_pain(strikes, ce_oi, pe_oi, inp.lot_size)
    mp_bias = mp.max_pain_bias(strikes, ce_oi, pe_oi, inp.atm)

    atm_iv_d = iv_mod.atm_iv(strikes, ce_iv, pe_iv, inp.atm, inp.step)
    iv_sig = iv_mod.iv_signals(
        atm_iv_d["atm_ce_iv"], atm_iv_d["atm_pe_iv"],
        prev.get("baseline_ce_iv"), prev.get("baseline_pe_iv"))
    skew = iv_mod.skew_curve(strikes, ce_iv, pe_iv, inp.atm, inp.step)
    em = expected_move(inp.spot, inp.india_vix)

    # summed theta pools for writer-strength (Greeks L37)
    sum_ce_theta = sum((r.ce_greeks.theta for r in rows if r.ce_greeks), 0.0)
    sum_pe_theta = sum((r.pe_greeks.theta for r in rows if r.pe_greeks), 0.0)

    ce_pe_active = sig.ce_pe_active(ce_oi, pe_oi, ce_chg, pe_chg)
    signals = {
        "ce_pe_active": ce_pe_active,
        "option_buy_sell": sig.option_buy_sell(atm_iv_d["atm_iv"], iv_threshold),
        "writer_strength": sig.writer_strength(sum_ce_theta, sum_pe_theta),
        "max_pain_bias": mp_bias,
        "composite_bias": sig.composite_bias(pcr["pcr_oi"], mp_bias, ce_pe_active),
    }

    # ATM straddle & decay
    def _ltp_at(side_oi_getter):
        i = int(np.argmin(np.abs(strikes - inp.atm)))
        return rows[i]
    atm_row = rows[int(np.argmin(np.abs(strikes - inp.atm)))]
    straddle = straddle_premium(atm_row.ce.ltp, atm_row.pe.ltp)

    # serialize per-strike table
    chain = []
    for r in rows:
        chain.append({
            "strike": r.strike,
            "ce": _leg(r.ce, r.ce_iv, r.ce_greeks, r.ce_buildup),
            "pe": _leg(r.pe, r.pe_iv, r.pe_greeks, r.pe_buildup),
            "total_oi": r.total_oi,
        })

    return {
        "underlying": inp.underlying,
        "spot": inp.spot,
        "atm": inp.atm,
        "step": inp.step,
        "t_years": inp.t_years,
        "chain": chain,
        "totals": totals,
        "pcr": pcr,
        "support_resistance": sr,
        "max_pain": maxpain["max_pain"],
        "pain_curve": maxpain["pain_curve"],
        "total_oi_curve": maxpain["total_oi_curve"],
        "atm_iv": atm_iv_d,
        "iv_signals": iv_sig,
        "iv_skew": skew,
        "expected_move": em,
        "straddle": {
            "premium": straddle,
            "decay": decay_step(straddle, prev.get("straddle_premium")),
        },
        "theta_pool": {"ce": sum_ce_theta, "pe": sum_pe_theta},
        "signals": signals,
        # cross-snapshot state to persist for next recompute
        "_state": {
            "baseline_ce_iv": prev.get("baseline_ce_iv", atm_iv_d["atm_ce_iv"]),
            "baseline_pe_iv": prev.get("baseline_pe_iv", atm_iv_d["atm_pe_iv"]),
            "straddle_premium": straddle,
        },
    }


def _leg(q, iv, g, buildup) -> dict:
    return {
        "ltp": q.ltp, "oi": q.oi, "oi_change": q.oi_change,
        "volume": q.volume, "atp": q.atp, "atp_minus_ltp": (q.atp or 0.0) - (q.ltp or 0.0),
        "bid": q.bid, "ask": q.ask, "iv": iv,
        "delta": g.delta if g else None, "gamma": g.gamma if g else None,
        "theta": g.theta if g else None, "vega": g.vega if g else None,
        "buildup": buildup,
    }
