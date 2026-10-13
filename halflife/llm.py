"""Nemotron on Nebius Token Factory, through the OpenAI-compatible API.

One function: ask for JSON, get a dict back. Handles code fences, retries,
and models that ignore response_format.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from openai import AsyncOpenAI

from .config import settings

_client: AsyncOpenAI | None = None

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.nebius_api_key,
            base_url=settings.nebius_base_url,
            timeout=120.0,
        )
    return _client


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} block, for models that add prose.
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(cleaned[start : end + 1])


async def chat_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4000,
    retries: int = 3,
) -> dict[str, Any]:
    """Send a prompt that asks for JSON and return the parsed object.

    `model` overrides the default (used to escalate hard verdicts to a bigger Nemotron)."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            kwargs: dict[str, Any] = dict(
                model=model or settings.nemotron_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            # Not every model accepts this; drop it on retries and rely on the prompt.
            if attempt == 0:
                kwargs["response_format"] = {"type": "json_object"}
            response = await client().chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            return _parse_json(content)
        except Exception as exc:  # noqa: BLE001 - we retry on anything transient
            last_error = exc
            await asyncio.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Nemotron call failed after {retries} attempts: {last_error}")
