"""Premium / theta decay & ATM straddle tracking (Premium / Decay / ATM sheets).

These are time-dependent: they compare the current premium to the previous
snapshot. The pipeline threads the prior straddle/premium in from the store.
"""
from __future__ import annotations


def straddle_premium(ce_ltp_atm: float | None, pe_ltp_atm: float | None):
    if ce_ltp_atm is None or pe_ltp_atm is None:
        return None
    return ce_ltp_atm + pe_ltp_atm


def decay_step(current: float | None, previous: float | None):
    """Δpremium since last snapshot (negative => decaying)."""
    if current is None or previous is None:
        return None
    return current - previous


def coi_per_volume(oi_change: float, volume: float):
    """New OCI 'C Coi/Vol' / 'P Coi/Vol' — fresh OI added per unit volume."""
    if not volume:
        return None
    return oi_change / volume
