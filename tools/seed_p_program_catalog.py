#!/usr/bin/env python3
"""seed_p_program_catalog.py — emit the 500 SECOND-PROGRAM rows (P1-P500) into the registry.

Ian (2026-09-05): a second comprehensive trajectory program — "many real issues + UI/UX
improvement opportunities still remain" across the production pages, spanning all 13 full-stack
layers and the ~102-dim UFAI rubric. This seeder lands the P-A..P-L WAVE CATALOG (the structure);
the deepwalk (Phase 2) then FILLS the specifics issue-driven.

TOKEN-ECONOMY + NO-PHANTOM discipline (CLAUDE.md, and the T201-T500 precedent in
seed_expansion_catalog.py): do NOT hand-invent 500 arcs. Every row is GENERATED as
(a REAL surface on disk) x (a NAMED probe theme), so no row can name a page or a function that
does not exist — build_all() asserts every referenced path/function resolves before writing.

Every one of the 500 enters at status 'specced', pct 5, empty basis - honest: specced, not walked.
The overall program % DROPS when these land (725 -> 1225 rows); that drop is the anti-drift signal
the header is for, never hand-adjusted.

  (default)  insert/replace P1-P500 in trajectory_registry.json (idempotent)
  --dry-run  print the counts and samples, write nothing
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
CRITIC = ROOT / "critic_registry.json"
ROSTER = ROOT / "substrate" / "reference" / "page_roster.json"
FUNCTIONS = ROOT / "supabase" / "functions"

# ---- the 12 waves: id, name, size. Sizes sum to exactly 500 (asserted in build_all). ----
WAVES = [
    ("P-A", "Frontend render & CSS integrity", 72),
    ("P-B", "Auth, RLS & tenant depth", 40),
    ("P-C", "Data correctness & KPI truth", 48),
    ("P-D", "Realtime & subscriptions", 28),
    ("P-E", "Caching, CDN & offline", 32),
    ("P-F", "LLM / AI-chain grounding", 44),
    ("P-G", "Accessibility deep", 44),
    ("P-H", "Mobile, touch & PWA deep", 40),
    ("P-I", "Trust, interpretability & honesty", 36),
    ("P-J", "Cross-page chains v2", 40),
    ("P-K", "Ops, observability & availability", 36),
    ("P-L", "Compound & systemic", 40),
    # P-M (Ian, 2026-09-06: "text wrapped on their container in inventory; the hive board's More overflows left on a
    # phone; hunt other kinds of issues aside from what I raised"): the PHONE-FIT wave - every root/tools page x the 4
    # shapes tools/prove_phone_fit.mjs measures at 390x844. 51 pages x 4 lenses = 204 rows, P501..P704.
    ("P-M", "Phone fit: wrap, overflow & menus", 204),
]

# hive-scoped authed app pages (a real subset of the roster's root kind; asserted to exist)
AUTHED = [
    "achievements.html", "agentic-rag-observability.html", "ai-quality.html", "alert-hub.html",
    "analytics-report.html", "analytics.html", "asset-hub.html", "assistant.html",
    "audit-log.html", "community.html", "dayplanner.html", "engineering-design.html",
    "founder-console.html", "hive.html", "inventory.html", "llm-observability.html",
    "logbook.html", "marketplace-admin.html", "marketplace-seller-profile.html",
    "marketplace-seller.html", "marketplace.html", "ph-intelligence.html",
    "plant-connections.html", "platform-actions.html", "pm-scheduler.html",
    "project-manager.html", "project-report.html", "promo-poster.html", "public-feed.html",
    "report-sender.html", "resume.html", "shift-brain.html", "skillmatrix.html",
    "validator-catalog.html", "voice-journal.html",
]

# surfaces that carry KPI/aggregate numbers a reader trusts
KPI_PAGES = [
    "analytics.html", "analytics-report.html", "asset-hub.html", "alert-hub.html",
    "shift-brain.html", "ph-intelligence.html", "project-report.html",
    "pm-scheduler.html", "inventory.html", "skillmatrix.html", "logbook.html",
    "hive.html", "achievements.html", "founder-console.html", "llm-observability.html",
    "ai-quality.html", "agentic-rag-observability.html", "marketplace-seller.html",
    "audit-log.html", "community.html", "public-feed.html", "dayplanner.html",
    "marketplace-admin.html",
]

REALTIME_PAGES = ["alert-hub.html", "hive.html", "logbook.html", "public-feed.html",
                  "community.html", "shift-brain.html", "marketplace.html"]

TRUST_PAGES = ["marketplace.html", "marketplace-seller.html", "marketplace-seller-profile.html",
               "status.html", "assistant.html", "ai-quality.html", "resume.html",
               "ph-intelligence.html", "public-feed.html", "index.html", "community.html",
               "validator-catalog.html"]

OPS_PAGES = ["status.html", "audit-log.html", "llm-observability.html",
             "agentic-rag-observability.html", "ai-quality.html", "founder-console.html",
             "platform-actions.html", "validator-catalog.html", "offline-fallback.html"]

# ---- probe themes per wave: the NAMED lens each row walks its surface with ----
THEMES = {
    "P-A": [
        ("render resolves", "every tile/field resolves to a real value - no undefined, NaN, "
         "'null', or an empty box standing in for a failed read"),
        ("CSS contract", "no horizontal overflow, no pinned/clipped box, no shift source; the "
         "declared classes are actually wired to elements that exist"),
        ("escHtml coverage", "every innerHTML sink on the page routes through escHtml - a name "
         "carrying markup renders as text, not as HTML"),
        ("empty vs failed", "an empty state and a failed read are visually distinguishable; a "
         "refused (RLS-filtered) read is not painted as 'all clear'"),
    ],
    "P-B": [
        ("cross-hive read refusal", "a member of hive B loads the page while scoped to hive A - "
         "zero foreign rows reach the DOM, and the refusal is legible, not a silent zero"),
        ("write-authz depth", "every mutating control on the page re-checks role at the DB, not "
         "only in the UI - a demoted user's stale tab cannot write"),
    ],
    "P-C": [
        ("tile == DB canonical", "each headline number equals the canonical query for the same "
         "window - measured, not eyeballed"),
        ("cap is not a total", "a row cap, a page size, or a LIMIT is never rendered as a total; "
         "the label says which it is"),
        ("window & label agree", "the qualifier sits NEXT to its figure and names the same window "
         "the query used - no two clocks in one view"),
    ],
    "P-D": [
        ("channel filter is tenant-scoped", "the subscription's filter cannot deliver a foreign "
         "hive's row, proven with a two-context live test, not read off the code"),
        ("listener lifecycle", "navigating away removes the channel - getChannels() returns to "
         "baseline, no leak across a repaint or a route change"),
        ("reconnect & backfill", "after an offline window the view reconciles to the DB rather "
         "than showing a gap it never fills"),
        ("repaint keeps focus & draft", "a live poll repaint does not throw a keyboard user to "
         "body or discard an in-progress field"),
    ],
    "P-E": [
        ("SW staleness", "a shipped change actually reaches a returning visitor - the service "
         "worker version bumps and the old shell cannot survive it"),
        ("_headers is prod-only", "the header contract (CSP, Permissions-Policy, cache-control) "
         "is asserted against PROD, where it is the only place it applies"),
        ("cache key & invalidation", "an LLM/view cache key includes every input that changes the "
         "answer; a stale answer cannot outlive its source"),
        ("offline path", "the offline fallback is reachable and honest about what is unavailable"),
    ],
    "P-F": [
        ("grounding containment", "every number/claim in the generated prose is a member of the "
         "grounding set the request actually sent - digest at render, never trust the model"),
        ("provider fallback chain", "the WHOLE chain is exercised, not just the first hop - each "
         "fallback returns a shaped response and the trace records which one answered"),
        ("rate-limit bucket", "the per-hive and per-user buckets are separate and a noisy caller "
         "cannot starve the hive"),
        ("refusal & error shape", "a refusal, a timeout and an exhausted provider are three "
         "distinguishable states, each JSON-shaped with a trace id"),
    ],
    "P-G": [
        ("keyboard path", "the whole task is completable from the keyboard; focus never lands in "
         "a trap and never disappears after a dynamic update"),
        ("announcement reaches a user", "a status string is not an announcement until it reaches "
         "assistive tech - aria-label alone is invisible to sighted users"),
        ("contrast from CSSOM", "contrast is measured from the computed style, not from the "
         "declared token - the cascade decides"),
        ("semantics & landmarks", "headings, landmarks and control names describe the real "
         "structure, so the page is navigable without sight"),
    ],
    "P-H": [
        ("tap targets", "every interactive control clears the 44px floor at 320px - measured on "
         "the live box, not on the class"),
        ("safe area & chrome", "content clears the notch, the home indicator and the browser's "
         "own bars; nothing load-bearing hides behind them"),
        ("landscape & tablet", "the layout survives 768 landscape - no clipped modal, no Save "
         "button pushed off-screen"),
        ("PWA install & shell", "install, launch and cold-start work as a real app, offline shell "
         "included"),
    ],
    "P-M": [
        ("no horizontal overflow", "at 390 and 360 wide the document is never wider than the viewport and no "
         "visible element is cut at either edge - measured on the live boxes, decorative off-canvas art excluded"),
        ("labels stay on one line", "no button, tab, pill, badge or KPI label wraps onto a second line inside its own "
         "control at phone width - count line boxes with a Range, never the padded height"),
        ("text stays in its card", "no unbroken token (an asset id, an email, a URL, a title) spills past its parent's "
         "box - overflow-wrap / ellipsis / a shorter label, whichever the content deserves"),
        ("menus stay in the viewport", "every more/kebab/menu trigger, once tapped, reveals a menu whose box lies "
         "inside the viewport - anchored menus clamp, sheets never park half off-screen"),
    ],
    "P-I": [
        ("a claim a query enforces", "every trust chip/badge on the surface is backed by a query "
         "that could refute it - no decoration promising what nothing checks"),
        ("honest interpretability", "the page says WHY it shows what it shows, and its confidence "
         "language matches the evidence it actually has"),
        ("the fourth state", "unknown / empty / failed / refused are four distinct states, each "
         "said plainly rather than collapsed into a reassuring zero"),
    ],
    "P-J": [
        ("hand-off carries context", "the state a user built on page A survives into page B - "
         "intent, filters, selection and identity all cross the boundary"),
        ("the return path", "coming back does not lose work, and the back button lands somewhere "
         "the user recognises"),
    ],
    "P-K": [
        ("health is a living producer", "the health/status signal is produced by something that "
         "actually runs - a trust signal without a living producer is decoration"),
        ("the log is greppable", "an error reaches an aggregator with a trace id that ties the "
         "browser event to the edge invocation and the DB write"),
        ("degradation is legible", "a partial outage degrades visibly and specifically - the "
         "scope of an outage is part of the claim"),
        ("the gate actually runs", "the lock this surface claims is registered and re-run - an "
         "unregistered or skipped gate locks nothing"),
    ],
    "P-L": [
        ("compound failure", "two real faults at once (a slow provider + a stale cache; an RLS "
         "refusal + a realtime gap) - the page must stay honest under both"),
        ("systemic ripple", "one write ripples through every consumer that reads it; each "
         "consumer is checked, not only the one the walk happened to open"),
    ],
}

# ── LENS APPLICABILITY (the anti-vacuity rule) ───────────────────────────────────────────────
# ★A LENS POINTED AT A SURFACE THAT CANNOT EXHIBIT IT IS A ROW THAT CAN ONLY EVER PASS VACUOUSLY.
# Measured, not theorised: of P-A's 18 'escHtml coverage' rows, EIGHT landed on pages with no
# innerHTML sink at all (offline-fallback + 7 calculators). Walking those would have produced
# eight clean greens that assert nothing, and 500 such rows is exactly how a program reaches a
# false 100%. So a lens declares the signal its surface must show, the pairing only ever pairs a
# lens with a surface that can exhibit it, and build_all() asserts no vacuous row survives.
# None = the lens applies to every surface in its wave's pool (e.g. "render resolves": every page
# renders; the P-F lenses: every edge function has a response contract).
LENS_SIGNALS = {
    ("P-A", "escHtml coverage"): r"innerHTML",
    ("P-A", "empty vs failed"): r"\.from\(|\.rpc\(|getDb\(|fetch\(",
    ("P-B", "cross-hive read refusal"): r"hive_id|wh_active_hive_id",
    ("P-B", "write-authz depth"): r"\.insert\(|\.update\(|\.delete\(|\.upsert\(",
    # getDb( dropped from this signal (2026-09-05): every founder-gated page calls getDb() just to
    # check access, so symbol-gallery — a static library with no data read — was paired with a
    # 'tile == DB canonical' lens it can never exhibit. A tile needs a READ: .from( or .rpc(.
    ("P-C", "tile == DB canonical"): r"\.from\(|\.rpc\(",
    ("P-C", "cap is not a total"): r"\.limit\(|LIMIT |slice\(0",
    ("P-D", "channel filter is tenant-scoped"): r"\.channel\(|removeChannel|postgres_changes",
    ("P-D", "listener lifecycle"): r"\.channel\(|addEventListener|removeChannel",
    ("P-D", "reconnect & backfill"): r"\.channel\(|navigator\.onLine|postgres_changes",
    ("P-D", "repaint keeps focus & draft"): r"setInterval|setTimeout|\.channel\(",
    ("P-E", "SW staleness"): r"serviceWorker|sw\.js",
    ("P-E", "offline path"): r"offline|navigator\.onLine",
    ("P-E", "cache key & invalidation"): r"cache|Cache",
    ("P-G", "keyboard path"): r"<button|<a |tabindex|<input",
    ("P-G", "announcement reaches a user"): r"aria-|role=|<button",
    ("P-G", "contrast from CSSOM"): r"color|background",
    ("P-H", "tap targets"): r"<button|<a |<input|onclick",
    ("P-H", "PWA install & shell"): r"manifest|serviceWorker|sw\.js",
    ("P-I", "a claim a query enforces"): r"badge|chip|verified|trust|rating|★",
    ("P-J", "hand-off carries context"): r"href=|location\.|localStorage",
    ("P-J", "the return path"): r"href=|history\.|location\.",
    ("P-K", "the log is greppable"): r"console\.error|onerror|trace_id|whTrace",
    ("P-K", "health is a living producer"): r"health|status|uptime|incident",
}

CELLS = {
    "P-A": "narrow-320|worker|browser-ui|operate",
    "P-B": "wide-1920|oversight|api-direct|comply",
    "P-C": "wide-1920|oversight|browser-ui|audit",
    "P-D": "narrow-320|worker|browser-ui|operate",
    "P-E": "narrow-320|worker|browser-ui|operate",
    "P-F": "wide-1920|oversight|api-direct|operate",
    "P-G": "narrow-320|assistive-tech|browser-ui|operate",
    "P-H": "narrow-320|worker|browser-ui|operate", "P-M": "phone-390|worker|browser-ui|operate",
    "P-I": "wide-1920|oversight|browser-ui|audit",
    "P-J": "narrow-320|worker|browser-ui|operate",
    "P-K": "wide-1920|oversight|api-direct|audit",
    "P-L": "fixed-kiosk-print|machine-client|webhook-inbound|operate",
}

LAYERS = {
    "P-A": ["F"], "P-B": ["AU", "S"], "P-C": ["D", "F"], "P-D": ["A", "D", "LB"],
    "P-E": ["CA", "H"], "P-F": ["C", "A", "RL"], "P-G": ["F"], "P-H": ["F", "CA"], "P-M": ["F", "CA"],
    "P-I": ["F", "D"], "P-J": ["F", "A"], "P-K": ["L", "AV", "CI"],
    "P-L": ["F", "A", "D", "AU", "C", "CA", "AV"],
}

# ★LAYERS BELONG TO THE LENS, NOT THE WAVE. Holding them at wave granularity made the two
# invariants contradict each other: the gap map said design-system / symbol-gallery /
# validator-catalog need layer S, S is owned by wave P-B, and P-B's lenses are TENANT-RLS lenses
# (cross-hive reads, write-authz) that genuinely cannot apply to a static gallery page. Both
# assertions were right; the model was wrong. Security on those pages is an ESCAPING concern, and
# the lens that actually exercises it is P-A's "escHtml coverage" — a Frontend-wave lens doing
# Security-layer work. Only a per-LENS mapping can say that. Anything not listed inherits its
# wave's layers.
LENS_LAYERS = {
    ("P-A", "escHtml coverage"): ["F", "S"],     # an innerHTML sink is the XSS surface
    ("P-A", "empty vs failed"): ["F", "D"],      # distinguishing empty from failed is a read concern
    ("P-C", "tile == DB canonical"): ["D", "F"],
    ("P-E", "offline path"): ["CA", "AV"],       # the offline path is availability, not just cache
    ("P-G", "keyboard path"): ["F"],
    ("P-K", "the log is greppable"): ["L"],
    ("P-K", "health is a living producer"): ["AV", "L"],
    ("P-K", "degradation is legible"): ["AV", "F"],
    ("P-K", "the gate actually runs"): ["CI"],
}


def _lens_layers(wave: str, lens: str) -> list:
    return LENS_LAYERS.get((wave, lens), LAYERS[wave])


def _label(path: str) -> str:
    """Human label for a real page path - derived, never invented."""
    if path.startswith("tools/"):
        return path.split("/")[1].replace("-", " ")
    if path.startswith("learn/"):
        seg = path.split("/")[1]
        return "learn index" if seg == "index.html" else "learn: " + seg.replace("-", " ")
    return path[:-5].replace("-", " ")


def _roster() -> dict:
    reg = json.loads(ROSTER.read_text(encoding="utf-8"))
    out = {"root": [], "tools": [], "learn": []}
    for p in reg["pages"]:
        out[p["kind"]].append(p["path"])
    for k in out:
        out[k].sort()
    return out


# An LLM/AI-chain function, recognised by NAME SHAPE rather than a hand-kept list, so a function
# added next month sorts correctly without anyone remembering to edit this file.
_AI_MARKERS = ("voice-", "ai-", "tts-", "rag", "llm", "orchestrator", "agent", "semantic",
               "embed", "ocr", "extract", "summarizer", "assist", "populator", "scan",
               "analyzer", "recommender", "eval", "gateway", "brain", "intelligence",
               # the sibling seeder's canonical AI list (seed_expansion_catalog.WAVE_I_FUNCTIONS)
               # names resume-polish and data-fabric-normalizer as AI; these markers keep the two
               # generators agreeing about what "an AI function" is.
               "polish", "normalizer", "ingest", "capture", "ml-")


def _is_ai_chain(name: str) -> bool:
    return any(m in name for m in _AI_MARKERS)


def _functions() -> list:
    """All edge functions, AI-chain ones FIRST.

    ★P-F's row budget (44) is smaller than the function count (62), so the ORDER of this list
    decides which 18 the wave never reaches. Plain alphabetical dropped the tail - which is the
    entire voice chain (voice-action-router / -semantic-rag / -transcribe / -model-call /
    -embeddings / -journal-agent / -logbook-entry / -report-intent), temporal-rag-orchestrator,
    tts-speak, walkthrough-analyzer, visual-defect-capture and vehicle-doc-extract. For a wave
    named 'LLM / AI-chain grounding' those are the LAST 18 to drop, not the first. Sorting the
    AI-chain functions ahead of the rest makes the truncation land on cmms-sync and
    supervisor-reset-password instead, where this lens has least to say."""
    names = sorted(d.name for d in FUNCTIONS.iterdir()
                   if d.is_dir() and not d.name.startswith("_"))
    return sorted(names, key=lambda n: (0 if _is_ai_chain(n) else 1, n))


_ASSIGN_CACHE: dict = {}


def _gap_assignment() -> dict:
    """wave -> [(page, lens)] : each never-covered cell closed by EXACTLY ONE wave.

    ★ONE CELL, ONE OWNER. Letting every wave whose lenses touch a layer close all of that layer's
    gap cells meant a D gap on nine pages was closed by P-A ("empty vs failed" covers D) AND by
    P-C AND by P-I — three waves each spending rows on the same nine cells. P-A alone carried ~32
    required rows for cells other waves were better placed to own, and its breadth fell to 40/73.
    Assign each cell once, to the FIRST wave in program order that has a lens covering the layer
    and applying to the page, and the redundancy disappears.

    ONE row per gap CELL, not one per lens, for the same reason: a cell is closed by a single row
    naming its page and layer (the earlier per-lens form turned 13 Frontend gaps into 52 rows)."""
    if _ASSIGN_CACHE:
        return _ASSIGN_CACHE
    gaps = _true_gap_cells()
    pools = _pools()
    out = {w: [] for w, _, _ in WAVES}

    def _try(wave, layer, pg):
        if pg not in pools[wave]:
            return False
        hit = next((lens for lens, _ in THEMES[wave]
                    if layer in _lens_layers(wave, lens) and _applies(wave, lens, pg)), None)
        if not hit:
            return False
        if (pg, hit) not in out[wave]:
            out[wave].append((pg, hit))
        return True

    # ★PRIMARY OWNER FIRST. Program order alone handed P-A every cell it could touch — including
    # the D cells that P-C (the data wave) exists to own — because P-A comes first and "empty vs
    # failed" happens to cover D. P-A then carried ~32 required rows and its breadth sat at 40/73
    # while P-C had room to spare. Pass 1 gives a cell to a wave whose DECLARED layers include it;
    # pass 2 lets any wave with a covering lens take what pass 1 could not place.
    for layer, pages in gaps.items():
        for pg in pages:
            placed = any(_try(w, layer, pg) for w, _n, _s in WAVES if layer in LAYERS[w])
            if not placed:
                any(_try(w, layer, pg) for w, _n, _s in WAVES)
    _ASSIGN_CACHE.update(out)
    return _ASSIGN_CACHE


def _required_pairs(wave: str, lenses: list, surfaces: list) -> list:
    """The (surface, lens) pairs THIS wave owns for closing never-covered cells."""
    return list(_gap_assignment().get(wave, []))


_SRC_CACHE: dict = {}


def _src(surface: str) -> str:
    """Surface text, cached — the pairing reads every page once, not once per lens."""
    if surface not in _SRC_CACHE:
        p = ROOT / surface
        try:
            _SRC_CACHE[surface] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            _SRC_CACHE[surface] = ""
    return _SRC_CACHE[surface]


def _applies(wave: str, lens: str, surface: str) -> bool:
    """Can this surface exhibit this lens at all? (see LENS_SIGNALS — the anti-vacuity rule)"""
    sig = LENS_SIGNALS.get((wave, lens))
    if sig is None:
        return True
    if wave == "P-F":                      # edge functions: pooled by name, not read here
        return True
    return bool(re.search(sig, _src(surface), re.I))


def _pair(wave: str, surfaces: list, themes: list, n: int) -> list:
    """n DISTINCT (surface, lens) pairs where the lens CAN apply to the surface.

    Budget is split as evenly as the applicable sets allow: each lens takes a round-robin turn and
    draws its next unused applicable surface, so no lens is starved and no surface is duplicated
    under the same lens. A lens with fewer applicable surfaces than its even share simply runs out
    and the remaining budget flows to the lenses that can still say something — which is the right
    behaviour, and it is REPORTED (--coverage) rather than hidden."""
    # ★BREADTH FIRST, THEN ROTATE, AND SKIP WHAT CANNOT APPLY. A lens-major round-robin (each lens
    # drawing its own next applicable surface) satisfied applicability but collapsed BREADTH:
    # P-A fell from 72 distinct pages to 21, because all four lenses kept drawing from the front of
    # their own pools. The surface axis is the one that must be walked widely — 72 pages under one
    # rotating lens each beats 21 pages under four. So iterate SURFACES in order (every surface is
    # reached before any is reused), and for each take the next lens in diagonal rotation that both
    # applies to it and is not already paired with it.
    T = len(themes)
    pairs, used = [], set()
    # ★REQUIRED PAIRS GO FIRST. Prepending a gap PAGE to the pool is not enough: which lens that
    # page receives depends on its index in the diagonal rotation, so the one lens that covers the
    # needed layer may never be the one assigned (validator-catalog kept missing its L and S cells
    # that way). The cells the gap map demands are therefore emitted explicitly, before the
    # rotation fills the remaining budget.
    probe_of = dict(themes)
    for s, lens in _required_pairs(wave, [t for t, _ in themes], surfaces):
        if len(pairs) >= n:
            break
        if (s, lens) not in used:
            pairs.append((s, (lens, probe_of[lens])))
            used.add((s, lens))
    for d in range(T):
        for si, s in enumerate(surfaces):
            if len(pairs) >= n:
                return pairs
            for k in range(T):
                lens, probe = themes[(si + d + k) % T]
                if (s, lens) not in used and _applies(wave, lens, s):
                    pairs.append((s, (lens, probe)))
                    used.add((s, lens))
                    break
    return pairs


def _spread(surfaces: list, themes: list, n: int) -> list:
    """n DISTINCT (surface, lens) pairs, breadth-first across surfaces with the lens rotating.

    ★The first version of this walked theme-major (all surfaces under lens 0, then lens 1...).
    That is correct only when n >= surfaces x themes; whenever n <= len(surfaces) — which was true
    for FOUR of the twelve waves (P-A 72 rows/72 pages, P-F, P-G, P-H) — every row got lens 0 and
    the other three lenses were never walked at all. The generated catalog is what exposed it:
    P-A's row printed a single lens where the wave declares four. A distribution bug hides in the
    data, not in the code; the surface that renders it is what catches it.

    Diagonal order fixes both halves at once: for offset d, surface s takes lens (s + d) % T. For a
    fixed surface the lens differs on every pass, so across d = 0..T-1 each (surface, lens) pair
    appears EXACTLY once (no duplicate rows), while the first pass already touches every surface
    (breadth first). Taking the first n pairs therefore spreads lenses evenly no matter how n, S
    and T relate."""
    S, T = len(surfaces), len(themes)
    pairs = []
    for d in range(T):
        for s in range(S):
            pairs.append((surfaces[s], themes[(s + d) % T]))
            if len(pairs) == n:
                return pairs
    i = 0                       # n > S*T -> cycle rather than silently truncate (no silent caps)
    while len(pairs) < n:
        pairs.append((surfaces[i % S], themes[i % T]))
        i += 1
    return pairs


_POOL_CACHE: dict = {}


def _pools() -> dict:
    """Per-wave surface pools, every entry a REAL path/function on disk (asserted below)."""
    if _POOL_CACHE:
        return _POOL_CACHE
    roster = _roster()
    fns = _functions()
    all_paths = set(roster["root"]) | set(roster["tools"]) | set(roster["learn"])
    for p in AUTHED + KPI_PAGES + REALTIME_PAGES + TRUST_PAGES + OPS_PAGES:
        assert p in all_paths, f"phantom surface {p!r} - not in page_roster.json"
    tools_pages, learn_pages = roster["tools"], roster["learn"]
    _POOL_CACHE.update({
        "P-A": roster["root"] + tools_pages[:30],
        "P-B": AUTHED,
        "P-C": KPI_PAGES,
        "P-D": REALTIME_PAGES,
        "P-E": ["offline-fallback.html", "index.html"] + AUTHED[:14],
        "P-F": fns,
        "P-G": roster["root"] + tools_pages[:8] + learn_pages[:4],
        "P-H": roster["root"] + tools_pages[:8],
        "P-M": roster["root"] + tools_pages[:8],   # the same phone-facing pool as P-H, every page x every lens
        "P-I": TRUST_PAGES,
        "P-J": AUTHED,
        "P-K": OPS_PAGES,
        "P-L": AUTHED[:20],
    })
    # ── STEER ON THE MEASUREMENT (see _true_gap_cells) ────────────────────────────────────────
    # Prepend each wave's never-covered pages for the layers that wave owns. Prepending (not
    # appending) matters: _spread walks surfaces breadth-first, so a page at the front is reached
    # inside the wave's row budget while one at the back may fall past it.
    gaps = _true_gap_cells()
    for wave, _name, _size in WAVES:
        want = []
        # per-LENS: a gap page only helps if a lens of this wave both COVERS that layer and
        # CAN APPLY to that page. Steering on the wave's layers alone put pages into pools whose
        # lenses could never touch them, and the anti-vacuity rule then refused to pair them —
        # the two invariants deadlocked until the layer model moved down to the lens.
        for lens, _probe in THEMES[wave]:
            for layer in _lens_layers(wave, lens):
                for pg in gaps.get(layer, []):
                    if pg not in want and _applies(wave, lens, pg):
                        want.append(pg)
        if want:
            pool = _POOL_CACHE[wave]
            _POOL_CACHE[wave] = want + [p for p in pool if p not in want]
    return _POOL_CACHE


def _pool_for(wave: str) -> list:
    return _pools()[wave]


def _true_gap_cells() -> dict:
    """(layer -> [pages]) for cells the platform has NEVER covered at that layer.

    ★A CATALOG THAT MISSES AN UNTOUCHED CELL IS THE ONE FAILURE THIS PROGRAM CANNOT AFFORD.
    Phase 1's matrix measured the first cut of this catalog and found NINE applicable cells that
    no locked trajectory had ever walked — symbol-gallery (S/D/L), plant-connections (D/L),
    design-system (S), platform-actions (D), learn/index (F/CA) — because each wave's pool was a
    curated page list (AUTHED, KPI_PAGES, OPS_PAGES) and those five pages fell between them. Five
    hand-added page names would have closed it for today and silently re-opened the next time a
    page is added.

    So the pools are STEERED by the measurement instead: every wave prepends the pages that are
    genuinely uncovered for the layers that wave owns, and build_all() then ASSERTS no true-gap
    cell is left unnamed. The guarantee holds as the platform grows, which a hand-list cannot."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_coverage_matrix import build as _build_matrix
    m = _build_matrix()
    gaps: dict = {}
    for c in m["cells"]:
        # Steer on `applicable AND locked_legacy_rows == 0`, NOT on verdict == "gap".
        # The verdict already accounts for P rows, so seeding a cell flips it out of `gap` and the
        # next run would drop the page again — the pools would oscillate instead of converging.
        # This condition depends only on the legacy program and the page's own source, so it is
        # the same on every run: 51 cells today, and the same 51 after seeding.
        # Pages walked by a locked legacy row (`gap-legacy`) are deliberately NOT steered on —
        # they were covered, merely unprovable at layer granularity, and chasing them would spend
        # the row budget re-covering finished work.
        if c["applicable"] and not c["locked_legacy_rows"]:
            gaps.setdefault(c["layer"], []).append(c["page"])
    return gaps


def build_all() -> list:
    pool = _pools()
    rows = []
    n = 0
    for wave, wname, size in WAVES:
        pairs = _pair(wave, pool[wave], THEMES[wave], size)
        for surface, (theme, probe) in pairs:
            n += 1
            is_fn = wave == "P-F"
            where = f"supabase/functions/{surface}" if is_fn else surface
            label = surface if is_fn else _label(surface)
            rows.append({
                "id": f"P{n}", "wave": wave, "status": "specced", "pct": 5, "basis": "",
                "title": f"{theme} - {label}",
                "story": (f"Walk {where} with the '{theme}' lens: {probe}. "
                          "Record every pain with a file:line receipt (A7), fix central-first, "
                          "close with an instrument the walk itself discovered, then lock."),
                "pages": [] if is_fn else [surface],
                "functions": [surface] if is_fn else [],
                "layers": _lens_layers(wave, theme),
                "cells": [CELLS[wave]],
            })
    _want = sum(sz for _, _, sz in WAVES)
    assert len(rows) == _want, f"P program must be exactly {_want} rows (the WAVES sizes), built {len(rows)}"
    assert [r["id"] for r in rows] == [f"P{i}" for i in range(1, _want + 1)]
    # ★TEETH for the distribution bug this seeder actually shipped once (see _spread): a wave that
    # declares four lenses and walks one is a silently narrowed program - the count still reads 500
    # and the header still reads 5%, so nothing else in the stack could notice. Assert here, where
    # the rows are built, that every declared lens is actually walked and no (surface, lens) pair
    # is duplicated.
    for wave, wname, size in WAVES:
        wrows = [r for r in rows if r["wave"] == wave]
        seen_lens = {r["title"].rsplit(" - ", 1)[0] for r in wrows}
        want_lens = {t for t, _ in THEMES[wave]}
        assert seen_lens == want_lens, (
            f"{wave}: declares lenses {sorted(want_lens)} but walks {sorted(seen_lens)} - "
            "the wave would be silently narrowed")
        pairs = [(r["title"], tuple(r["pages"] or r["functions"])) for r in wrows]
        assert len(set(pairs)) == len(pairs), f"{wave}: duplicate (surface, lens) rows"

    # ★THE INVARIANT: no never-covered cell may be left unnamed by the catalog. This is the check
    # Phase 1 had to discover by measuring; from here it fails the build instead. If a wave's row
    # budget is too small to reach its steered pages the assert fires with the exact cells, which
    # is a real signal (re-balance the sizes), never something to silence.
    # ★ANTI-VACUITY: no row may point a lens at a surface that cannot exhibit it.
    vac = [(r["id"], r["title"]) for r in rows if r["pages"]
           and not _applies(r["wave"], r["title"].rsplit(" - ", 1)[0], r["pages"][0])]
    assert not vac, f"vacuous rows (lens cannot apply to surface): {len(vac)} e.g. {vac[:5]}"

    named = {(p, l) for r in rows for p in (r["pages"] or []) for l in r["layers"]}
    missed = sorted((p, l) for l, ps in _true_gap_cells().items() for p in ps
                    if (p, l) not in named)
    assert not missed, ("never-covered cells left unnamed by the P catalog "
                        f"({len(missed)}): {missed[:8]}")
    # no-phantom proof: every referenced surface resolves on disk
    for r in rows:
        for p in r["pages"]:
            assert (ROOT / p).exists(), f"{r['id']}: page {p} does not exist on disk"
        for f in r["functions"]:
            assert (FUNCTIONS / f).is_dir(), f"{r['id']}: function {f} does not exist on disk"
    return rows


def _critic_rows(rows: list) -> list:
    """The matching CRITIC-DEEPWALK rows for the 500 P trajectories.

    ★×16, and the gate proved it in the same hour: critic_registry's R3 requires EVERY non-descoped
    trajectory id to appear in the critic bank exactly once, so the instant the registry grew to
    1225 the critic gate went RED with '500 in-scope trajectories missing'. That is the bind working
    - and the rule it teaches is that the two banks grow in ONE change, from ONE seeder, or they
    drift apart the first time someone runs only half of it. Hence this lives here rather than in a
    second script nobody remembers to run.

    Every row enters at 'pending' - honest: not walked, nothing graded. The P-F rows are edge
    functions with no UI, so they carry the explicit no_ui_basis R5 requires instead of pages."""
    out = []
    for r in rows:
        fn = (r.get("functions") or [None])[0]
        out.append({
            "id": r["id"], "wave": r["wave"], "status": "pending",
            "pages": list(r.get("pages") or []),
            "cell": r["cells"][0],
            "walk_viewport_px": 390 if "narrow-320" in r["cells"][0] else 1920,
            "target_source": "p-program-catalog", "needs_review": False,
            "dims_graded": [], "findings": [],
            **({"no_ui_basis": f"edge function supabase/functions/{fn} — no UI surface; critiqued "
                               "against the AI/API dimensions via its contract, not a browser walk"}
               if fn else {}),
        })
    return out


def main() -> int:
    rows = build_all()
    from collections import Counter
    by_wave = Counter(r["wave"] for r in rows)
    order = [w for w, _, _ in WAVES]
    if "--dry-run" in sys.argv or "--coverage" in sys.argv:
        print(f"built {len(rows)} P rows - " + " | ".join(f"{k} {by_wave[k]}" for k in order))
        # NO SILENT CAPS: say per wave how much of its surface pool the row budget actually
        # reaches, so a wave that covers 44 of 62 functions reads as 44 of 62, never as "done".
        print(f"{'wave':6} {'rows':>4} {'lenses':>7} {'surfaces':>18}  coverage")
        for wave, wname, size in WAVES:
            wrows = [r for r in rows if r["wave"] == wave]
            surf = {(r["pages"] or r["functions"])[0] for r in wrows}
            pool_n = len(_pool_for(wave))
            lens_n = len(THEMES[wave])
            cells = pool_n * lens_n
            print(f"{wave:6} {len(wrows):>4} {lens_n:>7} {len(surf):>8}/{pool_n:<9}"
                  f"  {len(wrows)}/{cells} cells = {100*len(wrows)/cells:.0f}%"
                  + ("" if len(surf) == pool_n else f"  ({pool_n - len(surf)} surfaces not reached)"))
        if "--dry-run" in sys.argv:
            for i in (0, 72, 112, 160, 188, 220, 264, 308, 348, 384, 424, 460):
                print("sample:", json.dumps(rows[i], ensure_ascii=False)[:180])
            return 0
        return 0
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    kept = [t for t in reg["trajectories"]
            if not (t["id"].startswith("P") and t["id"][1:].isdigit())]  # idempotent
    # ★NEVER REGENERATE OVER A ROW THAT HAS MOVED. "Idempotent" used to mean drop every P row
    # and rebuild — correct on the day the catalog landed, and a data-loss trap the moment the
    # program started walking: 175 rows carried status/basis/gates by the same afternoon, and one
    # re-run (a pool tweak, a lens rename) would have reset all of them to specced/5 with their
    # receipts gone. A row that has left `specced`, or has been re-pointed at a finding
    # (tools/repoint_p_row.py stamps its basis), is HISTORY — keep it verbatim under its id and
    # let the generator fill only the ids that are still untouched. The catalog stays 500 by
    # construction; a kept row simply outranks the pairing the generator would have given its id.
    prior = {t["id"]: t for t in reg["trajectories"]
             if t["id"].startswith("P") and t["id"][1:].isdigit()}
    def _moved(t):
        return t.get("status") != "specced" or (t.get("basis") or "").strip() or t.get("artifacts")
    preserved = 0
    merged = []
    for r in rows:
        old = prior.get(r["id"])
        if old and _moved(old):
            merged.append(old); preserved += 1
        else:
            merged.append(r)
    rows = merged
    if preserved:
        print(f"preserved {preserved} P row(s) that had already moved (status/basis/gates kept verbatim)")
    reg["trajectories"] = kept + rows
    reg["count"] = len(reg["trajectories"])
    reg["updated"] = "2026-09-05"
    tmp = REGISTRY.with_suffix(".json.tmp")        # atomic: open(w) truncates before the write
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, REGISTRY)
    print(f"registry now holds {reg['count']} trajectories ({len(kept)} prior + {len(rows)} P). "
          + " | ".join(f"{k} {by_wave[k]}" for k in order))

    # ── the critic bank grows in the SAME command (★×16; critic R3 requires 1:1 coverage) ──
    crit = json.loads(CRITIC.read_text(encoding="utf-8"))
    # ★THE PRESERVATION RULE MUST HOLD ON BOTH SIDES OF A PAIRED WRITE (2026-09-06). The trajectory side above kept every
    # row that had moved; this side rebuilt EVERY P critic row as pending — and the first re-run (landing wave P-M) erased
    # 500 rows of critiques + improvement refs (critic 73.5% -> 36.4%), recoverable only because they were derived artifacts
    # (critic_from_board + the closer rebuilt them). Keep every existing P critic row verbatim; add only the ids that are new.
    ckept = [r for r in crit["rows"]
             if not (r["id"].startswith("P") and r["id"][1:].isdigit())]
    cprior = {r["id"]: r for r in crit["rows"] if r["id"].startswith("P") and r["id"][1:].isdigit()}
    fresh = _critic_rows(rows)
    crit["rows"] = ckept + [cprior.get(r["id"], r) for r in fresh]
    print(f"critic rows preserved verbatim: {sum(1 for r in fresh if r['id'] in cprior)}; new pending: {sum(1 for r in fresh if r['id'] not in cprior)}")
    crit["count"] = len(crit["rows"])
    crit["updated"] = "2026-09-05"
    ctmp = CRITIC.with_suffix(".json.tmp")
    ctmp.write_text(json.dumps(crit, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(ctmp, CRITIC)
    print(f"critic bank now holds {crit['count']} rows ({len(ckept)} prior + {len(rows)} P pending)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
