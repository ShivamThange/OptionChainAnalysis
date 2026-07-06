# Option Chain Live Dashboard

A high-performance, local option-chain analytics dashboard that replaces the
`Option Chain Algo D1-MAV2.xlsm` workbook. It ingests **live** market data
(Kite Connect real-time primary + NSE public fallback) and rebuilds every metric
from the workbook — Max Pain, PCR, OI buildup, support/resistance, Greeks, IV
skew/squeeze, expected-move bands, premium decay, Bollinger bands, and the
directional signals — with the math corrected/optimized where provably better.

See [`docs/METRICS_SPEC.md`](docs/METRICS_SPEC.md) for the full, cell-verified
metric definitions.

## Architecture

```
Kite (real-time)  ─┐
                   ├─► provider manager ─► live state ─► analytics engine ─► WebSocket ─► React UI
NSE (fallback)    ─┘                          │                                            (REST for history)
                                              └─► snapshot scheduler ─► SQLite (history)
```

- **backend/** — Python 3.11 + FastAPI + asyncio. Providers, Black-76/BSM engine
  (NumPy/SciPy, Newton–Raphson IV), SQLite (WAL) time-series, snapshot scheduler.
- **frontend/** — React + Vite + TypeScript, tuned for high-frequency delta
  updates (zustand selective subscriptions, virtualized grid, canvas charts).

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the frontend)
- **Kite Connect** subscription (https://kite.trade) for real-time data —
  *optional to start*. Without it the app runs on NSE public data (delayed,
  rate-limited). There is **no auth bypass**: Kite stays dormant until you set
  `KITE_API_KEY`/`KITE_API_SECRET`.

## Setup

### Backend
```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # edit as needed
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

## Enabling Kite Connect (when you buy it)

1. Subscribe to Kite Connect and create an app at https://developers.kite.trade
   to get **API key** and **API secret**.
2. (Recommended) Enable **external TOTP** 2FA on your Zerodha account and copy
   the base32 secret — lets the backend auto-refresh the daily access token.
3. Put `KITE_API_KEY`, `KITE_API_SECRET`, `KITE_USER_ID`, `KITE_PASSWORD`,
   `KITE_TOTP_SECRET` in `backend/.env`. Set `DATA_PROVIDER=kite` (or leave
   `auto`). The app switches to real-time websocket ticks; NSE remains the
   automatic fallback.

## Validation against the workbook

The engine is unit-tested against Excel's own cached numbers:
```bash
cd backend
python tests/extract_golden.py "path/to/Option Chain Algo D1-MAV2.xlsm"  # regenerate fixture
pytest
```

## Notes on the original workbook

- The "live data" was an **RTD datafeed add-in** (fields keyed by NSE token),
  not a scraper. The VBA contained **no analytics** — only snapshot/autosave/
  recalc timers, all replaced here by the backend + DB + scheduler.
- All 34 "external links" were stale references to old workbook copies.
