"""Tests that need no API keys: replay, summaries, and report rendering."""

from pathlib import Path

import pytest

from halflife import pipeline, report
from halflife.claims import _chunks

SAMPLE = Path(__file__).parent.parent / "examples" / "runs" / "sample.jsonl"
DOC = Path(__file__).parent.parent / "examples" / "runs" / "sample.md"


@pytest.mark.asyncio
async def test_replay_streams_every_event_in_order():
    events = [e async for e in pipeline.replay(SAMPLE, speed=1e9)]
    assert events[0]["type"] == "started"
    assert events[-1]["type"] == "done"
    times = [e["t"] for e in events]
    assert times == sorted(times)


@pytest.mark.asyncio
async def test_collect_and_render():
    data = await pipeline.collect(pipeline.replay(SAMPLE, speed=1e9))
    assert data["summary"]["total"] == len(data["claims"])
    md = report.table(data["claims"], data["verdicts"], data["summary"])
    assert "rotted" in md and "| ❌ |" in md
    annotated = report.annotate(DOC.read_text(), data["claims"], data["verdicts"])
    assert "**pip install fastcache==1.4.2**" in annotated


def test_summary_scores_half_credit_for_drift():
    verdicts = [{"status": s} for s in ("fresh", "drifted", "rotted", "unverified")]
    s = pipeline.summarise(verdicts)
    assert s["checked"] == 3 and s["freshness"] == 0.5


def test_chunking_preserves_offsets():
    doc = "\n\n".join(f"paragraph {i} " + "x" * 900 for i in range(30))
    chunks = _chunks(doc)
    assert len(chunks) > 1
    for offset, chunk in chunks:
        assert doc[offset : offset + len(chunk)] == chunk
