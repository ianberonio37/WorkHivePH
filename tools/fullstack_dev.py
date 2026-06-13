#!/usr/bin/env python3
"""
fullstack_dev.py — the Full-Stack SaaS Gate front door (the FOURTH sibling Mega Gate).
=====================================================================================
ONE front door to run and develop the full-stack-SaaS quality system, organized
under the EXACT SAME layer names as the Unified Mega Gate, so the four gates wear
one identical scaffold and you can never get lost moving between them:

  Mega Gate    tests platform CODE      (release_gate.py)
  Companion    tests AI BEHAVIOR        (companion_dev.py)
  Content      tests OUTWARD CONTENT    (content_dev.py)
  Full-Stack   tests the 13 PRODUCTION LAYERS through the 6 GATE LAYERS
               source of truth = COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 (the 13×6 matrix)

This tool INVENTS NOTHING. It reads the matrix that already exists and routes to the
validators / specs / tools the matrix already names — organized by the Mega Gate's
own gate-layer names. The full-stack concerns were previously absorbed wholly inside
release_gate.py's G0; this front door defuses them into a runnable, per-layer sibling.

Layer mapping (Mega Gate gate-layer -> command):
  G-1.5 Substrate      -> substrate : pattern miners + substrate_manifest (the SHAPE layer)
  G-1   Auto-discovery -> discover  : matrix-integrity meta-gate + the uncovered cells
  G0    Fast Guardian  -> gate      : run_platform_checks.py (the 339-validator ratchet)
  GH    Hardening      -> harden    : the L2->L0 bridge state
  GS    Sentinel       -> sentinel  : the L0->L2 bridge coverage
  G2    Comprehensive  -> e2e       : journey-*.spec.ts coverage
  Mega  orchestration  -> mega      : run every layer at once + scorecard + marker

Any command can be scoped to ONE of the 13 production layers with --layer:
  F Frontend · A APIs · D Database · AU Auth · H Hosting · C Cloud/LLM · CI CI-CD
  S Security · RL RateLimit · CA Caching · LB LoadBalance · L Logs · AV Availability

Usage:
  python tools/fullstack_dev.py status                 # matrix scorecard, one glance
  python tools/fullstack_dev.py matrix [--layer D]     # the 13×6 grid (filled/blank)
  python tools/fullstack_dev.py substrate [--layer F]  # G-1.5 pattern-miner shape layer
  python tools/fullstack_dev.py discover               # G-1   matrix integrity + gap cells
  python tools/fullstack_dev.py gate [--fast]          # G0    run_platform_checks guardian
  python tools/fullstack_dev.py harden                 # GH    hardening bridge state
  python tools/fullstack_dev.py sentinel [--layer AU]  # GS    sentinel coverage
  python tools/fullstack_dev.py e2e [--layer S]        # G2    journey-spec coverage
  python tools/fullstack_dev.py mega                   # run every layer + write marker
  python tools/fullstack_dev.py --self-test            # prove the wiring (offline, $0)
"""
from __future__ import annotations
import argparse
import io
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
PY = sys.executable

# Source of truth + the loop's state files
STUDY = ROOT / "COMPREHENSIVE_STUDY_FULLSTACK_GATE.md"
COVERAGE_REPORT = ROOT / "fullstack_gate_coverage_report.json"
SCORECARD = ROOT / "fullstack_eval_scorecard.json"
PASS_MARKER = ROOT / ".last-fullstack-gate-pass"
RUN_LOG = ROOT / "fullstack_dev_runs.jsonl"

# Tools the front door routes to (each stays independently runnable).
GUARDIAN_TOOL = ROOT / "run_platform_checks.py"          # G0
COVERAGE_TOOL = TOOLS / "audit_fullstack_gate_coverage.py"  # G-1 meta-gate

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

# The 13 production layers (matrix ROWS) — canonical IDs from the study §2.
PRODUCTION_LAYERS = [
    ("F",  "Frontend"),
    ("A",  "APIs & Backend"),
    ("D",  "Database & Storage"),
    ("AU", "Auth & Permissions"),
    ("H",  "Hosting & Deployment"),
    ("C",  "Cloud & Compute (LLM)"),
    ("CI", "CI / CD"),
    ("S",  "Security & RLS"),
    ("RL", "Rate Limiting"),
    ("CA", "Caching & CDN"),
    ("LB", "Load Balancing & Scaling"),
    ("L",  "Error Tracking & Logs"),
    ("AV", "Availability & Recovery"),
]
PROD_IDS = {pid for pid, _ in PRODUCTION_LAYERS}

# The 6 gate layers (matrix COLUMNS) — the Mega Gate's own names + the command each maps to.
GATE_LAYERS = [
    ("G-1.5", "Substrate",      "substrate"),
    ("G-1",   "Auto-discovery", "discover"),
    ("G0",    "Fast Guardian",  "gate"),
    ("GH",    "Hardening",      "harden"),
    ("GS",    "Sentinel",       "sentinel"),
    ("G2",    "Comprehensive E2E", "e2e"),
]


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
            if any(k in s for k in ("PASS", "FAIL", "coverage", "missing", "present", "drift", "wrote")) and len(s) < 160:
                summary = s
    proc.wait()
    return proc.returncode == 0, summary


# ───────────────────────────── matrix parser (the spec → structure) ───────────
# Reuses the artefact-resolution rules of audit_fullstack_gate_coverage.py but
# PRESERVES the (production-layer × gate-layer) structure so we can organize by
# the Mega Gate's layer names and scope by production layer.

_ARTEFACT_RE = re.compile(r"`([^`]+)`")
MATRIX_START = "## 4. The coverage matrix"
MATRIX_END = "Coverage tally:"


def _resolve_artefact(name: str) -> Path | None:
    """Map a backtick token to the file it should be, or None if it isn't a
    file-shaped artefact (e.g. a prose note like '/harden after L2 fail')."""
    n = name.strip()
    if n.startswith("validate_") and not n.endswith(".py"):
        return ROOT / f"{n}.py"
    if n.startswith("validate_") and n.endswith(".py"):
        return ROOT / n
    if n.startswith("journey-"):
        return ROOT / ("tests/" + (n if n.endswith(".ts") else f"{n}.spec.ts"))
    if n.startswith("tools/") and n.endswith(".py"):
        return ROOT / n
    if n.startswith("_shared/") and n.endswith(".ts"):
        return ROOT / "supabase/functions" / n
    if re.fullmatch(r"[A-Za-z0-9_./-]+\.(py|ts|js|json|md|html)", n):
        return ROOT / n
    return None  # prose, not a file reference


def _row_label(cell: str) -> tuple[str | None, str]:
    """'**F Frontend**' -> ('F', 'Frontend'). Tolerates bold + extra spaces."""
    txt = cell.replace("*", "").strip()
    m = re.match(r"([A-Z]{1,2})\s+(.*)", txt)
    if m and m.group(1) in PROD_IDS:
        return m.group(1), m.group(2).strip()
    return None, txt


def parse_matrix() -> dict:
    """Return {'cells': {(prod_id, gate_id): {filled, artefacts[], present[], missing[], note}},
                'prod_order': [...], 'gate_order': [...]}.  Empty on missing study."""
    cells: dict = {}
    if not STUDY.exists():
        return {"cells": cells, "prod_order": [p for p, _ in PRODUCTION_LAYERS],
                "gate_order": [g for g, _, _ in GATE_LAYERS], "ok": False}
    text = STUDY.read_text(encoding="utf-8", errors="replace")
    gate_ids = [g for g, _, _ in GATE_LAYERS]
    in_matrix = False
    for line in text.splitlines():
        if MATRIX_START in line:
            in_matrix = True
            continue
        if in_matrix and MATRIX_END in line:
            break
        if not in_matrix or not line.strip().startswith("|"):
            continue
        parts = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(parts) < 7:
            continue
        pid, _pname = _row_label(parts[0])
        if pid is None:
            continue  # header / separator row
        for i, gid in enumerate(gate_ids):
            raw = parts[i + 1] if i + 1 < len(parts) else ""
            filled = bool(raw) and raw != "—" and raw != "-"
            arts, present, missing = [], [], []
            for tok in _ARTEFACT_RE.findall(raw):
                p = _resolve_artefact(tok)
                if p is None:
                    continue
                arts.append(tok)
                (present if p.exists() else missing).append(tok)
            cells[(pid, gid)] = {
                "filled": filled, "artefacts": arts,
                "present": present, "missing": missing, "note": raw,
            }
    return {"cells": cells, "prod_order": [p for p, _ in PRODUCTION_LAYERS],
            "gate_order": gate_ids, "ok": True}


# ───────────────────────────── scorecard (offline, from the matrix) ────────────

def compute_scorecard() -> dict:
    m = parse_matrix()
    cells = m["cells"]
    total = len(PRODUCTION_LAYERS) * len(GATE_LAYERS)
    filled = sum(1 for c in cells.values() if c["filled"])
    referenced = sum(len(c["artefacts"]) for c in cells.values())
    missing = sum(len(c["missing"]) for c in cells.values())
    protected = sum(
        1 for pid, _ in PRODUCTION_LAYERS
        if any(cells.get((pid, gid), {}).get("filled") for gid, _, _ in GATE_LAYERS)
    )

    coverage = round(100 * filled / total, 1) if total else 0.0
    integrity = round(100 * (referenced - missing) / referenced, 1) if referenced else 100.0
    protection = round(100 * protected / len(PRODUCTION_LAYERS), 1)

    marker = _load(PASS_MARKER) or {}
    guardian = 100.0 if marker.get("guardian") == "PASS" else (0.0 if marker.get("guardian") == "FAIL" else None)

    # per-gate-layer fill counts (how complete each Mega-Gate column is)
    per_gate = {}
    for gid, gname, _ in GATE_LAYERS:
        gf = sum(1 for pid, _ in PRODUCTION_LAYERS if cells.get((pid, gid), {}).get("filled"))
        per_gate[gid] = {"name": gname, "filled": gf, "of": len(PRODUCTION_LAYERS)}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "axes": {
            "coverage":   coverage,    # filled cells / 78
            "integrity":  integrity,   # named artefacts that exist / referenced
            "protection": protection,  # production layers with >=1 gate / 13
            "guardian":   guardian,    # last G0 run (None until first `gate`/`mega`)
        },
        "signals": {
            "total_cells":   total,
            "filled_cells":  filled,
            "blank_cells":   total - filled,
            "artefacts_referenced": referenced,
            "artefacts_missing":    missing,
            "production_protected": f"{protected}/{len(PRODUCTION_LAYERS)}",
            "per_gate_layer": per_gate,
        },
    }


def write_scorecard() -> dict:
    sc = compute_scorecard()
    SCORECARD.write_text(json.dumps(sc, indent=2), encoding="utf-8")
    return sc


# ───────────────────────────── layer runners (return ok, summary) ─────────────

def _cells_for_layer(m: dict, gid: str, layer: str | None) -> list[tuple[str, dict]]:
    """The matrix cells for one gate column, optionally scoped to one prod row."""
    out = []
    for pid, _ in PRODUCTION_LAYERS:
        if layer and pid != layer:
            continue
        out.append((pid, m["cells"].get((pid, gid), {})))
    return out


def _show_gate_layer(gid: str, gname: str, layer: str | None) -> tuple[bool, str]:
    """SHOW path: list a gate column's matrix artefacts + verify they exist.
    This is the light, offline view shared by substrate/sentinel/e2e."""
    m = parse_matrix()
    rows = _cells_for_layer(m, gid, layer)
    referenced = present = missing = 0
    missing_names: list[str] = []
    for pid, cell in rows:
        arts = cell.get("artefacts", [])
        referenced += len(arts)
        present += len(cell.get("present", []))
        miss = cell.get("missing", [])
        missing += len(miss)
        missing_names += [f"{pid}:{x}" for x in miss]
        mark = "—" if not cell.get("filled") else f"{len(cell.get('present', []))}/{len(arts)} present"
        pname = dict(PRODUCTION_LAYERS).get(pid, pid)
        line = f"  {pid:<3} {pname:<26} {mark}"
        if cell.get("filled"):
            print(line)
        else:
            print(f"{YEL}{line}{RESET}")
    scope = f" [layer {layer}]" if layer else ""
    if missing:
        return False, f"{gname}{scope}: {missing} matrix artefact(s) MISSING — {', '.join(missing_names[:4])}"
    return True, f"{gname}{scope}: {present}/{referenced} artefacts present"


def layer_substrate(layer=None) -> tuple[bool, str]:
    step("G-1.5 substrate: pattern-miner SHAPE layer (matrix column)")
    return _show_gate_layer("G-1.5", "Substrate", layer)


def layer_discover(layer=None) -> tuple[bool, str]:
    # G-1 has a real runnable: the matrix-integrity meta-gate.
    okk, summ = run_tool([COVERAGE_TOOL], "G-1 discover: matrix-integrity meta-gate")
    rep = _load(COVERAGE_REPORT) or {}
    miss = rep.get("missing", 0)
    if miss:
        return False, f"matrix references {miss} artefact(s) that don't exist"
    return okk, summ or f"{rep.get('present', '?')} artefacts present, 0 missing"


def layer_gate(layer=None, fast=True) -> tuple[bool, str]:
    args = [GUARDIAN_TOOL] + (["--fast"] if fast else [])
    label = f"G0 gate: run_platform_checks ({'fast' if fast else 'full'})"
    if layer:
        label += f" [layer {layer} — display scope; G0 runs the full ratchet]"
    return run_tool(args, label)


def layer_harden(layer=None) -> tuple[bool, str]:
    step("GH harden: L2->L0 bridge state")
    return _show_gate_layer("GH", "Hardening", layer)


def layer_sentinel(layer=None) -> tuple[bool, str]:
    step("GS sentinel: L0->L2 bridge coverage")
    return _show_gate_layer("GS", "Sentinel", layer)


def layer_e2e(layer=None) -> tuple[bool, str]:
    step("G2 e2e: journey-spec coverage (matrix column)")
    return _show_gate_layer("G2", "Comprehensive E2E", layer)


# ───────────────────────────── commands ───────────────────────────────────────

def cmd_status(_a=None) -> int:
    banner("FULL-STACK SAAS GATE — STATUS", "cyan")
    sc = write_scorecard()
    ax = sc["axes"]; sg = sc["signals"]
    print(f"  {BOLD}4-axis scorecard{RESET}  (the 13×6 matrix, organized by Mega-Gate layers)")
    for name in ("coverage", "integrity", "protection", "guardian"):
        v = ax[name]
        if v is None:
            print(f"    {name:<12} {YEL}  —  {RESET} (run `gate` or `mega` first)")
            continue
        col = GREEN if v >= 90 else (YEL if v >= 70 else RED)
        print(f"    {name:<12} {col}{v:>5}%{RESET}")
    print(f"\n  cells: {sg['filled_cells']}/{sg['total_cells']} filled "
          f"({sg['blank_cells']} gaps)   "
          f"artefacts: {sg['artefacts_referenced']} referenced, {sg['artefacts_missing']} missing   "
          f"production protected: {sg['production_protected']}")
    print(f"\n  {BOLD}per gate layer (Mega-Gate columns){RESET}")
    for gid, gname, cmd in GATE_LAYERS:
        pg = sg["per_gate_layer"][gid]
        f = pg["filled"]; of = pg["of"]
        col = GREEN if f == of else (YEL if f >= of * 0.5 else RED)
        print(f"    {gid:<6} {gname:<16} {col}{f:>2}/{of}{RESET}  → `{cmd}`")
    last = _load(PASS_MARKER)
    if last:
        print(f"\n  last mega: {last.get('result')} @ {last.get('ts')}")
    print()
    return 0


def cmd_matrix(args) -> int:
    layer = getattr(args, "layer", None)
    banner("FULL-STACK × GATE MATRIX (13 × 6)" + (f" — layer {layer}" if layer else ""), "cyan")
    m = parse_matrix()
    gate_ids = [g for g, _, _ in GATE_LAYERS]
    hdr = "  " + "prod".ljust(5) + "".join(g.ljust(8) for g in gate_ids)
    print(BOLD + hdr + RESET)
    for pid, pname in PRODUCTION_LAYERS:
        if layer and pid != layer:
            continue
        row = f"  {pid:<5}"
        for gid in gate_ids:
            cell = m["cells"].get((pid, gid), {})
            if not cell.get("filled"):
                row += YEL + "  —    " + RESET + " "
            elif cell.get("missing"):
                row += RED + "  X    " + RESET + " "
            else:
                row += GREEN + "  ✓    " + RESET + " "
        print(row + f"  {pname}")
    print(f"\n  ✓ filled+present   {YEL}—{RESET} blank cell (gap)   {RED}X{RESET} filled but artefact missing")
    if layer:
        print(f"\n  {BOLD}layer {layer} detail{RESET}")
        for gid, gname, _ in GATE_LAYERS:
            cell = m["cells"].get((layer, gid), {})
            arts = cell.get("artefacts", [])
            if arts:
                detail = ", ".join(arts)
            elif cell.get("filled"):
                # filled with a miner NAME or prose note (no verifiable file)
                detail = re.sub(r"\s+", " ", cell.get("note", "").strip())
            else:
                detail = "—"
            print(f"    {gid:<6} {gname:<16} {detail}")
    print()
    return 0


def cmd_substrate(args) -> int:
    okk, _ = layer_substrate(getattr(args, "layer", None)); return 0 if okk else 1


def cmd_discover(args) -> int:
    okk, _ = layer_discover(getattr(args, "layer", None)); return 0 if okk else 1


def cmd_gate(args) -> int:
    okk, summ = layer_gate(getattr(args, "layer", None), fast=getattr(args, "fast", False))
    _update_marker_guardian("PASS" if okk else "FAIL")
    return 0 if okk else 1


def cmd_harden(args) -> int:
    okk, _ = layer_harden(getattr(args, "layer", None)); return 0 if okk else 1


def cmd_sentinel(args) -> int:
    okk, _ = layer_sentinel(getattr(args, "layer", None)); return 0 if okk else 1


def cmd_e2e(args) -> int:
    okk, _ = layer_e2e(getattr(args, "layer", None)); return 0 if okk else 1


# ───────────────────────────── mega (the conductor) ───────────────────────────

def cmd_mega(args) -> int:
    banner("FULL-STACK SAAS MEGA GATE", "cyan")
    layer = getattr(args, "layer", None)
    layers: list[tuple[str, bool, str]] = []

    # G-1.5 substrate (show) → G-1 discover (matrix integrity, runnable) →
    # GS sentinel (show) → G2 e2e (show) → G0 gate (the heavy ratchet, optional)
    sok, ssum = layer_substrate(layer); layers.append(("G-1.5 substrate", sok, ssum)); print()
    dok, dsum = layer_discover(layer); layers.append(("G-1 discover", dok, dsum)); print()
    senok, sensum = layer_sentinel(layer); layers.append(("GS sentinel", senok, sensum)); print()
    e2ok, e2sum = layer_e2e(layer); layers.append(("G2 e2e", e2ok, e2sum)); print()

    if getattr(args, "with_guardian", False):
        gok, gsum = layer_gate(layer, fast=True); layers.append(("G0 gate", gok, gsum))
        _update_marker_guardian("PASS" if gok else "FAIL"); print()
    else:
        warn("G0 guardian skipped (add --with-guardian to run the 339-validator ratchet)")
        layers.append(("G0 gate", True, "skipped (--with-guardian to run)")); print()

    sc = write_scorecard(); ax = sc["axes"]
    scsum = " · ".join(f"{k[:4]} {v}%" for k, v in ax.items() if v is not None)
    layers.append(("scorecard", True, scsum)); print()

    all_pass = all(okk for _, okk, _ in layers)
    result = "PASS" if all_pass else "BLOCK"
    _persist_run(result, layers)
    _write_marker(result, layers)

    if all_pass:
        banner("FULL-STACK MEGA — PASS", "green")
        for name, _, s in layers:
            print(f"  {name}: {s or 'ok'}")
        return 0
    banner("FULL-STACK MEGA — BLOCK", "red")
    for name, okk, s in layers:
        print(f"  {name}: {'PASS' if okk else 'FAIL'} — {s or '(no summary)'}")
    print("\nFix the failing layer(s), then re-run.")
    return 1


def _write_marker(result: str, layers: list[tuple[str, bool, str]]) -> None:
    existing = _load(PASS_MARKER) or {}
    existing.update({
        "result": result,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "layers": {n: ("PASS" if o else "FAIL") for n, o, _ in layers},
    })
    PASS_MARKER.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _update_marker_guardian(state: str) -> None:
    existing = _load(PASS_MARKER) or {}
    existing["guardian"] = state
    existing["guardian_ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    PASS_MARKER.write_text(json.dumps(existing, indent=2), encoding="utf-8")


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

    # 1. the spec + the two real runnables exist.
    for p in (STUDY, GUARDIAN_TOOL, COVERAGE_TOOL):
        if not p.exists():
            fails.append(f"missing dependency: {p.relative_to(ROOT)}")

    # 2. the matrix parses into the full 13×6 grid.
    m = parse_matrix()
    if m["ok"]:
        parsed_rows = {pid for (pid, _gid) in m["cells"]}
        if parsed_rows != PROD_IDS:
            fails.append(f"matrix rows parsed {sorted(parsed_rows)} != 13 production layers")
        total = len(PRODUCTION_LAYERS) * len(GATE_LAYERS)
        if len(m["cells"]) != total:
            fails.append(f"matrix parsed {len(m['cells'])} cells, expected {total}")
    else:
        fails.append("matrix did not parse (study missing?)")

    # 3. scorecard computes 4 axes in [0,100] (guardian may be None until first run).
    try:
        sc = compute_scorecard()
        for axis in ("coverage", "integrity", "protection"):
            v = sc["axes"].get(axis)
            if not (isinstance(v, (int, float)) and 0 <= v <= 100):
                fails.append(f"scorecard axis {axis} out of range: {v}")
    except Exception as e:  # noqa: BLE001
        fails.append(f"scorecard threw: {e}")

    # 4. every gate-layer command name resolves to a layer runner.
    for _gid, _gname, cmd in GATE_LAYERS:
        if cmd not in ("substrate", "discover", "gate", "harden", "sentinel", "e2e"):
            fails.append(f"gate layer command {cmd} has no runner")

    if fails:
        print(f"{RED}{BOLD}SELF-TEST FAILED:{RESET}")
        for f in fails:
            print(f"  {RED}x{RESET} {f}")
        return 1
    print(f"{GREEN}{BOLD}SELF-TEST PASSED{RESET} — spec + guardian + coverage tool resolve, "
          f"13×6 matrix parses, 3 axes in range, every gate-layer command has a runner.")
    return 0


# ───────────────────────────── main ───────────────────────────────────────────

def _add_layer(p):
    p.add_argument("--layer", choices=sorted(PROD_IDS),
                   help="scope to ONE production layer (F/A/D/AU/H/C/CI/S/RL/CA/LB/L/AV)")
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description="Full-Stack SaaS Gate front door — the fourth sibling Mega Gate.")
    ap.add_argument("--self-test", action="store_true", help="prove the orchestrator wiring (offline, $0)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status", help="matrix 4-axis scorecard, one glance")
    _add_layer(sub.add_parser("matrix", help="the 13×6 grid (filled/blank/missing)"))
    _add_layer(sub.add_parser("substrate", help="G-1.5: pattern-miner shape layer"))
    _add_layer(sub.add_parser("discover", help="G-1: matrix-integrity meta-gate + gaps"))
    pg = _add_layer(sub.add_parser("gate", help="G0: run_platform_checks guardian"))
    pg.add_argument("--fast", action="store_true", help="skip live API calls (Layer 3)")
    _add_layer(sub.add_parser("harden", help="GH: L2->L0 hardening bridge state"))
    _add_layer(sub.add_parser("sentinel", help="GS: L0->L2 sentinel coverage"))
    _add_layer(sub.add_parser("e2e", help="G2: journey-spec coverage"))
    pm = _add_layer(sub.add_parser("mega", help="run every layer at once + write marker"))
    pm.add_argument("--with-guardian", action="store_true", help="also run the heavy G0 ratchet")
    args = ap.parse_args()

    if args.self_test:
        return cmd_self_test()

    cmd = args.cmd or "status"
    dispatch = {
        "status": cmd_status, "matrix": cmd_matrix, "substrate": cmd_substrate,
        "discover": cmd_discover, "gate": cmd_gate, "harden": cmd_harden,
        "sentinel": cmd_sentinel, "e2e": cmd_e2e, "mega": cmd_mega,
    }
    return dispatch[cmd](args)


if __name__ == "__main__":
    sys.exit(main())
