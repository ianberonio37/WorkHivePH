---
target: assistant.html as David Velasco (W45887)
total_score: 34
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\assistant.html"
target_fingerprint: "sha256:ac2dd365d741d606a9398dcb586674c5765e3eb11faa6c42f0f55e7fcfd96dad"
target_path: "C:\\Users\\ILBeronio\\Desktop\\Industry 4.0\\AI Maintenance Engineer\\Self-learning Road-Map\\Build & Sell with Claude Code\\Website simple 1st\\assistant.html"
timestamp: 2026-10-12T14-20-50Z
slug: assistant-html
---
⚠️ DEGRADED: single-context (Ian, this session: "only you for now, no other coding agents" - so no sub-agents; Assessment A was
recorded before Assessment B's detector output was read, then B, then this synthesis)

# Critique: assistant.html (Work Assistant) as David Velasco - 2026-10-13, design lens W45887

Mode: Operate (a worker asking about his own plant). Walked through the Playwright MCP at phone-390 and desktop-1280, signed
in through the wall; targeted live probes on the states a screenshot cannot show.

## Design Health Score (before -> after)

| # | Heuristic | Before | After | Key issue |
|---|-----------|--------|-------|-----------|
| 1 | Visibility of System Status | 4 | 4 | scope banner ("answers are based on its live data, read when you ask"), Online/Offline word, "Thinking..." with role=status and staged notes |
| 2 | Match System / Real World | 3 | 4 | plant vocabulary throughout; the persona tag read "· Zaniah" with no role - now "· with Zaniah" |
| 3 | User Control and Freedom | 3 | 4 | New Chat, Chat/Journal, stoppable answers; the open navigation hub had no visible way to close - fixed |
| 4 | Consistency and Standards | 2 | 3 | the navigation button's glyph was a STOP square, beside this page's own stop control - now a compass |
| 5 | Error Prevention | 3 | 3 | empty send disabled, IME composition guard on Enter, disclaimer before acting |
| 6 | Recognition Rather Than Recall | 2 | 3 | the primary navigation control was recognisable by an unlabeled square only |
| 7 | Flexibility and Efficiency | 3 | 3 | suggestion chips, Enter sends; a touch screen was told "Shift+Enter" - now told only what is true there |
| 8 | Aesthetic and Minimalist Design | 3 | 3 | one focused column; the phone header still carries title, worker, persona, language and New Chat on two rows |
| 9 | Error Recovery | 4 | 4 | "I couldn't reach your job records just now ... that does not mean they are missing", offline banner, copy fallback |
| 10 | Help and Documentation | 3 | 3 | the guide chip, the Journal explainer, the AI disclaimer |
| **Total** | | **30/40** | **34/40** | Good -> Strong |

## Design Specificity Verdict
Authored for this product: the banner names the hive and says the answer reads its live data when asked; the three
suggestions are this trade's questions (worst MTBF, what to prioritise this week, parts to reorder); a slow question is saved to
a Journal instead of timing out. Nothing here is category-interchangeable.

Deterministic scan (Assessment B): 1 primary finding - pulsing-dot x1, the .typing-dot "Thinking..." indicator - MEASURED live
and pinned: 0 typing animations at rest; while thinking 3 dots run 1.2 s infinitely on opacity and transform only; 0 under
prefers-reduced-motion; the word "Thinking...", role=status and aria-busy=true carry the state. 6 advisories (design-system
colour 3, font-size 2, radius 1). Walk: 0 overlap or occlusion findings, 0 low-contrast nodes, 0 controls under 44 px, smallest
text 12 px; painted colours 6 of 7 on tokens (one #94a3b8 paragraph). Overlay injection was not run: the live helper writes
live.js into project HTML entries; the browser evidence is the walker's in-page record plus the probes below.

## What's Working
- It says what it knows and how fresh it is, before anyone asks.
- Failure is honest and survivable: unreachable records are named as unreachable, not missing, and the chat continues.
- Long questions do not die on a timeout - they land in the Journal, and the page says so up front.

## Priority Issues (all fixed in this walk, verified live)
- [P1] **The navigation hub stood down for its OWN panel** - every app page. #wh-hub-panel is role="dialog", so
  standDownWhileDialogOpen() matched it on open and set the hub's wrapper to visibility:hidden AND aria-hidden="true": the
  toggle vanished (no visible close on a phone) and the whole open panel left the accessibility tree, painted only because it
  sets visibility:visible itself. Fix (nav-hub.js): stand down only for dialogs OUTSIDE the hub. Measured after: open ->
  wrapper visible, no aria-hidden, toggle on top showing ✕, aria-expanded=true; tap ✕ closes; Escape closes and returns focus
  to the toggle; the sign-in dialog still makes the hub stand down. (/impeccable harden)
- [P1] **The hub's glyph was "🔲", a stop square** - on a chat page, the universal "stop generating" symbol, with no visible
  label at rest. Fix (wh-icons.css, the one central icon library): 🧭; open, the toggle shows ✕ (the old svg rotate-to-X rule
  had been dead since the emoji conversion). (/impeccable clarify)
- [P2] **"· Zaniah" read as part of the worker's name** ("Work Assistant David Velasco · Zaniah") and said nothing about
  who Zaniah is. Fix: "· with Zaniah" (English half only; the Filipino half keeps the original "· "). (/impeccable clarify)
- [P3] **A phone was told "Shift+Enter for a new line"** - no touch keyboard has it. Fix: on a coarse pointer the hint is
  "Enter sends" (English half only). (/impeccable clarify)

## Persona Red Flags
- **Screen-reader user**: opened the hub and met a panel that did not exist for him (aria-hidden ancestor) - fixed.
- **Phone worker in the plant**: opened the hub and had no visible way back - fixed.
- **First-timer**: "Zaniah" with no role - fixed; "FIL" remains a bare code (it carries aria-label "Switch to Filipino").

## Minor Observations
- In Field mode the hub's "All tools" section holds one tile (Home) above an empty scroll area - the hub's, not this page's.
- The two-row phone header is dense; nothing in it is wrong, all of it is load-bearing.

## Questions to Consider
- Should the hub's Field mode keep an "All tools" section that holds a single tile?
- Is "FIL" the right label for the language switch, for a reader who does not yet know it is one?

Questions skipped: 4 Priority Issues would require them, but this is a roadmap row - Ian's standing direction is to fix and
verify what the lens finds, so the fixes are made and the two open questions travel in the report to Ian instead.
