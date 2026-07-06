"""Provider manager: selection + Kite→NSE failover.

- effective_provider == "nse": run NSE only.
- effective_provider == "kite": run Kite as primary; if Kite fails to start
  (missing creds, login error) or goes unhealthy, transparently bring up NSE so
  data keeps flowing. Recovers back to Kite when it's healthy again.
No auth bypass: if Kite creds are absent, we simply never start Kite.
"""
from __future__ import annotations

import asyncio
import logging

from ..auth.kite_login import KiteCredentialsMissing
from ..state import LiveStore
from .nse import NSEProvider

log = logging.getLogger("provider.manager")


class ProviderManager:
    def __init__(self, settings, store: LiveStore):
        self.settings = settings
        self.store = store
        self._kite = None
        self._nse: NSEProvider | None = None
        self._underlyings: list[str] = []
        self._active = "none"
        self._watchdog: asyncio.Task | None = None

    @property
    def active_source(self) -> str:
        return self._active

    async def start(self, underlyings: list[str]) -> None:
        self._underlyings = underlyings
        if self.settings.effective_provider == "kite":
            await self._try_start_kite(underlyings)
        if self._active != "kite":
            await self._start_nse(underlyings)
        self._watchdog = asyncio.create_task(self._watch())

    async def stop(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
        if self._kite:
            await self._kite.stop()
        if self._nse:
            await self._nse.stop()

    async def _try_start_kite(self, underlyings) -> bool:
        from .kite import KiteProvider
        try:
            self._kite = KiteProvider(self.store, self.settings,
                                      self.settings.strike_window)
            await self._kite.start(underlyings)
            self._active = "kite"
            log.info("Active data source: KITE (real-time)")
            return True
        except KiteCredentialsMissing as e:
            log.warning("Kite disabled (%s). Falling back to NSE.", e)
        except Exception:  # noqa: BLE001
            log.exception("Kite start failed; falling back to NSE")
        self._kite = None
        return False

    async def _start_nse(self, underlyings) -> None:
        if self._nse is None:
            self._nse = NSEProvider(self.store, poll_interval=30.0,
                                    strike_window=self.settings.strike_window)
            await self._nse.start(underlyings)
        if self._active != "kite":
            self._active = "nse"
            log.info("Active data source: NSE (fallback/interim)")

    async def _watch(self) -> None:
        """Keep data flowing: if Kite is primary but unhealthy, ensure NSE is up;
        when Kite recovers, prefer it again."""
        while True:
            await asyncio.sleep(10.0)
            if self.settings.effective_provider != "kite":
                continue
            kite_ok = self._kite is not None and await self._kite.healthy()
            if not kite_ok:
                if self._kite is None:
                    await self._try_start_kite(self._underlyings)
                if (self._kite is None or not await self._kite.healthy()):
                    await self._start_nse(self._underlyings)
            elif kite_ok and self._active != "kite":
                self._active = "kite"
                log.info("Kite healthy again; primary = KITE")
