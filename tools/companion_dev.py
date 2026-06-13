#!/usr/bin/env python3
"""
companion_dev.py — the AI Companion Developer Tool (the companion's Mega Gate).
=============================================================================
ONE front door to develop, evaluate, and self-improve the WorkHive AI companion,
structured as a self-improving CLOSED LOOP modeled on the platform's Unified Mega
Gate (release_gate.py + the 7-layer tester panel). See COMPANION_DEV_TOOL.md.

The Mega Gate tests platform CODE; this tests the companion's BEHAVIOUR. Same
machine, different subject: live thumbs are the mine, golden sets are the checks,
the locked-test split is the forward-only anti-overfit ratchet, and the optimizer
turns failures into improvements.

Layer mapping (Mega Gate -> companion):
  G-1.5 Substrate      -> substrate : harvest live signals + observables -> manifest
  G-1   Auto-discovery -> discover  : enumerate dims<->golden<->grader<->baseline, flag orphans
  G0    Static         -> gate      : ai_eval_gate companion-gate (per-dim locked-test, n-aware)
  G1    Data           -> eval      : *-golden-capture specs -> graded observations (live)
  G2    Journeys       -> eval      : companion_battery live stack (Agent/Memory/RAG/Safety)
  G3    UFAI Battery   -> optimize  : companion_optimize GEPA reflect->propose->measured A/B
  Mega  orchestration  -> mega      : run the loop, write .last-companion-gate-pass, persist run

Usage:
  python tools/companion_dev.py status          # scorecard + harvest queue + last A/B, one glance
  python tools/companion_dev.py substrate        # G-1.5  build companion_substrate_manifest.json
  python tools/companion_dev.py discover         # G-1    coverage check (exit 1 on orphan)
  python tools/companion_dev.py harvest          #        thumbs-down -> candidates (human-disposed)
  python tools/companion_dev.py dispose          #        show the triage queue
  python tools/companion_dev.py eval [--dim D]    # G1+G2  grader self-tests ($0); --live = capture
  python tools/companion_dev.py optimize          # G3     reflect -> propose (measured A/B is manual)
  python tools/companion_dev.py gate              # G0     per-dim locked-test gate (exit 1 on regress)
  python tools/companion_dev.py mega [--live] [--propose]   # run the whole loop + write pass marker
  python tools/companion_dev.py --self-test       # prove the orchestrator wiring (NO DB / NO model)

Offline-first: status/substrate/discover/gate/eval(self-test)/optimize(propose)/mega(default)
are $0 and need no DB or model. The LIVE arms (eval --live capture, the measured A/B in
optimize) need the local Supabase + edge runtime + LLM and are opt-in, exactly like the Mega
Gate's --with-battery / --with-ai-deep heavy phases.
"""
from __future__ import annotations
import argparse
import io
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
PY = sys.executable

# Artifacts (the loop's state)
SCORECARD = ROOT / "companion_eval_scorecard.json"
BASELINES = ROOT / "companion_dim_baselines.json"
SPLITS = ROOT / "gate_eval_splits.json"
CANDIDATES = ROOT / "companion_harvest_candidates.json"
PROMOTED = ROOT / "companion_harvest_promoted.json"
AB_RESULTS = ROOT / "companion_ab_results.json"
PROPOSALS = ROOT / "companion_optimization_proposals.json"
RUBRIC = ROOT / "companion_stack_rubric.json"
PROBE_TAXONOMY = ROOT / "companion_probe_taxonomy.json"  # the probe-TYPE baseline (COMPANION_PROBE_TAXONOMY.md)
PROBE_COVERAGE = ROOT / "companion_probe_coverage.json"  # live coverage report (probes layer output)
MANIFEST = ROOT / "companion_substrate_manifest.json"   # NEW (G-1.5 output)
PASS_MARKER = ROOT / ".last-companion-gate-pass"          # NEW (mirror .last-gate-pass)
RUN_LOG = ROOT / "companion_dev_runs.jsonl"               # NEW (run persistence)

# Tools the front door orchestrates (they stay independently runnable).
HARVEST = TOOLS / "companion_harvest.py"
OPTIMIZE = TOOLS / "companion_optimize.py"
GATE = TOOLS / "ai_eval_gate.py"
SCORECARD_TOOL = TOOLS / "companion_eval_scorecard.py"
GRADER = TOOLS / "companion_rigorous_grader.py"
PERTURB = TOOLS / "companion_perturb.py"   # §9 #2 perturbation-invariance generator (self-test = offline metric check)
JUDGE = TOOLS / "companion_judge.py"       # cross-model LLM judge for JUDGMENT probes (live calibration = --self-test)
DELIVERY_GATE = TOOLS / "companion_delivery_gate.py"  # L0 static delivery gate (surface wiring: render/feedback/mount)
SURFACE_BATTERY = ROOT / "companion_surface_battery.js"            # L2/L3 live battery engine (window.__CSURF, MCP-driven)
SURFACE_REPORT = ROOT / "companion_surface_battery_report.json"   # last live Surface-Battery verdict (written by the MCP walk)
PROBE_LIVE_REPORT = ROOT / "companion_probe_live_report.json"     # last live BRAIN-probe verdicts (__CSURF.runProbe via MCP)
DIM_EVAL = {d: TOOLS / f"companion_{d}_eval.py" for d in ("agent", "rag", "memory", "persona", "domain", "robustness")}
PRODUCT_DIMS = ("agent", "rag", "memory", "persona", "domain", "robustness")

# §9 #3 overfitting gauge: train pass-rate exceeding locked-test by this many pp is a memorization smell.
OVERFIT_GAP_PP = 15.0

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


# ───────────────────────────── shared helpers (Mega-Gate idioms) ──────────────

def banner(text, color="cyan"):
    bar = "=" * 64
    c = {"cyan": CYAN, "green": GREEN, "red": RED, "yellow": YEL}.get(color, "")
    r = RESET if c else ""
    print(f"\n{c}{bar}{r}\n{c}  {text}{r}\n{c}{bar}{r}\n")


def step(text): print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
def ok(text): print(f"  {GREEN}OK{RESET} {text}")
def fail(text): print(f"  {RED}X{RESET} {text}")
def warn(text): print(f"  {YEL}!{RESET} {text}")


def _load(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        warn(f"could not parse {p.name}: {e}")
        return None


def run_tool(args, label=None) -> tuple[bool, str]:
    """Run a sibling tool; stream output, return (ok, last_summary_line)."""
    if label:
        step(label)
    proc = subprocess.Popen(
        [PY, *map(str, args)], cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    summary = ""
    for line in proc.stdout:
        clean = line.rstrip()
        if clean:
            print(f"    {clean}")
            s = clean.strip()
            if any(p in s for p in ("PASS", "FAIL", "OK", "SKIP", "BLOCK", "Summary", "ok", "exit")) and len(s) < 160:
                summary = s
    proc.wait()
    return proc.returncode == 0, summary


def _n_to_block(tol_pp: float) -> int:
    """n-aware threshold: a dim only effectively BLOCKS once its locked-test n is
    large enough to absorb a single-unit flake within tolerance (ceil(100/tol))."""
    if not tol_pp or tol_pp <= 0:
        return 0  # 0.0pp tolerance (safety) = always enforced via the frozen gate
    return math.ceil(100.0 / tol_pp)


# ───────────────────────────── G-1.5 substrate ────────────────────────────────

def build_substrate_manifest() -> dict:
    """Aggregate the loop's MINE state into one manifest (pure: no writes, no
    subprocess). Mirrors substrate_manifest.json = aggregation of miner outputs."""
    sc = _load(SCORECARD) or {}
    bl = _load(BASELINES) or {}
    cand_doc = _load(CANDIDATES) or {}
    ab = _load(AB_RESULTS) or {}
    props = _load(PROPOSALS) or {}
    rubric = _load(RUBRIC) or {}

    dims = sc.get("dimensions", {})
    coverage = (sc.get("coverage", {}) or {}).get("by_dimension", {})
    bl_dims = bl.get("dimensions", {})

    cands = cand_doc.get("candidates", []) if isinstance(cand_doc, dict) else []
    disp = {"pending": 0, "accepted": 0, "rejected": 0}
    for c in cands:
        d = c.get("disposition", "pending")
        disp[d] = disp.get(d, 0) + 1

    # Live-observable coverage from the stack rubric (the G2 battery pillars).
    pillars = []
    if isinstance(rubric, dict):
        pillars = list((rubric.get("pillars") or rubric.get("dimensions") or {}).keys()) \
            if isinstance(rubric.get("pillars") or rubric.get("dimensions"), dict) \
            else (rubric.get("pillars") if isinstance(rubric.get("pillars"), list) else [])

    prop_list = props.get("proposals", []) if isinstance(props, dict) else []

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": 1,
        "layer": "G-1.5 substrate (companion)",
        "source": "aggregated from scorecard + baselines + harvest candidates + observables",
        "dims_total": len(dims),
        "dims_active": sum(1 for d in dims.values() if d.get("status") == "active"),
        "golden_corpus": coverage,
        "baselines": {
            d: {
                "locked_test_pass_rate": (bl_dims.get(d, {}).get("locked_test", {}) or {}).get("pass_rate"),
                "locked_test_n": (bl_dims.get(d, {}).get("locked_test", {}) or {}).get("n"),
            }
            for d in bl_dims
        },
        "harvest": {
            "candidates_total": len(cands),
            **disp,
            "generated_at": cand_doc.get("generated_at") if isinstance(cand_doc, dict) else None,
        },
        "live_observables": {"pillars": pillars},
        "optimization": {
            "proposals": len(prop_list),
            "last_ab": {
                "proposal": ab.get("proposal") if isinstance(ab, dict) else None,
                "decision": ab.get("decision") if isinstance(ab, dict) else None,
            },
        },
    }


def layer_substrate() -> tuple[bool, str]:
    step("G-1.5 substrate: aggregate the mine (golden corpus + harvest + observables)")
    try:
        man = build_substrate_manifest()
        MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        fail(f"substrate manifest build failed: {e}")
        return False, str(e)
    h = man["harvest"]
    summary = (f"{man['dims_active']}/{man['dims_total']} dims active · "
               f"harvest {h['candidates_total']} cand ({h['pending']} pending) · "
               f"{man['optimization']['proposals']} proposals")
    ok(f"{MANIFEST.name} written — {summary}")
    return True, summary


# ───────────────────────────── G-1 discover ───────────────────────────────────

def _golden_file_for(dim: str, dim_obj: dict) -> Path | None:
    """Resolve a dim's golden-set file from its scorecard entry (parse the
    referenced filename; n/a -> None)."""
    import re
    gs = str(dim_obj.get("golden_set", ""))
    if gs.strip().lower().startswith("n/a"):
        return None
    m = re.search(r"(companion_\w+_golden\.json|companion_probe_bank\.json)", gs)
    if not m:
        return None
    name = m.group(1)
    # probe bank lives under tools/
    return (TOOLS / name) if name == "companion_probe_bank.json" else (ROOT / name)


def discover_check(sc: dict, bl: dict) -> tuple[bool, list[str], str]:
    """G-1 auto-discovery: every dimension must resolve to its golden set, grader,
    eval harness, and (for product dims) a frozen baseline. Orphans FAIL. Also
    flags golden files on disk that no dimension claims. Pure (no writes)."""
    issues: list[str] = []
    dims = sc.get("dimensions", {})
    bl_dims = (bl or {}).get("dimensions", {})
    claimed_golden: set[str] = set()

    if not GRADER.exists():
        issues.append(f"grader missing: {GRADER.name}")

    for name, obj in dims.items():
        active = obj.get("status") == "active"
        gf = _golden_file_for(name, obj)
        if gf is not None:
            claimed_golden.add(gf.name)
            if not gf.exists() and active:
                issues.append(f"[{name}] active dim's golden set missing: {gf.name}")
        elif active and name not in ("cost",):
            issues.append(f"[{name}] active dim has no resolvable golden set")

        # product dims need a per-dim eval harness + a frozen baseline
        if name in PRODUCT_DIMS:
            if not DIM_EVAL[name].exists():
                issues.append(f"[{name}] eval harness missing: {DIM_EVAL[name].name}")
            if active and name not in bl_dims:
                issues.append(f"[{name}] active dim has no frozen baseline in {BASELINES.name}")

    # orphan golden files: a companion_*_golden.json on disk that NO dimension claims
    # AND that carries no probe_type tags. A probe-tagged golden file is claimed by the
    # taxonomy (families folded into existing dims — doctrine, safety-gaps), not an orphan.
    for gp in ROOT.glob("companion_*_golden.json"):
        if gp.name in claimed_golden:
            continue
        if _doc_has_probe_type(_load(gp)):
            continue
        issues.append(f"orphan golden set on disk (no dimension claims it, no probe_type tags): {gp.name}")

    n_dims = len(dims)
    n_active = sum(1 for d in dims.values() if d.get("status") == "active")
    summary = f"{n_dims} dims ({n_active} active), {len(claimed_golden)} golden sets resolved"
    return (len(issues) == 0), issues, summary


# ───────────────────────────── probe-type coverage ────────────────────────────

def _collect_probe_type_tags() -> set[str]:
    """Scan every companion_*_golden.json for `probe_type` tags on units. As golden
    units are authored/tagged with a taxonomy id, live coverage grows — the forward-
    only depth signal. Recursive so it finds the tag wherever a golden shape nests it."""
    tags: set[str] = set()

    def _walk(o):
        if isinstance(o, dict):
            pt = o.get("probe_type")
            if isinstance(pt, str):
                tags.add(pt)
            elif isinstance(pt, list):
                tags.update(str(x) for x in pt)
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)

    for gp in ROOT.glob("companion_*_golden.json"):
        _walk(_load(gp))
    return tags


def _doc_has_probe_type(doc) -> bool:
    """True if a loaded golden doc carries any `probe_type` tag (claimed by the taxonomy)."""
    found = False

    def _w(o):
        nonlocal found
        if found:
            return
        if isinstance(o, dict):
            if isinstance(o.get("probe_type"), (str, list)):
                found = True
                return
            for v in o.values():
                _w(v)
        elif isinstance(o, list):
            for v in o:
                _w(v)

    _w(doc)
    return found


def probe_coverage() -> dict | None:
    """Compute probe-type coverage: per family, total types, the seed estimate
    (have/partial/missing from the taxonomy), and LIVE tags found in golden sets.
    Pure (no writes). Returns None if the taxonomy is absent."""
    tax = _load(PROBE_TAXONOMY)
    if not tax:
        return None
    probes = tax.get("probes", [])
    families = tax.get("families", {})
    tags = _collect_probe_type_tags()

    fam: dict[str, dict] = {}
    for p in probes:
        f = p.get("family", "?")
        d = fam.setdefault(f, {"total": 0, "have": 0, "partial": 0, "missing": 0, "live": 0, "ids": []})
        d["total"] += 1
        cov = p.get("coverage", "missing")
        d[cov] = d.get(cov, 0) + 1
        if p.get("id") in tags:
            d["live"] += 1
        d["ids"].append(p.get("id"))

    total = len(probes)
    live = sum(1 for p in probes if p.get("id") in tags)
    est = sum(1 for p in probes if p.get("coverage") in ("have", "partial"))
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_probe_types": total,
        "live_tagged": live,             # forward-only: grows as golden units get probe_type tags
        "estimated_covered": est,        # seed belief (taxonomy coverage field)
        "missing_families": [f for f, d in fam.items() if d["have"] == 0 and d["partial"] == 0 and d["live"] == 0],
        "by_family": {f: {"label": families.get(f, f), **{k: v for k, v in d.items() if k != "ids"}} for f, d in fam.items()},
    }

    # ── WIRING axis (J-O) — a SEPARATE forward-only count (COMPANION_WIRING_PROBE_STUDY.md).
    # behaviour `probes[]` above asks "does the companion SAY the right thing"; wiring asks
    # "does every internal function FIRE". Covered = distinct wire_targets among have/partial
    # (or live-tagged) wiring probes, over a fixed `wire_total` (the study's wire census).
    wax = tax.get("wiring_axis")
    if wax:
        wprobes = wax.get("probes", [])
        wfam_labels = wax.get("families", {})
        wfam: dict[str, dict] = {}
        for p in wprobes:
            f = p.get("family", "?")
            d = wfam.setdefault(f, {"total": 0, "have": 0, "partial": 0, "missing": 0, "live": 0, "ids": []})
            d["total"] += 1
            wcov = p.get("coverage", "missing")
            d[wcov] = d.get(wcov, 0) + 1
            if p.get("id") in tags:
                d["live"] += 1
            d["ids"].append(p.get("id"))
        covered_targets = {
            p.get("wire_target") for p in wprobes
            if p.get("coverage") in ("have", "partial") or p.get("id") in tags
        }
        wire_total = wax.get("wire_total", len(wprobes))
        out["wiring"] = {
            "wire_total": wire_total,
            "wiring_covered": len(covered_targets),       # forward-only: ratchets W1-W9 toward ~57/62
            "probe_rows": len(wprobes),
            "missing_families": [f for f, d in wfam.items() if d["have"] == 0 and d["partial"] == 0 and d["live"] == 0],
            "by_family": {f: {"label": wfam_labels.get(f, f), **{k: v for k, v in d.items() if k != "ids"}} for f, d in wfam.items()},
        }
    return out


def layer_probes() -> tuple[bool, str]:
    """G-1 sibling: probe-TYPE coverage (how much of the architecture we actually
    exercise). Advisory — surfaces the depth gap, never blocks."""
    step("probes: probe-type coverage (taxonomy vs golden sets)")
    cov = probe_coverage()
    if cov is None:
        warn(f"{PROBE_TAXONOMY.name} absent — run the taxonomy build first (advisory skip)")
        return True, "no taxonomy (skip)"
    PROBE_COVERAGE.write_text(json.dumps(cov, indent=2, ensure_ascii=False), encoding="utf-8")
    for f, d in sorted(cov["by_family"].items()):
        flag = RED + "MISSING" + RESET if (d["have"] == 0 and d["partial"] == 0 and d["live"] == 0) else ""
        print(f"    {f} {d['label'][:34]:<34} {d['have']}+{d['partial']}/{d['total']} est · {d['live']} live {flag}")
    summary = (f"{cov['live_tagged']} tagged / {cov['estimated_covered']} est of "
               f"{cov['total_probe_types']} types · missing families: "
               f"{','.join(cov['missing_families']) or 'none'}")
    ok(summary)

    # ── WIRING axis (J-O) — separate forward-only count (anti-drift target for W1-W9).
    w = cov.get("wiring")
    if w:
        print(f"    {BOLD}— wiring axis (J-O): every internal function FIRES —{RESET}")
        for f, d in sorted(w["by_family"].items()):
            flag = RED + "0-covered" + RESET if (d["have"] == 0 and d["partial"] == 0 and d["live"] == 0) else ""
            print(f"    {f} {d['label'][:42]:<42} {d['have']}+{d['partial']}/{d['total']} · {d['live']} live {flag}")
        wsummary = (f"wiring: {w['wiring_covered']}/{w['wire_total']} wires covered "
                    f"({w['probe_rows']} probe rows) · dark families: "
                    f"{','.join(w['missing_families']) or 'none'}")
        ok(wsummary)
        summary = f"{summary} || {wsummary}"
    return True, summary


def layer_discover() -> tuple[bool, str]:
    step("G-1 discover: dims <-> golden <-> grader <-> baseline coverage")
    sc = _load(SCORECARD)
    if not sc:
        fail(f"{SCORECARD.name} missing/unparseable")
        return False, "no scorecard"
    passed, issues, summary = discover_check(sc, _load(BASELINES) or {})
    for i in issues:
        fail(i)
    if passed:
        ok(summary + " — no orphans")
    return passed, summary


# ───────────────────────────── status ─────────────────────────────────────────

# ──────────────────── L2/L3 live brain-probe battery ──────────────────────────

def layer_probe_battery() -> tuple[bool, str]:
    """L2/L3 live brain-probe battery. A taxonomy probe (golden unit) is EXERCISED
    LIVE against the real companion via window.__CSURF.runProbe (Playwright MCP),
    and its verdict feeds the appropriate layers:
      • PASS -> the probe is live-walked (coverage confirms the type is exercised, G-1)
      • FAIL -> a harvest candidate (G-1.5 substrate -> golden -> L4 eval) — the
                live miss becomes a corpus fix, exactly like a thumbs-down.
    Reads companion_probe_live_report.json (written by the MCP walk). Forward-only:
    a FAIL blocks and is named as a harvest candidate; no live run yet -> warns."""
    step("L2/L3 brain-probe battery — live probes via Playwright MCP (window.__CSURF.runProbe)")
    rep = _load(PROBE_LIVE_REPORT)
    if not rep:
        warn("no live probe verdicts yet — run the MCP walk (__CSURF.runProbe per golden probe)")
        return True, "no live probe run on record (non-blocking)"
    probes = rep.get("probes", [])
    fails = [p for p in probes if not p.get("pass")]
    for p in probes:
        (ok if p.get("pass") else fail)(f"{p.get('probe_type') or '?':<4} {p.get('id'):<28} [{p.get('mode')}]")
    for p in fails:
        warn(f"FAIL {p.get('id')} -> harvest candidate (feeds substrate->golden->eval); reply: {str(p.get('reply',''))[:80]}")
    walked = ", ".join(sorted({p.get("probe_type") for p in probes if p.get("probe_type")}))
    if fails:
        return False, f"{len(fails)}/{len(probes)} live probe(s) FAIL -> {len(fails)} harvest candidate(s)"
    return True, f"{len(probes)} probe(s) live-walked PASS ({walked})"


# ─────────────────────────── L0 static delivery ──────────────────────────────

def layer_delivery() -> tuple[bool, str]:
    """L0 static: the companion's surface-wiring gate (companion_delivery_gate.py).

    Mirrors the Mega Gate's Layer 0 (run_platform_checks --fast) but scoped to the
    companion DELIVERY surfaces: does the answer the brain produced actually reach
    the screen (gateway_unwrap), does the client path exist (client_wiring), does
    👍/👎 reach the harvest sink (feedback_sink), does the launcher mount once
    (single_mount). Every OTHER layer here grades the BRAIN via its own client +
    unwrap and never executes the product's delivery code — so this is the layer
    that catches a live 'flop' the eval/battery stay green through. Forward-only
    ratchet (companion_delivery_baseline.json)."""
    okk, summary = run_tool(
        [DELIVERY_GATE],
        "L0 static delivery: gateway_unwrap · client_wiring · feedback_sink · single_mount",
    )
    return okk, summary or "delivery checks ran"


def layer_surface() -> tuple[bool, str]:
    """L2/L3 live Surface Battery — the DELIVERY counterpart of the brain battery
    (companion_battery.js / __CSB). Where L0 static reads the code and asks 'WOULD
    it deliver?', this drives the REAL surface in a live browser and asserts what
    the user SEES: a non-empty bubble, a single widget, a 👍 that lands an
    ai_reply_feedback row. Like the Mega Gate's L3 __UFAI live waves, it is DRIVEN
    VIA PLAYWRIGHT MCP (needs the live local stack + a signed-in session) — not a
    $0 headless layer. It reads the last verdict the MCP walk wrote to
    companion_surface_battery_report.json (forward-only: a missing/failed report
    blocks; a passing one ok). A NEW failure here becomes a NEW L0 static check
    (the GH Hardening bridge, L2→L0)."""
    if not SURFACE_BATTERY.exists():
        fail(f"{SURFACE_BATTERY.name} (the __CSURF engine) not found")
        return False, "engine missing"
    step("L2/L3 surface battery — live, driven via Playwright MCP (window.__CSURF)")
    print(f"    Engine: {SURFACE_BATTERY.name}  ·  install: fetch + (0,eval)(text) → window.__CSURF")
    print( "    MCP walk (through the Flask bridge, signed in):")
    print( "      logbook.html → run({surface:'launcher'})  · assistant.html → run({surface:'assistant'})"
           " · voice-journal.html → run({surface:'voice'})")
    rep = _load(SURFACE_REPORT)
    if not rep:
        warn("no live verdict yet — run the MCP walk to write companion_surface_battery_report.json")
        return False, "no live run on record"
    surfaces = rep.get("surfaces", [])
    fails = [s for s in surfaces if not s.get("pass")]
    line = " · ".join(f"{s['surface']} {s.get('score', '?')}" for s in surfaces)
    if rep.get("all_pass") and not fails:
        ok(f"last live run {rep.get('generated_at', '?')} — {line}")
        return True, f"{len(surfaces)} surfaces PASS ({line})"
    fail(f"surfaces failing: {', '.join(s['surface'] for s in fails)}")
    return False, f"{len(fails)} surface(s) failing ({line})"


# ───────────────── the two self-improving bridges (GH / GS) ───────────────────
# Mirrors the Unified Mega Gate's two bridges, pointed at the companion:
#   GH Hardening (L2 -> L0): a live Surface-Battery defect becomes a new L0 static
#                            check (companion_delivery_gate.py). This session did it
#                            by hand: the live flop -> the gateway_unwrap check.
#   GS Sentinel  (L0 -> L2): every L0 static check must have a live __CSURF scenario
#                            that exercises the same invariant — no static rule left
#                            un-walked. This is the deterministic coverage view.
# L0 static check  ->  the L2 __CSURF live check(s) that exercise the same invariant.
_L0_L2_COVERAGE = {
    "gateway_unwrap": ["render_reply", "gateway_delivers"],
    "client_wiring":  ["render_reply", "feedback_row"],
    "feedback_sink":  ["feedback_row"],
    "single_mount":   ["single_mount"],
}


def layer_sentinel() -> tuple[bool, str]:
    """GS Sentinel (L0->L2) coverage + GH Hardening (L2->L0) candidates. Reads the
    L0 delivery report + the L2 Surface-Battery report and proves every L0 static
    check has a live __CSURF scenario, and flags any live check with no L0 guard
    (a Hardening candidate). Blocks on an UN-WALKED L0 check (a static rule no live
    scenario exercises)."""
    step("bridges: GS Sentinel (L0->L2 coverage) + GH Hardening (L2->L0 candidates)")
    drep = _load(ROOT / "companion_delivery_report.json")
    srep = _load(SURFACE_REPORT)
    l0_checks = [r["check"] for r in (drep.get("checks", []) if drep else [])] or list(_L0_L2_COVERAGE.keys())
    l2_present = set()
    for s in (srep.get("surfaces", []) if srep else []):
        for c in s.get("checks", []):
            l2_present.add(c.get("name"))

    gaps, covered = [], []
    for chk in l0_checks:
        scenarios = [s for s in _L0_L2_COVERAGE.get(chk, []) if s in l2_present]
        (covered if scenarios else gaps).append(chk)
        mark = ok if scenarios else fail
        mark(f"L0 {chk:<15} -> L2 [{', '.join(scenarios) or 'NO LIVE SCENARIO'}]")
    # Hardening direction: live checks with no L0 guard at all.
    guarded_l2 = {v for vs in _L0_L2_COVERAGE.values() for v in vs}
    hardening = sorted(c for c in l2_present if c not in guarded_l2 and c != "ui_unwrap")
    for c in hardening:
        warn(f"L2 {c} has no L0 static guard — Hardening candidate (consider a companion_delivery_gate check)")

    if gaps:
        return False, f"{len(gaps)} L0 check(s) un-walked by L2: {', '.join(gaps)}"
    summary = f"{len(covered)}/{len(l0_checks)} L0 checks walked live"
    if hardening:
        summary += f" · {len(hardening)} hardening candidate(s)"
    return True, summary


def _effective_gate_state(name: str, obj: dict, bl_dims: dict) -> str:
    if not obj.get("blocking"):
        return "soft"
    tol = (obj.get("tolerance", {}) or {}).get("pass_rate_pp")
    if tol is None:  # cost uses pct; safety has 0.0pp
        tol = (obj.get("tolerance", {}) or {}).get("pct")
    nb = _n_to_block(float(tol) if tol is not None else 0)
    if name not in bl_dims:
        return "frozen" if name in ("safety",) else "warn (no baseline)"
    n = (bl_dims.get(name, {}).get("locked_test", {}) or {}).get("n", 0) or 0
    if nb == 0:
        return "frozen (enforced)"
    return f"BLOCKS" if n >= nb else f"warn {n}/{nb}"


def cmd_status() -> int:
    sc = _load(SCORECARD)
    if not sc:
        print(f"{RED}No scorecard ({SCORECARD.name}).{RESET}")
        return 1
    bl_dims = (_load(BASELINES) or {}).get("dimensions", {})
    dims = sc.get("dimensions", {})
    n_active = sum(1 for d in dims.values() if d.get("status") == "active")
    banner(f"COMPANION DEV — STATUS  ({n_active}/{len(dims)} dims active)", "cyan")

    print(f"  {BOLD}Dimension          status   locked-test    train        gap     gate{RESET}")
    for name, obj in sorted(dims.items(), key=lambda kv: kv[1].get("order", 99)):
        bd = bl_dims.get(name, {}) if name in bl_dims else {}
        b = bd.get("locked_test", {})
        pr = b.get("pass_rate")
        n = b.get("n")
        lt = f"{pr:.0f}% (n={n})" if pr is not None else "—"
        # §9 #3 overfitting gauge: train_pass − locked_test_pass. A large POSITIVE gap (train >>
        # held-out) is the memorization smell; a negative/zero gap is fine (locked-test is honest).
        tb = bd.get("train", {})
        tr = tb.get("pass_rate")
        tn = tb.get("n")
        train_s = f"{tr:.0f}% (n={tn})" if tr is not None else "—"
        gap = (tr - pr) if (tr is not None and pr is not None) else None
        if gap is None:
            gap_s = "—"
        else:
            gap_s = f"{'+' if gap >= 0 else '-'}{abs(gap):.0f}pp"
        overfit = gap is not None and gap >= OVERFIT_GAP_PP
        warn = f"  {YEL}overfit-smell{RESET}" if overfit else ""
        eff = _effective_gate_state(name, obj, bl_dims)
        st = obj.get("status", "?")
        stc = GREEN if st == "active" else YEL
        print(f"  {name:<17} {stc}{st:<8}{RESET} {lt:<14} {train_s:<12} {gap_s:<7} {eff}{warn}")

    # Harvest queue
    cand = _load(CANDIDATES)
    if cand and isinstance(cand, dict):
        cs = cand.get("candidates", [])
        disp = {}
        for c in cs:
            disp[c.get("disposition", "pending")] = disp.get(c.get("disposition", "pending"), 0) + 1
        print(f"\n  {BOLD}Harvest queue:{RESET} {len(cs)} candidate(s) "
              f"({', '.join(f'{k}={v}' for k, v in sorted(disp.items())) or 'empty'})")
    else:
        print(f"\n  {BOLD}Harvest queue:{RESET} none yet (run `harvest`)")

    # Optimization
    ab = _load(AB_RESULTS) or {}
    props = _load(PROPOSALS) or {}
    pl = props.get("proposals", []) if isinstance(props, dict) else []
    last_ab = f"{ab.get('proposal')} -> {ab.get('decision')}" if isinstance(ab, dict) and ab.get("decision") else "none"
    print(f"  {BOLD}Optimization:{RESET} {len(pl)} proposal(s) · last A/B: {last_ab}")

    # Probe-type coverage (the depth signal)
    cov = probe_coverage()
    if cov:
        miss = cov["missing_families"]
        print(f"  {BOLD}Probe coverage:{RESET} {cov['live_tagged']} tagged / {cov['estimated_covered']} est "
              f"of {cov['total_probe_types']} types"
              + (f" · {RED}missing families: {','.join(miss)}{RESET}" if miss else ""))
        # Wiring axis (J-O): does every internal function FIRE (vs behaviour above)
        w = cov.get("wiring")
        if w:
            wmiss = w["missing_families"]
            print(f"  {BOLD}Wiring coverage:{RESET} {w['wiring_covered']}/{w['wire_total']} wires"
                  + (f" · {RED}dark families: {','.join(wmiss)}{RESET}" if wmiss else ""))

    # Last mega pass
    marker = _load(PASS_MARKER)
    if marker and isinstance(marker, dict):
        print(f"  {BOLD}Last mega:{RESET} {marker.get('result', '?')} at {marker.get('ts', '?')}")
    else:
        print(f"  {BOLD}Last mega:{RESET} never run")
    print()
    return 0


# ───────────────────────────── thin wrappers ──────────────────────────────────

def cmd_harvest(_a) -> int:
    okk, _ = run_tool([HARVEST, "harvest"], "harvest: thumbs-down -> candidates")
    return 0 if okk else 1


def cmd_dispose(_a) -> int:
    run_tool([HARVEST, "report"], "dispose: triage queue")
    print(f"\n  Edit {CANDIDATES.name}: set disposition=accepted + target_dimension on keepers, "
          f"then `companion_dev.py optimize` / re-run the loop.")
    return 0


def cmd_eval(args) -> int:
    dims = [args.dim] if getattr(args, "dim", None) else list(PRODUCT_DIMS)
    if getattr(args, "live", False):
        print(f"{YEL}--live capture needs the local Supabase + edge runtime + a clean rate-limit "
              f"window. Run the per-dim capture spec, e.g.:{RESET}")
        for d in dims:
            print(f"    npx playwright test tests/{d}-golden-capture.spec.ts")
        print("  then re-run `companion_dev.py eval` to grade the captured observations.")
        return 0
    all_ok = True
    for d in dims:
        if not DIM_EVAL[d].exists():
            warn(f"[{d}] eval harness missing — skip"); continue
        okk, _ = run_tool([DIM_EVAL[d], "--self-test"], f"G1/G2 grader self-test: {d}")
        all_ok = all_ok and okk
    return 0 if all_ok else 1


def cmd_optimize(args) -> int:
    okk, _ = run_tool([OPTIMIZE, "propose"], "G3 optimize: reflect -> propose")
    print(f"  (measured A/B mutates a local edge fn + spends LLM calls — run it deliberately: "
          f"`companion_optimize.py ab --dim D ...`)")
    return 0 if okk else 1


def cmd_gate(_a) -> int:
    okk, _ = run_tool([GATE, "companion-gate"], "G0 gate: per-dim locked-test (forward-only, n-aware)")
    vok, _ = run_tool([SCORECARD_TOOL, "verify"], "scorecard registry verify")
    return 0 if (okk and vok) else 1


# ───────────────────────────── mega (closed loop) ─────────────────────────────

def cmd_mega(args) -> int:
    banner("COMPANION MEGA GATE", "cyan")
    layers: list[tuple[str, bool, str]] = []

    sok, ssum = layer_substrate(); layers.append(("substrate", sok, ssum)); print()
    dok, dsum = layer_discover(); layers.append(("discover", dok, dsum)); print()
    pok, psum = layer_probes(); layers.append(("probes", pok, psum)); print()

    # L0 static delivery (surface wiring: render/feedback/mount). Runs before the
    # brain layers — a broken surface makes a green brain useless to the worker.
    delok, delsum = layer_delivery(); layers.append(("delivery(L0)", delok, delsum)); print()

    if getattr(args, "live", False):
        eok = cmd_eval(argparse.Namespace(dim=None, live=True)) == 0
        layers.append(("eval(live)", eok, "capture instructions printed")); print()

    # G0 gate
    gok, gsum = run_tool([GATE, "companion-gate"], "G0 gate: per-dim locked-test")
    layers.append(("gate", gok, gsum)); print()

    # graders self-test (G1/G2 trust property, offline)
    grok = True
    for d in PRODUCT_DIMS:
        if DIM_EVAL[d].exists():
            o, _ = run_tool([DIM_EVAL[d], "--self-test"], f"grader self-test: {d}")
            grok = grok and o
    layers.append(("graders", grok, f"{sum(1 for d in PRODUCT_DIMS if DIM_EVAL[d].exists())} dim self-tests")); print()

    # perturbation-invariance metric self-test (§9 #2, offline) — proves the generator emits
    # intent-preserving variants AND the invariance metric separates a generalizer from a memorizer.
    if PERTURB.exists():
        pzok, _ = run_tool([PERTURB, "--self-test"], "perturb-invariance self-test (generalizer 100% vs memorizer 0%)")
        layers.append(("perturb", pzok, "invariance metric discriminates")); print()

    # L2/L3 live Surface Battery — opt-in (--live), like the Mega Gate's --with-battery.
    # Reads the last verdict the Playwright-MCP walk wrote; needs the live stack.
    if getattr(args, "live", False):
        surfok, surfsum = layer_surface(); layers.append(("surface(L2/L3 live)", surfok, surfsum)); print()
        pbok, pbsum = layer_probe_battery(); layers.append(("probe-battery(L2/L3 live)", pbok, pbsum)); print()
        senok, sensum = layer_sentinel(); layers.append(("sentinel(L0<->L2)", senok, sensum)); print()

    vok, _ = run_tool([SCORECARD_TOOL, "verify"], "scorecard registry verify")
    layers.append(("scorecard", vok, "registry well-formed")); print()

    if getattr(args, "propose", False):
        pok, _ = run_tool([OPTIMIZE, "propose"], "G3 optimize: reflect -> propose")
        layers.append(("optimize", pok, "proposals refreshed")); print()

    all_pass = all(okk for _, okk, _ in layers)
    result = "PASS" if all_pass else "BLOCK"
    _persist_run(result, layers)

    if all_pass:
        banner("COMPANION MEGA — PASS", "green")
        for name, _, s in layers:
            print(f"  {name}: {s or 'ok'}")
        _write_marker("PASS", layers)
        return 0
    banner("COMPANION MEGA — BLOCK", "red")
    for name, okk, s in layers:
        print(f"  {name}: {'PASS' if okk else 'FAIL'} — {s or '(no summary)'}")
    print("\nFix the failing layer(s), then re-run.")
    return 1


def _write_marker(result: str, layers: list[tuple[str, bool, str]]) -> None:
    PASS_MARKER.write_text(json.dumps({
        "result": result,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "layers": {n: ("PASS" if o else "FAIL") for n, o, _ in layers},
    }, indent=2), encoding="utf-8")


def _persist_run(result: str, layers: list[tuple[str, bool, str]]) -> None:
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "result": result,
        "layers": {n: {"ok": o, "summary": s} for n, o, s in layers},
    }
    try:
        with RUN_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


# ───────────────────────────── self-test ──────────────────────────────────────

def cmd_self_test() -> int:
    """Prove the orchestrator wiring with NO DB and NO model."""
    fails: list[str] = []

    # 1. every orchestrated tool + grader exists
    for t in [HARVEST, OPTIMIZE, GATE, SCORECARD_TOOL, GRADER, PERTURB, JUDGE, *DIM_EVAL.values()]:
        if not t.exists():
            fails.append(f"missing tool: {t.relative_to(ROOT)}")

    # 2. scorecard + baselines parse and carry the expected dims
    sc = _load(SCORECARD)
    if not sc or "dimensions" not in sc:
        fails.append("scorecard missing/malformed")
    else:
        for d in PRODUCT_DIMS + ("safety", "cost"):
            if d not in sc["dimensions"]:
                fails.append(f"scorecard missing dimension {d}")

    # 3. substrate manifest builds to the expected shape (pure, no write)
    try:
        man = build_substrate_manifest()
        for k in ("golden_corpus", "harvest", "baselines", "optimization", "dims_active"):
            if k not in man:
                fails.append(f"substrate manifest missing key {k}")
    except Exception as e:  # noqa: BLE001
        fails.append(f"substrate manifest build threw: {e}")

    # 4. discover passes on the REAL repo (no orphans today)
    if sc:
        passed, issues, _ = discover_check(sc, _load(BASELINES) or {})
        if not passed:
            fails.append("discover found orphans on the real repo: " + "; ".join(issues[:3]))

        # 5. discover CATCHES a synthetic orphan (teeth proof)
        import copy
        bad = copy.deepcopy(sc)
        bad["dimensions"]["__ghost__"] = {
            "status": "active", "order": 99,
            "golden_set": "companion_ghost_golden.json (does not exist)",
            "tolerance": {"pass_rate_pp": 5.0},
        }
        bpassed, bissues, _ = discover_check(bad, _load(BASELINES) or {})
        if bpassed or not any("ghost" in i.lower() for i in bissues):
            fails.append("discover did NOT catch a synthetic orphan dimension")

    # 5b. probe-type coverage builds + has the expected shape (if taxonomy present)
    cov = probe_coverage()
    if cov is not None:
        for k in ("total_probe_types", "live_tagged", "estimated_covered", "by_family"):
            if k not in cov:
                fails.append(f"probe_coverage missing key {k}")
        if cov.get("total_probe_types", 0) < 1:
            fails.append("probe taxonomy has 0 probe types")

        # 5c. WIRING axis shape (if wiring_axis present) — assert structure, NOT the count
        # (the count ratchets W1-W9, so pinning it would break later phases).
        w = cov.get("wiring")
        if w is not None:
            for k in ("wire_total", "wiring_covered", "probe_rows", "by_family"):
                if k not in w:
                    fails.append(f"wiring coverage missing key {k}")
            if w.get("wire_total", 0) < w.get("wiring_covered", 0):
                fails.append("wiring_covered exceeds wire_total (denominator math broken)")
            if w.get("probe_rows", 0) < 1:
                fails.append("wiring_axis present but has 0 probe rows")

    # 6. effective-gate-state math: n>=ceil(100/tol) BLOCKS, below WARNs
    if _n_to_block(5.0) != 20:
        fails.append(f"_n_to_block(5.0) expected 20, got {_n_to_block(5.0)}")
    st_block = _effective_gate_state("persona", {"blocking": True, "tolerance": {"pass_rate_pp": 5.0}},
                                     {"persona": {"locked_test": {"n": 25}}})
    st_warn = _effective_gate_state("persona", {"blocking": True, "tolerance": {"pass_rate_pp": 5.0}},
                                    {"persona": {"locked_test": {"n": 4}}})
    if st_block != "BLOCKS":
        fails.append(f"n=25 should BLOCK, got {st_block!r}")
    if not st_warn.startswith("warn"):
        fails.append(f"n=4 should WARN, got {st_warn!r}")

    if fails:
        print(f"{RED}{BOLD}SELF-TEST FAILED:{RESET}")
        for f in fails:
            print(f"  {RED}x{RESET} {f}")
        return 1
    print(f"{GREEN}{BOLD}SELF-TEST PASSED{RESET} — all tools resolve, scorecard well-formed, "
          f"substrate manifest builds, discover passes the repo + catches a synthetic orphan, "
          f"n-aware gate math correct.")
    return 0


# ───────────────────────────── main ───────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="AI Companion Developer Tool — the companion's Mega Gate.")
    ap.add_argument("--self-test", action="store_true", help="prove the orchestrator wiring (no DB/model)")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("status", help="scorecard + harvest + last A/B, one glance")
    sub.add_parser("substrate", help="G-1.5: build companion_substrate_manifest.json")
    sub.add_parser("discover", help="G-1: dims<->golden<->grader<->baseline coverage (exit 1 on orphan)")
    sub.add_parser("probes", help="probe-type coverage: how many of the ~60 taxonomy types have a golden unit")
    sub.add_parser("harvest", help="thumbs-down -> candidates")
    sub.add_parser("dispose", help="show the triage queue")
    pe = sub.add_parser("eval", help="G1+G2: grader self-tests ($0); --live = capture instructions")
    pe.add_argument("--dim", choices=PRODUCT_DIMS)
    pe.add_argument("--live", action="store_true")
    sub.add_parser("optimize", help="G3: reflect -> propose")
    sub.add_parser("delivery", help="L0 static: companion surface-wiring gate (render/feedback/mount, forward-only)")
    sub.add_parser("surface", help="L2/L3 live: Surface Battery verdict (window.__CSURF, driven via Playwright MCP)")
    sub.add_parser("probe-battery", help="L2/L3 live: brain-probe verdicts (__CSURF.runProbe via MCP) -> coverage/harvest feed")
    sub.add_parser("sentinel", help="bridges: GS Sentinel L0->L2 coverage + GH Hardening L2->L0 candidates")
    sub.add_parser("gate", help="L4 correctness: per-dim locked-test gate (exit 1 on regression)")
    pm = sub.add_parser("mega", help="run the whole loop + write .last-companion-gate-pass")
    pm.add_argument("--live", action="store_true", help="include live capture instructions")
    pm.add_argument("--propose", action="store_true", help="include the G3 propose arm")

    args = ap.parse_args()
    if args.self_test:
        return cmd_self_test()
    cmd = args.cmd or "status"
    if cmd == "status":    return cmd_status()
    if cmd == "substrate": return 0 if layer_substrate()[0] else 1
    if cmd == "discover":  return 0 if layer_discover()[0] else 1
    if cmd == "probes":    return 0 if layer_probes()[0] else 1
    if cmd == "delivery":  return 0 if layer_delivery()[0] else 1
    if cmd == "surface":   return 0 if layer_surface()[0] else 1
    if cmd == "probe-battery": return 0 if layer_probe_battery()[0] else 1
    if cmd == "sentinel":  return 0 if layer_sentinel()[0] else 1
    if cmd == "harvest":   return cmd_harvest(args)
    if cmd == "dispose":   return cmd_dispose(args)
    if cmd == "eval":      return cmd_eval(args)
    if cmd == "optimize":  return cmd_optimize(args)
    if cmd == "gate":      return cmd_gate(args)
    if cmd == "mega":      return cmd_mega(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
