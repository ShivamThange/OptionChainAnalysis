"""Index-level helpers: ATM strike, weekly-expiry date, expected-move bands.

Mirrors the INDEX sheet: ATM (M2/M5), expiry date `A25+IF(WEEKDAY=3,2,7)`,
and expected-move bands `AA22/AB22/AC22`.
"""
from __future__ import annotations

import datetime as dt
import math

# Excel's 1900 date system epoch (with the well-known leap-year off-by-one).
_EXCEL_EPOCH = dt.date(1899, 12, 30)


def excel_serial_to_date(serial: float) -> dt.date:
    return _EXCEL_EPOCH + dt.timedelta(days=int(serial))


def atm_strike(spot: float, step: float) -> float:
    """Nearest strike to spot on the strike grid."""
    return round(spot / step) * step


def next_weekly_expiry(today: dt.date) -> dt.date:
    """Workbook logic `A25 + IF(WEEKDAY(A25)=3, 2, 7)`.

    Excel WEEKDAY default: Sun=1..Sat=7, so 3 == Tuesday. If today is Tuesday,
    add 2 (Thursday of same week); otherwise add 7. Reproduced faithfully.
    (NSE weekly index expiry is Thursday; this matches the sheet's heuristic.)
    """
    excel_weekday = (today.weekday() + 2) % 7 or 7   # Mon(0)->2 ... Sun(6)->1
    add = 2 if excel_weekday == 3 else 7
    return today + dt.timedelta(days=add)


def time_to_expiry_years(today: dt.date, expiry: dt.date,
                         basis: float = 365.0) -> float:
    days = max((expiry - today).days, 0)
    # match the sheet's minimum of ~1 day so ATM Greeks never divide by zero
    return max(days, 1) / basis


def expected_move(price: float, india_vix: float, days_basis: float = 365.0) -> dict:
    """INDEX AA22/AB22/AC22 (bands are around the reference PRICE, i.e. spot).

    σ% = VIX / √(days_basis);  upper = price·(1+σ%/100);  lower = price·(1-σ%/100).
    (days_basis=365 reproduces the sheet; pass the trading days to expiry for a
    horizon-specific band.)
    """
    if india_vix is None or price is None:
        return {"sigma_pct": None, "upper": None, "lower": None}
    sigma_pct = india_vix / math.sqrt(days_basis)
    return {
        "sigma_pct": sigma_pct,
        "upper": price * (100.0 + sigma_pct) / 100.0,
        "lower": price * (100.0 - sigma_pct) / 100.0,
    }
