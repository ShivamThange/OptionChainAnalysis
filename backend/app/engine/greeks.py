"""Option pricing & Greeks — Black-Scholes-Merton and Black-76, vectorized.

Matches the workbook's Greeks sheet formulas cell-for-cell (validated against
`golden_workbook.json`), and adds a Newton-Raphson implied-vol solver so we can
compute IV for *every* strike (the RTD feed only supplied it for OTM strikes).

Conventions:
  - `sigma`, `r`, `q` are fractions (0.10 == 10%).
  - `t` is time to expiry in years.
  - `vega` is per 1 percentage-point of vol (workbook divides by 100).
  - `theta` is per calendar day (workbook divides by 365).
All functions accept scalars or NumPy arrays and broadcast.
"""
from __future__ import annotations

import numpy as np
from scipy.special import ndtr  # fast, vectorized standard-normal CDF

from .types import Greeks, OptionType

SQRT_2PI = np.sqrt(2.0 * np.pi)
_MIN_T = 1e-9
_MIN_SIG = 1e-9


def _norm_pdf(x):
    return np.exp(-0.5 * x * x) / SQRT_2PI


def d1_d2(s, k, sigma, r, q, t):
    """d1, d2 for Black-Scholes-Merton (spot underlying with yield q).

    For Black-76 (option on a future) pass q = r and s = future price.
    """
    s = np.asarray(s, dtype=float)
    k = np.asarray(k, dtype=float)
    sigma = np.maximum(np.asarray(sigma, dtype=float), _MIN_SIG)
    t = np.maximum(np.asarray(t, dtype=float), _MIN_T)
    vol_sqrt_t = sigma * np.sqrt(t)
    d1 = (np.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def price(s, k, sigma, r, q, t, opt: OptionType):
    """Theoretical option price (BSM). Black-76 => call with q=r, s=future."""
    d1, d2 = d1_d2(s, k, sigma, r, q, t)
    disc_q = np.exp(-q * t)
    disc_r = np.exp(-r * t)
    if opt == OptionType.CE:
        return s * disc_q * ndtr(d1) - k * disc_r * ndtr(d2)
    return k * disc_r * ndtr(-d2) - s * disc_q * ndtr(-d1)


def greeks(s, k, sigma, r, q, t, opt: OptionType) -> Greeks:
    """Full Greeks for a single strike/leg (scalar)."""
    d1, d2 = d1_d2(s, k, sigma, r, q, t)
    d1 = float(d1); d2 = float(d2)
    sigma = max(float(sigma), _MIN_SIG)
    t = max(float(t), _MIN_T)
    sqrt_t = np.sqrt(t)
    disc_q = np.exp(-q * t)
    disc_r = np.exp(-r * t)
    pdf_d1 = _norm_pdf(d1)

    gamma = disc_q * pdf_d1 / (s * sigma * sqrt_t)
    vega = s * disc_q * pdf_d1 * sqrt_t / 100.0            # per 1% vol
    common_theta = -(s * pdf_d1 * sigma * disc_q) / (2.0 * sqrt_t)

    if opt == OptionType.CE:
        delta = disc_q * ndtr(d1)
        theta = (common_theta - r * k * disc_r * ndtr(d2)
                 + q * s * disc_q * ndtr(d1)) / 365.0
        px = s * disc_q * ndtr(d1) - k * disc_r * ndtr(d2)
    else:
        delta = disc_q * (ndtr(d1) - 1.0)
        theta = (common_theta + r * k * disc_r * ndtr(-d2)
                 - q * s * disc_q * ndtr(-d1)) / 365.0
        px = k * disc_r * ndtr(-d2) - s * disc_q * ndtr(-d1)

    return Greeks(delta=float(delta), gamma=float(gamma), theta=float(theta),
                  vega=float(vega), price=float(px), d1=d1, d2=d2)


def implied_vol(market_price, s, k, r, q, t, opt: OptionType,
                tol: float = 1e-6, max_iter: int = 60) -> float | None:
    """Implied vol from market price via Newton-Raphson + bisection fallback.

    Seed with Brenner-Subrahmanyam (σ0 ≈ √(2π/T)·price/S), then Newton steps
    using analytic vega; if a step leaves the bracket or vega vanishes, fall
    back to bisection. Returns fraction, or None if no sane root (e.g. price
    below intrinsic).
    """
    market_price = float(market_price)
    s = float(s); k = float(k); t = float(t)
    if market_price <= 0.0 or t <= _MIN_T or s <= 0.0:
        return None

    # intrinsic (discounted) floor — below this there is no positive-vol root
    disc_r = np.exp(-r * t)
    disc_q = np.exp(-q * t)
    intrinsic = (max(s * disc_q - k * disc_r, 0.0) if opt == OptionType.CE
                 else max(k * disc_r - s * disc_q, 0.0))
    if market_price < intrinsic - 1e-6:
        return None

    lo, hi = 1e-4, 5.0                       # 0.01% .. 500%
    sigma = max(np.sqrt(2.0 * np.pi / t) * market_price / s, 1e-3)
    sigma = min(max(sigma, lo), hi)

    for _ in range(max_iter):
        diff = float(price(s, k, sigma, r, q, t, opt)) - market_price
        if abs(diff) < tol:
            return float(sigma)
        # tighten bracket using monotonicity of price in sigma
        if diff > 0:
            hi = sigma
        else:
            lo = sigma
        g = greeks(s, k, sigma, r, q, t, opt)
        vega_abs = g.vega * 100.0            # convert back to per-unit vol
        if vega_abs < 1e-8:
            sigma = 0.5 * (lo + hi)          # vega ~0 -> bisect
            continue
        step = diff / vega_abs
        new_sigma = sigma - step
        if not (lo < new_sigma < hi):        # left the bracket -> bisect
            new_sigma = 0.5 * (lo + hi)
        sigma = new_sigma

    # final bisection polish
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        diff = float(price(s, k, mid, r, q, t, opt)) - market_price
        if abs(diff) < tol:
            return float(mid)
        if diff > 0:
            hi = mid
        else:
            lo = mid
    return float(0.5 * (lo + hi))


def implied_vol_vector(prices, s, strikes, r, q, t, opt: OptionType):
    """Vectorized IV over an array of (price, strike). Loops the solver but is
    cheap for a single chain (~40-80 strikes) and keeps convergence robust."""
    prices = np.asarray(prices, dtype=float)
    strikes = np.asarray(strikes, dtype=float)
    out = np.full(prices.shape, np.nan)
    for i in range(prices.size):
        iv = implied_vol(prices[i], s, strikes[i], r, q, t, opt)
        if iv is not None:
            out[i] = iv
    return out
