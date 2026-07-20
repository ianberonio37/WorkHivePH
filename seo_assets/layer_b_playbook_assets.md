# Layer-B off-site playbook — asset skeletons (M4)

**Model:** Layer A made WorkHive *citable*; Layer B makes it *cited*. The harvest is one-directional — **~80% of GEO is earned off-site** (mentions beat backlinks ~3×; YouTube ~0.74 correlate; Reddit #1 cited domain; G2/Capterra profiles ~3× citation). **I prep every asset below; Ian executes the outward posting** (his accounts, his voice, his time). Each section is a SKELETON to fill/expand later.

---

## 1. G2 / Capterra product profile  ·  [fresh harvest lever — do this early, high ROI]
_Software-review presence = ~3× higher AI-citation probability (Leapd)._
- **Product name:** WorkHive  ·  **Category:** [PLACEHOLDER: CMMS / Maintenance Management / EAM]
- **Tagline:** free industrial intelligence platform for Filipino plants (logbook, PM, inventory, calculators, AI assistant)
- **Feature list to paste:** [derive from `platform_catalog.py` — logbook, PM scheduler, inventory, skill matrix, engineering calculators, predictive analytics, AI companion, CMMS integrations]
- **Pricing:** Free tier is the working product (no per-seat fee)
- **Seed-review ask template:** [PLACEHOLDER: short message to 5-10 pilot users requesting an honest G2/Capterra review]
- **Ian executes:** claim the listing on g2.com + capterra.com, paste the profile, gather reviews.

## 2. YouTube how-tos  ·  [strongest single AI-visibility correlate ~0.74]
- **Engine:** reuse the existing grounded flagship video pipeline (Remotion — see `reference_remotion_pipeline`).
- **First 5 script topics (map to top learn articles):** [PLACEHOLDER: e.g. "Log a repair by voice in 60s", "Calculate OEE", "Build a PM schedule free", "LOTO in 3 minutes", "Skill matrix from scratch"]
- **Per-video skeleton:** hook (the plain-benefit, no jargon) → 3-step demo → citable stat → CTA to the matching /learn article. Captions + transcript with the stat (crawlable).
- **Ian executes:** record/publish + set up the channel; I draft each script grounded in the article.

## 3. Reddit authentic participation  ·  [#1 cited domain in AI answers]
- **Subreddits:** r/maintenance, r/PLC, r/reliability, r/Philippines, r/engineering [PLACEHOLDER: confirm fit]
- **Rules (non-negotiable):** value-first, answer the actual question, disclose affiliation, NEVER spam/astroturf. One genuinely-helpful answer > ten links.
- **Answer template skeleton:** [problem restated] → [concrete steps] → [optional: "we built a free tool for this" only when directly relevant].
- **Ian executes:** post from his own account, his voice.

## 4. PH digital-PR one-pager  ·  [local authority + LocalBusiness truth]
- **One-pager sections (skeleton):** what WorkHive is (1 line) · the problem (imported ERPs fail PH plants — cite the Chronicle ERP article) · the free-for-Filipino-plants angle · founder (Ian, DTI-registered WorkHive Engineering Services) · 3 citable stats · contact.
- **Target outlets:** PSME, IIEE, PICHE bulletins · Rappler Tech · PhilStar Tech · manufacturing/industry PH blogs [PLACEHOLDER: confirm list].
- **Ian executes:** pitch. I draft the one-pager + tailored pitch notes.

## 5. Wikidata item  ·  [entity grounding → Knowledge Graph → sameAs truth]
- **Item skeleton:** label "WorkHive" · description "free industrial maintenance platform (Philippines)" · instance of: software / web service · developer: WorkHive Engineering Services · country: Philippines · official website: workhiveph.com · inception: 2026-04-06.
- **References:** every statement needs a citable source (the site, DTI record, any press from #4).
- **Ian executes:** submit at wikidata.org (needs an account); I draft the statements + sources. Once live, add the Wikidata URL to `sameAs` (see `entity_schema_scaffold.md`).

---

**Sequencing (when we execute):** G2/Capterra + Wikidata first (fastest citation lift, feed `sameAs`), then Reddit (ongoing), then YouTube (highest ceiling, most effort), then digital-PR. All tracked by the weekly SOV board (`m5_weekly_sov_ritual.md`).
