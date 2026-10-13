"""Score halflife against the ground-truth document.

    halflife check eval/ground_truth.md --record runs/gt.jsonl
    python scripts/eval.py runs/gt.jsonl

Each paragraph of eval/ground_truth.md is one claim with a known answer. Extracted
claims are mapped back to a paragraph by character offset (or by substring when the
model paraphrased), and each paragraph's verdict is compared with the accepted statuses.
Paragraphs that produced no claim count as misses: the extractor skipped something checkable.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "eval" / "ground_truth.md"
KEY = ROOT / "eval" / "ground_truth.json"


def paragraphs(doc: str) -> list[tuple[int, int, str]]:
    out, pos = [], 0
    for para in doc.split("\n\n"):
        out.append((pos, pos + len(para), para.strip()))
        pos += len(para) + 2
    return out


def main(run_path: str) -> int:
    doc = DOC.read_text()
    key = {item["text"]: item for item in json.loads(KEY.read_text())["items"]}
    paras = paragraphs(doc)

    claims: dict[int, dict] = {}
    verdicts: dict[int, dict] = {}
    for line in Path(run_path).read_text().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event["type"] == "claim":
            claims[event["claim"]["id"]] = event["claim"]
        elif event["type"] == "verdict":
            verdicts[event["id"]] = event["verdict"]

    # Map each claim to the ground-truth paragraph it came from.
    by_para: dict[str, list[dict]] = {}
    for cid, claim in claims.items():
        text = None
        if claim.get("start") is not None:
            for start, end, para in paras:
                if start <= claim["start"] < end:
                    text = para
                    break
        if text is None:
            for _, _, para in paras:
                if claim["text"].lower() in para.lower():
                    text = para
                    break
        if text in key and cid in verdicts:
            by_para.setdefault(text, []).append(verdicts[cid])

    hits, misses, skipped = 0, [], []
    confusion: Counter = Counter()
    for text, item in key.items():
        got = by_para.get(text)
        if not got:
            skipped.append(text)
            continue
        # If the extractor split a paragraph into several claims, take the most severe verdict.
        severity = {"rotted": 0, "drifted": 1, "unverified": 2, "fresh": 3}
        status = min((v["status"] for v in got), key=lambda s: severity[s])
        confusion[(item["expect"][0], status)] += 1
        if status in item["expect"]:
            hits += 1
        else:
            misses.append((text, item["expect"], status, got[0].get("note", "")))

    scored = len(key) - len(skipped)
    print(f"ground truth: {len(key)} claims, {scored} scored, {len(skipped)} not extracted")
    if scored:
        print(f"accuracy on scored claims: {hits}/{scored} = {hits / scored:.0%}")
    print(f"overall (skipped count as wrong): {hits}/{len(key)} = {hits / len(key):.0%}\n")

    if misses:
        print("wrong verdicts:")
        for text, expect, status, note in misses:
            print(f"  expected {'/'.join(expect):<16} got {status:<10} {text}\n    {note}")
    if skipped:
        print("\nnot extracted (the extractor missed these):")
        for text in skipped:
            print(f"  {text}")

    print("\nexpected → got:")
    for (exp, got), n in sorted(confusion.items()):
        print(f"  {exp:<10} → {got:<10} {n}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
