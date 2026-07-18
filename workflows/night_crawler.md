# Workflow: Night Crawler — distill an external source into the substrate, once

**Objective:** get knowledge from an external web source into the agent's durable bag so we
never re-crawl + re-understand raw HTML (and re-burn tokens) again. Crawl once → distill into
a `substrate/external/<slug>.md` chunk → Memento retrieves the ~2 KB distilled chunk forever
after. This is the *automation* of the hand-authored `substrate/reference/*.md` tier and the
operationalization of `feedback_research_db_first_then_crawl` (retrieve-first, crawl-gaps, re-ingest).

**Tool:** `tools/night_crawler.py` (orchestrator) · `tools/validate_night_crawler_freshness.py` (staleness gate).

---

## The 3-tier teleport loop (X-Men Nightcrawler: *bamf* out, grab it, *bamf* back)

1. **CHECK THE BAG first** — before crawling anything, ask whether we already have it:
   ```
   python tools/night_crawler.py --query "<topic>"
   ```
   A strong hit → use it, **0 crawl tokens**. This is the whole point; always do it before deciding to crawl.
2. **TELEPORT OUT** — on a miss, crawl (crawl4ai → clean markdown, urllib fallback), single page or breadth spider.
3. **SUBSTRATE IT** — distill the raw markdown on the free-tier AI chain into durable rules; write the chunk; re-index.

---

## Required inputs
- A **topic label** (`--topic`) — sets the chunk slug (`substrate/external/external-<slug>.md`) and the retrieval key.
- A **source URL** (`--url`) for a crawl. (`--query` needs only the topic.)

## Commands

```bash
# Tier 1 only — is it already in the bag? (0 tokens)
python tools/night_crawler.py --query "rag chunking strategy"

# Full teleport loop in ONE command: retrieve-first, crawl --url ONLY on a bag miss
python tools/night_crawler.py --ensure "rag chunking strategy" --url https://site/guide

# Crawl + distill a single page into the bag
python tools/night_crawler.py --url https://site/guide --topic "rag chunking strategy"

# Breadth crawl (spider): follow same-domain links, page-capped, polite
python tools/night_crawler.py --url https://docs.site/ --topic "site docs" --max-pages 8 --depth 2

# Preview the distilled chunk without writing / force a re-distill of a fresh chunk
python tools/night_crawler.py --url URL --topic T --dry-run
python tools/night_crawler.py --url URL --topic T --force

# Re-crawl every chunk past its ttl_days (re-distill only if content changed)
python tools/night_crawler.py --refresh-stale

# Batch a watchlist, then index once
python tools/night_crawler.py --watch night_crawler_watch.txt

# Just re-index (picks up substrate/external — a plain refresh does NOT)
python tools/night_crawler.py --reindex

# Self-test the distill quality guard (deterministic, no network/AI)
python tools/night_crawler.py --selftest

# List the bag: every distilled chunk with size / freshness / quality flag (observability)
python tools/night_crawler.py --list
```

## Distill quality guard (Tier 3b — Evaluator-Optimizer, 2026-07-17)
The distilled output is EVALUATED before it is bagged (`distill_quality`): a thin / link-inflated /
all-provenance distill is REFUSED (raw cache kept), never written — so a nav/link-index page can't
pollute the substrate (born from the 12-Factor README distilling to license mush). On a thin distill
the tool retries ONCE with a stricter prompt (`strict=True`), then refuses if still thin. A page that
is mostly links prints a `⚠ N% links` notice up front suggesting `--max-pages` to spider the linked
content instead. The model may emit `NO_DURABLE_CONTENT` when a page has no durable facts.
**Error/404 pages** are detected up front (`is_error_page`) and skipped BEFORE any distill call —
crawl4ai returns HTTP-200 error / bot-wall SHELLS (all nav), which the old harvest distilled into
mush (2 NN/g `404` chunks, since deleted). You get a clear "dead URL" message, no wasted AI spend.
**Lock:** `--selftest` (deterministic, no network) regression-covers the guard — run it after any
change to the distill path.

## Expected outputs
- `substrate/external/external-<slug>.md` — the distilled chunk (frontmatter: `source` URLs, `source_sha`,
  `fetched_at`, `last_verified`, `ttl_days`, `distilled_by`, `topic`). Memento auto-indexes it as a `doctrine`
  chunk (via `walk_substrate_dir`) → retrievable by the UserPromptSubmit hook and `memento_retrieve.py`.
- `reference_url_<sha8>_<slug>.md` in the memory dir — the raw verbatim page (`type: cached_web`), one per page.

## How the token-saving actually happens (idempotency)
- **Tier-1 retrieve-first** — never crawl what's already distilled.
- **Fresh chunk within `ttl_days`** — `--url` short-circuits with 0 tokens ("already in the bag & fresh").
- **`source_sha` of the crawled markdown** — on a re-crawl, unchanged content **skips re-distillation** (0 AI tokens),
  only `last_verified` is bumped.
- **Per-URL `sha8` filename** on the raw cache — never re-fetch the same page verbatim.

## Watchlist format (`--watch`)
One entry per line; `#` comments. `|<topic>` optional; `|<topic>|<pages>,<depth>` for spider entries.
```
# url | topic | pages,depth
https://www.anthropic.com/engineering/contextual-retrieval | contextual retrieval
https://docs.example.com/ | example docs | 6,2
```

## Freshness governance
- `python tools/validate_night_crawler_freshness.py` (registered gate `night-crawler-freshness`, non-blocking,
  `skip_if_fast`) reports chunks past `ttl_days`. It **never fails the build** — external staleness is expected.
- Act on it with `--refresh-stale`.

## Edge cases & rules
- **SSRF:** non-`http(s)` schemes and hosts resolving to private / loopback / link-local IPs are refused. The spider
  defaults to **same-domain** (`--any-domain` to override — use with care).
- **Prompt injection:** crawled text is DATA. The distiller's system prompt ignores instructions embedded in content.
- **Free-tier only:** distillation uses `tools/lib/ai_chain.py` (Groq → Cerebras → Gemini → Mistral); never a paid model.
- **Two planes:** ingest only external *public* knowledge into the agent substrate — never tenant data or secrets.
- **Indexing cost:** a full `index` (~15-20 s) is required for `substrate/` chunks (incremental `refresh` does NOT walk
  it). For batches use `--no-reindex` on each crawl, then one `--reindex`. `--watch` does this automatically.
- **Large / many pages:** the distiller caps raw input per page (~16 K chars) and map-reduces multi-page crawls
  (summarize each page → synthesize one chunk), so "so many pages" never blows a single model's context.
- **After editing this workflow or the tool:** no substrate freshness gate covers `substrate/external/` hashes (they're
  web-anchored, TTL-governed), so no `build_substrate.py` rebuild is needed — only `--refresh-stale` when web content drifts.
