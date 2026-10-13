"""Run the whole check as a stream of events.

Events (dicts with a "type" key) are what the CLI prints, the web UI animates,
and `--record` writes to disk. Replaying a recording yields the same events with
the same relative timing, so the UI behaves identically with no API calls.

Event types:
  started   {chars, source}
  claims    {count}                  all claims extracted
  claim     {claim}                  one per claim, in document order
  probe     {id, query}              a search was launched
  verdict   {id, verdict}            a search returned and was judged
  done      {summary}
  error     {message}
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .claims import Claim, extract_claims
from .config import settings
from .search import search
from .verify import judge

Event = dict[str, Any]


def summarise(verdicts: list[dict]) -> dict:
    counts = {"fresh": 0, "drifted": 0, "rotted": 0, "unverified": 0}
    for v in verdicts:
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    checked = counts["fresh"] + counts["drifted"] + counts["rotted"]
    score = round((counts["fresh"] + 0.5 * counts["drifted"]) / checked, 3) if checked else None
    return {"counts": counts, "checked": checked, "total": len(verdicts), "freshness": score}


async def run(doc: str, *, source: str = "paste", max_claims: int | None = None) -> AsyncIterator[Event]:
    """Yield events for a full check of `doc`."""
    settings.require_keys()
    t0 = time.monotonic()

    def stamp(event: Event) -> Event:
        event["t"] = round(time.monotonic() - t0, 3)
        return event

    yield stamp({"type": "started", "chars": len(doc), "source": source})

    try:
        claims = await extract_claims(doc, max_claims)
    except Exception as exc:  # noqa: BLE001
        yield stamp({"type": "error", "message": f"Claim extraction failed: {exc}"})
        return

    yield stamp({"type": "claims", "count": len(claims)})
    for claim in claims:
        yield stamp({"type": "claim", "claim": claim.to_dict()})

    # Fan out. Probes are announced as tasks start; verdicts arrive as they finish.
    queue: asyncio.Queue[Event | None] = asyncio.Queue()

    async def worker(claim: Claim) -> None:
        await queue.put({"type": "probe", "id": claim.id, "query": claim.query})
        try:
            sources, cached = await search(claim.query)
            verdict = await judge(claim, sources, cached)
            await queue.put({"type": "verdict", "id": claim.id, "verdict": verdict.to_dict()})
        except Exception as exc:  # noqa: BLE001
            await queue.put(
                {
                    "type": "verdict",
                    "id": claim.id,
                    "verdict": {
                        "claim_id": claim.id,
                        "status": "unverified",
                        "confidence": 0.0,
                        "current": "",
                        "source_url": None,
                        "note": f"Check failed: {exc}",
                        "cached": False,
                    },
                }
            )

    tasks = [asyncio.create_task(worker(c)) for c in claims]

    async def closer() -> None:
        await asyncio.gather(*tasks)
        await queue.put(None)

    asyncio.create_task(closer())

    verdicts: list[dict] = []
    while True:
        event = await queue.get()
        if event is None:
            break
        if event["type"] == "verdict":
            verdicts.append(event["verdict"])
        yield stamp(event)

    yield stamp({"type": "done", "summary": summarise(verdicts)})


async def record(events: AsyncIterator[Event], path: str | Path) -> AsyncIterator[Event]:
    """Tee events to a JSONL file while passing them through."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        async for event in events:
            fh.write(json.dumps(event) + "\n")
            fh.flush()
            yield event


async def replay(path: str | Path, speed: float = 1.0) -> AsyncIterator[Event]:
    """Yield recorded events with their original relative timing (divided by `speed`)."""
    events = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    start = time.monotonic()
    for event in events:
        target = event.get("t", 0.0) / max(speed, 1e-6)
        delay = target - (time.monotonic() - start)
        if delay > 0:
            await asyncio.sleep(delay)
        yield event


async def collect(events: AsyncIterator[Event]) -> dict:
    """Drain a stream into {claims, verdicts, summary} for reports."""
    claims: list[dict] = []
    verdicts: dict[int, dict] = {}
    summary: dict = {}
    async for event in events:
        if event["type"] == "claim":
            claims.append(event["claim"])
        elif event["type"] == "verdict":
            verdicts[event["id"]] = event["verdict"]
        elif event["type"] == "done":
            summary = event["summary"]
    return {"claims": claims, "verdicts": verdicts, "summary": summary}
