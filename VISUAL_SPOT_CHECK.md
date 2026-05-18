# Visual Spot-Check Checklist

**26 public pages.** Validators are green; this is the human eyeball pass for things automation can't see (typography flow, mobile overflow, hero alignment, dark-mode contrast on real screens).

**Time budget:** ~30-45 min total. Open each URL in two viewports (Chrome DevTools → Toggle Device Toolbar → iPhone 12 Pro for mobile, then close DevTools for desktop).

**Flask base URL:** `http://127.0.0.1:5000/workhive/`

---

## Universal checklist (every page)

For each page, scan top-to-bottom and confirm:

- [ ] **Logo + nav** renders cleanly; no broken images
- [ ] **H1** is a single line on desktop, wraps to 2-3 lines on mobile (no orphaned single-word lines)
- [ ] **Pill tag** (e.g. "Logbook · Rollout playbook") readable, not overflowing the container
- [ ] **Byline row** with publish + updated date sits under H1, all metadata visible
- [ ] **Orange "Short answer" callout** background contrasts cleanly; left border visible
- [ ] **Cyan "Who this is for" block** below it; bullets render as `·` (middle dot); 2-column on desktop, 1-column on mobile (Chrome DevTools < 640px)
- [ ] **Table of contents** anchor links work (tap each, scrolls to H2)
- [ ] **All H2 sections** render with proper spacing (no collapsed margins, no overflow)
- [ ] **Code blocks** (where present) horizontally scroll on mobile (no wrap-broken layout)
- [ ] **Tables** (where present) scroll horizontally on mobile if too wide; rows zebra on hover
- [ ] **Mid-article orange CTA box** renders with the right tool button (e.g. "Open the Logbook")
- [ ] **FAQ accordions** open and close on tap; `+` rotates to `−` cleanly
- [ ] **Sources list** at bottom; external links open in new tab
- [ ] **Author card** with `WH` orange avatar + email link
- [ ] **Back to /learn/** link works
- [ ] **Footer** with "Last updated 17 May 2026" timestamp
- [ ] **Browser tab title** matches the page title in `<head>`
- [ ] **No console errors** (open DevTools console; ignore Tailwind CDN dev warning)

---

## Per-page deep-dive (the 26)

### 1. Landing (workhive/index.html)

URL: http://127.0.0.1:5000/workhive/index.html

- [ ] Hero "Access Your Memory" loads with logo glow animation
- [ ] "In one paragraph" answer-first block renders below hero
- [ ] FAQ accordion above #join CTA expands cleanly (10 questions)
- [ ] Footer shows "Last updated 16 May 2026" (older timestamp; landing not modified today)
- [ ] OG image preview: open https://www.opengraph.xyz/url/https%3A%2F%2Fworkhiveph.com (when public) or just open `brand_assets/og-social.png` directly — should show the hex pattern + "Free Industrial Tools / for Every Filipino Worker"

### 2. Learn hub (workhive/learn/)

URL: http://127.0.0.1:5000/workhive/learn/index.html

- [ ] Hero "Free guides for the Philippine plant floor"
- [ ] 24 article cards render in a single column
- [ ] Hovering each card lifts it (orange border, transform)
- [ ] No "coming soon" cards remaining (all 23 tools covered)

### 3-26. Each /learn/<slug>/index.html article

For each of the 24 slugs below, run the universal checklist. Mark any anomalies inline:

| # | Slug | Anomalies |
|---|---|---|
| 3 | start-digital-logbook-philippine-factory | |
| 4 | what-is-oee-how-to-calculate | |
| 5 | mtbf-vs-mttr-for-supervisors | |
| 6 | maintenance-shift-handover-template | |
| 7 | spare-parts-inventory-philippine-plants | |
| 8 | free-pm-checklist-templates | |
| 9 | skill-matrix-for-maintenance-technicians | |
| 10 | dilo-wilo-day-planner-supervisors | |
| 11 | free-engineering-calculators-philippine-plants | |
| 12 | ai-work-assistant-maintenance-technicians | |
| 13 | predictive-maintenance-on-a-budget-philippines | |
| 14 | connecting-workhive-to-sap-maximo-cmms | |
| 15 | voice-to-text-maintenance-philippine-plant-floor | |
| 16 | building-asset-register-zero-budget | |
| 17 | maintenance-project-planning-template | |
| 18 | joining-and-growing-your-hive | |
| 19 | industrial-community-of-practice-philippines | |
| 20 | gamifying-maintenance-for-engagement | |
| 21 | industrial-marketplace-philippine-specialists | |
| 22 | predictive-alert-thresholds-plants | |
| 23 | dole-iso-audit-trail-from-logbook | |
| 24 | ai-quality-and-roi-stage-2-plants | |
| 25 | sensor-cmms-gateway-operations | |
| 26 | ph-industrial-benchmarks-intelligence | |

---

## Tool-specific spot-checks (the 4 with HowTo schema variations)

These have unique elements beyond the standard template; eyeball them carefully:

- **Maintenance shift handover** (`#6`): the worked Cabuyao bottling-line handover (lines ~340-380 in the rendered HTML) uses `<pre>` blocks with the P1/P2/P3 pill styling. Confirm the `pill-p1` red, `pill-p2` orange, `pill-p3` grey render on the priority tags.

- **Engineering calculators** (`#11`): the HVAC worked example has 5 `<pre>` code blocks with formula notation. Confirm they render in the orange monospace style and horizontally scroll on mobile (lines are long).

- **AI work assistant** (`#12`): the worked Pampanga food-plant prompt block uses a multi-line `<pre>` for the Taglish AI reply. Confirm formatting preserved and `<em>` italic spans render correctly.

- **Skill matrix** (`#9`): the 6-technician × 8-discipline example matrix uses custom `.lvl-cell` colored circles (1=blue, 2=teal, 3=purple, 4=orange gradient, 0/dash=grey). Confirm all show correctly and the table scrolls horizontally on mobile.

---

## Browser previews to check (after public deploy, optional)

OG card previews:
- [ ] Facebook Sharing Debugger: https://developers.facebook.com/tools/debug/
- [ ] Twitter Card Validator: https://cards-dev.twitter.com/validator
- [ ] LinkedIn Post Inspector: https://www.linkedin.com/post-inspector/
- [ ] WhatsApp: send a link to yourself; preview should show the new orange/navy/hex card

Search engine previews:
- [ ] Google rich results test: https://search.google.com/test/rich-results — paste a `/learn/<slug>/` URL; should show Article + FAQPage + HowTo + BreadcrumbList eligibility
- [ ] Schema.org validator: https://validator.schema.org/ — same; should show 0 errors

---

## If you find anomalies

| Issue type | What to do |
|---|---|
| **Typo in body text** | Open the file, fix the typo, save. No rebuild needed (Flask serves working tree). |
| **Mobile overflow on a table/code block** | Note the slug + section; come back to chat with "table overflow on `slug-name` section X" — I'll add CSS overflow rules. |
| **OG card preview broken** | Re-run `python _gen_og_card.py` (if it still exists) or check `brand_assets/og-social.png` is 1200x630 (right-click → Properties). |
| **JSON-LD error** | Won't happen — validators are green — but if it does, paste the error and I'll fix. |
| **Mobile menu broken** | Already known to work on landing; if broken on `/learn/`, paste the screenshot. |
| **404 on any link** | Tell me the URL; likely a missing trailing slash. |

---

## Sign-off

When done, just say "checklist done" and I'll log the spot-check completion in the SEO roadmap doc.
