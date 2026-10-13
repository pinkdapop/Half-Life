"""Pull out the claims in a document whose truth can change over time."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

from .config import settings
from .llm import chat_json

KINDS = ("version", "price", "command", "endpoint", "person", "date", "support", "limit", "other")

SYSTEM = (
    "You extract checkable, time-sensitive claims from technical documentation. "
    "You return JSON only, no prose, no code fences."
)

USER_TEMPLATE = """Document (markdown):
<<<
{chunk}
>>>

List the claims in this document whose truth can CHANGE over time, and that a web
search could confirm or refute today. Good claims: version numbers, release dates,
prices and quotas, install commands and flags, API endpoints and URLs, defaults and
limits, who holds a role, "X supports Y", "the latest release is Z".
Skip: opinions, explanations of how code works, instructions that are timeless,
generic advice, anything with no fact to check.

Rules:
- "text" must be an EXACT substring of the document, at most 200 characters.
- "query" is the web search most likely to find the current truth, at most 12 words.
- "kind" is one of: {kinds}.
- At most {max_claims} claims. Prefer the ones most likely to have changed.

Output exactly: {{"claims": [{{"text": "...", "query": "...", "kind": "..."}}]}}"""

CHUNK_CHARS = 8000


@dataclass
class Claim:
    id: int
    text: str
    query: str
    kind: str
    start: int | None  # character offset in the document, None if not located
    end: int | None

    def to_dict(self) -> dict:
        return asdict(self)


def _chunks(doc: str) -> list[tuple[int, str]]:
    """Split on blank lines into chunks under CHUNK_CHARS, keeping offsets."""
    if len(doc) <= CHUNK_CHARS:
        return [(0, doc)]
    out: list[tuple[int, str]] = []
    chunk_start, pos = 0, 0
    for para in doc.split("\n\n"):
        para_end = pos + len(para)
        if para_end - chunk_start > CHUNK_CHARS and pos > chunk_start:
            out.append((chunk_start, doc[chunk_start:pos]))
            chunk_start = pos
        pos = para_end + 2  # skip the "\n\n" separator
    out.append((chunk_start, doc[chunk_start:]))
    return out


def _locate(text: str, offset: int, chunk: str) -> tuple[int | None, int | None]:
    idx = chunk.find(text)
    if idx == -1:
        idx = chunk.lower().find(text.lower())
    if idx == -1:
        return None, None
    return offset + idx, offset + idx + len(text)


async def _extract_chunk(offset: int, chunk: str, budget: int) -> list[dict]:
    data = await chat_json(
        SYSTEM,
        USER_TEMPLATE.format(chunk=chunk, kinds=", ".join(KINDS), max_claims=budget),
    )
    found = []
    for raw in data.get("claims", []):
        text = str(raw.get("text", "")).strip()
        query = str(raw.get("query", "")).strip()
        if not text or not query:
            continue
        kind = raw.get("kind") if raw.get("kind") in KINDS else "other"
        start, end = _locate(text, offset, chunk)
        found.append({"text": text, "query": query, "kind": kind, "start": start, "end": end})
    return found


async def extract_claims(doc: str, max_claims: int | None = None) -> list[Claim]:
    """Extract, dedupe, and number the checkable claims in `doc`."""
    limit = max_claims or settings.max_claims
    chunks = _chunks(doc)
    per_chunk = max(8, limit // max(1, len(chunks)))
    results = await asyncio.gather(*(_extract_chunk(off, ch, per_chunk) for off, ch in chunks))

    seen: set[str] = set()
    claims: list[Claim] = []
    for found in results:
        for item in found:
            key = item["text"].lower()
            if key in seen:
                continue
            seen.add(key)
            claims.append(Claim(id=len(claims), **item))
            if len(claims) >= limit:
                return claims
    return claims
