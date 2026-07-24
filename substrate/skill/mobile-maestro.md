---
name: skill-mobile-maestro
type: skill
source: skill:mobile-maestro
source_sha: 51d2b0998e3b4fd8
last_verified: 2026-07-13
supersedes: null
---
## skill · mobile-maestro

Mobile UX, touch interactions, PWA, gestures, bottom nav, and safe areas. Triggers on "mobile", "touch", "PWA", "gesture", "swipe", "app-like", "safe area", "bottom nav", "install".

**Sections:** Mobile Maestro Agent · The 44px field GOAL ≠ the 24px WCAG floor; reflow is tested at 320px not 360 (2026-07-23, §11 UFAI DEEPWALK) · Your Responsibilities · How to Operate · getBoundingClientRect UNDER-reports on a transitioning/collapsed dialog — confirm with getComputedStyle before claiming a tap-target bug (Inventory PDDA A-axis, 2026-07-12) · Two mobile-fit failure modes an overflow check misses — trapped content + squished nowrap chips (2026-07-18, live prod journey) · Native-feel CSS baseline — the React-Native benchmark (rubric class T, 2026-07-18) · This Platform's Mobile Context · Grounded UFAI-Sweep mobile lessons (2026-06-07) · `box-sizing:border-box` eats padding — a "24+padding:10=44" tap target actually renders ~32px (2026-07-01, Arc U) · Mobile Checklist · PWA Setup (when requested) · Platform-Specific Mobile Lessons (learned from production) · 1. `viewport-fit=cover` is required before safe areas work · 2. iOS auto-zoom threshold is exactly 16px (1rem) · 2a. Tailwind utility classes silently override wh-input font-size below 16px · 3. `floating-ai.js` mobile bottom needs safe area guard · 4. Checkbox tap targets in checklist.html — audit the `width`/`height` directly · 5. `:active` state is the primary touch feedback mechanism · 6. manifest.json icon sizes — single asset for both 192 and 512 · 7. Bottom Sheet Is the Right UX for Field Confirmation Flows · Stale Panel Content on Slow Mobile Connections · PDF Export on Mobile — Known Browser Limitations · Native Select — Replace With Custom Picker for Browsable Lists · Discipline/Category Pill Rows — Wrap When 4+ Items · PDF `avoid-all` Pagebreak Causes Blank First Page on All Devices · Narrative Blocks — Class Required for Page-Break Safety on Mobile · Offline Queue UX — Field Worker Pattern · Query-First UX for Team/Multi-User Views · Output Format

(Deep source: `skill:mobile-maestro` — retrieve this TOC to know WHICH section to read.)
