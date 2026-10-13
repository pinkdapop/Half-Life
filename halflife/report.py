"""Turn a finished run into things people read: an annotated doc and a PR table."""

from __future__ import annotations

ICON = {"fresh": "✅", "drifted": "🟡", "rotted": "❌", "unverified": "⚪"}
LABEL = {"fresh": "still true", "drifted": "drifted", "rotted": "rotted", "unverified": "unverified"}


def annotate(doc: str, claims: list[dict], verdicts: dict[int, dict]) -> str:
    """Return the document with each located claim followed by its verdict footnote."""
    located = sorted(
        (c for c in claims if c.get("start") is not None and c["id"] in verdicts),
        key=lambda c: c["start"],
    )
    out, cursor = [], 0
    for claim in located:
        start, end = claim["start"], claim["end"]
        if start < cursor:  # overlapping claim; skip to keep the text intact
            continue
        v = verdicts[claim["id"]]
        out.append(doc[cursor:start])
        out.append(f"**{doc[start:end]}**")
        tag = f" {ICON[v['status']]} _{LABEL[v['status']]}"
        if v.get("note"):
            tag += f": {v['note']}"
        if v.get("source_url"):
            tag += f" ([source]({v['source_url']}))"
        out.append(tag + "_")
        cursor = end
    out.append(doc[cursor:])
    return "".join(out)


def table(claims: list[dict], verdicts: dict[int, dict], summary: dict) -> str:
    """Markdown table for a PR comment: changed claims first."""
    order = {"rotted": 0, "drifted": 1, "unverified": 2, "fresh": 3}
    rows = sorted(
        ((c, verdicts[c["id"]]) for c in claims if c["id"] in verdicts),
        key=lambda cv: (order[cv[1]["status"]], -cv[1]["confidence"]),
    )
    counts = summary.get("counts", {})
    score = summary.get("freshness")
    head = (
        f"## halflife: freshness {score:.0%}\n\n" if score is not None else "## halflife\n\n"
    ) + (
        f"{counts.get('rotted', 0)} rotted, {counts.get('drifted', 0)} drifted, "
        f"{counts.get('fresh', 0)} still true, {counts.get('unverified', 0)} unverified.\n\n"
    )
    lines = ["| | Claim | What is true now | Source |", "|---|---|---|---|"]
    for c, v in rows:
        text = c["text"].replace("|", "\\|")
        current = (v.get("current") or v.get("note") or "").replace("|", "\\|")
        src = f"[link]({v['source_url']})" if v.get("source_url") else ""
        lines.append(f"| {ICON[v['status']]} | {text} | {current} | {src} |")
    return head + "\n".join(lines) + "\n"
