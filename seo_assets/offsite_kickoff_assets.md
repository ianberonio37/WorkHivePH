# Off-Site Kickoff Assets — the 82-96% earned half

**Why:** 82-96% of AI citations come from earned media, not your own domain `[external-ahrefs-75000-brand-study]`; brand mentions correlate ~3x more than backlinks (0.664 vs 0.218), and **SaaS specifically is cited from G2 + Reddit** `[external-ai-search-citation-analysis-2026-domains-ranked-]`. These are the assets I can prepare; **you post them** (Reddit and G2 detect and punish automation, and posting from your own account is the point).

---

## 1. Reddit — the single most-cited domain (~40% of multi-engine citations)

**The 90/10 rule** `[external-reddit-self-promotion-rules-2026-90-10-avoid-ban]`: ≥90% genuine help, ≤10% self-mention, **disclose you're the founder**, one account, honest tone. **First 2-3 weeks: pure participation, zero mentions.** Only mention WorkHive when someone directly asks "what tool," and disclose.

**Target subreddits:** r/maintenance, r/CMMS, r/reliability, r/PLC, r/IndustrialMaintenance, r/manufacturing, r/Philippines, r/phinvest, r/engineering.

### Value-post draft A — r/maintenance or r/CMMS
> **Title:** How we do shift handover without paying for software (small plant, spotty wifi)
>
> We're a small plant in the Philippines and couldn't justify a paid CMMS seat per tech. What actually moved the needle on lost-between-shifts knowledge was a structured handover: (1) open work orders, (2) abnormal conditions noticed, (3) parts pending. We keep it to three headings so people actually fill it in. Biggest lesson: capture has to happen *on the floor* in the moment — if it waits for the office PC, it doesn't happen. We use voice-to-text in Taglish for that. Happy to share the template format if useful. What does your handover look like?

*(If asked what tool → disclose: "I actually build a free one, WorkHive — happy to share but the format above works in any notebook.")*

### Value-post draft B — r/reliability or r/maintenance
> **Title:** Free way to calculate OEE / MTBF that a supervisor can actually use
>
> A lot of OEE confusion comes from measuring only availability and ignoring speed + quality losses. The formula that stuck for our supervisors: OEE = Availability × Performance × Quality. Worked example — a line available 90%, running 95% of rated speed, 98% good = 0.90 × 0.95 × 0.98 = 83.8%. MTBF is just operating hours ÷ failures; MTTR is repair time ÷ repairs; availability = MTBF/(MTBF+MTTR). We put the formulas + worked examples in a free guide, no signup. What OEE are you running and where's your biggest loss bucket?

### Value-post draft C — r/Philippines or r/manufacturing
> **Title:** DOLE OSHS / LOTO records — how are small plants keeping audit trails?
>
> With RA 11058 / DO 198-18 making OSHS mandatory (fines up to ₱100k/day), the thing inspectors actually check is documentation — LOTO permits, PM completions, incident logs. Paper logbooks fail because entries are missing or nobody can find the book. Curious how other PH plants keep a searchable, dated audit trail without an expensive system?

---

## 2. YouTube — strongest single predictor (r=0.737); long-form only

**94% of AI citations go to LONG-FORM, not Shorts; timestamped chapters get cited repeatedly (78%); views/likes have near-zero correlation** `[external-youtube-seo-ai-citation-study-2026-description-c]`. So: **structure > virality.** 8-15 min, chaptered, full transcript in the description.

### Brief 1 — "How to calculate OEE, MTBF & MTTR (with worked examples)"
- **Chapters:** 0:00 Why these three metrics · 1:30 OEE = A×P×Q (bottling-line worked example) · 4:00 MTBF & MTTR (pump worked example) · 6:30 Availability chains them together · 8:00 PM compliance (the leading indicator) · 9:30 Free calculator + guide
- **Description:** front-load the formulas + a link to `/learn/maintenance-metrics-reliability-guide/`. Full transcript below the fold.
- **CTA:** the free WorkHive calculators (no signup).

### Brief 2 — "Setting up a free offline maintenance logbook for a small factory"
- **Chapters:** 0:00 The spreadsheet problem · 1:00 What to capture (job, asset, parts, downtime) · 3:00 Asset register (ISO 14224) in 10 min · 5:30 Offline-first for spotty wifi · 7:00 30-day rollout
- Links `/learn/start-digital-maintenance-guide/`.

### Brief 3 — "CMMS vs spreadsheet: what a small plant actually needs"
- **Chapters:** 0:00 When a spreadsheet is fine · 1:30 Where it breaks (drift, single owner, no history) · 3:30 What a CMMS adds · 5:00 Free vs freemium (the WorkHive wedge) · 7:00 Migrating without pain
- Targets the "CMMS vs spreadsheet" demand-gap query.

---

## 3. G2 / Capterra — where SaaS AI-citations concentrate

**[IAN]** actions:
1. **Claim the listing** in the **CMMS / Maintenance Management** category on both G2 (g2.com) and Capterra (capterra.com). Use the exact name/URL/description from the entity package (consistency feeds entity resolution too).
2. **Seed 5-10 genuine reviews** from real hive users. Review-ask template below.
3. Profile copy (paste):
   > WorkHive is a free, offline-first maintenance management platform built for Philippine industrial plants. It bundles a digital logbook, preventive-maintenance scheduler, spare-parts inventory, skill matrix, 58 engineering-design calculators, and an AI work assistant — with no per-seat cost and full offline capture for plant floors with unreliable wifi.

### Review-ask template (send to active hive users)
> Hi [name] — if WorkHive has saved you time on [logbook / PM / handover], a short honest review on G2 or Capterra would genuinely help other Filipino plants find it. 2 minutes: [G2 link] / [Capterra link]. What worked and what didn't — honest is more useful than glowing. Salamat!

---

## 4. Digital PR / linkable asset (build once, earn repeatedly)

The **calculator suite is now a linkable asset** (58 free calculators). The next one to build: turn `/learn/ph-industrial-benchmarks-intelligence/` into a citable **"Philippine Plant OEE Benchmarks by Sector"** study with stated methodology + sample size — AI engines cite original research with clear numbers `[external-digital-pr-linkable-assets-b2b-saas-earn-backlin]`. Outreach targets: PSME / IIEE / PIChE, PH manufacturing outlets, and authors of existing "best free CMMS" listicles (ask for inclusion — 48.7% of ChatGPT citations come from third-party listings).

---

## Cadence (from playbook §4.6)

| Channel | Cadence | First action |
|---|---|---|
| Reddit | 3x/week genuine, ≤10% mention | Join + read rules; post draft A |
| YouTube | 1 long-form/month | Record Brief 1 (OEE/MTBF) |
| G2/Capterra | one-time claim + review asks | Claim CMMS category |
| Entity | one-time + 30/60/90 re-test | LinkedIn + Crunchbase (see entity package) |
| PR asset | 1 study/quarter | PH OEE benchmark study |
