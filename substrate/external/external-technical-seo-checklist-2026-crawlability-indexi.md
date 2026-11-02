---
name: external-technical-seo-checklist-2026-crawlability-indexi
type: reference
source: https://developers.google.com/search/docs/essentials/technical
source_sha: 673eb89ca203c800
fetched_at: 2026-11-02T08:56:41Z
last_verified: 2026-11-02
ttl_days: 30
distilled_by: hand-read through WebFetch - re-anchored from debugbear.com, which refuses every connection
supersedes: https://www.debugbear.com/blog/technical-seo-checklist
topic: technical SEO checklist 2026 crawlability indexing
---

## reference · the technical SEO floor: crawlable, working, indexable

The source this chunk was distilled from - DebugBear's "technical SEO checklist" (debugbear.com/blog/technical-seo-checklist)
- refused every connection on 2026-11-02: curl's TLS handshake was refused, a real browser got
ERR_CONNECTION_CLOSED, and WebFetch's socket was closed. Its lever ("crawlability and indexability remain the floor")
now rests on Google's own statement of that floor.

Google Search Central, "Google Search technical requirements" (read 2026-11-02; the page shows no updated date):
* **Googlebot isn't blocked.** The page is publicly accessible and not blocked from crawling; pages behind a log-in are
  not crawled.
* **The page works.** It answers HTTP 200 (success); client and server error pages are not indexed.
* **The page has indexable content.** A file type Google Search supports, within Google's spam policies.
* Meeting them makes a page **eligible** for indexing; it does **not guarantee** indexing (and the page says nothing
  about ranking).

Held on WorkHive's deployed origin by: KA-S (a raw HTTP GET answers 200 and the canonical names the URL),
sitemap-promise, and seo-technical.
