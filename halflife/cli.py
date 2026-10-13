"""halflife command line.

  halflife check <file|url> [--record run.jsonl] [--out report.json] [--md report.md]
  halflife serve [--replay run.jsonl] [--port 8000]
  halflife report run.jsonl <original-doc> [--md report.md]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

from . import pipeline, report

_TAGS = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.DOTALL | re.IGNORECASE)


def load_text(target: str) -> tuple[str, str]:
    """Read a local file or fetch a URL. Returns (text, source label)."""
    if target.startswith("http://") or target.startswith("https://"):
        resp = httpx.get(target, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        body = resp.text
        if "text/html" in resp.headers.get("content-type", ""):
            body = _TAGS.sub(" ", body)
            body = re.sub(r"[ \t]+", " ", body)
            body = re.sub(r"\n\s*\n+", "\n\n", body)
        return body.strip(), target
    path = Path(target)
    return path.read_text(), path.name


def _print_event(event: dict) -> None:
    kind = event["type"]
    if kind == "claims":
        print(f"{event['count']} checkable claims")
    elif kind == "verdict":
        v = event["verdict"]
        mark = report.ICON[v["status"]]
        print(f"{mark} #{event['id']:<3} {v['status']:<10} {v['note']}")
    elif kind == "done":
        s = event["summary"]
        fresh = f"{s['freshness']:.0%}" if s["freshness"] is not None else "n/a"
        print(f"\nfreshness {fresh}  {s['counts']}")
    elif kind == "error":
        print(f"error: {event['message']}", file=sys.stderr)


async def _check(args: argparse.Namespace) -> int:
    doc, source = load_text(args.target)
    events = pipeline.run(doc, source=source, max_claims=args.max_claims)
    if args.record:
        events = pipeline.record(events, args.record)

    claims: list[dict] = []
    verdicts: dict[int, dict] = {}
    summary: dict = {}
    async for event in events:
        _print_event(event)
        if event["type"] == "claim":
            claims.append(event["claim"])
        elif event["type"] == "verdict":
            verdicts[event["id"]] = event["verdict"]
        elif event["type"] == "done":
            summary = event["summary"]

    if args.out:
        Path(args.out).write_text(
            json.dumps({"source": source, "claims": claims, "verdicts": verdicts, "summary": summary}, indent=2)
        )
    if args.md:
        md = report.table(claims, verdicts, summary) + "\n---\n\n" + report.annotate(doc, claims, verdicts)
        Path(args.md).write_text(md)
        print(f"wrote {args.md}")
    return 0


async def _report(args: argparse.Namespace) -> int:
    doc, _ = load_text(args.doc)
    data = await pipeline.collect(pipeline.replay(args.run, speed=1e9))
    md = report.table(data["claims"], data["verdicts"], data["summary"])
    md += "\n---\n\n" + report.annotate(doc, data["claims"], data["verdicts"])
    if args.md:
        Path(args.md).write_text(md)
        print(f"wrote {args.md}")
    else:
        print(md)
    return 0


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .web.app import create_app

    uvicorn.run(create_app(replay_path=args.replay), host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="halflife", description="Find out how much a document has decayed.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="verify a file or URL")
    p_check.add_argument("target")
    p_check.add_argument("--record", help="write events to this JSONL file for replay")
    p_check.add_argument("--out", help="write JSON results here")
    p_check.add_argument("--md", help="write an annotated markdown report here")
    p_check.add_argument("--max-claims", type=int, default=None)

    p_serve = sub.add_parser("serve", help="run the web UI")
    p_serve.add_argument("--replay", help="JSONL recording to offer as the demo run")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)

    p_report = sub.add_parser("report", help="render a recorded run as markdown")
    p_report.add_argument("run")
    p_report.add_argument("doc", help="the document that was checked")
    p_report.add_argument("--md")

    args = parser.parse_args(argv)
    if args.cmd == "check":
        sys.exit(asyncio.run(_check(args)))
    if args.cmd == "report":
        sys.exit(asyncio.run(_report(args)))
    if args.cmd == "serve":
        sys.exit(_serve(args))


if __name__ == "__main__":
    main()
