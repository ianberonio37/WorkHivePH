#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert MARKETPLACE registry rows to gate-backed evidence, on the page-bank rails.

WHY THIS EXISTS. The marketplace bank went from 752 green to 11 in one release: 741 rows expired
because the files they name changed. utils.js alone is cited by 664 of its 877 rows and moved by
+318 lines, so a live re-walk restores evidence that the NEXT shared-file edit expires again. A
gate-backed row does not expire that way -- it is re-earned by RUNNING the gate. Converting the
shapes a registered gate already settles turns a recurring re-walk bill into a one-time move, which
is exactly what the page banks did today (905 rows, 0 refusals).

WHY A SEPARATE TOOL AND NOT A --bank FLAG ON bank_page_walk.py. The schemas differ:
    page bank            scenarios[] keyed by oracle_key + subject.key
    marketplace registry scenarios[] keyed by category + state + surface  (the bank_live_walk shape)
A flag would have to fork the row-matching AND the evidence build, which is two implementations
wearing one name. This reuses the RAILS -- the gate's own classify(), gate_ids(), surface_urls(),
fn_digests() -- and only the matching differs.

IT CANNOT BANK SOMETHING THE GATE WOULD REJECT: every candidate goes through V.classify() before it
is kept, exactly as bank_page_walk does, so a row that would read invalid is refused here rather
than discovered by the gate later.

  python tools/bank_marketplace_gate.py --category <cat> --gate <gate-id> --src <prover> \
      --text <file> [--state <s>] [--surface <s>] [--apply]

--text is the same 3-section format the page conversions use: asserts / checked / value_checked,
separated by a line containing only ---
"""
import argparse
import importlib.util
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"
REGISTRY = os.path.join(ROOT, "live_mcp_registry.json")


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _refuse_incoherent(picked, a):
    """Refuse a selection one piece of evidence cannot honestly cover. Returns an exit code, or 0.

    TWO NEAR-MISSES, BOTH CAUGHT BY HAND, BOTH NOW CAUGHT HERE.

    ONE ORACLE PER CONVERSION. `--category` is a filing label, and the label has drifted from the
    claim. Q-payment-rails reads like the payment-rails gate's subject; its 36 rows actually carry
    the generic matrix oracles ("the surface renders real rows and every visible number matches its
    source of truth", "the empty state names what is missing", "the boundary case still renders").
    Converting on the name would have banked 36 rows citing a gate about which GCash number may
    appear on which screen, as proof of claims it never examines. One `--text` justification cannot
    truthfully describe two different claims, so a selection spanning two oracles is refused and the
    oracles are printed.

    ONE PERSONA, UNLESS THE EVIDENCE REALLY COVERS THEM ALL. The 47 rows carrying "a FAILED read
    renders an error, never the first-run invitation" match tests/failure-injection.spec.ts exactly:
    same oracle, same state, same URLs. They also carry personas anon/buyer/seller/admin/provider,
    while the spec runs as ONE signed-in fixture identity. An `anon` row claims the behaviour for a
    visitor who never signed in; a signed-in run cannot speak for it. That is this platform's own
    "the probe's persona was an ADMIN" defect, which produced seven false leak findings.
    """
    oracles = sorted({(r.get("oracle") or "").strip() for r in picked})
    if len(oracles) > 1:
        print(f"  {RED}REFUSING{RST}: these {len(picked)} row(s) carry {len(oracles)} DIFFERENT "
              f"oracles, and one justification cannot be true of all of them.")
        for o in oracles:
            print(f"      {DIM}- {o[:110]}{RST}")
        print(f"  Narrow with --state/--surface until the selection makes ONE claim, or convert the\n"
              f"  clusters separately. The category name is a filing label, not the claim.")
        return 2

    personas = sorted({r.get("persona") for r in picked if r.get("persona")})
    if len(personas) > 1 and not a.mixed_personas_ok:
        print(f"  {RED}REFUSING{RST}: these {len(picked)} row(s) span {len(personas)} personas "
              f"({', '.join(str(p) for p in personas)}) and evidence is usually gathered as ONE identity.")
        print(f"  An anon row claims the behaviour for someone who never signed in; a signed-in run\n"
              f"  cannot speak for it. Pass --persona <one>, or --mixed-personas-ok if the prover\n"
              f"  genuinely ran as each of them (and say so in --text).")
        return 2
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--src", required=True, help="the prover/gate script the rows will name")
    ap.add_argument("--text", required=True)
    ap.add_argument("--state")
    ap.add_argument("--surface")
    ap.add_argument("--persona", help="restrict to one persona; required when the picked rows span "
                                      "more than one and the evidence was gathered as a single identity")
    ap.add_argument("--mixed-personas-ok", action="store_true",
                    help="the evidence genuinely covers every persona in the picked set (rare; say why in --text)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    V = _gate()
    bank = json.load(io.open(REGISTRY, encoding="utf-8"))
    rows = bank.get("scenarios") or []
    gates, urls = V.gate_ids(), V.surface_urls(bank)

    if a.gate not in gates:
        print(f"  {RED}REFUSING{RST}: gate id {a.gate!r} is not registered in run_platform_checks - "
              f"rail R2 would reject every row citing it")
        return 2

    parts = io.open(a.text, encoding="utf-8").read().split("\n---\n")
    if len(parts) != 3:
        print(f"  {RED}REFUSING{RST}: --text needs exactly 3 sections "
              f"(asserts / checked / value_checked) separated by a line of ---; got {len(parts)}")
        return 2
    asserts, checked, value = (p.strip() for p in parts)

    picked = [r for r in rows
              if r.get("category") == a.category
              and (not a.state or r.get("state") == a.state)
              and (not a.surface or r.get("surface") == a.surface)
              and (not a.persona or r.get("persona") == a.persona)]
    if not picked:
        print(f"  {YEL}no rows{RST} match category={a.category!r} state={a.state!r} "
              f"surface={a.surface!r} persona={a.persona!r}")
        return 0

    rc = _refuse_incoherent(picked, a)
    if rc:
        return rc

    deps = sorted({a.src} | {r["surface"] for r in picked if r.get("surface")})
    banked = refused = 0
    for row in picked:
        ev = {"kind": "gate", "ref": f"gate:{a.gate}", "asserts": asserts, "checked": checked,
              "value_checked": value + " | depends_on: " + ", ".join(deps),
              "depends_on": deps, "sha": V.sha_of(deps) if hasattr(V, "sha_of") else None,
              "replay": f"python run_platform_checks.py --only {a.gate}"}
        candidate = dict(row)
        candidate["status"] = "green"
        candidate["evidence"] = ev
        state, why = V.classify(candidate, gates, urls)
        if state != "green":
            refused += 1
            print(f"  {YEL}REFUSED{RST} {row['id']}\n          {DIM}{why or state}{RST}")
            continue
        ev["fn_digests"] = V.fn_digests(deps)
        row["status"] = "green"
        row["evidence"] = ev
        banked += 1

    print(f"\n  banked {GREEN}{banked}{RST} · refused {refused}  "
          f"({'APPLIED' if a.apply else 'dry run'})")
    if a.apply and banked:
        tmp = REGISTRY + ".tmp"
        io.open(tmp, "w", encoding="utf-8").write(json.dumps(bank, indent=1, ensure_ascii=False))
        os.replace(tmp, REGISTRY)          # atomic: open(w) truncates before the write lands
        print(f"  wrote {REGISTRY}")
    return 0


def _self_test():
    """Both refusals must FIRE on the real shapes that nearly slipped through, and a coherent
    selection must still pass — a guard that refuses everything is as useless as one that refuses
    nothing."""
    class A:
        mixed_personas_ok = False
    a = A()
    ok = True

    def check(label, picked, expect, obj=a):
        nonlocal ok
        got = _refuse_incoherent(picked, obj)
        good = (got != 0) == expect
        ok = ok and good
        print(f"  {'ok  ' if good else 'FAIL'}  {label}")

    print("  (each case prints the refusal it is asserting)")
    check("two oracles under one category is refused",
          [{"oracle": "the surface renders real rows", "persona": "buyer"},
           {"oracle": "the empty state names what is missing", "persona": "buyer"}], True)
    check("five personas on one prover's evidence is refused",
          [{"oracle": "a FAILED read renders an error", "persona": p}
           for p in ("anon", "buyer", "seller", "admin", "provider")], True)

    class B(A):
        mixed_personas_ok = True
    check("...unless the operator states the evidence covers them all",
          [{"oracle": "a FAILED read renders an error", "persona": p}
           for p in ("anon", "buyer")], False, B())
    check("one oracle, one persona passes",
          [{"oracle": "a FAILED read renders an error", "persona": "buyer"},
           {"oracle": "a FAILED read renders an error", "persona": "buyer"}], False)
    check("a row with no persona recorded does not trip the persona guard",
          [{"oracle": "one claim", "persona": None}, {"oracle": "one claim", "persona": None}], False)
    print(f"\n  {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if "--self-test" in sys.argv[1:]:
    sys.exit(_self_test())
sys.exit(main(sys.argv[1:]))
