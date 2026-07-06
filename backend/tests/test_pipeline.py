"""End-to-end engine test: build a chain from the golden NIFTY block and run
the full snapshot pipeline. Validates structure + sanity of aggregate metrics."""
import json
from pathlib import Path

import pytest

from app.engine.index_calc import atm_strike, expected_move
from app.engine.pipeline import compute_snapshot
from app.engine.types import ChainInputs, Quote, StrikeRow

FIX = Path(__file__).parent / "fixtures" / "golden_workbook.json"


@pytest.fixture(scope="module")
def golden():
    return json.loads(FIX.read_text())


def _build_inputs(golden) -> ChainInputs:
    g = golden["greeks_inputs"]
    S, r, q, T = g["spot_E7"], g["rate_G7"] / 100, g["div_H7"] / 100, g["days_N7"] / 365
    ce = golden["underlyings"]["NIFTY"]["ce"]
    pe = golden["underlyings"]["NIFTY"]["pe"]
    by_strike: dict[float, StrikeRow] = {}
    for leg_rows, side in [(ce, "ce"), (pe, "pe")]:
        for rec in leg_rows:
            k = rec["strike"]
            if not k:
                continue
            row = by_strike.setdefault(k, StrikeRow(strike=k))
            q_obj = Quote(
                ltp=rec["ltp"] or 0.0, oi=rec["oi"] or 0.0,
                oi_change=rec["oi_change"] or 0.0, volume=rec["noc"] or 0.0,
                atp=rec["atp"] or 0.0, iv_feed=rec["iv_feed"])
            setattr(row, side, q_obj)
    strikes = [by_strike[k] for k in sorted(by_strike)]
    atm = atm_strike(S, 50)
    return ChainInputs(underlying="NIFTY", spot=S, strikes=strikes, r=r, q=q,
                       t_years=T, step=50, atm=atm,
                       india_vix=golden["index"]["india_vix"],
                       lot_size=50, is_future_underlying=False)


def test_snapshot_structure_and_sanity(golden):
    snap = compute_snapshot(_build_inputs(golden), iv_threshold=20.0)

    assert snap["underlying"] == "NIFTY"
    assert len(snap["chain"]) == 40
    # PCR present and positive
    assert snap["pcr"]["pcr_oi"] and snap["pcr"]["pcr_oi"] > 0
    # max pain is one of the listed strikes
    strikes = [c["strike"] for c in snap["chain"]]
    assert snap["max_pain"] in strikes
    # support < resistance region sanity (support from puts below, resistance above)
    sr = snap["support_resistance"]
    assert sr["support_1"] is not None and sr["resistance_1"] is not None
    # ATM IV computed for the near-ATM strikes
    assert snap["atm_iv"]["atm_iv"] is not None
    # OTM CE strikes (real time value, liquid) must all solve for IV + greeks.
    # (Deep-ITM quotes can sit below discounted intrinsic and legitimately yield
    #  no IV — that is expected, not a bug.)
    atm = snap["atm"]
    solved = 0
    for c in snap["chain"]:
        leg = c["ce"]
        if leg["ltp"] and leg["ltp"] > 1 and atm <= c["strike"] <= atm + 5 * snap["step"]:
            assert leg["iv"] is not None, f"no IV at CE {c['strike']}"
            assert leg["delta"] is not None
            solved += 1
    assert solved >= 3


def test_expected_move_matches_excel(golden):
    idx = golden["index"]
    # Excel's INDEX!M22 reference for the bands is the spot, not the ATM strike.
    em = expected_move(idx["nifty_spot"], idx["india_vix"], idx["em_days_basis"])
    assert em["sigma_pct"] == pytest.approx(idx["em_sigma_pct"], rel=1e-9)
    assert em["upper"] == pytest.approx(idx["em_upper"], rel=1e-9)
    assert em["lower"] == pytest.approx(idx["em_lower"], rel=1e-9)


def test_max_pain_is_true_minimizer(golden):
    snap = compute_snapshot(_build_inputs(golden))
    curve = {p["strike"]: p["pain"] for p in snap["pain_curve"]}
    mp_strike = snap["max_pain"]
    assert curve[mp_strike] == min(curve.values())
