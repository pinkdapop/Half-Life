"""Web UI backend. One page, two endpoints, server-sent events."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .. import pipeline
from ..cli import load_text

STATIC = Path(__file__).parent / "static"


class RunRequest(BaseModel):
    text: str | None = None
    url: str | None = None
    max_claims: int | None = None


def create_app(replay_path: str | None = None) -> FastAPI:
    app = FastAPI(title="halflife")
    runs: dict[str, asyncio.Queue] = {}

    async def pump(run_id: str, events: AsyncIterator[dict]) -> None:
        queue = runs[run_id]
        try:
            async for event in events:
                await queue.put(event)
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    def start(events: AsyncIterator[dict]) -> str:
        run_id = uuid.uuid4().hex[:12]
        runs[run_id] = asyncio.Queue()
        asyncio.create_task(pump(run_id, events))
        return run_id

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/config")
    async def config() -> dict:
        return {"replay_available": bool(replay_path)}

    @app.post("/api/runs")
    async def create_run(req: RunRequest) -> dict:
        if req.url:
            doc, source = await asyncio.to_thread(load_text, req.url)
        elif req.text and req.text.strip():
            doc, source = req.text, "paste"
        else:
            raise HTTPException(400, "Paste some text or give a URL.")
        return {"id": start(pipeline.run(doc, source=source, max_claims=req.max_claims)), "doc": doc}

    @app.post("/api/runs/replay")
    async def create_replay(speed: float = 1.0) -> dict:
        if not replay_path:
            raise HTTPException(404, "Server was started without --replay.")
        doc_path = Path(replay_path).with_suffix(".md")
        doc = doc_path.read_text() if doc_path.exists() else ""
        return {"id": start(pipeline.replay(replay_path, speed=speed)), "doc": doc}

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str) -> StreamingResponse:
        queue = runs.get(run_id)
        if queue is None:
            raise HTTPException(404, "Unknown run.")

        async def stream() -> AsyncIterator[str]:
            while True:
                event = await queue.get()
                if event is None:
                    yield "event: end\ndata: {}\n\n"
                    runs.pop(run_id, None)
                    return
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


app = create_app()
