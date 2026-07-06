"""Async SQLite time-series store (replaces the VBA RECORD* snapshot macros).

WAL mode + a single async connection + batched writes keep the hot path cheap.
Two granularities are stored:
  - `metric_snapshots`: one row per underlying per snapshot (aggregate metrics)
  - `strike_snapshots`: per-strike detail at each snapshot (for OI/decay charts)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import aiosqlite

log = logging.getLogger("storage.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metric_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    underlying  TEXT NOT NULL,
    spot        REAL,
    atm         REAL,
    max_pain    REAL,
    pcr_oi      REAL,
    pcr_volume  REAL,
    ce_oi       REAL,
    pe_oi       REAL,
    atm_iv      REAL,
    straddle    REAL,
    composite_bias TEXT,
    signals_json   TEXT
);
CREATE INDEX IF NOT EXISTS ix_metric_u_ts ON metric_snapshots(underlying, ts);

CREATE TABLE IF NOT EXISTS strike_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    underlying  TEXT NOT NULL,
    strike      REAL NOT NULL,
    ce_ltp REAL, ce_oi REAL, ce_oi_change REAL, ce_iv REAL, ce_volume REAL,
    pe_ltp REAL, pe_oi REAL, pe_oi_change REAL, pe_iv REAL, pe_volume REAL
);
CREATE INDEX IF NOT EXISTS ix_strike_u_ts ON strike_snapshots(underlying, ts);
"""


class SnapshotDB:
    def __init__(self, path: Path):
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self.path)
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.execute("PRAGMA synchronous=NORMAL;")
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        log.info("SnapshotDB ready at %s", self.path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def write_snapshot(self, ts: float, snap: dict) -> None:
        """Persist one computed snapshot (aggregate + per-strike) in one txn."""
        if self._db is None:
            return
        u = snap["underlying"]
        sig = snap["signals"]
        await self._db.execute(
            """INSERT INTO metric_snapshots
               (ts, underlying, spot, atm, max_pain, pcr_oi, pcr_volume,
                ce_oi, pe_oi, atm_iv, straddle, composite_bias, signals_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ts, u, snap["spot"], snap["atm"], snap["max_pain"],
             snap["pcr"]["pcr_oi"], snap["pcr"]["pcr_volume"],
             snap["totals"]["ce_oi"], snap["totals"]["pe_oi"],
             snap["atm_iv"]["atm_iv"], snap["straddle"]["premium"],
             sig["composite_bias"], json.dumps(sig)),
        )
        rows = [
            (ts, u, c["strike"],
             c["ce"]["ltp"], c["ce"]["oi"], c["ce"]["oi_change"], c["ce"]["iv"], c["ce"]["volume"],
             c["pe"]["ltp"], c["pe"]["oi"], c["pe"]["oi_change"], c["pe"]["iv"], c["pe"]["volume"])
            for c in snap["chain"]
        ]
        await self._db.executemany(
            """INSERT INTO strike_snapshots
               (ts, underlying, strike, ce_ltp, ce_oi, ce_oi_change, ce_iv, ce_volume,
                pe_ltp, pe_oi, pe_oi_change, pe_iv, pe_volume)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
        await self._db.commit()

    async def metric_history(self, underlying: str, limit: int = 500) -> list[dict]:
        if self._db is None:
            return []
        self._db.row_factory = aiosqlite.Row
        cur = await self._db.execute(
            """SELECT ts, spot, atm, max_pain, pcr_oi, pcr_volume, ce_oi, pe_oi,
                      atm_iv, straddle, composite_bias
               FROM metric_snapshots WHERE underlying=? ORDER BY ts DESC LIMIT ?""",
            (underlying, limit))
        rows = await cur.fetchall()
        return [dict(r) for r in reversed(rows)]

    async def series(self, underlying: str, column: str, limit: int = 500) -> list[dict]:
        """Return [{ts, value}] for one metric column (for Bollinger/charts)."""
        allowed = {"spot", "max_pain", "pcr_oi", "pcr_volume", "atm_iv", "straddle"}
        if column not in allowed:
            raise ValueError(f"column {column!r} not allowed")
        if self._db is None:
            return []
        cur = await self._db.execute(
            f"""SELECT ts, {column} AS value FROM metric_snapshots
                WHERE underlying=? AND {column} IS NOT NULL
                ORDER BY ts DESC LIMIT ?""", (underlying, limit))
        rows = await cur.fetchall()
        return [{"ts": r[0], "value": r[1]} for r in reversed(rows)]
