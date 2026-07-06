"""FastAPI app: REST endpoints + WebSocket live push.

Run: uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .service import DashboardService

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
service = DashboardService(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await service.start()
    try:
        yield
    finally:
        await service.stop()


app = FastAPI(title="Option Chain Dashboard", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "provider_selected": settings.effective_provider,
        "active_source": service.manager.active_source,
        "kite_enabled": settings.kite_enabled,
        "underlyings": settings.underlyings,
    }


@app.get("/api/underlyings")
async def underlyings():
    return {"underlyings": settings.underlyings,
            "tracked": service.store.names()}


@app.get("/api/snapshot")
async def all_snapshots():
    return {"active_source": service.manager.active_source,
            "data": service.latest()}


@app.get("/api/snapshot/{underlying}")
async def snapshot(underlying: str):
    snap = service.latest(underlying.upper())
    if snap is None:
        raise HTTPException(404, f"no data yet for {underlying}")
    return snap


@app.get("/api/history/{underlying}")
async def history(underlying: str, limit: int = 500):
    return {"underlying": underlying.upper(),
            "rows": await service.db.metric_history(underlying.upper(), limit)}


@app.get("/api/series/{underlying}/{column}")
async def series(underlying: str, column: str, limit: int = 500):
    try:
        data = await service.db.series(underlying.upper(), column, limit)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"underlying": underlying.upper(), "column": column, "series": data}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    queue = service.subscribe()
    # push current state immediately so a fresh client isn't blank
    await websocket.send_json({"type": "snapshot", "data": service.latest(),
                               "active_source": service.manager.active_source})
    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        service.unsubscribe(queue)
        with contextlib.suppress(Exception):
            await websocket.close()
