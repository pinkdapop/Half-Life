"""Decide whether a claim is still true, given search results."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from .claims import Claim
from .config import settings
from .llm import chat_json

STATUSES = ("fresh", "drifted", "rotted", "unverified")

SYSTEM = (
    "You are a documentation decay auditor. You decide whether a claim written some "
    "time ago is still true today, using ONLY the sources provided. You return JSON "
    "only, no prose, no code fences."
)

USER_TEMPLATE = """Today's date: {today}

Claim from the document:
"{text}"
Claim kind: {kind}

Sources:
{sources}

Classify the claim:
- fresh: still accurate today.
- drifted: partly outdated. A newer version, price, or recommended path exists,
  but following the claim still works or is approximately right.
- rotted: no longer true. Following the claim would fail or mislead.
- unverified: the sources do not settle it. Do not guess.

Be strict about evidence: if no source actually states the current value, say unverified.

Output exactly:
{{"status": "fresh|drifted|rotted|unverified",
  "confidence": 0.0-1.0,
  "current": "what is true now, in a few words, or empty",
  "source_index": <1-based index of the deciding source, or null>,
  "note": "one plain sentence a developer would want to read"}}"""


@dataclass
class Verdict:
    claim_id: int
    status: str
    confidence: float
    current: str
    source_url: str | None
    note: str
    cached: bool
    model: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _format_sources(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "(no results)"
    lines = []
    for i, s in enumerate(sources, start=1):
        published = f" (published {s['published']})" if s.get("published") else ""
        lines.append(f"[{i}] {s['title']}{published}\n    {s['url']}\n    {s['snippet']}")
    return "\n".join(lines)


async def _ask(claim: Claim, sources: list[dict[str, Any]], model: str | None) -> dict[str, Any]:
    return await chat_json(
        SYSTEM,
        USER_TEMPLATE.format(
            today=date.today().isoformat(),
            text=claim.text,
            kind=claim.kind,
            sources=_format_sources(sources),
        ),
        model=model,
        max_tokens=600,
    )


async def judge(claim: Claim, sources: list[dict[str, Any]], cached: bool) -> Verdict:
    if not sources:
        return Verdict(claim.id, "unverified", 0.0, "", None, "No search results.", cached)

    model = settings.nemotron_model
    data = await _ask(claim, sources, None)

    # Nano does the everyday calls; escalate only the verdicts it is unsure about.
    try:
        first_confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        first_confidence = 0.0
    if settings.escalate_model and first_confidence < settings.escalate_below:
        data = await _ask(claim, sources, settings.escalate_model)
        model = settings.escalate_model

    status = data.get("status") if data.get("status") in STATUSES else "unverified"
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    source_url = None
    idx = data.get("source_index")
    if isinstance(idx, int) and 1 <= idx <= len(sources):
        source_url = sources[idx - 1]["url"]

    return Verdict(
        claim_id=claim.id,
        status=status,
        confidence=confidence,
        current=str(data.get("current", "") or ""),
        source_url=source_url,
        note=str(data.get("note", "") or ""),
        cached=cached,
        model=model,
    )
