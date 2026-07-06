# Metrics Specification — reverse-engineered from `Option Chain Algo D1-MAV2.xlsm`

This is the **source of truth** for the analytics engine. Every metric below is
derived from the workbook's actual cell formulas (verified against the cached
values now stored in `backend/tests/fixtures/golden_workbook.json`). Where we
deliberately improve on the sheet, it is marked **[IMPROVED]** with the reason.

Sheet → engine module mapping is in the plan. All strike aggregations in the
sheet are `SUMIF(strike_range, K, value_range)`; because each strike appears
once per side, these are just per-strike lookups in code.

---

## 0. Data model (per underlying, per expiry)

Option Chain sheet block layout (confirmed):

| Underlying | Future row | CE rows | PE rows | Strike step |
|-----------|-----------|---------|---------|-------------|
| NIFTY     | 2         | 8–47    | 48–87   | 50          |
| BANKNIFTY | —         | 88–127  | 128–167 | 100         |

Per strike we ingest: `strike, ltp, oi, oi_change, %oi_change, iv_feed, atp
(avg price), noc (no. of contracts = volume proxy), bid, ask, volume`.

> **Note on IV:** the RTD feed only populated IV for OTM strikes (0/blank for
> ITM). We therefore **[IMPROVED]** compute IV ourselves for every strike (see
> §4), which the sheet could not.

---

## 1. Option Chain derived columns

- `ATP_minus_LTP = atp - ltp`  (Option Chain `AT = U - G`). Momentum tell:
  ATP>LTP → price fading intraday; ATP<LTP → price rising.
- `OI_per_NOC = oi / noc`  (col `BC`), `ChgOI_per_NOC = oi_change / noc` (`BD`).
- `SIGNAL` (`BE`) — composite of the signals in §3.
- Totals per side: `sum_CE_OI, sum_PE_OI, sum_CE_vol, sum_PE_vol,
  sum_CE_chgOI, sum_PE_chgOI` (`AW8/AX8`, `AW11/AX11`, `AW26/AW26`…).

## 2. Max Pain, PCR, Support/Resistance

- **PCR (OI)** = `sum_PE_OI / sum_CE_OI`.  **PCR (volume)** = `sum_PE_vol /
  sum_CE_vol`. (Standard; sheet tracks the component sums.)
- **Support / Resistance** (sheet `AU/AX/AY` blocks via `MAX` + 2nd `LARGE`):
  - Resistance-1 = strike of `MAX(CE_OI)`; Resistance-2 = strike of 2nd largest.
  - Support-1 = strike of `MAX(PE_OI)`; Support-2 = strike of 2nd largest.
  - Also max **OI-change** strikes (fresh positions) via `MAX(chgOI)`.
- **Max Pain** — **[IMPROVED]**. Sheet uses `BA = CE_OI + PE_OI` per strike and
  eyeballs the min/ladder. We compute the textbook version: for each candidate
  expiry price `E` in the strike set,
  `pain(E) = Σ_K CE_OI[K]·max(E−K,0) + Σ_K PE_OI[K]·max(K−E,0)` (× lot),
  max-pain strike = `argmin_E pain(E)`. We **also expose** the sheet's
  `CE_OI+PE_OI` per-strike series for parity/plots.
- **Max Pain Bullish/Bearish** (`AZ17`, `BA98`): from the ordered OI ladder
  around ATM — three-point monotonic check:
  - decreasing (`v3<v2<v1`) → `MAX PAIN BEARISH`
  - increasing (`v3>v2>v1`) → `MAX PAIN BULLISH`
  - else `NO SIGNAL`.

## 3. Directional signals

- **CE / PE ACTIVE** (`AY13`, `AZ93`): compares top-2 OI (or NOC) concentration
  on each side:
  `IF(AND(ce1>ce2, ce_x>ce_y), "CE ACTIVE", IF(AND(pe1<pe2,…),"PE ACTIVE",""))`.
  Interpretation: which side is adding dominant open interest → writers active.
- **OPTION BUY / SELL** (Greeks `K36`,`L35`): `avg ATM IV` over the 3 strikes
  nearest ATM. `<20 → OPTION BUY`, `>20 → OPTION SELL` (threshold configurable,
  `IV_BUY_SELL_THRESHOLD`). Rationale: low IV favours long options, high IV
  favours writing.
- **CALL / PUT WRITER STRONG** (Greeks `L37`): `Σ CE theta` vs `Σ PE theta`
  (`E34` vs `Q34`). If call-side decay dominates → `CALL WRITER STRONG`, else
  `PUT WRITER STRONG`.
- **OI-buildup classification** — **[IMPROVED]** (New OCI / OBS intent, made
  rigorous). Per strike from Δprice vs Δoi:
  - price ↑ & OI ↑ → **Long buildup**
  - price ↓ & OI ↑ → **Short buildup**
  - price ↑ & OI ↓ → **Short covering**
  - price ↓ & OI ↓ → **Long unwinding**

## 4. Greeks & IV (Greeks sheet — full Black-Scholes, verified)

Inputs (Greeks row 7, from INDEX): `S` = spot/future, `r = G7/100`,
`q = H7/100`, `T = N7/365` where `N7` = calendar days to expiry with the
weekly-expiry weekday adjustment. Golden snapshot used `r=0.10, q=0, T=1/365`.

Per strike `K`, with vol `σ` (as fraction):

```
d1 = ( ln(S/K) + (r - q + σ²/2)·T ) / ( σ·√T )      # Greeks AG11
d2 = d1 - σ·√T                                        # Greeks AH11
delta_call = e^(-qT)·N(d1)                            # G11
delta_put  = e^(-qT)·(N(d1) - 1)                      # O11
gamma      = e^(-qT)·φ(d1) / (S·σ·√T)                 # F11
vega       = S·e^(-qT)·φ(d1)·√T / 100                 # D11  (per 1% vol)
theta_call = [ -S·φ(d1)·σ·e^(-qT)/(2√T)
               - r·K·e^(-rT)·N(d2) + q·S·e^(-qT)·N(d1) ] / 365   # E11
call_px    = S·e^(-qT)·N(d1) - K·e^(-rT)·N(d2)        # H11
put_px     = K·e^(-rT)·N(-d2) - S·e^(-qT)·N(-d1)      # N11
```

`N` = standard normal CDF (`NORMSDIST`), `φ` = normal PDF.
**Validation anchor** (ATM K=16250): d1=0.152788, delta=0.560717,
call_px=42.2483, vega=3.3557, theta≈−19.9.

- **[IMPROVED] Black-76** for options on futures (`S` = future price, drift term
  drops the `-q`; discount both legs by `e^(-rT)`). Selectable per underlying.
- **[IMPROVED] Implied Vol by Newton–Raphson** from the option's market price
  (instead of the noisy/absent feed IV): seed with Brenner–Subrahmanyam
  `σ₀ ≈ √(2π/T)·(price/S)`, iterate `σ ← σ − (BS(σ)−mkt)/vega` until
  `|BS(σ)−mkt| < tol`; clamp to `[0.1%, 500%]`, fall back to bisection on
  non-convergence. Vectorized over the chain with NumPy/SciPy.

## 5. IV sheet — skew, squeeze, expected move

- Per-strike CE/PE IV around ATM (`ATM, ATM±50, ATM±100`) via SUMIF — becomes a
  small skew curve.
- **IV squeeze** (`W3/Z3`): current ATM IV vs a stored baseline (`Z1/AA1`);
  `diff = current − baseline`. Persist baseline in the time-series store.
- **CALL/PUT IV diff** and **IV SIGNAL** (`AD4 = AC4 − AB4`): call-IV vs put-IV
  skew sign → sentiment.
- **Expected move** (INDEX `AA22/AB22/AC22`): `σ% = VIX / √(days_basis)` (sheet
  uses `Z22=365`; a 1-day/annual toggle is exposed), `upper = ATM·(1+σ%/100)`,
  `lower = ATM·(1−σ%/100)`. Validation: VIX 13.21 → σ%=0.6914, bands
  16371.22 / 16146.38 around 16258.8.

## 6. Premium / Decay / ATM / Bollinger

- **ATM straddle premium** = `CE_ltp(ATM) + PE_ltp(ATM)`; tracked over time
  (ATM sheet history) → intraday decay curve.
- **Premium / Decay** (Premium, Decay sheets): per-strike CE/PE premium sampled
  on the snapshot cadence; `decay = premium[t] − premium[t−1]`; `COI/Vol` =
  `oi_change / volume`.
- **Bollinger Bands** (BB sheet): on a tracked series `x` (e.g. spot or PCR),
  `mid = SMA_n(x)`, `upper/lower = mid ± k·stdev_n(x)` (default `n=20, k=2`).

## 7. History / snapshots (replaces VBA `RECORD*`)

Periodic snapshots at 3/5/15-min cadence persist: per-strike chain, side totals,
PCR, max-pain, ATM straddle, ATM IV, signals. This replaces the `RECORD1/5/6/8/
25` copy-paste macros and the 5-min autosave — the DB *is* the history.
