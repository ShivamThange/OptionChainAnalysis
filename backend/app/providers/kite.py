"""Kite Connect real-time provider (primary when credentials are present).

Uses KiteTicker (websocket) in full mode for LTP / OI / volume / OHLC, plus
periodic REST `ltp()` for index spot and future price. Subscribes only to the
ATM±window strikes per underlying and re-centres when the ATM drifts.

Dormant unless `settings.kite_enabled` — there is no auth bypass.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time

from ..auth.kite_login import ensure_access_token
from ..instruments import (INDEX_SPOT_SYMBOL, UnderlyingInstruments,
                           build_for_underlying, window_tokens)
from ..state import LiveStore
from .base import MarketDataProvider

log = logging.getLogger("provider.kite")


class KiteProvider(MarketDataProvider):
    name = "kite"

    def __init__(self, store: LiveStore, settings, strike_window: int = 20):
        super().__init__(store)
        self.settings = settings
        self.strike_window = strike_window
        self._kite = None
        self._ticker = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._instruments: dict[str, UnderlyingInstruments] = {}
        self._subscribed: set[int] = set()
        self._oi_baseline: dict[int, float] = {}
        self._spot_symbols: dict[str, str] = {}   # symbol -> underlying
        self._fut_tokens: dict[int, str] = {}     # future token -> underlying
        self._last_tick: float = 0.0
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self, underlyings: list[str]) -> None:
        from kiteconnect import KiteConnect, KiteTicker

        self._loop = asyncio.get_running_loop()
        access_token = ensure_access_token(self.settings)  # raises if creds missing
        self._kite = KiteConnect(api_key=self.settings.kite_api_key)
        self._kite.set_access_token(access_token)

        nfo = self._kite.instruments("NFO")
        today = dt.date.today()
        for u in underlyings:
            ui = build_for_underlying(nfo, u, today)
            if ui:
                self._instruments[u] = ui
                st = self.store.get_or_create(u, ui.step, ui.lot,
                                              is_future_underlying=True)
                st.expiry = ui.expiry
                if ui.index_symbol:
                    self._spot_symbols[ui.index_symbol] = u
                if ui.future_token:
                    self._fut_tokens[ui.future_token] = u

        # need spot to pick the ATM window
        await self._refresh_spots()
        self._resubscribe_all()

        self._ticker = KiteTicker(self.settings.kite_api_key, access_token)
        self._ticker.on_ticks = self._on_ticks
        self._ticker.on_connect = self._on_connect
        self._ticker.on_reconnect = lambda ws, n: log.warning("Kite ticker reconnect #%d", n)
        self._ticker.on_close = lambda ws, code, reason: log.warning("Kite ticker closed: %s", reason)
        self._ticker.connect(threaded=True)   # runs its own thread + reconnection

        self._running = True
        self._tasks = [
            asyncio.create_task(self._spot_loop()),
            asyncio.create_task(self._recenter_loop()),
        ]
        log.info("Kite provider started for %s", list(self._instruments))

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._ticker:
            try:
                self._ticker.close()
            except Exception:  # noqa: BLE001
                pass

    async def healthy(self) -> bool:
        return self._running and (time.time() - self._last_tick) < 10.0

    # --- subscription management --------------------------------------------
    def _resubscribe_all(self) -> None:
        wanted: set[int] = set()
        for u, ui in self._instruments.items():
            st = self.store.get(u)
            if not st or not st.spot:
                continue
            atm = round(st.spot / ui.step) * ui.step
            for leg in window_tokens(ui, atm, self.strike_window):
                st.register_token(leg.token, leg.strike, leg.side)
                wanted.add(leg.token)
            if ui.future_token:
                wanted.add(ui.future_token)
        new = wanted - self._subscribed
        gone = self._subscribed - wanted
        if self._ticker and (new or gone):
            if new:
                self._ticker.subscribe(list(new))
                self._ticker.set_mode(self._ticker.MODE_FULL, list(new))
            if gone:
                self._ticker.unsubscribe(list(gone))
        self._subscribed = wanted

    def _on_connect(self, ws, response) -> None:
        if self._subscribed:
            ws.subscribe(list(self._subscribed))
            ws.set_mode(ws.MODE_FULL, list(self._subscribed))

    def _on_ticks(self, ws, ticks) -> None:
        """Runs on the ticker thread — keep it minimal and thread-safe."""
        now = time.time()
        self._last_tick = now
        for t in ticks:
            token = t.get("instrument_token")
            oi = t.get("oi")
            # intraday OI change vs first-seen OI this session
            oi_change = None
            if oi is not None:
                base = self._oi_baseline.setdefault(token, oi)
                oi_change = oi - base

            # futures / index tokens update spot rather than a leg
            u = self._fut_tokens.get(token)
            if u:
                st = self.store.get(u)
                if st:
                    st.future_ltp = t.get("last_price", st.future_ltp)
                    st.last_update = now
                continue

            for u, st in self.store.underlyings.items():
                if token in st.route:
                    st.apply_tick(
                        token,
                        ltp=t.get("last_price"),
                        oi=oi, oi_change=oi_change,
                        volume=t.get("volume_traded"),
                        atp=t.get("average_traded_price"),
                        prev_close=t.get("ohlc", {}).get("close"),
                        now=now,
                    )
                    st.source = "kite"
                    break

    # --- periodic REST refresh ----------------------------------------------
    async def _refresh_spots(self) -> None:
        if not self._spot_symbols:
            return
        try:
            data = await asyncio.to_thread(self._kite.ltp, list(self._spot_symbols))
        except Exception as e:  # noqa: BLE001
            log.warning("Kite ltp() failed: %s", e)
            return
        for sym, u in self._spot_symbols.items():
            q = data.get(sym)
            st = self.store.get(u)
            if q and st:
                st.spot = q["last_price"]

    async def _spot_loop(self) -> None:
        while self._running:
            await self._refresh_spots()
            await asyncio.sleep(2.0)

    async def _recenter_loop(self) -> None:
        while self._running:
            await asyncio.sleep(10.0)
            try:
                self._resubscribe_all()
            except Exception:  # noqa: BLE001
                log.exception("re-subscribe failed")
