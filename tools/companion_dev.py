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
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_probe_types": total,
        "live_tagged": live,             # forward-only: grows as golden units get probe_type tags
        "estimated_covered": est,        # seed belief (taxonomy coverage field)
        "missing_families": [f for f, d in fam.items() if d["have"] == 0 and d["partial"] == 0 and d["live"] == 0],
        "by_family": {f: {"label": families.get(f, f), **{k: v for k, v in d.items() if k != "ids"}} for f, d in fam.items()},
    }


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
    for t in [HARVEST, OPTIMIZE, GATE, SCORECARD_TOOL, GRADER, PERTURB, *DIM_EVAL.values()]:
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
    sub.add_parser("gate", help="G0: per-dim locked-test gate (exit 1 on regression)")
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
