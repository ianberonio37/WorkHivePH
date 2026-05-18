# Phase 6: Local Philippine SEO Playbook for WorkHive

**Created:** 2026-05-17
**Owner:** Ian Beronio
**Status:** DTI registration COMPLETE (2026-04-06, Business Name No. 8080496, WorkHive Engineering Services, National scope, owner Ian Lumayno Beronio, valid to 2031-04-06). Most Phase 6 deliverables now executable. **BIR registration intentionally deferred** while WorkHive stays free at the worker tier (see [[project-free-platform-stance]]). Remaining inputs needed to wire LocalBusiness schema fully: registered address + phone + lat/lng + social-handle URLs for sameAs array.
**Scope:** Closing the gap between WorkHive being a global free platform and WorkHive being the default Philippine industrial intelligence platform that AI engines, Google Maps, government agencies, and Philippine industry associations all recognise.

---

## Why local PH SEO is its own phase

Phases 0-5 covered the universal SEO/AEO/GEO playbook adapted for Philippine context. Phase 6 covers the **Philippine-specific authority signals** that international playbooks miss entirely:

- A US/EU SaaS does not need to be in the DTI Negosyo Center directory; a Philippine SaaS does.
- A US/EU industrial tool does not need PSME/IIEE/PIChE member listings; a Philippine industrial tool does.
- A Filipino factory searching "industrial software Philippines" weights local trust signals heavily; a German factory does not.

The 6 deliverables in this phase make WorkHive **provably Philippine-grounded** to every Filipino visitor, every Philippine search engine query, and every AI engine that cross-references country-of-origin signals.

---

## DTI registration complete (2026-04-06)

**WorkHive Engineering Services** is registered with DTI as Business Name No. **8080496**, valid 6 April 2026 to 6 April 2031, National scope, owned by **Ian Lumayno Beronio**. Documentary Stamp Tax paid. This unlocks the majority of Phase 6 deliverables.

| Deliverable | Needs DTI/SEC? | Status |
|---|---|---|
| Google Business Profile | Yes | ✅ Executable now (DTI cert satisfies verification) |
| LocalBusiness JSON-LD schema | Yes | ✅ Executable now (need address + phone + lat/lng) |
| BIR-compliant Marketplace receipts | Yes (BIR is separate from DTI) | Deferred per [[project-free-platform-stance]] (only needed for monetization) |
| PSME / IIEE / PIChE / MAP membership | Most accept sole proprietors | ✅ Executable now as WorkHive Engineering Services |
| DTI Negosyo Center directory | Yes | ✅ Executable now (use Business Name 8080496) |
| Bing Places / Apple Maps listings | Yes | ✅ Executable now |

**Already wired into the platform (`index.html` Organization schema):**
- `legalName`: WorkHive Engineering Services
- `founder`: Ian Lumayno Beronio
- `foundingDate`: 2026-04-06
- `identifier`: DTI Business Name 8080496

**Next regulatory step (deferred by user choice 2026-05-17):** BIR Form 1901 and Mayor's Permit are intentionally deferred while WorkHive stays free at the worker tier. Per [[project-free-platform-stance]], BIR registration is only needed when the user decides to enable Marketplace transactions or any other money-handling feature. None of the Phase 6 SEO deliverables below require BIR. DTI is sufficient.

What stays deferred while WorkHive is free:
- BIR-printed Official Receipts (only needed for Marketplace transactions)
- TIN branch code and 2307 withholding
- Mayor's Permit + Barangay Clearance (LGU compliance for money-handling)
- Stripe live mode for Marketplace

What remains fully executable under the free-platform stance:
- Google Business Profile (DTI cert verifies)
- LocalBusiness JSON-LD schema (`priceRange: "Free"` is accurate and a positive AI-engine signal)
- All PH business directories (BusinessList.ph, Yellow Pages PH, etc.)
- PSME / IIEE / PIChE / MAP memberships
- DTI Negosyo Center, DICT Startup Directory, TESDA partnership exploration
- All Philippine press pitches
- Bing Places / Apple Maps listings

---

## The 6 deliverables

### 1. Google Business Profile (GBP)

**Why critical:** Google Maps, Google Search, and Google Knowledge Panel all draw from GBP. When a Filipino searches "industrial software Philippines" or "free CMMS Philippines," the GBP listing surfaces in the local pack (the map with 3 results above the regular search). Without GBP, you do not appear in the local pack regardless of how good your /learn/ articles are.

**Setup steps (after DTI registration):**

1. Sign in to [business.google.com](https://business.google.com) with the Google account that owns workhiveph.com (consistent with GSC)
2. Add a business; choose "Software company" or "Computer software store" category (Google does not have a "industrial intelligence platform" category yet)
3. Service area: All Philippines (no physical storefront)
4. Verification: most likely postcard to your DTI-registered address (5-14 days). Phone verification sometimes offered for software businesses.
5. After verification, complete the profile:
   - Business name: WorkHive Platform
   - Category: Primary = Software company; Additional = Industrial equipment supplier, Business management consultant
   - Description: 750-character summary mirroring the workhiveph.com Organization schema (consistency builds entity authority)
   - Website: https://workhiveph.com/
   - Phone: PH mobile + landline if available
   - Service areas: list 5-10 major industrial regions (Calabarzon, NCR, Central Luzon, Cebu, Davao, etc.)
   - Photos: logo, founder photo, 5-10 screenshots of the platform
   - Posts: 1 GBP post per week (same content as Facebook Page, plus a "GBP exclusive" promotion offer)

**Maintenance:** post 1x/week, respond to reviews within 24 hours, update photos quarterly.

**KPI:** GBP impressions, direction requests, website clicks, calls. Target 1,000 monthly impressions by month 6.

---

### 2. LocalBusiness JSON-LD schema (currently deferred)

**Why:** Adds structured local-business signals that GBP, Google Search, Bing, and AI engines all consume. Compatible with the existing Organization + WebSite + SoftwareApplication + FAQPage schema in the `@graph` block on `index.html`.

**When to wire it in:** after DTI registration provides a registered address. The schema becomes legitimate at that point.

**Pattern to add to `index.html` `@graph` array (once DTI address available):**

```json
{
  "@type": "LocalBusiness",
  "@id": "https://workhiveph.com/#localbusiness",
  "name": "WorkHive Platform",
  "image": "https://workhiveph.com/brand_assets/workhive-logo-transparent.png",
  "url": "https://workhiveph.com",
  "telephone": "+63-XXX-XXX-XXXX",
  "priceRange": "Free",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "<DTI-registered street>",
    "addressLocality": "<City>",
    "addressRegion": "<Region, e.g. Metro Manila>",
    "postalCode": "<ZIP>",
    "addressCountry": "PH"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "XX.XXXXX",
    "longitude": "XXX.XXXXX"
  },
  "openingHoursSpecification": {
    "@type": "OpeningHoursSpecification",
    "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
    "opens": "09:00",
    "closes": "18:00"
  },
  "areaServed": { "@type": "Country", "name": "Philippines" },
  "sameAs": [
    "https://www.facebook.com/workhiveph",
    "https://www.linkedin.com/company/workhiveph",
    "https://www.youtube.com/@workhiveph",
    "<your Wikidata Q-number URL once Phase 3 Wikidata step done>"
  ]
}
```

Once DTI registration + GBP verification done, paste the actual address + phone + lat/lng + your final social handles into chat and I'll wire it into `index.html`.

---

### 3. Philippine business directories

**Why:** Backlinks from Philippine-TLD or PH-context directories signal regional authority to Google. Several are free; the paid ones are usually not worth it.

**Worth doing (free or low-cost):**

| Directory | Cost | Setup time |
|---|---|---|
| [BusinessList.ph](https://www.businesslist.ph) | Free | 15 min |
| [Yellow Pages Philippines](https://www.yellow-pages.ph) | Free basic, paid premium | 20 min |
| [PhilippineCompanies.com](https://www.philippinecompanies.com) | Free | 15 min |
| [DTI Negosyo Center directory](https://www.dti.gov.ph) | Free (after DTI registration) | 20 min |
| [PEZA business directory](https://www.peza.gov.ph) (if WorkHive registers as IT export enterprise) | Free | 1 hour |
| [DICT Philippine startup directory](https://www.dict.gov.ph) | Free | 30 min |

**Skip:** generic global "Top 10 SaaS" listing sites that charge for inclusion — low domain authority, often spammy, no real referral traffic.

**NAP consistency rule:** Name, Address, Phone must match exactly across GBP, every directory, and your own site footer. Google cross-references these signals. Inconsistent NAP (one directory says "WorkHive Platform Inc.", another says "WorkHive Inc.") splits your local authority signal.

---

### 4. Philippine industry association memberships

**Why:** PSME, IIEE, PIChE, MAP are the gatekeepers of Philippine industrial professional credibility. Member listings give backlinks plus direct access to the people who buy industrial software.

**Target associations (in priority order for WorkHive):**

| Association | What it covers | Why it matters |
|---|---|---|
| **PSME** (Philippine Society of Mechanical Engineers) | Mechanical, maintenance, HVAC | Most directly aligned with WorkHive's reliability/maintenance audience |
| **IIEE** (Institute of Integrated Electrical Engineers) | Electrical, instrumentation, automation | Aligned with engineering-design and integrations articles |
| **PIChE** (Philippine Institute of Chemical Engineers) | Process industries, oil/gas, petrochem | Aligned with predictive and analytics articles |
| **MAP** (Management Association of the Philippines) | Plant managers and ops directors | Decision-maker audience for adoption |
| **SMRP Philippines Chapter** (if chartered) | Maintenance and reliability professionals | Direct skill-matrix overlap |
| **ASEAN Federation of Engineering Organisations (AFEO)** | Regional / ASEAN-wide credibility | Important once expanding beyond PH |

**Engagement playbook per association:**

1. **Year 1:** Apply as member (sole proprietorship is accepted by most). Get directory listing. Attend 1 chapter event per quarter.
2. **Year 2:** Offer quarterly column for the newsletter. Speak at one annual convention.
3. **Year 3:** Sponsor an annual chapter event (PHP 50K-200K depending on association). Apply for an industry-recognition award.

Each association directory listing gives a high-trust backlink. Each convention speaking slot gives video content, press coverage, and direct decision-maker access.

---

### 5. Philippine industrial publications + press

**Why:** Press citations are the highest-authority backlinks possible for a Philippine SaaS. One BusinessWorld article citing WorkHive is worth more SEO authority than 100 directory listings combined.

**Target publications (in priority order):**

| Publication | Reach | Pitch angle |
|---|---|---|
| **BusinessWorld** (tech + business section) | High; daily | Founder profile, PH industrial intelligence quarterly report exclusive |
| **Manila Bulletin Business** | High; daily | Same as above plus PH-tech-startup angle |
| **The Daily Chronicle** (already a WorkHive citation source for logbook article) | Medium; growing | Mutual relationship: they cite WorkHive PH Intelligence data; WorkHive cites their ERP analysis |
| **Philippine Star Business** | High; daily | Free industrial tools for PH workforce angle |
| **Rappler IQ / In The Pipeline** | Medium; tech-focused | AI-in-industry analysis, OFW engineer career angle |
| **TechRadar Philippines** | Medium; tech-focused | Software review angle |
| **Inquirer Tech** | High; daily | Same as Philippine Star |
| **Plant Engineering Magazine (PH edition)** | Industry-focused | Maintenance + reliability deep dive |
| **PSME Engineer's Quarterly** | Member-focused | Quarterly technical column |
| **IIEE Electrical Engineering Journal** | Member-focused | Quarterly technical column |

**Pitch templates worth building:**

- **The data-exclusive pitch:** "First public PH Industrial Intelligence Q3 2026 report shows 62% median plant OEE in Cabuyao food sector. Embargoed under your byline."
- **The founder-story pitch:** "Filipino engineer building free industrial intelligence platform for PH plants; OFW-track career insurance angle."
- **The trend pitch:** "Why imported ERPs keep failing in Philippine plants" (riff on the Chronicle article that WorkHive already cites; offer fresh data).
- **The contrarian pitch:** "AI will not replace Filipino industrial workers; it will document them" (the career-protection thesis from AI Assistant article).

**Cadence:** 1 pitch per month per publication. Most will not respond; 2-3 will land per quarter at full discipline. Each landing is a press release page on your own site + the source backlink.

---

### 6. Government and regulatory authority signals

**Why:** Philippine government agency listings carry .gov.ph backlinks which Google weights very heavily for local authority. They also signal regulatory legitimacy to enterprise buyers.

**Targets:**

| Agency | What to pursue | Authority weight |
|---|---|---|
| **DTI** | Negosyo Center directory + sole proprietorship listing | Very high (.gov.ph) |
| **DOLE** | OSHS-compliant tooling registration (informal recognition); pitch the audit-trail article to DOLE BWC | High |
| **DICT** | Philippine Startup Directory listing; potentially CICT IT-BPM partner | High |
| **TESDA** | Free industrial training partner status; integrate WorkHive Skill Matrix with TESDA TVET competencies | High |
| **DOST** | Innovation directory if you apply as a Philippine tech innovator | High |
| **PEZA** | IT export enterprise registration if you ever monetise overseas | Medium (until needed) |
| **BIR** | BIR-compliant receipt issuance (gating for Marketplace go-live) | Compliance, not SEO |
| **NPC** (National Privacy Commission) | Data Privacy Act compliance registration | Compliance + enterprise-trust signal |

The TESDA partnership is particularly interesting: WorkHive Skill Matrix categories can map to TESDA TVET competency frameworks, which gives the platform pedagogical legitimacy that boosts both SEO (.gov.ph backlink) and the OFW-track career angle (TESDA certs travel internationally).

---

## 6-month Phase 6 execution calendar

| Month | Headline activity | Prerequisite |
|---|---|---|
| **0** | Complete DTI sole proprietorship registration (online via dti.gov.ph or in-person at any DTI office; PHP 500-1,000) | None (do this week) |
| **1** | Google Business Profile setup (postcard verification arrives in ~10 days) + free directory listings (BusinessList.ph, Yellow Pages PH, PhilippineCompanies.com) | DTI complete |
| **2** | GBP verified, LocalBusiness schema added to index.html, DTI Negosyo Center listing, NAP consistency audit across all directories | GBP postcard received |
| **3** | PSME + IIEE membership applications; first attendance at a chapter event | DTI complete |
| **4** | First press pitch round (BusinessWorld + Manila Bulletin + Chronicle + Philippine Star); first GBP review request from early hive members | PH Intelligence Q1 report data available |
| **5** | PIChE + MAP membership; DICT Startup Directory listing; TESDA partnership exploration | Months 3-4 complete |
| **6** | Phase 3 + Phase 5 + Phase 6 all running in parallel; quarterly KPI review against the SEO/AEO/GEO Roadmap | All foundations live |

---

## Coordination with Phase 3 (off-site authority)

Phase 6 deliverables overlap with Phase 3 in several places. The coordination map:

| Surface | Phase 3 covers | Phase 6 covers |
|---|---|---|
| Facebook | Page, Group, posting cadence, cross-posting to industry groups | (none — Phase 3 owns Facebook) |
| LinkedIn | Company page, founder personal, newsletter | (none — Phase 3 owns LinkedIn) |
| Wikipedia | Editing existing PH industry pages | (overlaps; coordinate with Wikidata for entity authority) |
| Industry associations (PSME / IIEE / PIChE / MAP) | Newsletter columns and convention talks | Membership applications, directory listings |
| Philippine publications | Quarterly content pitches | First-press push with data-exclusive angles |
| Government agencies | (none) | DTI, DOLE, DICT, TESDA, DOST listings |
| Google Business Profile | (none) | Phase 6 owns GBP |
| Directories (BusinessList.ph, etc.) | (none) | Phase 6 owns directory listings |

Phase 3 is the brand/community work; Phase 6 is the regulatory/institutional work. Both phases run in parallel from month 1 once DTI is registered.

---

## Tracking Phase 6 wins

Add these to your weekly review alongside the prompt audit:

| Metric | Target month 6 | Target month 12 |
|---|---|---|
| GBP impressions | 1,000/month | 10,000/month |
| GBP website clicks | 50/month | 500/month |
| Directory backlinks (PH .ph TLD) | 5 | 15 |
| Industry association memberships | 2 (PSME + IIEE) | 4 (+ PIChE + MAP) |
| Press citations (PH publications) | 1 landed | 5 landed |
| Government agency listings | 2 (DTI + 1 other) | 4 (DTI + DOLE + DICT + TESDA) |
| LocalBusiness schema live | Yes | Yes (with reviews aggregateRating) |

---

## What I need from you (in priority order)

| Item | Blocks what | When you have it |
|---|---|---|
| **DTI sole proprietorship registration certificate** | GBP, Marketplace, formal listings | Tell me you're registered; I will then prepare the LocalBusiness schema stub for you to fill in |
| **Registered address + landline + lat/lng + verified phone** | LocalBusiness schema | Paste into chat; I batch-update index.html in one pass |
| **Final social handles** (Facebook, LinkedIn, YouTube, TikTok, Wikidata Q-number) | sameAs array completion | Paste into chat; I update sameAs across Organization + LocalBusiness schemas |

If DTI registration is going to take a few weeks, the Phase 6 work parks until then. In the meantime, Phase 3 (off-site authority) and Phase 5 (measurement) can run without it.

---

## Phase 6 closes the SEO/AEO/GEO roadmap

When Phase 6 is executed (typically 6 months of disciplined work), WorkHive will be:

- **On-page complete:** 24 tool-aligned articles, 48K words, full schema stack, audience-broadened, zero em-dashes, 6/6 validator pass
- **Off-site authoritative:** Reddit + Wikipedia + Facebook + LinkedIn + YouTube + TikTok + Wikidata presence; PH industry association memberships; PH press citations
- **Locally rooted:** GBP verified, DTI/DICT/TESDA/DOLE listings, LocalBusiness schema, Philippine directory backlinks
- **Measurable:** GSC + Bing + GA4 + weekly prompt audit + quarterly PH Intelligence report

At that point, WorkHive is the structurally default answer when a Filipino plant manager asks ChatGPT / Perplexity / Gemini / Claude "what free industrial tools should I use" and when Google ranks for "free CMMS Philippines" and when Google Maps surfaces "industrial software" in NCR or Calabarzon.

The platform is then ready for the next chapter: scale, monetisation at the enterprise tier, and the regional expansion that the WorkHive 4-stage path was designed for.
