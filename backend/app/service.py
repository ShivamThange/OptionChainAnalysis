"""Runtime core: wires providers → engine recompute loop → WebSocket hub → DB.

Owns the debounced recompute loop that turns live state into metric snapshots,
keeps the latest snapshot per underlying, broadcasts to connected websockets,
and persists on the snapshot cadence.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time

from .config import Settings
from .engine.pipeline import compute_snapshot
from .providers.manager import ProviderManager
from .state import LiveStore
from .storage.db import SnapshotDB
from .storage.snapshots import SnapshotScheduler

log = logging.getLogger("service")


class DashboardService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = LiveStore()
        self.manager = ProviderManager(settings, self.store)
        self.db = SnapshotDB(settings.db_file)
        self.scheduler = SnapshotScheduler(self._persist_all, settings.snapshot_fast_sec)

        self._latest: dict[str, dict] = {}
        self._prev_state: dict[str, dict] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._recompute_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        await self.db.connect()
        await self.manager.start(self.settings.underlyings)
        self._running = True
        self._recompute_task = asyncio.create_task(self._recompute_loop())
        self.scheduler.start()
        log.info("DashboardService started (provider=%s)", self.settings.effective_provider)

    async def stop(self) -> None:
        self._running = False
        if self._recompute_task:
            self._recompute_task.cancel()
        self.scheduler.shutdown()
        await self.manager.stop()
        await self.db.close()

    # --- recompute loop ------------------------------------------------------
    async def _recompute_loop(self) -> None:
        interval = self.settings.recompute_debounce_ms / 1000.0
        r, q = self.settings.risk_free_rate, self.settings.dividend_yield
        today = dt.date.today()
        while self._running:
            await asyncio.sleep(interval)
            now = time.time()
            for name in self.store.names():
                st = self.store.get(name)
                inp = st.build_inputs(r, q, today)
                if inp is None:
                    continue
                try:
                    snap = compute_snapshot(inp, self._prev_state.get(name),
                                            self.settings.iv_buy_sell_threshold)
                except Exception:  # noqa: BLE001
                    log.exception("recompute failed for %s", name)
                    continue
                self._prev_state[name] = snap.pop("_state")
                snap["source"] = st.source or self.manager.active_source
                snap["stale"] = st.is_stale(now)
                snap["ts"] = now
                self._latest[name] = snap
            await self._broadcast()

    async def _broadcast(self) -> None:
        if not self._subscribers:
            return
        payload = {"type": "snapshot", "data": self._latest,
                   "active_source": self.manager.active_source}
        dead = []
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(queue)
        for d in dead:
            self._subscribers.discard(d)

    async def _persist_all(self, ts: float) -> None:
        for name, snap in self._latest.items():
            if snap:
                await self.db.write_snapshot(ts, snap)

    # --- accessors for the API ----------------------------------------------
    def latest(self, underlying: str | None = None):
        if underlying:
            return self._latest.get(underlying)
        return self._latest

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=8)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)
