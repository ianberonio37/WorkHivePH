# seo_assets/ — the M2-M5 execution scaffolds

Skeletons for every remaining phase of `SEO_AEO_GEO_MAXIMIZATION_ROADMAP.md`, built 2026-07-19 so execution later is fill-in-the-blank. **M1 already shipped** (5 answer-first openers + comparison table + schema-keep decision — all gates green). These scaffold M2-M5.

| File | Phase | What it is | Blocks on |
|---|---|---|---|
| `entity_schema_scaffold.md` | M2/M3 | Drop-in Organization `sameAs` + full E-E-A-T Person node + LocalBusiness (DTI reg already present). **The #1 AEO lever.** | Ian's profile URLs + 1-2 line bio + registered address |
| `m2_cold_lcp_fix_plan.md` | M2 | Kill the render-blocking Tailwind Play CDN (cold-LCP 3-5s→<2.5s). 3 approaches, self-host recommended. | Ian's OK on approach (site has no build step) |
| `layer_b_playbook_assets.md` | M4 | G2/Capterra profile, YouTube scripts, Reddit playbook, PH digital-PR one-pager, Wikidata item — all "I prep, Ian executes" | Ian executes outward posting (his accounts) |
| `m5_weekly_sov_ritual.md` | M5 | The weekly AI Share-of-Voice measurement loop (`geo_sov_audit.py`, 37 prompts, never run live) | Live answer-engine access (first run = Layer-B baseline) |

## What's genuinely local + I can still do without Ian (exhausted here)
- ✅ Entity JSON scaffold (exact snippet + injection checklist) — structure done, values are Ian's.
- ✅ Cold-LCP approach fully specced (steps + risk + verify) — execution is Ian-gated on approach.
- ✅ Every Layer-B asset skeletoned with the grounded angle + template.
- ✅ SOV ritual documented against the existing harness.

## What is genuinely Ian-gated (cannot be done locally)
- Profile URLs / founder bio / registered address (entity + LocalBusiness values).
- IndexNow key-file **deploy**, then `--submit` (see `SEO_PHASE_5_MEASUREMENT.md` §2b).
- Bing Webmaster + GSC sitemap submission (logins).
- All Layer-B outward posting (G2/Capterra claim, YouTube, Reddit, Wikidata, PR).
- Cold-LCP approach decision (site-wide render-path change).
- First live SOV run (needs the answer engines).

**Next real execution unit** the moment Ian provides input: fill `entity_schema_scaffold.md` (highest leverage) → inject → validate → done.
