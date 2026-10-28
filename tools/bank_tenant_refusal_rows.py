#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bank the S-lens trajectory rows whose page's OWN relations were proven to refuse a stranger.

THE LENS. "The platform must refuse, on this page, a person who is not entitled to what it shows."
88 of those rows sit open needing the postgres instrument. tools/prove_tenant_refusal.mjs answers exactly
that question - as a real signed-in member through PostgREST, never as the superuser MCP, which owns every
table and carries rolbypassrls and so can prove what data EXISTS but never that a read was REFUSED.

*WHY THIS IS PER-PAGE AND NOT A BLANKET STAMP. A row belongs to ONE page. A green platform-wide sweep is not
evidence for a page unless the relations THAT page reads are among the ones measured - and 44 of the 67 tenant
tables had no foreign rows at all, so a refusal there proves nothing ("nothing to hide" is not a boundary).
So each row's basis is built from the intersection of:
    the relations its page actually reads   (.from('x') in the page source)
  x the relations the report proved refuse  (verdict ok AND foreign_rows > 0 AND not public-by-design)
and a page whose intersection is EMPTY is left OPEN with the reason recorded, never closed on someone else's
evidence. That is the whole discipline: a basis must describe the page in its own receipt.

USAGE  python tools/bank_tenant_refusal_rows.py [--apply]
"""
import argparse
import glob
import io
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "tenant_refusal_report.json")
REGISTRY = os.path.join(ROOT, "trajectory_registry.json")
MANIFEST = os.path.join(ROOT, "live_walk_manifest.json")
LENS = "The platform must refuse"
GATE_ID = "tenant-refusal"          # as registered in run_platform_checks.py
READ_RE = re.compile(r"""\.from\(\s*['"]([a-z0-9_]+)['"]""")


SCRIPT_RE = re.compile(r'''<script[^>]*src="(?!http)([^"]+\.js)"''')


def page_source(page):
    """The page AND the sibling script it delegates to.

    *A GLOB IS A CLAIM ABOUT COVERAGE. The first version read only the .html, so engineering-design.html looked
    like a page with no data layer at all - its reads live in engineering-design.js (engineering_calcs,
    project_links, both proven). Reading only the file named in the row would have left three rows open with the
    reason "reads []", which was my reader's blind spot reported as a fact about the page. Only the page's OWN
    script is followed (same basename): utils.js and nav-hub.js are shared chrome, graded once elsewhere, and
    folding their reads into every page would credit each page with relations it does not itself touch.
    """
    p = os.path.join(ROOT, page)
    if not os.path.exists(p):
        return ""
    src = io.open(p, encoding="utf-8", errors="replace").read()
    own = page.rsplit("/", 1)[-1][:-5] if page.endswith(".html") else page
    for rel in SCRIPT_RE.findall(src):
        if rel.rsplit("/", 1)[-1][:-3] != own:
            continue
        q = os.path.join(ROOT, rel)
        if os.path.exists(q):
            src += "\n" + io.open(q, encoding="utf-8", errors="replace").read()
    return src


def proven(section):
    """Only a relation that HAD something to hide and still refused is evidence."""
    return {k: v for k, v in section.items()
            if v.get("verdict") == "ok" and v.get("foreign_rows", 0) > 0
            and not v.get("public_by_design")}


def evidence(rep):
    """Every relation a GREEN report proved refuses, keyed by name, with the kind of proof it is."""
    tables, views = proven(rep["tables"]), proven(rep["views"])
    # person-scoped rows carry their own shape: a stranger's rows refused while the actor sees his own
    person = {k: v for k, v in rep.get("person", {}).items()
              if v.get("verdict") == "ok" and v.get("other_person_rows", 0) > 0}
    # *A PUBLIC SURFACE'S BOUNDARY IS THE PUBLISHED SUBSET, NOT THE HIVE. public-feed.html reads only
    # v_community_posts_truth, which is public-by-design - so proven() excludes it and the row sat open. But the
    # row's ask ("refuse a person who is not entitled to what it shows") IS answered there, just with a different
    # property: the page withholds ROWS rather than a tenant. The prover now asserts that subset at run time
    # against SQL (expected vs got), so it is a measured invariant and not a declaration, and a view carrying a
    # matching subset oracle is evidence of exactly the kind this row needs.
    subset = {k: v for k, v in rep["views"].items()
              if (v.get("subset") or {}).get("ok") and v["subset"]["expected"] > 0}
    ALL = {}
    for src, kind in ((tables, "table"), (views, "view"), (person, "person"), (subset, "subset")):
        for k, v in src.items():
            ALL.setdefault(k, dict(v, _kind=kind))
    return ALL


# *THE READING MUST BE THE ROW'S PERSONA'S OWN (2026-10-08). The prover can now be asked as any seeded person
# (`--as`/`--email`), and each run writes its own report - so a supervisor row is banked from a SUPERVISOR's refusals
# (a supervisor's policy arms are wider than a worker's: she reads the audit log, writes any asset of her hive) and a
# solo owner's from a person with NO hive (every hive is foreign to him; his control is his own hive-less rows). Every
# other persona is a plain member of a hive, which is what the default report measures. A row whose persona has no
# green report stays OPEN and says so - it is never banked on another person's reading.
def persona_report_kind(persona):
    # oversight is cast as a supervisor too (tools/lx_walk_args.py SUP_PERSONAS), so it reads as one
    if persona in ("supervisor", "fleet-supervisor", "oversight"):
        return "supervisor"
    if persona == "solo-owner":
        return "solo"
    # *A VISITOR HAS NO ACCOUNT, SO HIS READING IS THE ANON HALF (2026-10-28). Every report asks each relation a second
    # time with only the publishable key - exactly the request a signed-out visitor makes - and records `anon_sees`.
    # So an anon row is banked from that half of the default report, and its basis quotes what ANON saw; quoting the
    # member's figures for a person who never signed in would describe somebody else.
    if persona == "anon":
        return "anon"
    return "member"


def load_reports():
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "tenant_refusal_report*.json"))):
        try:
            rep = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if not rep.get("pass"):
            print("skipped {0} - not green; a failing sweep cannot bank a row".format(os.path.basename(path)))
            continue
        kind = ("solo" if rep.get("solo") else "supervisor" if rep.get("actor_role") == "supervisor"
                else "member" if os.path.basename(path) == os.path.basename(REPORT) else None)
        # several readings may speak for one persona (two supervisors whose foreign hives differ): keep them all,
        # and let each row take the one that proved the most of ITS page's relations
        if kind:
            out.setdefault(kind, []).append((rep, evidence(rep), os.path.basename(path)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    reports = load_reports()
    if "member" not in reports:
        print("REFUSED - the default report is not green; a failing sweep cannot bank a row")
        return 1

    # through the registry UNION (tools/registry_io.py): the cube's rows live in trajectory_registry_cx.json
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import registry_io as _rio
    reg = _rio.load_doc()
    rows = reg["trajectories"]
    byid = {r["id"]: r for r in rows}
    man = json.load(open(MANIFEST, encoding="utf-8"))

    # ★AND THE CUBE'S S ROWS ON THE PILLARS A REFUSAL READING ANSWERS (2026-10-28). F ("it is true and wired") is the
    # refusal holding on the page's own relations; I ("this persona may, and may not") is the same reading's two
    # halves - the foreign rows refused AND the actor's own still visible (the control). U - what the person can TELL
    # when refused - is no database reading's to answer, and an S row on the A pillar is held off its layer.
    def is_cube_s(r):
        cx = (byid.get(r["id"]) or {}).get("cx") or {}
        return cx.get("layer") == "S" and cx.get("pillar") in ("F", "I")
    targets = [r for r in man["rows"]
               if not (r["kind"] == "live" and r["gated"])
               and r["mcp"] == "postgres-mcp" and (r["lens"].startswith(LENS) or is_cube_s(r))]

    src_cache, banked, skipped, fresh = {}, [], [], []
    for t in targets:
        row = byid[t["id"]]
        lx, cx = row.get("lx") or {}, row.get("cx") or {}
        # a cube row names its own page; the manifest's `surface` is the route's start (index.html), not the page
        page = lx.get("page") or cx.get("page") or t["surface"]
        persona = lx.get("persona") or cx.get("persona") or row.get("persona") or "any"
        pk = persona_report_kind(persona)
        rk = "member" if pk == "anon" else pk          # the anon half lives in the default report
        if rk not in reports:
            skipped.append((t["id"], page, ["no green report as a {0} ({1})".format(pk, persona)]))
            continue
        if page not in src_cache:
            src_cache[page] = page_source(page)
        reads = sorted(set(READ_RE.findall(src_cache[page])))
        rep, ALL, rep_file = max(reports[rk], key=lambda x: sum(1 for r in reads if r in x[1]))
        hit = [r for r in reads if r in ALL]
        if pk == "anon":
            # only a relation the visitor's request was actually measured on can speak for him
            hit = [r for r in hit if "anon_sees" in ALL[r]]
        if not hit:
            skipped.append((t["id"], page, reads[:4]))
            continue

        # the sharpest relation first: the one with the most foreign rows it refused to hand over
        hit.sort(key=lambda r: -ALL[r].get("foreign_rows", 0))
        quotes = []
        for r in hit[:4]:
            v = ALL[r]
            if pk == "anon":
                # the visitor's own figures only: what existed, and what a request with no session was handed
                if v["_kind"] == "person":
                    held = "a stranger's {0} row(s) existed".format(v["other_person_rows"])
                else:
                    held = "{0} foreign row(s) existed".format(v["foreign_rows"])
                quotes.append("{0} ({1}, the signed-out request was handed {2}{3})".format(
                    r, held, v["anon_sees"],
                    " - exactly the public subset, {0}".format(v["subset"]["says"]) if v["_kind"] == "subset" else ""))
                continue
            if v["_kind"] == "subset":
                sb = v["subset"]
                quotes.append("{0} (public-by-design, so the boundary is the PUBLISHED SUBSET: of {1} foreign "
                              "row(s) the asker saw exactly {2}, and {3} yields {2} - asserted in SQL on "
                              "this run, not declared)".format(r, v["foreign_rows"], sb["got"], sb["says"]))
            elif v["_kind"] == "person":
                quotes.append("{0} (a stranger's {1} row(s) refused; the actor's own {2} still visible)"
                              .format(r, v["other_person_rows"], v["own_rows"]))
            else:
                own = ", own {0} visible".format(v["own_rows"]) if v.get("own_rows") else ""
                quotes.append("{0} ({1} foreign row(s) existed, the asker saw {2}, anon saw {3}{4})"
                              .format(r, v["foreign_rows"], v["member_sees"], v["anon_sees"], own))
        tot = rep["totals"]
        vt, pt = rep["view_totals"], rep["person_totals"]
        basis = (
            "[{0}] pct -> 60. WALKED with the registered prover tools/prove_tenant_refusal.mjs - the "
            "postgres-instrument lens for this row, named in live_walk_manifest's MARKERS. IT IS NOT THE "
            "POSTGRES MCP ON PURPOSE: that connects as `postgres`, which owns every public table and carries "
            "rolbypassrls, so RLS is never consulted and the read answers with the foreign hive's rows. A "
            "superuser lens can prove what data EXISTS; it can never prove a read was REFUSED. This asks as "
            "{1} ({2}, {18}) through PostgREST with a real minted token, and again with only the "
            "publishable key as anon, for the rows of {3}. {19}MEASURED ON {4}'s OWN RELATIONS: {5}. "
            "PLATFORM-WIDE IN THE SAME RUN: {6}/{7} tenant tables, {8}/{9} hive-scoped views, {10}/{11} "
            "person-scoped tables (no hive_id - the boundary there is the PERSON, which is the shape of the "
            "logbook defect), {12}/{13} by-id (BOLA, the row asked for by its own uuid with no hive filter at "
            "all) and {14}/{15} write-authz (forge/patch/erase into the foreign hive) all refused. A relation "
            "with nothing to hide is reported n/a and NEVER counted as a pass - {16} tenant tables fell there - "
            "and the write control proves the probe can still be accepted where it should be ({17}), so three "
            "refusals cannot mean three malformed requests."
        ).format(date.today().isoformat(), rep["actor"], rep["actor_hive"], rep["foreign_hive"], page,
                 "; ".join(quotes), tot["tested"] - tot["leaks"], tot["tested"],
                 vt["tested"] - vt["leaks"], vt["tested"], pt["tested"] - pt["leaks"], pt["tested"],
                 tot["bola_tested"] - tot["bola_leaks"], tot["bola_tested"],
                 tot["write_tested"] - tot["write_bad"], tot["write_tested"], tot["na"], tot["write_control"],
                 {"supervisor": "a SUPERVISOR, whose policy arms are wider than a worker's",
                  "solo": "a SOLO OWNER, so every hive is foreign to him",
                  "member": "a plain member",
                  "anon": "a plain member"}[pk],
                 ("THE ROW'S PERSONA IS anon - a visitor with no account - AND THE QUOTED FIGURES ARE THE SIGNED-OUT "
                  "HALF OF THIS RUN ({0}): each relation asked again with only the publishable key, which is the "
                  "request a visitor makes. ".format(rep_file) if pk == "anon" else
                  "THE ROW'S PERSONA IS {0}, AND THIS IS THAT PERSONA'S OWN READING ({1}). ".format(persona, rep_file)
                  if pk != "member" else ("THE ROW'S PERSONA IS {0}: a plain member of a hive, which is what this "
                                          "reading measures ({1}). ".format(persona, rep_file)
                                          if persona not in ("any", "") else "")))
        # *IDEMPOTENT ON THE BASIS, NOT ON THE MANIFEST. The manifest is a snapshot taken BEFORE this run, so a
        # second --apply sees the same 88 rows still "open" and would prepend a second copy of the same receipt.
        # A row that already cites this prover keeps its wording and only has the gate ensured below.
        prev = row.get("basis") or ""
        if "prove_tenant_refusal.mjs" not in prev:
            row["basis"] = (basis + " || " + prev) if prev else basis
            fresh.append(t["id"])
        row["status"] = "locking"
        row["pct"] = max(int(row.get("pct") or 0), 60)
        # *locking MEANS THE GATE IS BUILT, so the row must NAME it - validate_trajectory_registry enforces
        # exactly that, and the first --apply failed on 79 rows for leaving artifacts.gates empty. The prover
        # is registered in run_platform_checks as `tenant-refusal`, so the row re-earns its green by re-running
        # that gate rather than by anyone remembering what was once true.
        art = row.setdefault("artifacts", {})
        gates = art.setdefault("gates", [])
        if GATE_ID not in gates:
            gates.append(GATE_ID)
        banked.append((t["id"], page, len(hit)))

    print("S-lens postgres rows: {0}  ->  bankable {1} ({2} newly written, {3} already cited this prover) "
          "- left open {4}".format(len(targets), len(banked), len(fresh),
                                   len(banked) - len(fresh), len(skipped)))
    for i, p, n in banked[:6]:
        print("   bank {0:7} {1:30} {2} proven relation(s)".format(i, p, n))
    if banked[6:]:
        print("   ... and {0} more".format(len(banked) - 6))
    for i, p, reads in skipped:
        print("   OPEN {0:7} {1:30} reads {2} - none proven; needs its own evidence".format(i, p, reads))
    if not a.apply:
        print("\n(dry run - pass --apply to write)")
        return 0
    # through the union, at the main file's own indent: a cube row lives in its shard, and a rewrite of the main file
    # alone never reaches it (registry_io.save_doc is atomic per file)
    with io.open(REGISTRY, encoding="utf-8") as fh:
        fh.readline()
        second = fh.readline()
    _rio.save_doc(reg, indent=max(1, len(second) - len(second.lstrip(" "))) if second.strip() else 2)
    print("\nWROTE {0} row(s) through the registry union".format(len(banked)))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    sys.exit(main())
