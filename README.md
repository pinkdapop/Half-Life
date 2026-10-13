# halflife

Every document decays. halflife tells you how much.

Paste a README, a tutorial, or an onboarding doc. halflife pulls out every claim that can go stale, checks each one against the live web in parallel, and hands the document back annotated: still true, drifted, rotted, or unverified, with the current source linked.

Built for the [Nebius x NVIDIA Global AI Hackathon 2026](https://nebiusglobalaihackathon.devpost.com/).

## How it works

1. **Extract.** NVIDIA Nemotron (served on Nebius Token Factory) reads the document and lists the claims whose truth can change over time: version numbers, prices, commands, endpoints, who holds a role, "X supports Y".
2. **Fan out.** Every claim becomes a Tavily search. Up to 200 run concurrently; results are cached on disk so a re-run of the same document costs nothing.
3. **Judge.** For each claim, Nemotron reads the sources and returns a verdict with a one-line note and the URL that settles it.
4. **Report.** You get the document back annotated inline, a freshness score, and a table you can drop into a PR comment.

The web UI shows the fan-out live: each claim is a node, each search is a probe in flight, each verdict colours the node when it lands.

## Quickstart

```bash
git clone https://github.com/pinkdapop/Half-Life
cd Half-Life
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add NEBIUS_API_KEY and TAVILY_API_KEY
```

Check a file from the terminal:

```bash
halflife check examples/rotted-readme.md --record runs/first.jsonl --md report.md
```

Run the web UI:

```bash
halflife serve
# open http://localhost:8000
```

### Try it without spending credits

A recorded run replays through the full UI with the original timing, so you can develop the swarm view, record the demo video, and show it off without a single API call:

```bash
halflife serve --replay examples/runs/sample.jsonl
```

`examples/runs/sample.jsonl` is a synthetic recording made for UI development. Replace it with a real one: `halflife check <file> --record examples/runs/real.jsonl`.

## Credits budget

The Builder Program gives $50 Token Factory + $25 Tavily. A 200-claim run is 200 searches, so halflife is built to be frugal by default:

- every Tavily result is cached by query hash in `.halflife-cache/`
- claims are deduplicated before fan-out
- `TAVILY_SEARCH_DEPTH=basic` (1 credit per search instead of 2)
- record once, replay forever

## As a GitHub Action

Drop `action/` into a workflow and halflife comments on every PR that touches your docs with what has drifted since the last edit. See [`action/README.md`](action/README.md).

## Layout

```
halflife/
  claims.py     extract checkable claims (Nemotron)
  search.py     Tavily fan-out with disk cache and concurrency limit
  verify.py     per-claim verdict (Nemotron)
  pipeline.py   orchestration; yields events; record and replay
  report.py     annotated markdown and PR-comment table
  cli.py        halflife check / serve / report
  web/          FastAPI app, SSE stream, swarm UI
action/         GitHub Action wrapper
examples/       rotted docs and recorded runs
```

## Stack

- NVIDIA Nemotron via Nebius Token Factory (OpenAI-compatible API)
- Tavily for search
- FastAPI + server-sent events; the UI is one HTML file with no build step

## License

MIT
