"""One-off: extract a golden dataset from the source workbook for validation.

Pulls the cached INPUT snapshot (the option-chain values the RTD feed had at
save time) *and* the cached COMPUTED outputs (Greeks, expected-move bands, ATM)
so the engine can be asserted against Excel's own numbers.

Usage:
    python backend/tests/extract_golden.py "path/to/Option Chain Algo D1-MAV2.xlsm"

Writes backend/tests/fixtures/golden_workbook.json
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Option Chain block layout (confirmed from the workbook):
#   NIFTY future  = row 2
#   NIFTY   CE    = rows 8..47      NIFTY   PE = rows 48..87
#   BANKNIFTY CE  = rows 88..127    BANKNIFTY PE = rows 128..167
BLOCKS = {
    "NIFTY": {"ce": (8, 47), "pe": (48, 87), "fut_row": 2},
    "BANKNIFTY": {"ce": (88, 127), "pe": (128, 167), "fut_row": None},
}
# Option Chain columns -> field
OC_COLS = {
    "Z": "strike", "G": "ltp", "X": "oi", "AD": "oi_change",
    "AG": "iv_feed", "U": "atp", "Y": "noc", "V": "volume",
}


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    out = []
    for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
        out.append("".join(t.text or "" for t in si.iter(NS + "t")))
    return out


def _load_sheet(z: zipfile.ZipFile, sheet: str, ss: list[str]) -> dict[str, str]:
    root = ET.fromstring(z.read(f"xl/worksheets/{sheet}.xml"))
    cells: dict[str, str] = {}
    for row in root.iter(NS + "row"):
        for c in row.findall(NS + "c"):
            v = c.find(NS + "v")
            if v is None:
                continue
            val = v.text
            if c.get("t") == "s" and val is not None:
                try:
                    val = ss[int(val)]
                except (ValueError, IndexError):
                    pass
            cells[c.get("r")] = val
    return cells


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def extract(path: str) -> dict:
    z = zipfile.ZipFile(path)
    ss = _shared_strings(z)
    oc = _load_sheet(z, "sheet1", ss)   # Option Chain
    idx = _load_sheet(z, "sheet2", ss)  # INDEX
    gr = _load_sheet(z, "sheet5", ss)   # Greeks

    def chain_block(lo, hi):
        rows = []
        for r in range(lo, hi + 1):
            rec = {f: _num(oc.get(f"{col}{r}")) for col, f in OC_COLS.items()}
            rows.append(rec)
        return rows

    data = {"underlyings": {}}
    for u, b in BLOCKS.items():
        data["underlyings"][u] = {
            "ce": chain_block(*b["ce"]),
            "pe": chain_block(*b["pe"]),
            "future_ltp": _num(oc.get(f"G{b['fut_row']}")) if b["fut_row"] else None,
        }

    # INDEX-sheet scalars (Greeks inputs + expected-move bands)
    data["index"] = {
        "nifty_spot": _num(idx.get("B2")),
        "nifty_atm": _num(idx.get("M2")),
        "banknifty_atm": _num(idx.get("M5")),
        "india_vix": _num(idx.get("B18")),
        "expiry_serial": _num(idx.get("B25")),
        "today_serial": _num(idx.get("C25")),
        "em_sigma_pct": _num(idx.get("AA22")),
        "em_upper": _num(idx.get("AB22")),
        "em_lower": _num(idx.get("AC22")),
        "em_days_basis": _num(idx.get("Z22")),
    }

    # Greeks-sheet inputs (row 7) and per-strike cached outputs (NIFTY block r11..r33)
    data["greeks_inputs"] = {
        "spot_E7": _num(gr.get("E7")),
        "rate_G7": _num(gr.get("G7")),      # r (percent)
        "div_H7": _num(gr.get("H7")),       # q (percent)
        "days_N7": _num(gr.get("N7")),      # calendar days to expiry (adjusted)
    }
    gcols = {"K": "strike", "J": "ce_iv", "AG": "d1", "AH": "d2", "G": "delta",
             "D": "vega", "E": "theta", "F": "gamma", "H": "call_px", "N": "put_px",
             "I": "ce_ltp"}
    greeks_rows = []
    for r in range(11, 34):
        rec = {name: _num(gr.get(f"{col}{r}")) for col, name in gcols.items()}
        if rec["strike"] is not None:
            greeks_rows.append(rec)
    data["greeks_rows"] = greeks_rows

    return data


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:/Users/thang/Downloads/Option Chain Algo D1-MAV2.xlsm"
    out_dir = Path(__file__).resolve().parent / "fixtures"
    out_dir.mkdir(parents=True, exist_ok=True)
    result = extract(src)
    out = out_dir / "golden_workbook.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    nifty = result["underlyings"]["NIFTY"]
    print(f"Wrote {out}")
    print(f"  NIFTY future LTP : {nifty['future_ltp']}")
    print(f"  NIFTY CE strikes : {len(nifty['ce'])}  PE strikes: {len(nifty['pe'])}")
    print(f"  Greeks inputs    : {result['greeks_inputs']}")
    print(f"  Greeks rows      : {len(result['greeks_rows'])}")
