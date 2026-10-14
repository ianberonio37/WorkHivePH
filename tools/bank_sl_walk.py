#!/usr/bin/env python3
"""bank_sl_walk.py - bank SL (sub-layer) rows (§SL, 2026-10-14) from the evidence their instrument produces.

Two modes, one per instrument a row declares (`sl.instrument`):

  --prover <results.json>   CONTRACT rows (instrument "library sweep ..."): a registered batch prover over every page.
                            A row banks only when the prover's readings for ITS page are clean in EVERY engine it ran
                            (the sub-layers this file knows how to read from tools/prove_page_survives_optional_failures
                            .mjs: H1 needs the as-served reading clean in Chromium AND WebKit), and the named gates PASS.
  --walk <SL id> --steps f  WALK rows: a chrome-devtools MCP walk as the page's cast, recorded through
                            tools/record_mcp_walk.py (which refuses a receipt without the sub-layer, the persona and
                            steps at both viewports). An engine-sensitive row (sl.engine webkit) also needs --webkit
                            <results.json> holding clean WebKit readings for the page: no MCP drives WebKit, so the
                            Playwright WebKit run is that half, named in the receipt's witness and checked here.

The registry is written only when everything holds; a row is never moved on a partial reading. Writes indent=2, the
format the seeders and HEAD use (one writer flipping the whole 56 MB file to indent=1 is how a 4,399-row seed nearly
committed a 1.7M-line diff, 2026-10-14).

  python tools/bank_sl_walk.py --prover .tmp/sl_walk1_results.json --sublayer H1
  python tools/bank_sl_walk.py --walk SL916 --steps .tmp/w4_steps/SL916.json --witness "..." [--webkit .tmp/sl_walk1_results.json]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROVER = "tools/prove_page_survives_optional_failures.mjs"
# the gates that hold each sub-layer this banker settles (all registered in run_platform_checks.py)
GATES = {
    "H1": ["page-survives-optional-failures", "csp-covers-what-ships", "deploy-headers-local"],
    "A3": ["page-survives-optional-failures", "realtime-blocked-socket"],
    "AV1": ["page-survives-optional-failures", "realtime-blocked-socket"],
}
# which prover readings settle a contract sub-layer: (condition, engines that must ALL be clean)
PROVER_READS = {"H1": ("as-served", ("chromium", "webkit"))}


def _load_registry() -> dict:
    return json.load(io.open("trajectory_registry.json", encoding="utf-8"))


def _write_registry(reg: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(ROOT), suffix=".tmp")
    with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, "trajectory_registry.json")


def _run_gate(script: str, *args: str) -> tuple[bool, str]:
    exe = ["node", script] if script.endswith(".mjs") else [sys.executable, script]
    r = subprocess.run(exe + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    last = next((ln for ln in reversed(out.strip().splitlines()) if "PASS" in ln or "FAIL" in ln), out.strip()[-160:])
    return r.returncode == 0, last.strip()[:200]


def _readings(results: dict, page: str, condition: str, engine: str) -> list[dict]:
    return [r for r in results.get("results", []) if r.get("page") == page and r.get("condition") == condition
            and r.get("engine") == engine]


def _bank(reg: dict, rid: str, basis: str, gates: list[str]) -> None:
    t = next(x for x in reg["trajectories"] if x["id"] == rid)
    locked = t.get("status") == "locked"
    st, pct = ("locked", 100) if locked else ("locking", 60)
    old = t.get("basis") or ""
    t["status"], t["pct"] = st, pct
    t["basis"] = basis.replace("{pct}", str(pct)) + (" || " + old if old else "")
    arts = t.setdefault("artifacts", {})
    arts["gates"] = sorted(set(arts.get("gates") or []) | set(gates))


def _closed(rids: list[str]) -> dict:
    import live_walk_manifest as lm
    bm = lm.build()
    rows = {x["id"]: x for x in (bm["rows"] if isinstance(bm, dict) else bm)}
    return {rid: lm.row_closed(rows[rid]) for rid in rids if rid in rows}


def bank_prover(results_path: str, sublayer: str, gates_only: bool) -> int:
    if sublayer not in PROVER_READS:
        print(f"no prover reading is defined for {sublayer} - nothing banked")
        return 1
    results = json.load(io.open(results_path, encoding="utf-8"))
    condition, engines = PROVER_READS[sublayer]
    gate_lines = []
    for g in GATES[sublayer]:
        script = {"page-survives-optional-failures": None,   # its run IS the results file being banked
                  "csp-covers-what-ships": "tools/validate_csp_covers_what_ships.py",
                  "deploy-headers-local": "tools/prove_deploy_headers.py",
                  "realtime-blocked-socket": "tools/prove_realtime_blocked_socket.mjs"}.get(g)
        if not script:
            continue
        ok, line = _run_gate(script)
        gate_lines.append(f"{g} {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"gate {g} is not green ({line}) - nothing banked")
            return 1
    if not (results.get("teeth") or {}).get("bit"):
        print("the prover's teeth did not bite on this run - nothing banked")
        return 1
    reg = _load_registry()
    today = time.strftime("%Y-%m-%d")
    banked, skipped = [], []
    for t in reg["trajectories"]:
        s = t.get("sl") or {}
        if s.get("sublayer") != sublayer or t.get("status") in ("locking", "locked", "descoped"):
            continue
        page = s.get("page")
        per = {e: _readings(results, page, condition, e) for e in engines}
        if not all(per.values()):
            continue                                 # the prover never read this page in every engine
        bad = [f"{e}: {'; '.join(r['problems'])}" for e, rs in per.items() for r in rs if not r.get("ok")]
        if bad:
            skipped.append(f"{t['id']} {page}: " + " | ".join(bad)[:200])
            continue
        chars = " and ".join(f"{rs[0].get('chars')} chars in {e.capitalize()}" for e, rs in per.items())
        basis = (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {PROVER} (gate page-survives-optional-failures; real "
                 f"Chromium AND WebKit, signed in as {t.get('persona')} through the product's own sign-in form, every "
                 f"document served the SHIPPED vercel.json CSP and Permissions-Policy with only the production Supabase "
                 f"origins mapped to the local stack): {sublayer} on {page} as-served {chars}, 0 CSP violations, 0 "
                 f"uncaught client_errors inserts, 0 pageerrors, no busy indicator left. What the page DOES on an action "
                 f"(a blob: image, a played audio) is held by csp-covers-what-ships, extended 2026-10-14 (c1192af4) after "
                 f"this walk found img-src without blob: and no media-src. Gates: {', '.join(gate_lines)}. Receipt "
                 f"{results_path} (generated {results.get('generated')}).")
        if not gates_only:
            _bank(reg, t["id"], basis, GATES[sublayer])
        banked.append(t["id"])
    if not banked:
        print(f"nothing to bank for {sublayer}" + (f" - held: {skipped}" if skipped else ""))
        return 1 if skipped else 0
    if not gates_only:
        _write_registry(reg)
    closed = _closed(banked) if not gates_only else {}
    print(f"{sublayer}: banked {len(banked)} row(s) {banked}" + (f"; held {len(skipped)}: {skipped}" if skipped else ""))
    if closed:
        print(f"  CLOSED: {sum(closed.values())}/{len(closed)}" + ("" if all(closed.values()) else f" - open: {[k for k, v in closed.items() if not v]}"))
    return 0


def bank_walk(rid: str, steps: str, witness: str, note: str, webkit: str | None, unproven: str,
              check: bool = True) -> int:
    reg = _load_registry()
    t = next((x for x in reg["trajectories"] if x["id"] == rid), None)
    if not t or not t.get("sl"):
        print(f"{rid}: not an SL row")
        return 1
    s = t["sl"]
    if str(s.get("instrument", "")).startswith("library"):
        print(f"{rid}: a contract row closes on its prover (--prover), not on a walk")
        return 1
    engine = "chromium"
    if s.get("engine") == "webkit":
        if not webkit:
            print(f"{rid}: an engine-sensitive row needs --webkit <the WebKit run's results> - nothing banked")
            return 1
        res = json.load(io.open(webkit, encoding="utf-8"))
        wk = [r for r in res.get("results", []) if r.get("page") == s.get("page") and r.get("engine") == "webkit"]
        if not wk or not all(r.get("ok") for r in wk):
            print(f"{rid}: the WebKit run holds no clean reading for {s.get('page')} - nothing banked")
            return 1
        engine = "webkit"
        witness = (f"WebKit half: {PROVER} ({webkit}, {res.get('generated')}): {s.get('page')} "
                   + "; ".join(f"{r['condition']} {r.get('chars')} chars, clean" for r in wk) + f". {witness}")
    cmd = [sys.executable, "tools/record_mcp_walk.py", "--id", rid, "--instrument", "chrome-devtools-mcp",
           "--layer", s["layer"], "--sublayer", s["sublayer"], "--as-persona", t.get("persona") or "",
           "--viewports", "phone-390,desktop-1280", "--engine", engine, "--steps", steps,
           "--witness", witness[:1900], "--note", note[:1500]]
    if unproven:
        cmd += ["--unproven", unproven[:400]]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    print(" ", out.splitlines()[-1][:220] if out else "(recorder said nothing)")
    if r.returncode != 0 or "refused" in out.lower() or "ok=True" not in out or unproven:
        print(f"{rid}: NOT banked")
        return 1
    today = time.strftime("%Y-%m-%d")
    basis = (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via chrome-devtools-mcp (a TRUE 390 and 1280 through CDP, "
             f"signed in as {t.get('persona')} through the product's own sign-in form; the condition induced by the MCP's "
             f"initScript before any page script): {note} Witness: {witness[:1200]} Receipt .tmp/mcp_walks/{rid}.json.")
    reg = _load_registry()
    _bank(reg, rid, basis, GATES.get(s["sublayer"], ["page-survives-optional-failures"]))
    _write_registry(reg)
    if not check:                       # a batch checks closure ONCE at its end (--check-closed): the ledger build is
        print(f"{rid}: banked")         # ~90 s, and per row it turned a 20-row bank into a 30-minute run (2026-10-14)
        return 0
    closed = _closed([rid])
    print(f"{rid}: CLOSED={closed.get(rid)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prover", help="a prove_page_survives_optional_failures.mjs results file")
    ap.add_argument("--sublayer", help="with --prover: the contract sub-layer to bank (H1)")
    ap.add_argument("--dry-run", action="store_true", help="with --prover: check gates and readings, write nothing")
    ap.add_argument("--walk", help="the SL id of a walk row")
    ap.add_argument("--steps")
    ap.add_argument("--witness", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--webkit", help="the WebKit run's results file, for an engine-sensitive row")
    ap.add_argument("--unproven", default="")
    ap.add_argument("--no-check", action="store_true", help="with --walk: skip the per-row ledger rebuild")
    ap.add_argument("--check-closed", nargs="+", help="report CLOSED for these ids (one ledger build)")
    a = ap.parse_args()
    if a.check_closed:
        c = _closed(a.check_closed)
        print(f"CLOSED {sum(c.values())}/{len(c)}" + ("" if all(c.values()) else f" - open: {[k for k, v in c.items() if not v]}"))
        return 0 if all(c.values()) else 1
    if a.prover:
        return bank_prover(a.prover, a.sublayer or "", a.dry_run)
    if a.walk:
        return bank_walk(a.walk, a.steps, a.witness, a.note, a.webkit, a.unproven, check=not a.no_check)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
