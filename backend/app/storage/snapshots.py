"""Snapshot persistence scheduler (replaces VBA RECORD1/5/6/8/25 macros).

Persists the latest computed snapshot at the fast cadence. The fast cadence is
the most granular of the workbook's 3/5/15-min recorders and subsumes them for
history/charting; med/slow remain configurable for future per-horizon rollups.
"""
from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger("storage.snapshots")


class SnapshotScheduler:
    def __init__(self, persist_cb: Callable[[float], Awaitable[None]],
                 fast_sec: int = 180):
        self._persist = persist_cb
        self._fast = fast_sec
        self._sched = AsyncIOScheduler()

    def start(self) -> None:
        self._sched.add_job(self._run, "interval", seconds=self._fast,
                            id="snapshot_fast", max_instances=1,
                            coalesce=True, next_run_time=None)
        self._sched.start()
        log.info("Snapshot scheduler started (every %ds)", self._fast)

    async def _run(self) -> None:
        try:
            await self._persist(time.time())
        except Exception:  # noqa: BLE001
            log.exception("snapshot persist failed")

    def shutdown(self) -> None:
        if self._sched.running:
            self._sched.shutdown(wait=False)
