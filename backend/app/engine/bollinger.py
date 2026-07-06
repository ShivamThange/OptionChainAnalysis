"""Bollinger Bands (BB sheet) on any tracked series."""
from __future__ import annotations

import numpy as np


def bollinger(series, n: int = 20, k: float = 2.0) -> dict:
    """SMA ± k·stdev over the last n points. Uses population stdev (matches
    Excel STDEVP-style band width used on OI/PCR/price series)."""
    x = np.asarray([v for v in series if v is not None], dtype=float)
    if x.size == 0:
        return {"mid": None, "upper": None, "lower": None, "n": 0}
    window = x[-n:]
    mid = float(np.mean(window))
    sd = float(np.std(window))  # population stdev
    return {
        "mid": mid,
        "upper": mid + k * sd,
        "lower": mid - k * sd,
        "n": int(window.size),
    }
