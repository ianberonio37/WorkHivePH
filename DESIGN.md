---
name: WorkHive
description: Free industrial maintenance tools for every Filipino worker — dark plant-floor UI, amber on navy, Poppins.
colors:
  amber-primary: "#F7A21B"
  amber-deep: "#D88A0E"
  amber-light: "#FDB94A"
  amber-text: "#FDB94A"
  cyan-accent: "#29B6D9"
  cyan-deep: "#1A9ABF"
  cyan-light: "#5FCCE8"
  cyan-text: "#5FCCE8"
  navy-ground: "#162032"
  navy-mid: "#1F2E45"
  navy-raised: "#2A3D58"
  steel-muted: "#7B8794"
  steel-bright: "#CFD7E0"
  cloud-foreground: "#F4F6FA"
  green-ok: "#4ade80"
  red-alert: "#f87171"
  red-text: "#FDC9C9"
  violet-ai: "#a78bfa"
  violet-text: "#C4B5FD"
  text-muted: "rgba(255, 255, 255, 0.80)"
typography:
  display:
    fontFamily: "Poppins, system-ui, -apple-system, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 800
    lineHeight: 1.15
  headline:
    fontFamily: "Poppins, system-ui, -apple-system, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.25
  title:
    fontFamily: "Poppins, system-ui, -apple-system, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Poppins, system-ui, -apple-system, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Poppins, system-ui, -apple-system, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.35
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace"
    fontSize: "0.85rem"
    fontWeight: 700
    lineHeight: 1.3
  # The DOCUMENT role is not the app's type - it is the type of the artefacts the app GENERATES for
  # somebody to print, send or feed to a machine. Recorded here (2026-09-18, W46028) because the record
  # was silent about it and silence made every conforming element read as a violation: the detector
  # flagged resume.html's Arial as "not declared in DESIGN.md typography" when Arial is the correct and
  # deliberate choice - an ATS parses a standard system serif or sans reliably and a webfont poorly, and
  # the sheet is black ink on white paper, a different medium from a dark UI. Same correction the mono
  # role needed on 2026-09-16, and the same reason: a record that describes less than what ships turns
  # working code into findings, and the honest-looking response is to "fix" the working code.
  # Members: resume.html's .resume-paper export sheet; engineering-design.js's drawing title blocks
  # (7-11px labels and signature lines, dark ink on white, to a drafting convention).
  document:
    fontFamily: "Arial, Helvetica, sans-serif"
    fontSize: "12px-24px (the printed sheet's own scale, not the UI ramp)"
    medium: "black ink on white; print and ATS parsing, never a screen surface of the product"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.amber-primary}"
    textColor: "{colors.navy-ground}"
    rounded: "{rounded.sm}"
    height: "44px"
    padding: "6px 16px"
  button-secondary:
    backgroundColor: "rgba(255, 255, 255, 0.06)"
    textColor: "{colors.cloud-foreground}"
    rounded: "{rounded.sm}"
    height: "44px"
    padding: "6px 12px"
  chip-selected:
    backgroundColor: "rgba(247, 162, 27, 0.15)"
    textColor: "{colors.amber-text}"
    rounded: "{rounded.pill}"
    height: "44px"
  card:
    backgroundColor: "{colors.navy-mid}"
    textColor: "{colors.cloud-foreground}"
    rounded: "{rounded.lg}"
    padding: "16px"
  input:
    backgroundColor: "rgba(255, 255, 255, 0.04)"
    textColor: "{colors.cloud-foreground}"
    rounded: "{rounded.sm}"
    height: "44px"
---

# Design System: WorkHive

_Recorded 2026-09-15 from the shipped code (`tokens.css` — the single source of truth the `validate_design_tokens.py` gate holds; `components.css`; `utils.js`; the served pages) by Impeccable's `document` playbook, scan mode, without an interview. Descriptive names below are inferred from the values and PRODUCT.md's brand commitments. This records the incumbent world; refinement preserves it._

## Overview

A dark plant-floor console: deep navy grounds, cloud-white text, one amber accent that marks the primary action and the current selection, cyan for information and links, green/red/violet only as status hues. Everything is built for a gloved hand on a 320–390 px phone first (44 px controls, one column, pills for selection, cards for grouping) and then widens to a 680 px column on desktop. Mood, inferred: industrial, calm, legible at arm's length; no decoration that is not a signal.

## Colors

- **Grounds:** `navy-ground #162032` (page), `navy-mid #1F2E45` (cards, elevation 1), `navy-raised #2A3D58` (elevation 2, hover). Card faces are usually a 145° gradient between the mid and raised navies at 40–80 % over the ground, with a 1 px `rgba(255,255,255,0.07–0.10)` hairline.
- **Primary accent:** amber `#F7A21B` (deep `#D88A0E`, light `#FDB94A`). Amber is the CTA fill (text in navy), the selected tab/chip tint (`rgba(247,162,27,0.15)` face, `0.3–0.4` border), and the tier "gold". `amber-text #FDB94A` is the amber for text on dark (APCA-graded).
- **Secondary accent:** cyan `#29B6D9` (deep `#1A9ABF`, light `#5FCCE8`) for links, information rows, the "platinum" tier; `cyan-text #5FCCE8` on dark.
- **Neutrals:** `cloud #F4F6FA` foreground; `text-muted rgba(255,255,255,0.80)` for secondary text; `steel-bright #CFD7E0` for muted labels on dark (raised from `#A9B6C4` after APCA measurement; `steel #7B8794` only on light surfaces such as resume.html).
- **Status:** green `#4ade80` (ok / XP gained), red `#f87171` (alert; `red-text #FDC9C9` for text on tinted chips), violet `#a78bfa` (the AI companion; `violet-text #C4B5FD`). Status tints are the hue at 7 % on the face and 30 % on the border.
- Rules the code already keeps: no raw brand hex on a page (tokens only, ratcheted by the L3 gate); grays are one cool family (navy-tinted), never mixed warm/cool; no purple/blue "AI gradient" — violet is a status hue for the companion, not a surface.

## Typography

- **Face:** Poppins 400/500/600/700/800 (Google Fonts, `display=optional`), inherited into form controls by a `tokens.css` rule; system-ui fallback.
- **Ramp (target, 16 px root):** display 1.5 rem/800 (level-up, hero numbers), headline 1.125 rem/700 (page titles), title 0.95 rem/700 (section headings, sentence case), body 0.875 rem/400 (0.85–0.9 rem in prose), label 0.75 rem/600 (chips, captions, meta rows). **Floor: 12 px (0.75 rem) for anything a person reads; 11 px is the absolute floor for functional text (Impeccable's detector rule).** The incumbent pages carried a 0.58–0.7 rem micro-label habit (9–11 px, all-caps, +0.08–0.12 em tracking) — measured 2026-09-15 at 1,143 detector findings platform-wide — which the design lenses are removing page by page; do not reintroduce it.
- **Mono (asset codes only):** `ui-monospace, SFMono-Regular, monospace` for nameplate tags in the printed
  report (`analytics-report.html` `.asset-card-name`). A tag like `UPS-002` is read character by character
  and compared against a plate on a machine, so it gets the one face where a zero cannot be an O. It never
  carries prose, a heading or a number a person reads as a quantity. (Recorded 2026-09-15 by the design
  lens: the detector was right that an undeclared family is drift - the answer was to decide, not to hide.)
- KPI digits are `font-variant-numeric: tabular-nums`. Headings are sentence case; all-caps is reserved for 2–3-word status pills at ≥ 0.75 rem with ≤ 0.04 em tracking. Body measure ≤ 70 ch (`max-width: 70ch` on prose blocks). No gradient text.

## Layout

- One centred column: `.page-wrap { max-width: 680px; padding: 1rem }` on app pages; public/learn pages use a wider reading column. Phone first: grids collapse to 2 columns at ≤ 520 px and 1 column at ≤ 340 px; nothing may widen the page (320 px reflow, WCAG 1.4.10).
- Shared chrome on every app page: the nav-hub fab (56 px, bottom-right, `z 9998`) and panel, the companion (`z 9999`), the offline banner (top), the consent region, the source chip (`role=status`) under the page title, the learn chip (bottom-left). Fixed chrome must never cover an interactive control at rest (the overlap record checks it on every walk).
- Spacing rhythm: 4 / 8 / 16 / 24 px; tight inside a group, generous between groups; more space above a heading than below it.

## Elevation & Depth

Layered tonal navies rather than heavy shadows: elevation 0 = ground, 1 = card (`navy-mid`), 2 = raised/hover (`navy-raised`). Shadow vocabulary in `tokens.css`: `shadow-1` (0 1px 2px + 0 2px 6px), `shadow-2` (0 4px 10px + 0 8px 24px), `shadow-3` (0 12px 32px + 0 4px 12px) — offset and soft-blurred, black at 16–34 %. Zero-offset coloured halos (the tier-avatar "glow" family) are decoration under the craft floor and are being retired by the motion/slop lenses; a tier is signalled by its ring colour and a 2 px ring, not a glow.

**Coloured shadows — recorded 2026-09-16 from a census, not asserted.** The sentence above says shadows are black, and the platform ships **73 coloured box-shadows** on served pages. Rather than declare 73 live declarations wrong, they were measured, and the system is recorded as it actually is — with the constraint that separates depth from decoration:

| Shape | Count | Status |
|---|---:|---|
| `0 0 0 2–3px rgba(hue, .08–.15)` — spread only, no blur | 14 | **A RING.** Already endorsed above; mostly focus rings. |
| `0 <y>px <blur>px rgba(hue, .12–.45)` — offset AND blur | 47 | **DEPTH, admitted to the vocabulary.** A control may cast a shadow in its OWN hue (an amber CTA, an accent card): the craft floor's depth test is offset + soft blur, and these pass it. |
| `0 0 <blur>px rgba(hue, .5–.8)` — zero offset, blurred | 12 | **DECORATION. Retired**, per the sentence above. |

So the rule is not "shadows are black". It is **offset + blur, in black OR in the element's own hue; never a zero-offset coloured halo.** The `shadow-1/2/3` tokens remain the default and stay black — a coloured shadow is a deliberate accent on a control that already carries that hue, never a free choice.

This is the same correction the `mono` role needed on the same day, and the reason is worth keeping: DESIGN.md is a record of the *incumbent* system, so a line that describes less than what ships makes every conforming element read as a violation — and then a detector flags 47 of them and the honest-looking response is to "fix" working code. When the record and the code disagree, settle it by measuring the code's SHAPE (here: three distinct shapes wearing one detector label), not by trusting either side.

## Shapes

- Radii: 8 px controls and small chips, 12 px cards and dialogs, 16 px hero/section cards, 999 px pills, 50 % avatars. One silhouette per job (R3): selection controls (`[aria-pressed]`, `[aria-selected]`, `[aria-checked]`, tabs, radios, switches) wear the pill; press buttons keep the 8–12 px card-family radius.
- Hairlines `1px solid rgba(255,255,255,0.07–0.10)`; accent borders are 1 px tints of the status hue, never a thick coloured `border-left`.
- Cards are never nested inside cards; a group inside a card is a flat list with hairline dividers.

## Components

- **Primary button:** amber gradient (`amber-primary → amber-light`, 135°) or flat amber, navy text 700, 8 px radius, `min-height 44px`, `transition opacity 0.15s`; active state dims to 75 %.
- **Secondary / ghost button:** `rgba(255,255,255,0.06)` face, hairline border, cloud text, 44 px; disabled shows `cursor: not-allowed`.
- **Tabs and chips:** pill radius; selected = amber 15 % face, amber text, 40 % border; unselected = white 4 % face, muted text; 44 px tall.
- **Inputs (`.wh-input`, `.wh-select`):** white 4 % face, hairline border, 8 px radius, `min-height 44px`, Poppins inherited, amber focus ring.
- **Cards (`.section-card`, `.simple-card`, `.domain-card`):** navy gradient face, hairline, 16 px radius, 16 px padding; a label (0.75 rem/600) above a hero value (1.125–1.5 rem/800, tabular) above a one-line sub (0.8 rem) and an optional status pill.
- **Verdict banner (plain-read contract):** icon + one bold sentence + one small line, tinted by state (healthy green / watch amber / attention red / empty white 3 %).
- **Source chip:** `role=status`, 0.75 rem muted, under the title: "Live · refreshed on load · based on …".
- **Notices (`_whShowNotice`):** fixed, above the bottom chrome, dismissible with a 44 px ✕, never over an interactive control.
- **Tier rings (`.wh-avatar`):** iron / bronze / silver / gold / platinum / legend — a coloured ring around the initials, the level in a small badge; static at rest.

## Do's and Don'ts

- Do: tokens only; 44 px targets; sentence-case headings; 12 px floor; tabular digits; one accent; ease-out motion under 300 ms on a state change only; `prefers-reduced-motion` honoured; English and Filipino on every screen.
- Don't: micro-labels under 12 px; all-caps tracked eyebrows as headings; kickers above headings; nested cards; zero-offset glows; continuous decorative animation; gradient text; purple/blue AI gradients; three identical icon-heading-text cards as a page's structure; a modal for a task that needs no interruption; the same number rendered twice on one screen.
