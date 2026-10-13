"""Tavily search with a disk cache and a concurrency limit.

Credits are the scarce resource in this project, so every result is cached by a
hash of (query, depth, max_results). Re-running the same document costs nothing.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from tavily import AsyncTavilyClient

from .config import settings

_client: AsyncTavilyClient | None = None
_semaphore: asyncio.Semaphore | None = None


def _tavily() -> AsyncTavilyClient:
    global _client
    if _client is None:
        _client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    return _client


def _limiter() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.concurrency)
    return _semaphore


def _cache_path(query: str) -> Path:
    key = f"{query}|{settings.search_depth}|{settings.max_results}"
    digest = hashlib.sha1(key.encode()).hexdigest()
    return Path(settings.cache_dir) / f"{digest}.json"


def _normalise(raw: dict[str, Any]) -> list[dict[str, Any]]:
    sources = []
    for item in raw.get("results", []):
        sources.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": (item.get("content") or "")[:1200],
                "published": item.get("published_date"),
                "score": item.get("score"),
            }
        )
    return sources


async def search(query: str) -> tuple[list[dict[str, Any]], bool]:
    """Return (sources, cached). Sources are trimmed to what the judge needs."""
    path = _cache_path(query)
    if path.exists():
        return json.loads(path.read_text()), True

    async with _limiter():
        raw = await _tavily().search(
            query,
            search_depth=settings.search_depth,
            max_results=settings.max_results,
            include_answer=False,
        )
    sources = _normalise(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sources))
    return sources, False
