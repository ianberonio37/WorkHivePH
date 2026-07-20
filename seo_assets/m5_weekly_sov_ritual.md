# M5 — weekly AI Share-of-Voice ritual (the measurement loop)

**Why:** you cannot improve what you do not measure, and no dashboard measures whether ChatGPT/Perplexity cite WorkHive. The harness already exists: `tools/geo_sov_audit.py` with **37 bilingual prompts** (English + Taglish) in `prompt_audit_queries.json`, scoring per-engine citation / mention / recommendation / sentiment with a forward-only ratchet. It has **never been run live** — the first run is the Layer-B baseline.

## The ritual (weekly, ~20 min)
1. `python tools/geo_sov_audit.py --score` across ChatGPT / Perplexity / Gemini / Google AI-Overviews / Claude.
2. Log the board: for each engine, is WorkHive **cited / mentioned / recommended**, and at what rank/sentiment.
3. Watch the per-engine split (harvest: only 11% of domains are cited by BOTH ChatGPT + Perplexity — expect uneven progress; Wikipedia matters for ChatGPT, Reddit for AI-Overviews/Perplexity).
4. Trend it weekly; the ratchet flags regressions.

## Targets (from the roadmap)
- **AEO:** ≥70% first-mention on the prompt set.
- **GEO:** #1/tied SOV + ≥70% presence on Perplexity + AI-Overviews.

## Cadence
- **Weeks 1-2:** establish the baseline (first live run) + wire GA4/BWT reporting.
- **Ongoing:** weekly run; ≤90-day content refresh on any article that slips; every new Layer-B asset (G2, Wikidata, Reddit thread, YouTube video) should show up as a citation lift within 2-6 weeks.

## Prereqs
- Live access to the answer engines (Layer B — Ian/session).
- `prompt_audit_queries.json` is ready (37 prompts). Expand toward 50 as new query intents appear.

**Status:** harness READY; first live baseline run is the M3 measurement-go-live step.
