#!/usr/bin/env python3
"""
content_dev.py — the Content Grounding Gate front door (the THIRD sibling Mega Gate).
====================================================================================
ONE front door to develop, evaluate, and self-improve every OUTWARD-facing surface
(landing page, /learn articles, SEO/AEO/GEO artifacts, video marketing), structured
as a self-improving CLOSED LOOP modeled on release_gate.py + companion_dev.py.

  Mega Gate tests platform CODE   (release_gate.py)
  Companion Dev tests AI BEHAVIOR (companion_dev.py)
  Content Grounding tests OUTWARD CONTENT — does it still match the ever-evolving
  platform? Source of truth = the auto-derived Platform Catalog (platform_catalog.py).

Layer mapping (Mega Gate -> content):
  G-1.5 Substrate      -> substrate : build platform_catalog.json + content_substrate_manifest.json
  G-1   Auto-discovery -> discover  : coverage / orphans / gaps across the 4 surfaces
  G0    Static         -> gate      : content_grounding_gate.py drift validators (ratcheted)
  G3    Loop           -> harvest/dispose/regenerate (built in P4)
  Mega  orchestration  -> mega      : run the loop, write .last-content-gate-pass + 4-axis scorecard

Usage:
  python tools/content_dev.py status        # 4-axis scorecard + drift + coverage, one glance
  python tools/content_dev.py substrate      # G-1.5  rebuild catalog + substrate manifest
  python tools/content_dev.py discover       # G-1    coverage / orphans / gaps
  python tools/content_dev.py gate [--strict]# G0     drift validators (forward-only ratchet)
  python tools/content_dev.py harvest        # G3     drift -> regeneration candidates (P4)
  python tools/content_dev.py dispose        #        triage queue (P4)
  python tools/content_dev.py regenerate     #        drive generators from the catalog (P4)
  python tools/content_dev.py mega           # run the whole loop + write .last-content-gate-pass
  python tools/content_dev.py --self-test    # prove the orchestrator wiring (no server/model)
"""
from __future__ import annotations
import argparse
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
PY = sys.executable
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

# Artifacts (the loop's state)
CATALOG = ROOT / "platform_catalog.json"
MANIFEST = ROOT / "content_substrate_manifest.json"
DISCOVER = ROOT / "content_discover_report.json"
GATE_REPORT = ROOT / "content_grounding_report.json"
GATE_BASELINE = ROOT / "content_grounding_baseline.json"
SCORECARD = ROOT / "content_eval_scorecard.json"
PASS_MARKER = ROOT / ".last-content-gate-pass"
RUN_LOG = ROOT / "content_dev_runs.jsonl"

# Tools the front door orchestrates (each stays independently runnable).
CATALOG_TOOL = TOOLS / "platform_catalog.py"
SUBSTRATE_TOOL = TOOLS / "content_substrate.py"
GATE_TOOL = TOOLS / "content_grounding_gate.py"
HARVEST_TOOL = TOOLS / "content_harvest.py"   # built in P4

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
            if any(k in s for k in ("PASS", "FAIL", "coverage", "orphans", "drift", "wrote", "→")) and len(s) < 140:
                summary = s
    proc.wait()
    return proc.returncode == 0, summary


# ───────────────────────────── 4-axis scorecard ───────────────────────────────

def compute_scorecard() -> dict:
    """freshness · coverage · correctness · grounding — computed live from the
    catalog + discover + gate report (no server/model needed)."""
    import platform_catalog as pc
    import content_substrate as cs
    import content_grounding_gate as cg

    cat = pc.build_catalog()
    disc = cs.discover(cat)
    checks = cg.run_checks()

    arts = cat["articles"]
    dated = sum(1 for a in arts if a["date_modified"])
    freshness = round(100 * dated / len(arts), 1) if arts else 0.0

    coverage = disc["coverage"]["summary"]["article_coverage_pct"]

    total_checks = len(cg.CHECK_ORDER)
    clean_checks = sum(1 for n in cg.CHECK_ORDER if checks[n]["count"] == 0)
    correctness = round(100 * clean_checks / total_checks, 1) if total_checks else 0.0

    # grounding = share of content claims that resolve to a real catalog feature.
    orphans = disc["metrics"]["orphan_count"]
    feature_refs = (
        len(cat["public_surface"]["llms_txt"]["maps"])
        + len(cat["public_surface"]["llms_txt"]["feature_bullets"])
        + len(cat["public_surface"]["index"].get("feature_list", []))
        + sum(1 for _ in disc["coverage"]["by_feature"])
    ) or 1
    grounding = round(100 * (1 - orphans / feature_refs), 1)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "axes": {
            "freshness":   freshness,
            "coverage":    coverage,
            "correctness": correctness,
            "grounding":   grounding,
        },
        "signals": {
            "articles":           len(arts),
            "undated":            len(arts) - dated,
            "total_drift":        sum(checks[n]["count"] for n in cg.CHECK_ORDER),
            "drift_checks_clean": f"{clean_checks}/{total_checks}",
            "orphans":            orphans,
            "gaps":               disc["metrics"]["gap_count"],
            "learn_hub_unlisted": disc["metrics"].get("learn_hub_unlisted", 0),
        },
    }


def write_scorecard() -> dict:
    sc = compute_scorecard()
    SCORECARD.write_text(json.dumps(sc, indent=2), encoding="utf-8")
    return sc


# ───────────────────────────── layers (return ok, summary) ────────────────────

def layer_substrate() -> tuple[bool, str]:
    okk, summ = run_tool([CATALOG_TOOL], "G-1.5 substrate: derive platform_catalog.json")
    okk2, summ2 = run_tool([SUBSTRATE_TOOL], "G-1.5 substrate: content_substrate_manifest.json")
    return (okk and okk2), (summ2 or summ)


def layer_discover() -> tuple[bool, str]:
    okk, summ = run_tool([SUBSTRATE_TOOL, "--discover"], "G-1 discover: coverage / orphans / gaps")
    disc = _load(DISCOVER) or {}
    orphans = disc.get("metrics", {}).get("orphan_count", 0)
    if orphans:
        return False, f"{orphans} orphan(s) — content claims with no catalog backing"
    return okk, summ or "0 orphans"


def layer_gate(strict: bool = False) -> tuple[bool, str]:
    args = [GATE_TOOL] + (["--strict"] if strict else [])
    return run_tool(args, f"G0 gate: content drift validators ({'strict' if strict else 'ratchet'})")


# ───────────────────────────── commands ───────────────────────────────────────

def cmd_status(_a=None) -> int:
    banner("CONTENT GROUNDING — STATUS", "cyan")
    sc = write_scorecard()
    ax = sc["axes"]; sg = sc["signals"]
    print(f"  {BOLD}4-axis scorecard{RESET}")
    for name in ("freshness", "coverage", "correctness", "grounding"):
        v = ax[name]
        col = GREEN if v >= 90 else (YEL if v >= 70 else RED)
        print(f"    {name:<12} {col}{v:>5}%{RESET}")
    print(f"\n  articles: {sg['articles']} ({sg['undated']} undated)   "
          f"drift checks clean: {sg['drift_checks_clean']}   total drift: {sg['total_drift']}")
    print(f"  orphans: {sg['orphans']}   gaps: {sg['gaps']}   learn-hub unlisted: {sg['learn_hub_unlisted']}")
    last = _load(PASS_MARKER)
    if last:
        print(f"\n  last mega: {last.get('result')} @ {last.get('ts')}")
    print()
    return 0


def cmd_substrate(_a=None) -> int:
    okk, _ = layer_substrate()
    return 0 if okk else 1


def cmd_discover(_a=None) -> int:
    okk, _ = layer_discover()
    return 0 if okk else 1


def cmd_gate(args) -> int:
    okk, _ = layer_gate(strict=getattr(args, "strict", False))
    return 0 if okk else 1


def _harvest_available() -> bool:
    return HARVEST_TOOL.exists()


def cmd_harvest(_a=None) -> int:
    if not _harvest_available():
        warn("content_harvest.py not built yet (lands in P4 — the self-improving loop).")
        return 0
    okk, _ = run_tool([HARVEST_TOOL, "harvest"], "G3 harvest: drift -> regeneration candidates")
    return 0 if okk else 1


def cmd_dispose(_a=None) -> int:
    if not _harvest_available():
        warn("content_harvest.py not built yet (lands in P4).")
        return 0
    okk, _ = run_tool([HARVEST_TOOL, "report"], "G3 dispose: triage queue")
    return 0 if okk else 1


def cmd_regenerate(_a=None) -> int:
    if not _harvest_available():
        warn("content_harvest.py not built yet (lands in P4).")
        return 0
    # --all previews every proposal to staging (.tmp/content_regen/) — forward-only,
    # nothing touches a live surface, so it is safe as the one-click cockpit action.
    okk, _ = run_tool([HARVEST_TOOL, "regenerate", "--all"], "G3 regenerate: catalog-grounded proposals -> staging")
    return 0 if okk else 1


# ───────────────────────────── mega (closed loop) ─────────────────────────────

def cmd_mega(args) -> int:
    banner("CONTENT GROUNDING MEGA GATE", "cyan")
    layers: list[tuple[str, bool, str]] = []

    sok, ssum = layer_substrate(); layers.append(("substrate", sok, ssum)); print()
    dok, dsum = layer_discover(); layers.append(("discover", dok, dsum)); print()
    gok, gsum = layer_gate(strict=getattr(args, "strict", False)); layers.append(("gate", gok, gsum)); print()

    # self-tests of the underlying tools (trust property, offline, $0)
    tok = True
    for t in (CATALOG_TOOL, SUBSTRATE_TOOL, GATE_TOOL):
        o, _ = run_tool([t, "--self-test"], f"self-test: {t.name}")
        tok = tok and o
    layers.append(("self-tests", tok, "catalog + substrate + gate self-tests")); print()

    sc = write_scorecard()
    ax = sc["axes"]
    scsum = " · ".join(f"{k[:4]} {v}%" for k, v in ax.items())
    layers.append(("scorecard", True, scsum)); print()

    all_pass = all(okk for _, okk, _ in layers)
    result = "PASS" if all_pass else "BLOCK"
    _persist_run(result, layers)

    if all_pass:
        banner("CONTENT MEGA — PASS", "green")
        for name, _, s in layers:
            print(f"  {name}: {s or 'ok'}")
        _write_marker("PASS", layers)
        return 0
    banner("CONTENT MEGA — BLOCK", "red")
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

def cmd_self_test(_a=None) -> int:
    """Prove the orchestrator wiring with NO server and NO model."""
    fails: list[str] = []

    # 1. every orchestrated tool exists (harvest is P4 — allowed absent).
    for t in (CATALOG_TOOL, SUBSTRATE_TOOL, GATE_TOOL):
        if not t.exists():
            fails.append(f"missing tool: {t.relative_to(ROOT)}")

    # 2. the underlying modules import + build a catalog of the expected shape.
    try:
        import platform_catalog as pc
        cat = pc.build_catalog()
        for k in ("features", "articles", "public_surface", "counts"):
            if k not in cat:
                fails.append(f"catalog missing key {k}")
        if len(cat.get("features", [])) < 20:
            fails.append("catalog has < 20 features")
    except Exception as e:  # noqa: BLE001
        fails.append(f"catalog build threw: {e}")

    # 3. scorecard computes 4 axes in [0,100].
    try:
        sc = compute_scorecard()
        for axis in ("freshness", "coverage", "correctness", "grounding"):
            v = sc["axes"].get(axis)
            if not (isinstance(v, (int, float)) and 0 <= v <= 100):
                fails.append(f"scorecard axis {axis} out of range: {v}")
    except Exception as e:  # noqa: BLE001
        fails.append(f"scorecard threw: {e}")

    # 4. the gate self-test passes (teeth proven inside that tool).
    try:
        import content_grounding_gate as cg
        if cg.self_test() != 0:
            fails.append("content_grounding_gate self-test failed")
    except Exception as e:  # noqa: BLE001
        fails.append(f"gate self-test threw: {e}")

    if fails:
        print(f"{RED}{BOLD}SELF-TEST FAILED:{RESET}")
        for f in fails:
            print(f"  {RED}x{RESET} {f}")
        return 1
    print(f"{GREEN}{BOLD}SELF-TEST PASSED{RESET} — all tools resolve, catalog builds, "
          f"4-axis scorecard in range, drift gate self-test green.")
    return 0


# ───────────────────────────── main ───────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Content Grounding Gate front door — the third sibling Mega Gate.")
    ap.add_argument("--self-test", action="store_true", help="prove the orchestrator wiring (no server/model)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status", help="4-axis scorecard + drift + coverage, one glance")
    sub.add_parser("substrate", help="G-1.5: rebuild catalog + substrate manifest")
    sub.add_parser("discover", help="G-1: coverage / orphans / gaps")
    pg = sub.add_parser("gate", help="G0: content drift validators (forward-only ratchet)")
    pg.add_argument("--strict", action="store_true", help="fail on ANY drift (ignore baseline)")
    sub.add_parser("harvest", help="G3: drift -> regeneration candidates (P4)")
    sub.add_parser("dispose", help="G3: triage queue (P4)")
    sub.add_parser("regenerate", help="G3: drive generators from the catalog (P4)")
    pm = sub.add_parser("mega", help="run the whole loop + write .last-content-gate-pass")
    pm.add_argument("--strict", action="store_true", help="run the gate layer in strict mode")
    args = ap.parse_args()

    if args.self_test:
        return cmd_self_test()

    cmd = args.cmd or "status"
    dispatch = {
        "status": cmd_status, "substrate": cmd_substrate, "discover": cmd_discover,
        "gate": cmd_gate, "harvest": cmd_harvest, "dispose": cmd_dispose,
        "regenerate": cmd_regenerate, "mega": cmd_mega,
    }
    return dispatch[cmd](args)


if __name__ == "__main__":
    sys.exit(main())
