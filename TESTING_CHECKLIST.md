# WorkHive Testing Checklist — Pre-Launch

A page-by-page test list drawn from your skill files (QA, Frontend, Mobile Maestro, Multitenant, Performance) — covers angles you wouldn't think of from your own seat.

**How to use this:**
- Work through it page-by-page in any order. Use seeded data; no need to type real entries.
- Tick items as `[x]` when verified, leave `[ ]` when failing or skipped.
- A failed test → log it: minor visual = fix here; real platform bug = add to `PRODUCTION_FIXES.md` (just say "save this finding: …").
- Test against **two viewports**: desktop (1280px) and mobile (375px — Chrome DevTools → Device Mode → iPhone SE).
- Test as **two roles**: a `worker` (e.g. `carmenmarquez`) and a `supervisor` (find one in Studio → `hive_members` filter `role=supervisor`).
- Test cross-hive: sign in as a Manila worker, check they cannot see Cebu data anywhere.

**Last updated:** 2026-05-03 · **Reset baseline:** ~6,100 rows across 3 hives × 15 workers

---

## 0. Pre-test smoke tests (every reset+seed)

Run these once after any reset/re-seed:

- [ ] Seeder dashboard shows 12 tables with non-zero counts (3 / 15 / 90 / ~3700 / 90 / ~1500 / 81 / ~440 / 15 / ~30 / ~27 / ~90)
- [ ] Studio → Table Editor → spot-check 3 random rows in `logbook` — Filipino names, real equipment, dates spread over 90 days
- [ ] Studio → `worker_profiles` shows 15 rows with usernames + display_names + emails ending `@auth.workhiveph.com`
- [ ] Sign in to platform with `carmenmarquez` / `test1234` succeeds — navbar shows "Carmen"
- [ ] No red errors in browser console on landing

---

## 1. Authentication & identity (cross-page)

These control the whole platform — break early, fail loudly.

### Sign in
- [ ] Wrong password → "Wrong username or password" (says "username" not "email")
- [ ] Correct credentials → modal closes, navbar shows first name
- [ ] Eye toggle on password field reveals/hides text
- [ ] After sign in, `wh_last_worker` set in localStorage matches your display_name

### Sign up
- [ ] Existing username → live "✗ Username taken" badge appears in <500ms
- [ ] Available username → "✓ Available" badge
- [ ] Password < 6 chars → validation error shown
- [ ] Mismatched confirm password → error shown
- [ ] Sign up with displayName matching a seeded worker_name → "Account secured! Your existing records as [name] are now linked"

### Session restore (cache-clear scenario)
- [ ] Open any page in incognito while signed in → does NOT immediately redirect; async session check restores wh_last_worker from worker_profiles
- [ ] Open any page after clearing localStorage entirely → redirects to `/index.html?signin=1`

### Sign out
- [ ] All seven localStorage keys cleared after sign out: `wh_last_worker`, `wh_worker_name`, `workerName`, `wh_active_hive_id`, `wh_hive_id`, `wh_hive_role`, `wh_hive_name`
- [ ] After sign out, opening any app page redirects to sign-in

### Identity consistency (run on EVERY page)
- [ ] Page reads localStorage with fallback chain (e.g. `wh_active_hive_id || wh_hive_id`) — not just one key
- [ ] Logged-out user lands on sign-in screen (not a `prompt()` dialog) on every page

---

## 2. Hive isolation (multi-tenant) — critical

Sign in as a Manila worker. None of the below should reveal Cebu or Davao data.

- [ ] Logbook list — only Manila entries
- [ ] Inventory — only Manila parts
- [ ] PM scheduler — only Manila assets
- [ ] Skill matrix members list — only Manila workers
- [ ] Community feed (Hive tab) — only Manila posts
- [ ] Marketplace listings — see ALL hives' published listings (this is correct — marketplace is cross-hive)
- [ ] Public feed — only posts where `public=true` from any hive (correct)
- [ ] Analytics — KPIs/charts reflect ONLY Manila data
- [ ] Switch hive (if multi-hive) — every list re-queries with new hive_id, no stale data flashed

---

## 3. Logbook (`logbook.html`)

### Render with seeded data
- [ ] Entries appear in My Entries tab — count matches the worker's seeded count (~100/300/500)
- [ ] Each card shows: machine + tag, category badge (Mechanical/Electrical/etc), maintenance type pill (Breakdown / PM / Inspection / Project), status (Open/Closed)
- [ ] Date shows correctly (90-day range, not all "today")
- [ ] Click an entry → detail view opens with all fields populated: problem, action, knowledge, root cause, downtime, parts, consequence, readings, production output

### Add new entry (real interaction)
- [ ] Step 1: Pick an asset → tag-id field populates
- [ ] Step 2: Maintenance type dropdown shows 4 options: Breakdown / PM / Inspection / Project Work
- [ ] Step 2: Category dropdown shows 7 disciplines (Mechanical / Electrical / Hydraulic / Pneumatic / Instrumentation / Lubrication / Other)
- [ ] Step 2: When category selected AND maint_type is Breakdown → "Quick Readings" section appears with discipline-appropriate fields (e.g. Mechanical → temperature/vibration/pressure)
- [ ] Step 2: Root cause dropdown shows 12 options (Misalignment / Wear / etc)
- [ ] Step 3: Save Entry button enabled only after required fields filled
- [ ] Saved entry appears at TOP of My Entries list immediately
- [ ] Refresh page → new entry persists (it's in the DB)

### Edit-in-place
- [ ] Click "Edit" on any entry → form scrolls into view, banner shows machine name + Cancel
- [ ] All fields pre-populated correctly: machine, type, status, category, problem, root_cause, action, knowledge, downtime, parts, photo, consequence, readings, production_output
- [ ] Step wizard collapsed (all panels visible at once)
- [ ] Cancel returns to "new entry" mode, form cleared
- [ ] Update Entry submits via `saveEditFromForm()` — entry's `id` unchanged, `created_at` unchanged, edited_at populated

### Field parity (silent data loss check)
- [ ] After saving a new entry → reload the page → click that entry's detail → ALL fields you filled appear (none lost)
- [ ] After editing an entry → reload → all edited fields persist
- [ ] Specifically check: `failure_consequence`, `readings_json`, `production_output`, `tasklist_acknowledged` — these are easy to drop in edit modals

### Offline queue (DevTools → Network → Offline)
- [ ] Submit logbook entry while offline → orange "Offline" banner appears
- [ ] Entry shows in list with "Pending sync" badge (not lost)
- [ ] Refresh page while offline → entry still visible (IndexedDB)
- [ ] Go back online → toast "X entries synced"
- [ ] Pending badge disappears

### Team feed
- [ ] Switch to Team Feed tab → list is EMPTY initially with prompt "Search team entries above"
- [ ] Worker dropdown populated with all hive members
- [ ] Date range defaults to last 7 days
- [ ] Tap "Search Team" → results load (server-side filtered)

### Mobile-specific
- [ ] Form inputs do NOT trigger iOS auto-zoom on focus (font-size ≥ 16px)
- [ ] All buttons ≥ 44×44px tap target
- [ ] Photo upload button works on mobile (camera + gallery options)

---

## 4. Inventory (`inventory.html`)

- [ ] Parts list shows 27 items (or whatever your hive count is)
- [ ] Each item shows: part_number, part_name, qty_on_hand, min_qty, bin_location
- [ ] Items below min_qty highlighted (red/orange badge)
- [ ] Filter by category — only matching parts shown
- [ ] Search by part number or name — narrows list

### Use part flow
- [ ] Click "Use" on an item → modal asks qty + reason
- [ ] Submit → qty_on_hand decreases, transaction logged in inventory_transactions
- [ ] If new qty falls below min_qty → low-stock alert (toast/badge)

### Restock flow
- [ ] Click "Restock" → modal for qty
- [ ] Submit → qty_on_hand increases, transaction logged with type=restock

### Approval flow (for shared catalog)
- [ ] Worker submits a NEW inventory item → status=pending
- [ ] Supervisor logs in → sees pending items in approval queue
- [ ] Supervisor approves → status flips to approved, item visible to all
- [ ] Supervisor rejects → item not visible to others

### Field parity
- [ ] Add new item → reload → all fields persist (notes, linked_asset_ids, photo, bin_location)

---

## 5. PM Scheduler (`pm-scheduler.html`)

- [ ] Asset list shows ~30 PM assets (matches seeded count for one hive)
- [ ] Each asset shows: name, tag_id, location, category, criticality, last_anchor_date
- [ ] Click asset → scope items list (the periodic checks)
- [ ] Each scope item shows: item_text, frequency, due date

### Frequency math
- [ ] Weekly items show next-due date 7 days after last completion
- [ ] Monthly items show 30 days
- [ ] Quarterly items show 90 days
- [ ] Overdue items highlighted (red/orange) — date < today

### Mark complete
- [ ] Click "Mark complete" on a scope item → modal opens for notes
- [ ] Submit → completion logged, due date advances
- [ ] Refresh — completion persists, no duplicate row

### Calendar / overview
- [ ] Calendar shows due dates over the next 30/60/90 days
- [ ] Past completions visible with date/worker

---

## 6. Analytics (`analytics.html`)

The most data-hungry page — should have rich content with seeded data.

### Hero numbers (top of page)
- [ ] Total entries: ~3,700 OR ~hive's share if hive-scoped (~1,200)
- [ ] MTBF: realistic number in days/hours, not 0 or NaN
- [ ] MTTR: realistic number in hours
- [ ] PM compliance: 80-100% range
- [ ] OEE / Quality: only shows if production_output rows exist (we seeded some)

### Period selector (critical — common bug area)
- [ ] Default period = last 7 days → numbers reflect just that week
- [ ] Switch to last 30 days → numbers RECALCULATE (don't stay frozen on 7-day data)
- [ ] Switch to last 90 days → numbers grow proportionally
- [ ] Hero numbers show ACTUAL VALUE (e.g. "152 entries"), NOT just direction labels (e.g. ↑ +12%)

### Direction indicators
- [ ] Up-arrow + green for "good" direction (e.g. PM compliance ↑)
- [ ] Down-arrow + red for "bad" direction (e.g. MTBF ↓)
- [ ] Same metric direction is consistent everywhere it appears

### Charts
- [ ] Plotly charts render (not blank)
- [ ] Charts inside collapsed cards still render correctly when expanded (lazy-init / resize on expand)
- [ ] Y-axis shows correct direction (Plotly auto-inverts for decreasing data — verify max value is at top)

### Equipment breakdown
- [ ] Top failing equipment list — populated, sorted by failure count
- [ ] Click equipment → drill-down to entries

---

## 7. Skill Matrix (`skillmatrix.html`)

- [ ] Workers list shows hive members (15 if showing all, ~5 if hive-scoped)
- [ ] Each worker has primary_skill + targets + earned badges count
- [ ] Click worker → discipline grid (Mechanical / Electrical / Instrumentation / Hydraulics / HVAC / Welding / Pipefitting / Reliability / Safety)

### Take exam
- [ ] Click discipline → exam modal opens
- [ ] Score ≥ 70 → badge awarded → appears in worker's badges
- [ ] Score < 70 → "Failed" message, attempt logged in skill_exam_attempts but no badge
- [ ] Cooldown: cannot retake same level immediately (configurable hours)

### Levels
- [ ] Level 1-5 progression — must pass level N before attempting level N+1
- [ ] Level 5 = expert badge

### Heatmap (if visible)
- [ ] Color intensity reflects level (level 5 = darkest)
- [ ] Empty cells = no attempt yet

---

## 8. Community (`community.html`)

### Render with seeded posts
- [ ] Hive tab shows ~30 posts from your hive (we seeded 3-9 per author × 5 authors)
- [ ] Each post shows: author display_name, content, category badge, timestamp, reactions count
- [ ] Categories visible: general, safety, technical, announcement (4 valid values)
- [ ] Posts sorted newest-first

### Post composer
- [ ] Type post → category picker shows 4 options
- [ ] Submit → post appears at TOP of feed immediately (optimistic) AND persists after refresh
- [ ] Posting too fast (3 in 30s) → rate-limit error shown via DB trigger
- [ ] Empty content → submit disabled OR validation error

### Reactions
- [ ] Click 👍 (or other emoji) → reaction count increments, button highlighted
- [ ] Click again → reaction removed, count decrements
- [ ] Reacting to your own post — allowed (or blocked, depending on platform rule)
- [ ] **At 3 reactions on one post → post author's XP increments by 20** (per DB trigger)

### Replies
- [ ] Click reply → composer expands inline
- [ ] Submit → reply appears under post, count increments
- [ ] Replying too fast (5 in 15s) → rate-limit error from trigger
- [ ] **Each reply → +10 XP for replier** (DB trigger)

### Edit / delete own post
- [ ] Edit your own post → content updates, `edited_at` populated, "(edited)" badge appears
- [ ] Soft-delete your own post → disappears from feed, doesn't actually drop from DB

### Mentions
- [ ] Type `@` → autocomplete shows hive members
- [ ] Pick one → name inserted as styled mention
- [ ] Mentioned user gets a notification (if implemented)

### Public toggle
- [ ] Mark a post public → it appears on `public-feed.html` for non-hive members
- [ ] Mark private → removed from public feed

### Realtime
- [ ] Open community in two browser windows (different workers, same hive)
- [ ] Worker A posts → Worker B sees the post appear without refresh (within ~2s)
- [ ] Worker A reacts → Worker B sees reaction count update

### XP & badges (DB triggers)
- [ ] First post in hive → +50 XP
- [ ] Safety category post → +25 XP (stacks)
- [ ] **At 10th post → "Voice of the Hive" badge attempt** (this is currently broken — see PRODUCTION_FIXES.md #1; seeder caps at 9 to avoid)

### Virtual list
- [ ] Scroll the feed — cards beyond viewport collapse to stubs (heights match — no scroll jump)
- [ ] Scroll back up — stubs re-expand to full cards correctly

---

## 9. Public Feed (`public-feed.html`)

- [ ] Only shows posts where `public=true` (we seeded ~30% as public, so expect ~30 posts visible)
- [ ] Posts from ALL hives (not just signed-in user's hive) — this is correct
- [ ] No ability to edit/delete others' posts
- [ ] Reactions still work cross-hive
- [ ] If signed out — public feed STILL accessible (no auth required to read)

---

## 10. Marketplace (`marketplace.html`)

- [ ] Listings show across 3 sections: Parts / Training / Jobs
- [ ] We seeded ~27 listings — confirm visible count
- [ ] Each card: title, price (or "Inquire" for jobs), location, condition badge, seller name + verified tick
- [ ] Filter by section — only matching listings shown
- [ ] Filter by category (Pumps / VFDs / etc) — narrows further
- [ ] Search by keyword — uses search_vector tsvector match
- [ ] Click listing → detail page opens with description, full price, contact info

### Contact-only flow (no Stripe in current launch)
- [ ] "Contact seller" button shows seller_contact (phone/email)
- [ ] No "Buy now" / Stripe checkout button visible (per launch plan)

### Saved searches
- [ ] Save a search → entry created in marketplace_saved_searches
- [ ] Email digest scheduled (won't fire locally; check DB row exists)

### View count
- [ ] Open a listing → view_count increments by 1
- [ ] Refresh same page → only +1 (debounced, not +1 per refresh — TBD if implemented)

---

## 11. Marketplace Seller (`marketplace-seller.html`)

- [ ] My listings tab shows only seller's own listings
- [ ] Status filter: Draft / Published / Sold / Removed
- [ ] Create new listing → form with section/category/title/description/price/condition/location
- [ ] Save as draft → status=draft, not visible in public marketplace
- [ ] Publish → status=published, visible everywhere
- [ ] Edit listing → updates persist
- [ ] Mark sold → status=sold, listing pulled from public

---

## 12. Day Planner (`dayplanner.html`)

- [ ] Page loads (already built per memory — DILO/WILO/MILO/YILO views)
- [ ] Today view shows current day schedule
- [ ] Week view shows 7 days
- [ ] Add schedule item → category, time, notes, optional logbook ref
- [ ] Reload — items persist
- [ ] Items linked to logbook entries — clickable

---

## 13. Engineering Design (`engineering-design.html`)

- [ ] Calc selector shows 6 disciplines (per memory: subcategory headers + search + recent chips)
- [ ] Search bar narrows list
- [ ] Recent chips show last-used calcs
- [ ] Pick a calc → form opens with required inputs
- [ ] Fill inputs → "Calculate" produces a result
- [ ] Generate BOM → 10 sync points pass (per memory: 10 sync points across 2 render functions)
- [ ] Generate SOW → discipline signature line present (13th sync point)
- [ ] Print preview → margin:0 + body padding (no browser headers/footers)
- [ ] PDF export → no blank first page (avoid-all `pagebreak`)

---

## 14. AI Assistant (`assistant.html`)

⚠️ Edge functions need API keys not configured locally — most AI features won't work in test mode. Verify what does:

- [ ] Page loads, conversation history visible
- [ ] Type a message → submit
- [ ] Expect: error message saying API key not configured (graceful failure, not silent freeze)
- [ ] No console errors beyond the expected fetch failure
- [ ] Floating AI button visible on other pages (clears safe-area-inset-bottom on mobile)

---

## 15. Report Sender (`report-sender.html`)

- [ ] Recipient list — pulls from `report_contacts`
- [ ] Period selector — calendar period dates correct (Mon-Sun for week, full month for month)
- [ ] Generate report → preview renders
- [ ] Print preview → margin:0 + body padding
- [ ] Send → expects edge function (won't work locally without Resend key — graceful error OK)

---

## 16. Platform Health (`platform-health.html`)

⚠️ Per recent commit, this page is gated on `marketplace_platform_admins`.

- [ ] Sign in as a regular worker → page redirects or shows "no access"
- [ ] Add yourself to `marketplace_platform_admins` table in Studio (`worker_name = "Carmen Marquez"`, `granted_by = "Seed Admin"`)
- [ ] Refresh → page now loads
- [ ] Validator results visible
- [ ] Failed validators highlighted

---

## 17. Hive Dashboard (`hive.html`)

- [ ] Active hive name shown in header
- [ ] Member list shows worker names + roles
- [ ] Invite code visible (and copy-to-clipboard works) — for supervisors only
- [ ] Switch hive (if multi-hive membership) → entire page re-renders with new hive context
- [ ] Stats: total members, total assets, total open work orders

### Supervisor-only actions
- [ ] As worker: kick member button is HIDDEN (or disabled)
- [ ] As supervisor: kick member button works → audit log entry created in `hive_audit_log`
- [ ] Approve pending member → status changes to active

---

## 18. Symbol Gallery + Architecture (`symbol-gallery.html`, `architecture.html`)

These are reference docs. Quick checks:

- [ ] symbol-gallery.html — IEC/ISA symbols render as inline SVGs (no broken image icons)
- [ ] architecture.html — diagrams render, sections collapsible

---

## 19. Mobile-only checklist (run separately at 375px)

- [ ] All pages at 375px — no horizontal scroll on any
- [ ] Bottom nav-hub (FAB) doesn't overlap iOS home indicator (clears safe-area-inset-bottom)
- [ ] Floating AI button doesn't overlap home indicator
- [ ] Sticky CTAs (e.g. logbook "Save Entry") clear FAB
- [ ] All inputs/textareas/selects ≥16px font-size — focus does NOT auto-zoom
- [ ] Tap targets ≥44×44px (toggles, icons, action buttons)
- [ ] Forms scroll smoothly to focused field on mobile
- [ ] Modals scrollable when content exceeds viewport
- [ ] Pull-to-refresh blocked on form pages (or doesn't break state)

---

## 20. Performance / console (run on every page once)

- [ ] No red errors in browser console
- [ ] No 404 for required scripts/assets (Tailwind/Supabase/utils.js/nav-hub.js — we expect 1 PWA logo 404 from manifest, that's known)
- [ ] Page loads within 3s on simulated Slow 3G (DevTools → Network → Slow 3G)
- [ ] No render-blocking sync fetches (charts/lists should show skeleton/spinner first)
- [ ] No memory leaks: navigate between 3 pages 10× → DevTools → Performance → Memory should stabilize, not grow forever

---

## 21. Cross-page integration (the sneaky bugs)

These bugs only show up by navigating between pages — easy to miss in single-page testing.

- [ ] Sign out from page A → all pages redirect to sign-in
- [ ] Switch hive on page A → page B (when opened next) reflects new hive context
- [ ] Add inventory item on inventory.html → it's pickable in logbook.html "parts used" picker without refresh
- [ ] Add asset on hive.html (or wherever) → it appears in PM scheduler asset list
- [ ] Logbook entry with parts_used → those parts get qty_change tx in inventory_transactions
- [ ] PM completion → optionally creates a logbook entry with `pm_completion_id` reference
- [ ] Community post made → if author has skill_profile, XP increments for the right worker
- [ ] Marketplace listing created → seller's `total_sales` updated when sold

---

## 22. After testing — what to do

For each failed item:

1. **Read the failure carefully.** Is it:
   - A seeder problem (my generated data was wrong) → tell me, I fix the seeder, you reset+re-seed.
   - A platform problem (your code has a real bug or gap) → say "save this finding: [description]" and I append it to `PRODUCTION_FIXES.md` with the right severity tag.

2. **Take a screenshot** if visual.

3. **Note the URL + which user role + which hive** when reporting — narrows the repro.

---

## Suggested test order (one sitting = ~90 min)

If you only have 90 minutes, work through pages in this order — covers 80% of risk:

1. Section 0 (smoke) — 5 min
2. Section 1 (auth) — 10 min
3. Section 2 (hive isolation) — 10 min
4. Section 3 (logbook) — 20 min — most surface area
5. Section 4 (inventory) — 10 min
6. Section 5 (PM scheduler) — 10 min
7. Section 6 (analytics) — 15 min — second most complex
8. Section 8 (community) — 10 min

The rest can be done in follow-up sessions.
