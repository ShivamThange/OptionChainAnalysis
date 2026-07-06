"""NSE public option-chain provider (fallback / interim primary).

Polls NSE's public JSON endpoints. NSE requires a browser-like session: fetch
the site root once to obtain cookies, then hit the API with those cookies and a
referer. Data is delayed (~1-3 min) and rate-limited, so we poll gently and
back off on errors. No login or credentials required.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time

import httpx

from ..state import LiveStore
from .base import MarketDataProvider

log = logging.getLogger("provider.nse")

INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}
_BASE = "https://www.nseindia.com"
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{_BASE}/option-chain",
}
# Default lot sizes (only scales max-pain magnitude; cancels in argmin & ratios).
DEFAULT_LOTS = {"NIFTY": 75, "BANKNIFTY": 35, "FINNIFTY": 65, "MIDCPNIFTY": 140}


def _parse_expiry(s: str) -> dt.date:
    return dt.datetime.strptime(s, "%d-%b-%Y").date()


class NSEProvider(MarketDataProvider):
    name = "nse"

    def __init__(self, store: LiveStore, poll_interval: float = 30.0,
                 strike_window: int = 20):
        super().__init__(store)
        self.poll_interval = poll_interval
        self.strike_window = strike_window
        self._client: httpx.AsyncClient | None = None
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._last_ok: float = 0.0

    async def start(self, underlyings: list[str]) -> None:
        self._client = httpx.AsyncClient(
            headers=_HEADERS, timeout=httpx.Timeout(10.0), follow_redirects=True)
        await self._bootstrap_cookies()
        self._running = True
        self._tasks = [asyncio.create_task(self._poll_loop(u)) for u in underlyings]
        # VIX + index spots refresher
        self._tasks.append(asyncio.create_task(self._vix_loop()))
        log.info("NSE provider started for %s", underlyings)

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._client:
            await self._client.aclose()

    async def healthy(self) -> bool:
        return self._running and (time.time() - self._last_ok) < self.poll_interval * 3

    # --- internals -----------------------------------------------------------
    async def _bootstrap_cookies(self) -> None:
        try:
            await self._client.get(f"{_BASE}/", timeout=10.0)
            await self._client.get(f"{_BASE}/option-chain", timeout=10.0)
        except httpx.HTTPError as e:
            log.warning("NSE cookie bootstrap failed: %s", e)

    async def _get_json(self, url: str) -> dict | None:
        for attempt in range(3):
            try:
                resp = await self._client.get(url)
                if resp.status_code == 401 or resp.status_code == 403:
                    await self._bootstrap_cookies()
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as e:
                log.debug("NSE GET %s failed (%s), retry %d", url, e, attempt)
                await asyncio.sleep(1.5 * (attempt + 1))
        return None

    async def _get_expiries(self, underlying: str) -> list[str]:
        data = await self._get_json(
            f"{_BASE}/api/option-chain-contract-info?symbol={underlying}")
        if not data:
            return []
        return data.get("expiryDates") or data.get("records", {}).get("expiryDates", [])

    async def _poll_loop(self, underlying: str) -> None:
        # NSE moved to the v3 endpoint: needs type + explicit expiry.
        oc_type = "Indices" if underlying in INDEX_SYMBOLS else "Equity"
        lot = DEFAULT_LOTS.get(underlying, 1)
        while self._running:
            expiries = await self._get_expiries(underlying)
            if expiries:
                expiry_str = expiries[0]  # nearest
                url = (f"{_BASE}/api/option-chain-v3?type={oc_type}"
                       f"&symbol={underlying}&expiry={expiry_str}")
                data = await self._get_json(url)
                if data:
                    try:
                        self._ingest(underlying, data, expiry_str, lot)
                        self._last_ok = time.time()
                    except Exception:  # noqa: BLE001 - one bad payload must not kill the loop
                        log.exception("NSE ingest error for %s", underlying)
            await asyncio.sleep(self.poll_interval)

    def _ingest(self, underlying: str, data: dict, expiry_str: str, lot: float) -> None:
        rec = data.get("records", data)
        rows = rec.get("data", [])
        spot = rec.get("underlyingValue") or 0.0
        if not rows:
            return
        near_expiry = _parse_expiry(expiry_str)

        strikes = sorted({r["strikePrice"] for r in rows})
        step = _infer_step(strikes) or 50
        atm = round(spot / step) * step if step else spot
        lo, hi = atm - self.strike_window * step, atm + self.strike_window * step

        st = self.store.get_or_create(underlying, step, lot, is_future_underlying=False)
        st.spot = spot
        st.expiry = near_expiry
        now = time.time()

        # Use a synthetic token per (strike, side) so state routing stays uniform.
        for r in rows:
            k = r.get("strikePrice")
            if k is None or k < lo or k > hi:
                continue
            for side, key in (("ce", "CE"), ("pe", "PE")):
                leg = r.get(key)
                if not leg:
                    continue
                token = _synth_token(underlying, k, side)
                st.register_token(token, k, side)
                st.apply_tick(
                    token,
                    ltp=leg.get("lastPrice"),
                    oi=leg.get("openInterest"),
                    oi_change=leg.get("changeinOpenInterest"),
                    volume=leg.get("totalTradedVolume"),
                    iv=(leg.get("impliedVolatility") or None),
                    bid=leg.get("buyPrice1"),
                    ask=leg.get("sellPrice1"),
                    now=now,
                )
        st.source = "nse"

    async def _vix_loop(self) -> None:
        url = f"{_BASE}/api/allIndices"
        while self._running:
            data = await self._get_json(url)
            if data:
                vix = None
                for idx in data.get("data", []):
                    if idx.get("index") == "INDIA VIX":
                        vix = idx.get("last")
                        break
                if vix is not None:
                    for st in self.store.underlyings.values():
                        st.india_vix = vix
            await asyncio.sleep(self.poll_interval * 2)


def _infer_step(strikes: list[float]) -> float | None:
    if len(strikes) < 2:
        return None
    diffs = sorted(strikes[i + 1] - strikes[i] for i in range(len(strikes) - 1))
    return diffs[len(diffs) // 2]  # median gap


def _synth_token(underlying: str, strike: float, side: str) -> int:
    """Stable synthetic int token for NSE (no real instrument tokens)."""
    return hash((underlying, int(strike), side)) & 0x7FFFFFFF
