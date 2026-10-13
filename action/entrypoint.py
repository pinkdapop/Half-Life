"""Check the given markdown files and post one PR comment with the results."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from halflife import pipeline, report


async def check(path: str) -> str:
    doc = Path(path).read_text()
    data = await pipeline.collect(pipeline.run(doc, source=path))
    return f"### `{path}`\n\n" + report.table(data["claims"], data["verdicts"], data["summary"])


def pr_number() -> int | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return None
    event = json.loads(Path(event_path).read_text())
    return (event.get("pull_request") or {}).get("number")


def post_comment(body: str) -> None:
    number, repo, token = pr_number(), os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (number and repo and token):
        print(body)
        return
    resp = httpx.post(
        f"https://api.github.com/repos/{repo}/issues/{number}/comments",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"body": body},
        timeout=30.0,
    )
    resp.raise_for_status()


async def main(files: list[str]) -> None:
    sections = await asyncio.gather(*(check(f) for f in files if Path(f).exists()))
    post_comment("\n\n".join(sections) if sections else "halflife: none of the given files exist.")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
