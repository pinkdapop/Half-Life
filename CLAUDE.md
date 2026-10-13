# CLAUDE.md — halflife

Read this fully before touching anything. It is the handoff from the planning conversation that produced this repo.

## What this is

halflife finds out how much a document has decayed. Paste a README, tutorial, or onboarding doc; it extracts every claim whose truth can change over time, verifies each one against the live web in parallel, and returns the document annotated: still true, drifted, rotted, or unverified, with the current source linked.

One-line pitch: **Every document decays. halflife tells you how much.**

The problem is real and simple: every judge has lost an afternoon to a setup guide that was true two years ago. The product is the fix, and the swarm visual is the demo.

## The hackathon (this is why the repo exists)

- Nebius x NVIDIA Global AI Hackathon 2026, on Devpost: https://nebiusglobalaihackathon.devpost.com/
- **Submissions close Oct 30, 2026, 10:00 AM PT.** Judging Dec 1–15, winners ~Jan 11, 2027.
- Hard requirements: the project must run on **Nebius Token Factory or Nebius AI Cloud** and use **at least one NVIDIA open-source model** (we use Nemotron via Token Factory).
- Prizes: $20K grand, $10K second, $6K third, **$3K Best Use of Tavily**, Jetson Orin Nano per track winner.
- Tracks: Coding & Agentic Engineering, Best Apps & Agents, Personal AI, Physical AI. We target **Best Apps & Agents** (the GitHub Action also makes a case for Coding & Agentic Engineering; pick one in the submission form, don't straddle).
- Judges are engineers from NVIDIA and Nebius plus Tavily staff. Every sponsor's product must be visibly doing necessary work: Nemotron extracts and judges, Tavily searches, Nebius serves and parallelises.
- The builder is **solo**, no hardware, building with AI assistance. Goal is **first place**. That means: one sharp feature done flawlessly, a convincing 2-minute video, a clean repo with real commit history. Not a platform.
- Credits come from the Nebius Builder Program (https://dev.nebius.com/builders): $50 Token Factory, $50 AI Cloud, $25 Tavily. **Tavily credits are the scarce resource.** A 200-claim run is 200+ searches.

Check the Devpost submission form for the exact fields and video requirements before Oct 28; don't assume.

## Architecture

```
halflife/
  config.py     Settings from env (.env.example lists them all)
  llm.py        chat_json(): Nemotron on Token Factory via the OpenAI SDK, JSON parsing, retries,
                response_format fallback for models that reject it
  claims.py     extract_claims(): chunk doc (8k chars on blank lines), Nemotron lists checkable claims,
                spans resolved back into the doc, dedupe, cap at HALFLIFE_MAX_CLAIMS
  search.py     search(): Tavily AsyncTavilyClient, semaphore(HALFLIFE_CONCURRENCY), disk cache keyed by
                sha1(query|depth|max_results) in .halflife-cache/
  verify.py     judge(): Nemotron reads sources → Verdict(status, confidence, current, source_url, note)
  pipeline.py   run(): async generator of events; record() tees to JSONL; replay() replays with original
                timing; collect() drains into {claims, verdicts, summary}; summarise() computes freshness
  report.py     annotate(): doc with bold claims + verdict footnotes; table(): PR-comment markdown
  cli.py        halflife check <file|url> [--record] [--out] [--md] / serve [--replay] / report
  web/app.py    FastAPI: POST /api/runs, POST /api/runs/replay, GET /api/runs/{id}/events (SSE), GET /
  web/static/index.html  the swarm UI, one file, no build step
action/         composite GitHub Action + entrypoint.py posting a PR comment
examples/rotted-readme.md         a deliberately stale README
examples/runs/sample.jsonl + .md  SYNTHETIC recording for UI dev. Labelled as such. Replace with a real one.
tests/test_offline.py             4 tests, no keys needed. `pytest -q` must stay green.
scripts/bootstrap.sh              git init + gh repo create --public + push
```

### Event protocol (pipeline → CLI / UI / recording)

All events carry `t` (seconds since run start). Types, in order:
`started {chars, source}` → `claims {count}` → `claim {claim}` ×N (document order) → interleaved `probe {id, query}` (search launched) and `verdict {id, verdict}` (search returned and judged, arrives out of order) → `done {summary}`. `error {message}` can appear anywhere.

Claim: `{id, text, query, kind, start, end}`; `start/end` are char offsets into the doc or null if the model paraphrased.
Verdict: `{claim_id, status, confidence, current, source_url, note, cached}`.
Statuses: `fresh` (still true), `drifted` (partly outdated but still works), `rotted` (no longer true), `unverified` (sources don't settle it; never guess).
Freshness score = (fresh + 0.5·drifted) / (fresh + drifted + rotted). Unverified is excluded.

### Stack facts

- Token Factory base URL: `https://api.tokenfactory.nebius.com/v1/`, OpenAI-compatible, bearer key.
- `NEMOTRON_MODEL` defaults to `nvidia/Nemotron-3-Nano-30B-A3B`. **Verify the exact id in the Token Factory catalog on first run** and change `.env` if it differs. Model ids keep the publisher namespace and casing.
- Tavily: `search_depth=basic` (1 credit) by default, `max_results=5`. Advanced costs 2 credits; only switch if basic is demonstrably too weak.
- Python 3.11+, fully async, deps: openai, tavily-python, httpx, python-dotenv, fastapi, uvicorn. Dev: pytest, pytest-asyncio.

## Rules for working in this repo

1. **Never spend credits casually.** Cache stays on. Dedupe stays on. Use `--replay` for UI work. Record real runs with `--record` and reuse them. Before any change that adds API calls, ask whether a replay would do.
2. **Never fake a demo.** `sample.jsonl` is synthetic and must stay labelled synthetic in the README. The video must be recorded from a real `--record`ed run. Judges will ask.
3. **Keep the UI one HTML file, no build step.** Canvas animation driven by the real SSE stream. The swarm is the only loud thing on the page; everything else is quiet text on paper. Palette and type are set in `:root`; verdict colours are the only chroma. No cards, no shadows, no all-caps labels, no decorative motion. Copy is plain sentence case.
4. **Scope discipline.** It is one person with ~17 days. Before adding a feature, ask: does this make the 2-minute video better or the judges' first click better? If not, it's a post-hackathon issue.
5. `pytest -q` green before every commit. `.env` is gitignored; never commit keys.
6. Commit early and often with real messages. The commit history is part of the submission.
7. Don't paraphrase or lengthen the user's README pitch into marketing. Judges can smell generated READMEs; keep it specific and short.

## Known gaps (honest list)

- Model id default is unverified against the live catalog (see above).
- `response_format=json_object` is sent on the first attempt only; if a model errors on it, retries drop it. Watch the logs on first real run.
- `load_text()` for URLs does naive HTML tag stripping. Fine for raw markdown and GitHub READMEs; messy for arbitrary pages. Tavily `extract` would be better but costs credits.
- The annotated doc in the UI is plain text with underlines, not rendered markdown. Acceptable for v1.
- Claims the model paraphrases get `start: null` and don't appear in the annotated doc, only in the list. Prompt insists on exact substrings; measure how often it fails on a real run.
- No tests cover the live pipeline (they'd need keys). Consider one integration test gated on env vars.
- The Action installs from the parent directory via `pip install action/..`; test it once on a real PR before claiming it works in the README.

## Roadmap to Oct 30

- **By Oct 15:** keys in, model id verified, first real `halflife check examples/rotted-readme.md --record examples/runs/real.jsonl`. Look at the claims and verdicts by hand. Fix the prompts until the verdicts are ones you'd trust. This is the whole product; spend the time here.
- **By Oct 18:** UI polished against the real recording. Mobile layout checked. Annotated doc readable. Freshness score prominent.
- **By Oct 20:** GitHub Action tested on a real PR in this repo. Screenshot of the PR comment in the README.
- **By Oct 22:** feature freeze. Everything end-to-end. Post the idea on Devpost's team finder if still solo; a frontend person for the swarm is the only hire worth making.
- **Oct 23–27:** demo video (aim ~2 min: the problem in 15 seconds, paste a stale README, watch the swarm, show the annotated result, show the PR comment, state the stack). README final pass. Record a second real run on a well-known public README for the video if it demonstrates better than the example.
- **Oct 28:** submit on Devpost with a day to spare. Fill every field. Name Nemotron, Token Factory, and Tavily explicitly in the write-up.

## Ideas parked (do not build before Oct 30)

Verifying claims by executing them in a fresh Nebius VM (the "does this README actually run" variant); rendered markdown in the UI; docs-site crawling; scheduled re-checks; multi-doc dashboards. All good, all later.
