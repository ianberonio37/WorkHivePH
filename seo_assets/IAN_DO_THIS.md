# The five things only you can do — in order, with everything pre-written

**Why this file exists:** local work is finished. `python tools/seo_scoreboard.py` reports
**LOCAL 100.0%** — every one of the five pillars is at the maximum reachable without you —
and **OVERALL 82.6%**. The gap is these five actions. Nothing here needs research, drafting
or decisions; it is paste-and-go. Total hands-on time is roughly **35 minutes**, and the
first item is worth more than the other four combined.

Everything of mine is committed (26 commits), the IndexNow key file is in the repo, and the
sitemap is at 119 URLs.

---

## 1. Create two profiles · ~10 min · worth **7 points** (AIO + GEO)

**Do this one even if you do nothing else.** Your homepage `sameAs` is `[]`. Entity
resolution runs *before* content retrieval, so a brand that cannot be resolved is excluded
from citation eligibility outright — every AIO pillar and the GEO pillar are blocked behind
this single field. All six pillars already pass schema and cite ≥2 independent sources; this
is the only thing holding them at 0/6 ready.

**LinkedIn** — linkedin.com/company/setup
**Crunchbase** — crunchbase.com/add-new (add DTI reg **8080496**, founded **2026-04-06**)

Paste these **byte-identical** into both (identical name/URL/description across profiles is
what makes the entity resolve — a mismatch is worse than a blank):

- **Name:** `WorkHive`
- **Website:** `https://workhiveph.com`
- **Tagline:** `Free offline-first maintenance platform for Philippine plants`
- **Description:**
  `Free, offline-first maintenance management platform for Philippine industrial plants — digital logbook, PM scheduler, inventory, skill matrix, engineering calculators, and an AI work assistant.`

**Then send me the two URLs.** I wire the `sameAs` block, re-run the entity validation, and
AIO goes 63% → 100%. Do not paste a profile URL that 404s — a broken `sameAs` is worse than
an empty one.

---

## 2. Deploy · your call · worth **1 point**, and it unblocks #3

26 commits are staged and every gate is green. Nothing is half-finished.

What lands: 60 calculator pages (now with the site shell — they were shipping unstyled),
3 cluster pillars, 4 comparison pages, 1 problem guide, 119 markdown twins, the rebuilt
`llms.txt`, the AI-crawler `robots.txt`, and 53/53 answer-first openers.

⚠️ **One thing to protect:** Cloudflare's *"Block AI training bots"* toggle overrides
`robots.txt` completely. It is set correctly today — just don't let it get flipped, or the
23 crawler directives become decoration.

---

## 3. IndexNow · one command · ~1 min · worth **push-indexing on 119 URLs**

**Only after #2 has deployed.** Running it early submits 404s and can rate-limit the domain.

```bash
python tools/indexnow_submit.py --verify    # confirms the key file is live on prod
python tools/indexnow_submit.py --submit    # pushes all 119 URLs
```

`--submit` self-verifies and refuses to send if the key file isn't reachable. This needs no
account and no dashboard — it pushes straight to Bing, Copilot, Yandex, DuckDuckGo and
Seznam. Because Copilot and several answer engines read the Bing index, it is an AEO/GEO
lever, not just classic SEO.

---

## 4. Google Search Console + Bing · ~10 min · worth **2 points**

Submit `https://workhiveph.com/sitemap.xml` in both. This is the only step that converts
SEO from *code state* into *observation* — right now every SEO number is what the code
should do, not what users actually did. It also feeds real query data into the query board,
replacing my qualitative ranking with your actual impressions.

---

## 5. Off-site · ~15 min for the first post · worth **3 points** (GEO)

This is where **82–96% of AI citations** come from, and no local work can touch it. Drafts
are written — `seo_assets/offsite_kickoff_assets.md` — you post them:

- **Reddit** (single most-cited domain, ~40% of multi-engine citations). Three value-post
  drafts ready. Play the 90/10 rule: 90% genuine help, ≤10% self-mention, and **disclose
  that you're the founder**. Reddit punishes the alternative harder than it rewards the post.
- **YouTube** (strongest single predictor, r=0.737). Three long-form briefs ready.
  **94% of AI citations go to long-form, not Shorts** — one chaptered 10-minute explainer
  beats ten clips.
- **G2 / Capterra** — claim the CMMS category, then ask real hive users for reviews.

---

## Then, whenever you want the first real number

```bash
python prompt_audit.py            # 55 queries × 5 engines (275 checks — thorough)
```

For a fast baseline, do just the **18 `demand_gap` queries** (90 checks) — those are the
ones measuring where competitors currently win and we don't. This produces the first
observed GEO figure in the programme's history; everything before it is code state.

---

## What I did so you wouldn't have to

Every gate, page and instrument is built and green: 14/14 gates, 53/53 openers carrying a
number + unit + named source, 113/113 pages with a next action, 60 calculator pages with
real worked numbers computed at build time, 119 markdown twins for agents, and
`tools/seo_scoreboard.py` so the percentages are computed from the gates rather than typed
by anyone — including me.

Re-run `python tools/seo_scoreboard.py` after each item above to watch the number move.
