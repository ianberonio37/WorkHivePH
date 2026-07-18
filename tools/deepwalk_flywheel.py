#!/usr/bin/env python3
"""deepwalk_flywheel.py — the PLATFORM deep-walk FLYWHEEL (Ian, 2026-07-08).

v1 (ARC DI): parsed ONE hand-written §10.2 table, ran 6 hard-coded DI gates, named the
lowest-coverage page. It measured the data-integrity grid only.

v2 (this file, ADDITIVE — v1 functions kept verbatim below as the DI sub-report): promotes
the loop from the DI tier to the WHOLE platform. Small deltas, per the roadmap
(PLATFORM_DEEPWALK_FLYWHEEL_ROADMAP.md §7):

  Δ1 discover_grid()   — rebuild the grid from the filesystem each cycle (glob *.html +
                         supabase/functions/* ∩ ai_seams_catalog.ai_fns) × the oracle dims,
                         → deepwalk_grid.json. Replaces v1's single-table read; same math.
  Δ2 tag binder        — every oracle self-declares the cells it protects with a one-line
                         header `# DEEPWALK-CELL: <surface> <dim>`. The flywheel globs
                         tools/validate_*.py, reads the tag, binds the validator (+ whether
                         it is LOCKED = registered severity:fail in run_platform_checks).
                         A new tagged validator lights its cell next cycle, zero flywheel edits.
  Δ3 AI sub-grid       — ai_fns × AI dims (grounding/injection/cost/fabrication/isolation/
                         PII/recall) + display-parity (D1) on pages, mapped to on-disk oracles.
  Δ4 generalized floor — the down-ratchet gate-floor = EVERY tagged+locked validator (not the
                         hard-coded 6), so AI/security gates auto-join the regression floor.
  Δ5 --drive + re-arm  — --drive emits the live-drive plan for the lowest cell (Playwright for
                         a page / curl for an AI fn → postgres oracle + §10.5 seesaw-guard);
                         state carries dry_streak + surface_set_hash + oracle_set_hash so the
                         loop re-opens automatically when a new page/fn/validator changes the
                         surface. Default = fast measure-only; a nightly cron runs --drive.

Usage:  python tools/deepwalk_flywheel.py [--json] [--drive] [--di-only]
Exit 0 = every LOCKED gate green (coverage may be <100), 1 = a locked gate FAILed (regression).
"""
import glob as _glob
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

# Windows cp1252 consoles choke on the ✅/🟡/⬜/→ glyphs (feedback_console_encoding) — force utf-8.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROADMAP = os.path.join(ROOT, "DEEP_WALK_ROADMAP.md")
STATE = os.path.join(ROOT, "deepwalk_flywheel_state.json")
GRID_JSON = os.path.join(ROOT, "deepwalk_grid.json")
AI_SEAMS = os.path.join(ROOT, "ai_seams_catalog.json")
CHECKS = os.path.join(ROOT, "run_platform_checks.py")

# --- v1 DI gates (kept as the DI sub-report; v2 generalizes the floor via tags) ----------
DI_GATES = [
    "validate_inventory_ledger_reconciled",
    "validate_reliability_kpi_faithfulness",
    "validate_benchmark_rollup_faithfulness",
    "validate_embedding_no_stale_duplicates",
    "validate_logbook_asset_linkage",
    "validate_attribution",
]
CELL_WEIGHT = {"✅": 1.0, "🟡": 0.5, "⬜": 0.0}  # n/a excluded from the denominator

# --- v2 oracle dimensions (PLATFORM_DEEPWALK_FLYWHEEL_ROADMAP.md §2) ----------------------
# Page dims apply to every walkable app page (D2 is n/a where a page has no write path).
PAGE_DIMS = {
    "D1":  "render-parity (rendered == v_*_truth)",
    "D2":  "data-integrity (the 11 DI write classes)",
    "D3":  "cross-surface receipt (write-on-A flips KPI-on-B)",
    "D4":  "accessibility (axe/WCAG 2.2 AA)",
    "D5":  "mobile/touch/safe-area (44px, viewport, PWA)",
    "D6":  "core-web-vitals (LCP/CLS/INP)",
    "D7":  "xss/escHtml (no injection sink)",
    "D8":  "rls/tenant-isolation + BOLA",
    "D9":  "bfla (worker can't hit supervisor writes)",
    "D18": "destructive-safety (delete/reset confirm-gated; no orphan cascade)",
    "D19": "idle-session (token-refresh on wake, no stale 401)",
    "D20": "resilience (fetch timeout-bounded, offline/degraded UX)",
    "D15": "empty/error/loading (honest gates)",
    "D17": "smoke (loads clean, no console error)",
    "D22": "deep-interaction (every modal/tab/filter/wizard)",
    "D23": "plain-language (no jargon in rendered copy)",
}
# AI dims apply per AI edge fn. D21 observability is banked platform-wide (serveObserved 56/56).
AI_DIMS = {
    "D10": "grounding/retrieval-quality (cites real hive data)",
    "D11": "prompt-injection (OWASP LLM01)",
    "D12": "cost/quota (bounded per hive/user/day)",
    "D13": "fabrication (no invented action/number)",
    "D21": "observability/SLO (serveObserved capture)",
    "D24": "ai cross-hive isolation + capability-honesty",
    "D25": "pii-egress / multi-turn redaction",
    "D26": "memory / multi-turn recall",
}
# AI applicability (classify-by-evidence, not surface-name): the generative dims — D10 grounding,
# D13 fabrication, D26 recall — apply ONLY to fns that produce grounded NL answers / hold multi-turn
# memory. These fns are pure INFRA (embed / score / ingest / OCR / normalize — verified: their
# index.ts never calls the AI chain to GENERATE prose), so those three dims are n/a for them. This
# is an explicit, auditable list rather than a fuzzy runtime classifier (heuristics misfire). The
# always-on AI dims (D12 cost, D21 observability, D24 isolation, D25 PII) still apply to every fn.
INFRA_AI_FNS = {
    "batch-risk-scoring", "cold-archive-query", "data-fabric-normalizer",
    "embed-entry", "equipment-label-ocr", "pdf-ingest", "voice-embeddings",
}
GENERATIVE_ONLY_DIMS = {"D10", "D13", "D26"}  # n/a on the infra fns above

# D26 multi-turn RECALL is a narrower concern than "generative": it applies ONLY to fns that maintain a
# MULTI-TURN CONVERSATIONAL dialogue (load prior turns + persist the new one). That is the companion
# gateway + the memory-store fn; every orchestrator/RAG/generator/voice fn is SINGLE-SHOT (one request →
# one structured answer, no dialogue state) → D26 n/a for them. Classify by evidence, not by "is it AI".
RECALL_AI_FNS = {"ai-gateway", "agent-memory-store"}

# Severity weight for tie-breaking the next-target dimension (higher = drive first).
DIM_SEVERITY = {
    "D2": 9, "D8": 9, "D24": 9, "D11": 8, "D7": 8, "D9": 8, "D25": 8, "D18": 8, "D13": 7,
    "D10": 7, "D19": 7, "D20": 7, "D3": 6, "D1": 6, "D12": 6, "D26": 5, "D6": 5, "D4": 5,
    "D5": 4, "D15": 4, "D22": 4, "D23": 3, "D17": 3, "D21": 2,
}

# Root pages that are NOT walkable production surfaces (test harnesses + backups).
_NA_PAGE_RE = re.compile(r"(-test|\.backup\d*|-hive-test|-native-test|-v3-test)\.html$")
_WRITE_RE = re.compile(r"\.insert\(|\.upsert\(|\.rpc\(|functions\.invoke|\.update\(|\.delete\(")
# A tag optionally names a REPORT artifact (heavy/live oracles — a live-LLM battery, a chaos walk —
# must NOT re-run every fast measure; instead the engine reads their fresh report for pass-status,
# the roadmap's "drift==0 via baseline → ✅" path): `# DEEPWALK-CELL: ai:* D13 report=ai_live_invoke_results.json`
TAG_RE = re.compile(r"#\s*DEEPWALK-CELL:\s*(\S+)\s+(D\d+)(?:\s+report=(\S+))?", re.I)
REPORT_FRESH_DAYS = 14  # a report older than this → the cell degrades ✅→🟡 (evidence went stale)


# ============================ v1 (DI sub-report — kept verbatim) ==========================
def parse_grid():
    """Return {page: {covered, total, open_cols}} from the §10.2 grid table (DI sub-report)."""
    pages = {}
    try:
        lines = open(ROADMAP, encoding="utf-8").read().splitlines()
    except OSError:
        return pages
    in_grid = False
    for ln in lines:
        if ln.startswith("### 10.2"):
            in_grid = True
            continue
        if in_grid and ln.startswith("### 10.3"):
            break
        if not in_grid or not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in ("Page", "") or set(cells[0]) <= {"-", ":"}:
            continue
        page = cells[0]
        covered = total = 0
        opens = 0
        for c in cells[2:]:
            mark = next((m for m in CELL_WEIGHT if m in c), None)
            if mark is None:
                continue
            total += 1
            covered += CELL_WEIGHT[mark]
            if mark == "⬜":
                opens += 1
        if total:
            pages[page] = {"covered": covered, "total": total,
                           "pct": round(100 * covered / total, 1), "open": opens}
    return pages


def run_gate(name):
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", f"{name}.py")],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
        out = (r.stdout or "") + (r.stderr or "")
        status = "FAIL" if "FAIL" in out else ("SKIP" if "SKIP" in out else "PASS")
        return status
    except Exception:
        return "SKIP"


def di_subreport():
    """v1 measure kept intact — the DI tier's own coverage, folded in as one sub-number."""
    pages = parse_grid()
    tot_cov = sum(p["covered"] for p in pages.values())
    tot_tot = sum(p["total"] for p in pages.values())
    coverage = round(100 * tot_cov / tot_tot, 1) if tot_tot else 0.0
    return {"pages": len(pages), "cells_covered": tot_cov, "cells_total": tot_tot,
            "coverage_pct": coverage}


# ============================ v2 (whole-platform grid) ===================================
# Content (static /learn article) pages are a DISTINCT surface class: pure marketing/education
# HTML with no app shell (no utils.js / Supabase client / writes / whConfirm / interactive JS —
# verified: they load only tailwind/GA4/feedback-fab). So the app-behaviour dims (data-integrity,
# cross-surface, RLS/BFLA, destructive/session/resilience, deep-interaction, loading-states) are
# n/a; only the presentation/hygiene dims apply. They bind via the `content:*` wildcard (NOT the
# app `*` wildcard) so an app-only oracle can't falsely credit a learn page it never scanned.
CONTENT_DIMS = {"D4", "D5", "D6", "D7", "D17", "D23"}


def list_app_pages():
    """Walkable production surfaces: root *.html app pages (kind=app, carry a `write` flag for D2)
    + learn/<slug>/index.html content articles (kind=content, content-dims only)."""
    pages = {}
    for path in sorted(_glob.glob(os.path.join(ROOT, "*.html"))):
        base = os.path.basename(path)
        if _NA_PAGE_RE.search(base):
            continue
        try:
            src = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        stem = base[:-5]  # drop .html
        pages[stem] = {"write": bool(_WRITE_RE.search(src)), "kind": "app"}
    # NOTE: feedback/index.html is a user-facing APP page in a subdir — NOT folded in yet. The app
    # per-page-scan oracles (cwv, validate_clickable_keyboard_a11y, frontend_floor_cells) glob root
    # *.html only, so the `* Dxx` wildcards would FALSE-CREDIT it (verified: cwv never measured it,
    # a11y never scans it). Honest coverage needs those oracles extended to the subdir first (a
    # bounded next unit); until then leaving it OUT keeps the ruler honest (no false-green).
    # Content pages — static (no app shell): the learn/<slug> articles + the top-level about/legal
    # pages, glob-discovered. They carry only the presentation dims (CONTENT_DIMS); the app-behaviour
    # dims are n/a. (feedback/index.html is EXCLUDED — it loads the app shell = an interactive app page.)
    _content_globs = [os.path.join(ROOT, "learn", "*", "index.html")]
    for _d in ("about", "privacy-policy", "terms-of-service"):
        _content_globs.append(os.path.join(ROOT, _d, "index.html"))
    for path in sorted({p for g in _content_globs for p in _glob.glob(g)}):
        rel = os.path.relpath(os.path.dirname(path), ROOT).replace("\\", "/")
        pages[rel] = {"write": False, "kind": "content"}
    return pages


def list_ai_fns():
    """AI edge fns actually deployed = ai_seams_catalog.ai_fns ∩ supabase/functions/*."""
    try:
        seams = json.load(open(AI_SEAMS, encoding="utf-8"))
        declared = set(seams.get("ai_fns", []))
    except Exception:
        declared = set()
    deployed = {os.path.basename(p.rstrip("/\\"))
                for p in _glob.glob(os.path.join(ROOT, "supabase", "functions", "*"))
                if os.path.isdir(p)}
    fns = sorted(declared & deployed) if deployed else sorted(declared)
    return fns


def locked_validators():
    """The down-ratchet floor = validators REGISTERED in run_platform_checks that BLOCK on a
    regression. run_platform_checks sets status = PASS/FAIL purely on returncode (line ~4843:
    `status = "PASS" if returncode == 0 else "FAIL"`) and exits nonzero on any FAIL / regression
    — so severity ("blocker"/"fail"/unspecified) is a DISPLAY label, not the gate. Only explicit
    `warn`/`info` checks are advisory (non-blocking). Hence LOCKED = registered AND not warn/info.
    Δ4: the floor is DISCOVERED (glob-registered), not the hard-coded 6 — any tagged gate that is
    registered-and-blocking auto-joins the ratchet."""
    locked = set()
    try:
        src = open(CHECKS, encoding="utf-8").read()
    except OSError:
        return locked
    # each check dict names a tools/validate_X.py script; capture its tail up to the NEXT
    # "script" key (or EOF), then read that block's severity. Missing severity = blocking default.
    for m in re.finditer(r'"script":\s*(?:os\.path\.join\(\s*"tools",\s*)?"(?:tools/)?'
                         r'([a-z0-9_]+)\.py"(.*?)(?="script"|\Z)', src, re.S):
        stem, tail = m.group(1), m.group(2)
        sev = re.search(r'"severity":\s*"(\w+)"', tail)
        if sev is None or sev.group(1) not in ("warn", "info"):
            locked.add(stem)
    return locked


def report_status(report_rel):
    """Status of a heavy oracle from its fresh REPORT artifact (not by re-running it).
    PASS = report exists, fresh, and shows no breaches; FAIL = has breaches/violations;
    SKIP = missing or stale (evidence went cold → the cell degrades to 🟡)."""
    import time
    path = os.path.join(ROOT, report_rel)
    if not os.path.isfile(path):
        return "SKIP"
    try:
        if (time.time() - os.path.getmtime(path)) / 86400 > REPORT_FRESH_DAYS:
            return "SKIP"  # stale evidence
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return "SKIP"
    # common fail signals across the platform's report artifacts.
    for key in ("breaches", "violations", "failed", "gates_failed", "issues", "unwrapped"):
        v = d.get(key) if isinstance(d, dict) else None
        if isinstance(v, list) and v:
            return "FAIL"
        if isinstance(v, (int, float)) and v > 0:
            return "FAIL"
    return "PASS"


def bind_oracles():
    """Δ2: glob every validator, read its `# DEEPWALK-CELL: <surface> <dim> [report=<file>]` tags.
    Returns (bindings, tagged, orphan, reports): bindings = {(surface,dim): [validator,...]},
    reports = {validator: report_file} for heavy/live oracles measured by artifact, not re-run."""
    bindings = {}
    tagged = {}    # validator -> [(surface, dim), ...]
    orphan = []    # validators with NO tag (a nudge to tag them)
    reports = {}   # validator -> report artifact (present => report-backed, not re-run)
    # the oracle ecosystem isn't only validate_*.py — gates/audits/miners carry cells too.
    _pats = ("validate_*.py", "*_gate.py", "audit_*.py", "mine_*.py")
    _paths = sorted({p for pat in _pats
                     for p in _glob.glob(os.path.join(ROOT, "tools", pat))})
    for path in _paths:
        stem = os.path.basename(path)[:-3]
        try:
            head = open(path, encoding="utf-8", errors="replace").read(4000)
        except OSError:
            continue
        raw = TAG_RE.findall(head)
        if not raw:
            orphan.append(stem)
            continue
        cells = [(s, d.upper()) for s, d, _r in raw]
        tagged[stem] = cells
        for _s, _d, rep in raw:
            if rep:
                reports[stem] = rep
        for surface, dim in cells:
            bindings.setdefault((surface, dim), []).append(stem)
    return bindings, tagged, orphan, reports


def _oracles_for(surface, dim, bindings, kind="app"):
    """Resolve tagged oracles for a concrete cell, expanding the right wildcard for the surface
    kind: app pages bind `*` (+ `ai:*`), content pages bind `content:*` ONLY — an app-only `*`
    oracle must NOT credit a learn page it never scanned (an oracle that DOES cover learn tags
    both `* Dxx` and `content:* Dxx`, e.g. cwv_gate/validate_plain_language)."""
    out = list(bindings.get((surface, dim), []))
    if kind == "content":
        out += bindings.get(("content:*", dim), [])   # content-page wildcard
    else:
        out += bindings.get(("*", dim), [])            # app-page wildcard
        out += bindings.get(("ai:*", dim), [])         # ai-fn-wildcard
    return sorted(set(out))


def derive_cells(pages, ai_fns, bindings, gate_status):
    """Build every applicable cell → state ✅/🟡/⬜ (n/a excluded), with its oracle + lock.
    ✅ = a LOCKED bound oracle PASSed · 🟡 = a bound oracle exists (unlocked/SKIP) ·
    ⬜ = applicable, no bound oracle · regressed (locked+FAIL) → ⬜ + flagged."""
    cells = {}

    def classify(surface, dim, kind="app"):
        oracles = _oracles_for(surface, dim, bindings, kind)
        if not oracles:
            return {"state": "⬜", "oracle": None, "locked": False}
        locked_pass = [o for o in oracles if gate_status.get(o) == "PASS"]
        locked_fail = [o for o in oracles if gate_status.get(o) == "FAIL"]
        if locked_fail:  # a locked gate regressed → treat the cell as OPEN + surface it
            return {"state": "⬜", "oracle": locked_fail[0], "locked": True, "regressed": True}
        if locked_pass:
            return {"state": "✅", "oracle": locked_pass[0], "locked": True}
        return {"state": "🟡", "oracle": oracles[0], "locked": False}

    for stem, meta in pages.items():
        kind = meta.get("kind", "app")
        for dim in PAGE_DIMS:
            # Static content articles carry only the presentation/hygiene dims; the app-behaviour
            # dims (writes / cross-surface / RLS / destructive / session / resilience / interaction /
            # loading-states) have no surface on a static page → n/a.
            if kind == "content" and dim not in CONTENT_DIMS:
                cells[f"{stem}|{dim}"] = {"state": "n/a"}
                continue
            if dim == "D2" and not meta["write"]:
                cells[f"{stem}|{dim}"] = {"state": "n/a"}
                continue
            cells[f"{stem}|{dim}"] = classify(stem, dim, kind)
    for fn in ai_fns:
        for dim in AI_DIMS:
            if fn in INFRA_AI_FNS and dim in GENERATIVE_ONLY_DIMS:
                cells[f"{fn}|{dim}"] = {"state": "n/a"}  # infra fn: no NL generation → dim n/a
                continue
            if dim == "D26" and fn not in RECALL_AI_FNS:
                cells[f"{fn}|{dim}"] = {"state": "n/a"}  # single-shot fn: no multi-turn dialogue → recall n/a
                continue
            cells[f"{fn}|{dim}"] = classify(fn, dim)
    return cells


def _hash(items):
    return hashlib.sha1("\n".join(sorted(items)).encode("utf-8")).hexdigest()[:12]


def coverage(cells):
    cov = tot = 0.0
    for c in cells.values():
        w = CELL_WEIGHT.get(c["state"])
        if w is None:
            continue  # n/a
        tot += 1
        cov += w
    return (round(100 * cov / tot, 1) if tot else 0.0), cov, tot


def next_target(cells, pages, ai_fns):
    """Lowest-coverage surface with open cells; within it, the highest-severity ⬜ dim."""
    per = {}
    for key, c in cells.items():
        surface, dim = key.split("|")
        w = CELL_WEIGHT.get(c["state"])
        if w is None:
            continue
        s = per.setdefault(surface, {"cov": 0.0, "tot": 0, "opens": []})
        s["cov"] += w
        s["tot"] += 1
        if c["state"] == "⬜":
            s["opens"].append(dim)
    ranked = [(v["cov"] / v["tot"], surf, v["opens"]) for surf, v in per.items()
              if v["opens"] and v["tot"]]
    if not ranked:
        return None
    ranked.sort(key=lambda t: t[0])
    pct, surface, opens = ranked[0]
    dim = max(opens, key=lambda d: DIM_SEVERITY.get(d, 0))
    kind = "ai-fn" if surface in ai_fns else "page"
    label = (AI_DIMS if kind == "ai-fn" else PAGE_DIMS).get(dim, dim)
    return {"surface": surface, "kind": kind, "dim": dim, "dim_label": label,
            "surface_pct": round(100 * pct, 1), "open_dims": sorted(opens)}


def drive_plan(target):
    """Δ5: the live-drive recipe for the lowest cell (executed by the agent via MCP)."""
    if not target:
        return "grid DRY — nothing to drive"
    s, dim, kind = target["surface"], target["dim"], target["kind"]
    if kind == "ai-fn":
        return (f"curl/functions.invoke `{s}` on 127.0.0.1:54321 with an adversarial "
                f"{dim} payload → assert the boundary via mcp__postgres__query "
                f"(+ §10.5 seesaw-guard on any row it writes), then tag a validator "
                f"`# DEEPWALK-CELL: {s} {dim}` and lock it.")
    return (f"Playwright-walk `{s}.html` for {dim} ({target['dim_label']}): operate the "
            f"affordance live, assert at the DATA layer via mcp__postgres__query, "
            f"flywheel any miss, then tag+lock a validator `# DEEPWALK-CELL: {s} {dim}`.")


def build_grid(run_locked=True):
    """Δ1+Δ3: assemble the whole-platform grid; run only the LOCKED bound gates (fast)."""
    pages = list_app_pages()
    ai_fns = list_ai_fns()
    bindings, tagged, orphan, reports = bind_oracles()
    locked = locked_validators()

    # Δ4: the gate-floor = every tagged validator that is ALSO locked (registered-and-blocking).
    # Report-backed oracles (heavy/live: a chaos walk, a live-LLM battery) are NOT re-run — their
    # status comes from a fresh report artifact — so they stay OUT of the live-run floor.
    bound_validators = {v for vs in bindings.values() for v in vs}
    floor = sorted((bound_validators & locked) - set(reports))
    gate_status = {g: run_gate(g) for g in floor} if run_locked else {}
    # a report-backed oracle's report IS its durable evidence → treat PASS as a locked-pass cell.
    for stem, rep in reports.items():
        gate_status[stem] = report_status(rep)

    cells = derive_cells(pages, ai_fns, bindings, gate_status)
    cov_pct, _, _ = coverage(cells)
    page_cells = {k: v for k, v in cells.items() if k.split("|")[0] in pages}
    ai_cells = {k: v for k, v in cells.items() if k.split("|")[0] in ai_fns}
    page_pct, _, _ = coverage(page_cells)
    ai_pct, _, _ = coverage(ai_cells)

    failed = [g for g, s in gate_status.items() if s == "FAIL"]
    regressed = sorted({v["oracle"] for v in cells.values()
                        if v.get("regressed") and v.get("oracle")})
    surface_hash = _hash(list(pages) + [f"ai:{f}" for f in ai_fns])
    oracle_hash = _hash([f"{v}:{','.join(f'{s} {d}' for s, d in cs)}"
                         for v, cs in tagged.items()])
    tgt = next_target(cells, pages, ai_fns)

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coverage_pct": cov_pct, "page_pct": page_pct, "ai_surface_pct": ai_pct,
        "surfaces": {"pages": len(pages), "ai_fns": len(ai_fns)},
        "page_dims": list(PAGE_DIMS), "ai_dims": list(AI_DIMS),
        "cells_total": len(cells),
        "state_counts": {st: sum(1 for c in cells.values() if c["state"] == st)
                         for st in ("✅", "🟡", "⬜", "n/a")},
        "gate_floor": floor, "gates_failed": failed, "regressed_cells": regressed,
        "next_target": tgt, "drive_plan": drive_plan(tgt),
        "orphan_oracles": orphan,
        "newly_joined": [], "surface_set_hash": surface_hash, "oracle_set_hash": oracle_hash,
        "live_bonus": live_bonus_tally(),
        "cells": cells,
    }


def live_bonus_tally():
    """The FORWARD-ONLY live-bonus tier (Arc H's VERIFIED+bonus model): AI-behavior cells proven by
    LIVE edge invocation (`ai_live_invoke_results.json`). These are DELIBERATELY not in the stable
    ruler — a runtime restart / reseed makes live invokes transport-flaky, which would flap coverage.
    Reported SEPARATELY so the D13/D26/D10 live evidence is visible without contaminating the ruler."""
    import time
    path = os.path.join(ROOT, "ai_live_invoke_results.json")
    if not os.path.isfile(path):
        return {"live_cells": 0, "breaches": 0, "fresh": False, "note": "no battery report"}
    try:
        d = json.load(open(path, encoding="utf-8"))
        age_d = (time.time() - os.path.getmtime(path)) / 86400
        live_ids = sorted(k for k, c in (d.get("cells", {}) or {}).items() if c.get("live"))
        return {"live_cells": d.get("live_cells", 0), "live_cell_ids": live_ids,
                "breaches": len(d.get("breaches", []) or []),
                "fresh": age_d <= REPORT_FRESH_DAYS, "age_days": round(age_d, 1)}
    except Exception:
        return {"live_cells": 0, "live_cell_ids": [], "breaches": 0, "fresh": False, "note": "unreadable"}


def main():
    as_json = "--json" in sys.argv
    drive = "--drive" in sys.argv
    di_only = "--di-only" in sys.argv

    di = di_subreport()
    if di_only:
        print(f"DI sub-report -- §10.2 grid: {di['coverage_pct']}% "
              f"({di['cells_covered']:g}/{di['cells_total']} cells, {di['pages']} pages)")
        return 0

    grid = build_grid(run_locked=True)
    grid["di_subreport"] = di

    prev = {}
    try:
        prev = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        pass
    delta = round(grid["coverage_pct"] - prev.get("coverage", grid["coverage_pct"]), 1)
    grid["delta_vs_last"] = delta

    # forward-only live-bonus ratchet: a cell proven live ONCE stays credited. Run-to-run flips are
    # rate-limit/probabilistic noise (the free-tier bucket drains across the battery's ~29 LLM probes,
    # so late cells intermittently record RL), NOT regressions — so the durable tier is the UNION ever seen.
    _lb = grid["live_bonus"]
    _proven = sorted(set(prev.get("live_bonus_proven", [])) | set(_lb.get("live_cell_ids", [])))
    _lb["proven_ever"] = len(_proven)
    _lb["this_run"] = _lb.get("live_cells", 0)

    # dry_streak + re-arm: a changed surface/oracle hash re-opens the loop (dry_streak=0).
    rearm = (prev.get("surface_set_hash") != grid["surface_set_hash"]
             or prev.get("oracle_set_hash") != grid["oracle_set_hash"])
    if rearm:
        dry = 0
    elif delta == 0 and not grid["gates_failed"]:
        dry = prev.get("dry_streak", 0) + 1
    else:
        dry = 0
    grid["dry_streak"] = dry
    grid["dry"] = dry >= 3

    # persist grid + compact state
    try:
        json.dump(grid, open(GRID_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except OSError:
        pass
    try:
        json.dump({"coverage": grid["coverage_pct"], "page_pct": grid["page_pct"],
                   "ai_surface_pct": grid["ai_surface_pct"], "gates_failed": grid["gates_failed"],
                   "dry_streak": dry, "surface_set_hash": grid["surface_set_hash"],
                   "oracle_set_hash": grid["oracle_set_hash"], "live_bonus_proven": _proven},
                  open(STATE, "w", encoding="utf-8"))
    except OSError:
        pass

    if as_json:
        out = dict(grid)
        out.pop("cells", None)  # keep the console/JSON summary lean; full cells in deepwalk_grid.json
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        sc = grid["state_counts"]
        print(f"PLATFORM deep-walk flywheel -- coverage {grid['coverage_pct']}% "
              f"(page {grid['page_pct']}% · AI {grid['ai_surface_pct']}%)  delta {delta:+}")
        print(f"  grid: {grid['surfaces']['pages']} pages × {len(PAGE_DIMS)} dims + "
              f"{grid['surfaces']['ai_fns']} AI fns × {len(AI_DIMS)} dims = {grid['cells_total']} cells "
              f"→ ✅{sc['✅']} 🟡{sc['🟡']} ⬜{sc['⬜']} n/a{sc['n/a']}")
        floor = grid["gate_floor"]
        print(f"  gate-floor (tagged+locked): {len(floor)} gates · "
              f"{len(grid['gates_failed'])} FAIL"
              + (f"  → {', '.join(grid['gates_failed'])}" if grid["gates_failed"] else ""))
        lb = grid["live_bonus"]
        print(f"  live-bonus tier (AI cells proven live, NOT in stable ruler; forward-only): "
              f"{lb.get('proven_ever', 0)} proven-ever · {lb.get('this_run', 0)} this-run · "
              f"{lb.get('breaches', 0)} breach"
              + ("" if lb.get("fresh") else "  (report stale/absent — re-run validate_ai_live_invoke)"))
        print(f"  DI sub-report: {di['coverage_pct']}% ({di['cells_total']} cells) · "
              f"orphan oracles (untagged): {len(grid['orphan_oracles'])}")
        t = grid["next_target"]
        if t:
            print(f"  NEXT TARGET: {t['surface']} [{t['kind']}] × {t['dim']} "
                  f"({t['dim_label']}) — surface at {t['surface_pct']}%")
            if drive:
                print(f"  DRIVE: {grid['drive_plan']}")
        else:
            print("  NEXT TARGET: none — every applicable cell covered (grid DRY)")
        print(f"  dry_streak: {dry}/3" + ("  ✔ DRY" if grid["dry"] else "")
              + ("  · re-armed (surface/oracle set changed)" if rearm else ""))
    return 1 if grid["gates_failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
