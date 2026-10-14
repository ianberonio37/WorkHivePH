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
    "L1": ["error-capture-everywhere", "production-errors-read", "error-capture"],
    "AU2": ["role-reconciled", "role-checks", "storage-keys"],
    "AU3": ["ownership-by-account", "bug-repro-ratchet"],
}
# how the walk induced its condition, per sub-layer (the basis states it; walk 1's wording is the default)
CONDITION = {
    "AU2": ("the device role written into the page's own storage before the page loaded - the honest role and a false "
            "one, the same signed-in person with the server's hive_members.role set on the LOCAL database"),
    "AU3": ("the device's remembered display name (wh_last_worker) written into the page's own storage before it loaded - "
            "the person's own, then another real member's (another hive-less owner's for the solo cast); every text line "
            "and control compared with the two names masked APART (<ME> / <OTHER>), so a swap of who is who shows"),
}
CONDITION_DEFAULT = "the condition induced by the MCP's initScript before any page script"
# a bug-hunt class is walked by the sub-layer that meets its defect (its gates and wording follow that sub-layer)
BRH_CLASS_SUBLAYER = {"F": "AU2"}
# which prover settles a contract sub-layer, and which of its readings: (condition or None, engines that must ALL be clean)
PROVER_READS = {
    "H1": {"prover": PROVER, "gate": "page-survives-optional-failures", "condition": "as-served",
           "engines": ("chromium", "webkit")},
    "L1": {"prover": "tools/prove_error_capture_everywhere.mjs", "gate": "error-capture-everywhere", "condition": None,
           "engines": ("chromium", "webkit")},
}
GATE_SCRIPTS = {"csp-covers-what-ships": "tools/validate_csp_covers_what_ships.py",
                "deploy-headers-local": "tools/prove_deploy_headers.py",
                "realtime-blocked-socket": "tools/prove_realtime_blocked_socket.mjs",
                "production-errors-read": "tools/validate_production_error_groups.py",
                "error-capture": "tools/validate_error_capture.py"}


def _basis(sublayer: str, t: dict, page: str, per: dict, gate_lines: list, results_path: str, results: dict,
           today: str) -> str:
    spec = PROVER_READS[sublayer]
    head = f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {spec['prover']} (gate {spec['gate']}; real Chromium AND WebKit"
    tail = f" Gates: {', '.join(gate_lines)}. Receipt {results_path} (generated {results.get('generated')})."
    if sublayer == "L1":
        who = "anonymous" if t.get("persona") == "anon" else f"signed in as {t.get('persona')} through the product's own form"
        person = next((r.get("person") for rs in per.values() for r in rs if r.get("person")), None)
        real = ", ".join(f"{x['engine']} {x['rows_in_table']}" for x in results.get("real") or [])
        return (head + f", {who}): L1 on {page} - an uncaught error AND an unhandled rejection thrown after start-up were "
                f"each captured in both engines with the page's own pathname and the engine in the user agent"
                + (f", and the person ({person})" if person else ", with no identity (an anonymous row, as the policy requires)")
                + f". The anonymous path is proven by a REAL write per engine through migration 20261014000002's policy "
                f"({real} row(s), read back and removed); teeth: the pre-change shared scripts capture nothing. Read half: "
                f"production-errors-read answers every group in production_error_groups.json." + tail)
    chars = " and ".join(f"{rs[0].get('chars')} chars in {e.capitalize()}" for e, rs in per.items())
    return (head + f", signed in as {t.get('persona')} through the product's own sign-in form, every document served the "
            f"SHIPPED vercel.json CSP and Permissions-Policy with only the production Supabase origins mapped to the local "
            f"stack): {sublayer} on {page} as-served {chars}, 0 CSP violations, 0 uncaught client_errors inserts, 0 "
            f"pageerrors, no busy indicator left. What the page DOES on an action (a blob: image, a played audio) is held by "
            f"csp-covers-what-ships, extended 2026-10-14 (c1192af4) after this walk found img-src without blob: and no "
            f"media-src." + tail)


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


def _readings(results: dict, page: str, condition: str | None, engine: str) -> list[dict]:
    return [r for r in results.get("results", []) if r.get("page") == page and r.get("engine") == engine
            and (condition is None or r.get("condition") == condition)]


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
    spec = PROVER_READS[sublayer]
    condition, engines = spec["condition"], spec["engines"]
    gate_lines = []
    for g in GATES[sublayer]:
        script = None if g == spec["gate"] else GATE_SCRIPTS.get(g)   # the prover's own run IS the results file
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
    if sublayer == "L1" and not all(x.get("rows_in_table", 0) >= 2 for x in (results.get("real") or [{}])):
        print("an anonymous error did not land through the policy on this run - nothing banked")
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
        basis = _basis(sublayer, t, page, per, gate_lines, results_path, results, today)
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


def bank_refusal(sublayer: str, dry: bool) -> int:
    """S1 (read scope): every row's page through tools/prove_w4_layer_s.py's recipe - a foreign-hive member on the
    authenticated path, in a rolled-back transaction, must read zero of this hive's rows while the page's own member
    reads its own (the control). The gate w4-layer-entitlement runs the same recipe over every S row, SL S1 included."""
    if sublayer == "S2":
        return _bank_write_refusal(dry)
    if sublayer != "S1":
        print(f"no refusal recipe is defined for {sublayer} - nothing banked")
        return 1
    import prove_w4_layer_s as pw
    ok, line = _run_gate("tools/prove_w4_layer_s.py", "--check")
    if not ok:
        print(f"gate w4-layer-entitlement is not green ({line}) - nothing banked")
        return 1
    reg = _load_registry()
    rows = [t for t in reg["trajectories"] if (t.get("sl") or {}).get("sublayer") == "S1"
            and t.get("status") not in ("locking", "locked", "descoped")]
    pages = sorted({t["sl"]["page"] for t in rows})
    hive_tabs = pw.hive_id_tables(set().union(*(pw.tables_of(p) for p in pages)) if pages else set())
    verdict = {p: pw.check_page(p, hive_tabs) for p in pages}
    today = time.strftime("%Y-%m-%d")
    banked, held = [], []
    for t in rows:
        v, w = verdict[t["sl"]["page"]]
        if v == "BAD":
            held.append(f"{t['id']} {w[:160]}")
            continue
        how = ("refused a foreign hive" if v == "ok" else "nothing to refuse")
        basis = (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via tools/prove_w4_layer_s.py (gate w4-layer-entitlement, "
                 f"invoke + PostgREST as the caller: a member of ANOTHER hive, role authenticated + their JWT claims, in a "
                 f"rolled-back transaction, never the owner connection): S1 on {t['sl']['page']} - {how}. {w} Gate: "
                 f"{line[:160]}")
        if not dry:
            _bank(reg, t["id"], basis, ["w4-layer-entitlement", "rls-strict"])
        banked.append(t["id"])
    if not dry and banked:
        _write_registry(reg)
    print(f"S1: banked {len(banked)} row(s)" + (f"; HELD {len(held)} (a foreign hive read this hive's rows): {held}" if held else ""))
    return 1 if held else 0


def _bank_write_refusal(dry: bool) -> int:
    """S2 (write policies): tools/gen_write_authz_recipes.py --sl - for every table each S2 page WRITES (measured from
    its source), a member of ANOTHER hive on the authenticated path must touch 0 of this hive's rows on UPDATE and DELETE,
    and must not be able to MOVE their own row into a foreign hive (the WITH CHECK half); the page's own member is the
    control. Its recipes land in tools/psql_probes/, which the gate psql-probe-suite re-executes on every board."""
    import re as _re
    r = subprocess.run([sys.executable, "tools/gen_write_authz_recipes.py", "--sl"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    verdict = {}
    for ln in (r.stdout or "").splitlines():
        m = _re.match(r"\s+(PASS|n/a|FAIL)\s+(\S+)\s+(.*)", ln)
        if m:
            verdict[m.group(2)] = (m.group(1), m.group(3))
    ok, line = _run_gate("tools/validate_psql_probe_suite.py")
    if not ok:
        print(f"gate psql-probe-suite is not green ({line}) - nothing banked")
        return 1
    reg = _load_registry()
    today = time.strftime("%Y-%m-%d")
    banked, held = [], []
    for t in reg["trajectories"]:
        sl = t.get("sl") or {}
        if sl.get("sublayer") != "S2" or t.get("status") in ("locking", "locked", "descoped"):
            continue
        page = sl.get("page")
        v, detail = verdict.get(page, ("missing", "the recipe run named no verdict for this page"))
        if v not in ("PASS", "n/a"):
            held.append(f"{t['id']} {page}: {v} {detail[:120]}")
            continue
        recipe = f"tools/psql_probes/{page.replace('.html', '')}__write_authz_depth.sql"
        what = (f"refused a foreign-hive request: on every hive-scoped table {page} writes, a member of ANOTHER hive "
                f"touched 0 of this hive's rows on UPDATE and DELETE and could not move their own row into a foreign hive "
                f"(the WITH CHECK half), the page's own member served as the control - {detail} - recipe {recipe}"
                if v == "PASS" else f"nothing to refuse: {page} {detail}")
        basis = (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via tools/gen_write_authz_recipes.py --sl (invoke + "
                 f"PostgREST as the caller: role authenticated + the member's JWT claims in a rolled-back transaction, never "
                 f"the owner connection): S2 on {page} - {what}. The WITH CHECK half found marketplace_sellers and "
                 f"resume_documents accepting a row moved into a foreign hive; fixed by migration 20261014000003. Gate: "
                 f"psql-probe-suite {line[:80]}")
        if not dry:
            _bank(reg, t["id"], basis, ["psql-probe-suite"])
        banked.append(t["id"])
    if not dry and banked:
        _write_registry(reg)
    print(f"S2: banked {len(banked)} row(s)" + (f"; HELD {len(held)}: {held}" if held else ""))
    return 1 if held else 0


def bank_walk(rid: str, steps: str, witness: str, note: str, webkit: str | None, unproven: str,
              check: bool = True, instrument: str = "chrome-devtools-mcp") -> int:
    reg = _load_registry()
    t = next((x for x in reg["trajectories"] if x["id"] == rid), None)
    # a BRH row (the bug-hunt wave) carries the same receipt contract - a named person at both viewports - and is
    # settled by the same walk as the SL sub-layer that met its defect class (BRH-F <- AU2, 2026-10-14)
    if not t or not (t.get("sl") or t.get("brh")):
        print(f"{rid}: not an SL or BRH row")
        return 1
    s = t.get("sl") or t["brh"]
    key = s.get("sublayer") if t.get("sl") else BRH_CLASS_SUBLAYER.get(s.get("cls"), "")
    if t.get("brh") and not key:
        print(f"{rid}: no walk is defined for bug-hunt class {s.get('cls')} - nothing banked")
        return 1
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
    cmd = [sys.executable, "tools/record_mcp_walk.py", "--id", rid, "--instrument", instrument,
           "--layer", s["layer"], "--as-persona", t.get("persona") or "",
           "--viewports", "phone-390,desktop-1280", "--engine", engine, "--steps", steps,
           "--witness", witness[:1900], "--note", note[:1500]]
    if t.get("sl"):
        cmd += ["--sublayer", s["sublayer"]]
    if unproven:
        cmd += ["--unproven", unproven[:400]]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    print(" ", out.splitlines()[-1][:220] if out else "(recorder said nothing)")
    if r.returncode != 0 or "refused" in out.lower() or "ok=True" not in out or unproven:
        print(f"{rid}: NOT banked")
        return 1
    today = time.strftime("%Y-%m-%d")
    how = CONDITION.get(key, CONDITION_DEFAULT)
    view = ("a TRUE 390 and 1280 through CDP" if instrument.startswith("chrome-devtools")
            else "390x844 and 1280x800 set through Playwright; every edge call carried x-wh-walk-no-model through a context "
                 "route, so no model was called")
    basis = (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {instrument} ({view}, "
             f"signed in as {t.get('persona')} through the product's own sign-in form; {how}): {note} "
             f"Witness: {witness[:1200]} Receipt .tmp/mcp_walks/{rid}.json.")
    reg = _load_registry()
    _bank(reg, rid, basis, GATES.get(key, ["page-survives-optional-failures"]))
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
    ap.add_argument("--refusal", action="store_true", help="with --sublayer S1: bank through the foreign-hive refusal recipe")
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
    if a.refusal:
        return bank_refusal(a.sublayer or "", a.dry_run)
    if a.prover:
        return bank_prover(a.prover, a.sublayer or "", a.dry_run)
    if a.walk:
        return bank_walk(a.walk, a.steps, a.witness, a.note, a.webkit, a.unproven, check=not a.no_check)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
