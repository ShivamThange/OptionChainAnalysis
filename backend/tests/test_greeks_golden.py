"""Validate the Greeks engine against Excel's own cached values."""
import json
from pathlib import Path

import pytest

from app.engine.greeks import greeks, implied_vol
from app.engine.types import OptionType

FIX = Path(__file__).parent / "fixtures" / "golden_workbook.json"


@pytest.fixture(scope="module")
def golden():
    return json.loads(FIX.read_text())


def _inputs(golden):
    g = golden["greeks_inputs"]
    return g["spot_E7"], g["rate_G7"] / 100, g["div_H7"] / 100, g["days_N7"] / 365


def test_bsm_matches_excel_cached(golden):
    S, r, q, T = _inputs(golden)
    max_err = 0.0
    checked = 0
    for row in golden["greeks_rows"]:
        iv = row["ce_iv"]
        if not iv:
            continue
        g = greeks(S, row["strike"], iv / 100, r, q, T, OptionType.CE)
        for got, exp in [(g.d1, row["d1"]), (g.delta, row["delta"]),
                         (g.price, row["call_px"]), (g.vega, row["vega"]),
                         (g.theta, row["theta"])]:
            if exp is not None:
                max_err = max(max_err, abs(got - exp))
        checked += 1
    assert checked >= 10
    # Excel double precision — engine must match to ~1e-6
    assert max_err < 1e-6, f"max abs error {max_err}"


def test_implied_vol_round_trip(golden):
    S, r, q, T = _inputs(golden)
    for row in golden["greeks_rows"]:
        iv = row["ce_iv"]
        if not iv:
            continue
        px = greeks(S, row["strike"], iv / 100, r, q, T, OptionType.CE).price
        rec = implied_vol(px, S, row["strike"], r, q, T, OptionType.CE)
        assert rec is not None
        assert abs(rec * 100 - iv) < 1e-3, f"strike {row['strike']}: {rec*100} vs {iv}"


def test_implied_vol_below_intrinsic_is_none(golden):
    S, r, q, T = _inputs(golden)
    # price below intrinsic -> no valid IV
    assert implied_vol(0.01, S, S - 2000, r, q, T, OptionType.CE) is None
