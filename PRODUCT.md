# Product

<!-- impeccable:product-schema 1 -->

_Written 2026-09-15 from the repository's own record — `manifest.json`, `index.html` metadata, the UFAI roadmaps, the seeded hives and personas in `trajectory_registry.json` — per Ian's instruction that a product-truth interview is answered from the repo, not by asking. Lines that go beyond a verbatim source are tagged `(inferred from <file>)`._

## Platform

web

## Users

- **Primary:** Filipino industrial maintenance technicians and their supervisors, working in small multi-tenant teams ("hives") on the plant floor, in fleets, and in field service — on a personal Android phone, mid-shift, often one-handed, sometimes offline (`index.html` meta: "Free industrial tools for Filipino workers at every level … Built for the plant floor"; `manifest.json`: "Digital tools for industrial maintenance technicians"). The seeded hives are an electronics assembly plant, textile mills, jeepney/van/rider fleets, and similar (inferred from `trajectory_registry.json` personas and the seeder).
- **Secondary:** engineers, students and learners who arrive from search at the 60 public calculators (`tools/*/index.html`) and 55 learn articles (`learn/*/index.html`) without signing in (inferred from the registry's `anon` persona rows).
- **Tertiary:** a hive's founder/owner running the hive's month-end, procurement and marketplace side (inferred from the W3 archetypes "The founder's month-end", "Money in, money spent").

## Product Purpose

WorkHive is a free platform of digital maintenance tools — logbook, PM scheduler, inventory/parts tracker, skill matrix, asset hub, alert hub, shift brain, analytics, resume builder, community, marketplace — with an AI assistant grounded in the worker's own records (`manifest.json`, `index.html` meta). It exists so that a Filipino maintenance worker at any level has the same digital tools a licensed CMMS gives a large plant, on the phone already in their pocket. Success is a person completing a real maintenance task end to end on the phone — log the job, schedule the PM, find the part, check the skill, ask the assistant — and coming back the next shift (inferred from `UFAI_TRAJECTORY_ROADMAP.md`'s journey archetypes).

## Positioning

Free for every worker, bilingual (English and Filipino on every screen), offline-first (PWA shell precache with a pending-writes queue), hive-scoped (Supabase row-level security per team), and the assistant answers from the hive's own logbook, PM and inventory rather than from the open internet — a neighbouring CMMS cannot truthfully claim all five at once (inferred from `sw.js`, `wh-i18n-lite.js`, `utils.js`, the AI companion doctrine docs).

## Operating Context

- Served surfaces (measured by `tools/seed_expansion_wave4.py::served_pages()`): 32 root/app pages, 60 calculators, 55 learn articles + the learn index, 4 public pages (about, feedback, privacy-policy, terms-of-service).
- Field conditions: phone widths 320–390 CSS px, 44 px tap targets, one-column at narrow widths, degraded or absent network, noisy plant floor (voice journal), gloves and glare (inferred from `PDDA_UX_PAINPOINT_JOURNEY_ROADMAP.md` and `ACCESSIBILITY_UFAI_ROADMAP.md`).
- Rituals: shift start/end, PM month, breakdown-to-close-out, audit season, typhoon season, month-end (the W3 journey archetypes in `UFAI_TRAJECTORY_ROADMAP.md`).
- Documents and materials people bring: CMMS/SAP-PM exports, OEM manuals, nameplate and fault photos, part photos, resumes, short audio clips (`_fixtures/` kinds in the wave-4 seeder).

## Capabilities and Constraints

- Stack: static HTML pages with vanilla JavaScript and shared chrome (`nav-hub.js`, `wayfinding.js`, `offline-banner.js`, `wh-consent.js`, `utils.js`, `learn-link.js`), Tailwind with a purged build, Supabase (Postgres + RLS, PostgREST, edge functions), a PWA service worker (`sw.js`, precache list, `CACHE_NAME` bumped per change to a precached file), deployed on Vercel.
- Constraints every change must keep: core tools free (no paywall); English + Filipino parity on every screen (`wh_lang`, `wh-i18n-lite.js`); works offline and at 320 px; 44 px targets; shared chrome graded once and styled before paint; a precached file's edit needs a `CACHE_NAME` bump and `validate_sw_shell_membership.py`.
- Terminology: hive (a team/tenant), worker and supervisor (membership roles), nav-hub (the shared navigation shell), companion/assistant (the AI), PM (preventive maintenance), logbook, alert hub, shift brain.
- Undecided product facts: none recorded here; pricing beyond "free for workers" and the marketplace's commercial terms are out of this file's scope.

## Brand Commitments

- Name: WorkHive. Voice: plain, direct, bilingual; controls name their action; errors name the problem and the recovery (the confusion-ledger doctrine in `w4_confusions.json`).
- Type: Poppins 400–800 (`index.html`, `utils.js` `--wh-font`). Palette: amber `#F7A21B` (theme colour) on navy `#0f1e30` (background), with the 24 `--wh-*` tokens in `utils.js` (`--wh-amber`, `--wh-navy`, `--wh-navy-mid`, `--wh-navy-light`, `--wh-blue`, `--wh-green`, `--wh-orange`, `--wh-cloud`, …). These are binding: refinement keeps them; a redesign refines, never replaces, them.

## Evidence on Hand

- Real seeded data: hives, members, logbook, PM, inventory, marketplace rows in the local Supabase stack (`test-data-seeder/`).
- Real uploaded files with provenance: `_fixtures/<kind>/manifest.json` (CMMS export, nameplate photo, part photo, listing photo, resume, audio clip).
- The trajectory registry (`trajectory_registry.json`, 9,849 rows) and its walk receipts (`.tmp/mcp_walks/`), the confusion ledger (`w4_confusions.json`), the accessibility and UX roadmaps.
- Absent, and not to be fabricated: customer testimonials, named customers, benchmarks, press.

## Product Principles

1. The phone on the plant floor is the primary device; everything must work one-handed at 320 px and offline.
2. Filipino is not a translation layer; both languages are first-class on every screen.
3. The worker's own records are the source of truth for the assistant and the analytics; nothing is invented.
4. Free for the worker, forever; the hive's data belongs to the hive (RLS).
5. Every walked confusion becomes a fix; the platform is measured by whether a real person completes the task, not by whether the page renders.

## Accessibility & Inclusion

WCAG 2.2 AA targets (`ACCESSIBILITY_UFAI_ROADMAP.md`): contrast ≥ 4.5:1 for body text, 44 px tap targets, visible focus, `prefers-reduced-motion` honoured, no horizontal scroll at 320 px, screen-reader names on every control (the `aria-label`-only lesson: sighted users need visible names too).
