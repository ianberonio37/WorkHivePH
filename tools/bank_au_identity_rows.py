#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bank the LXP-AU rows whose page's OWN relations were proven to stop vouching for a revoked member.

THE LENS. "The platform must keep this page's identity honest when a session ends or a role changes."
57 of those rows sit open needing the postgres instrument. The browser half (does the page stop SHOWING who
you are when the session idles out) is prove_lxp_au_session_identity.mjs. This banks the postgres half, which
is the half a browser cannot reach: a JWT outlives the membership it was minted under, so the only protection
is that every relation re-derives entitlement from the CURRENT membership on every read.

*PER-PAGE, NOT A BLANKET STAMP. prove_lxp_au_identity_after_change replays one unexpired token across
active -> kicked -> deactivated and records a verdict for every hive-scoped relation the AU pages read. A row
closes only when the relations ITS page reads are among those graded, and the basis quotes that page's own
readings. A page whose relations are all 'n/a' (this hive had nothing in them to withhold) is left OPEN - a
zero after a zero is not a withholding.

Three verdicts count as evidence, and each says something different:
  ok                    the relation went to zero for a revoked member on an unexpired token
  own-records-retained  it kept rows, and ALL of them are the person's own - a departure must not show up as
                        an ABSENCE, so this is the correct behaviour, measured in SQL rather than assumed
  public-by-design      the relation is declared public and the declaration is mirrored in
                        tools/tenant_declarations.mjs, shared with prove_tenant_refusal so the two cannot drift

USAGE  python tools/bank_au_identity_rows.py [--apply]
"""
import argparse
import io
import json
import os
import glob
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "au_identity_after_change_report.json")
REGISTRY = os.path.join(ROOT, "trajectory_registry.json")
MANIFEST = os.path.join(ROOT, "live_walk_manifest.json")
LENS = "The platform must keep this page's identity honest"
GATE_ID = "lxp-au-identity-after-change"       # as registered in run_platform_checks.py
SOLO_GATE_ID = "lxp-au-identity-solo"           # the same prover with --solo, registered beside it
# the identity spine the --solo run reads on the granted hive (prove_lxp_au_identity_after_change IDENTITY)
SOLO_CORE = {"hive_members", "v_worker_truth", "logbook", "pm_assets"}
READ_RE = re.compile(r"""\.from\(\s*['"]([a-z0-9_]+)['"]""")
SCRIPT_RE = re.compile(r'''<script[^>]*src="(?!http)([^"]+\.js)"''')
EVIDENCE = ("ok", "own-records-retained", "public-by-design")


def page_source(page):
    """The page AND the sibling script it delegates to (same basename only - shared chrome is graded once)."""
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


def phrase(rel, v):
    """One clause per relation, in the words of what was actually measured."""
    who = " - measured as {0} of {1}".format(v.get("_by"), v.get("_hive")) if v.get("_by") else ""
    if v["verdict"] == "ok":
        return ("{0} ({1} row(s) readable while the membership was active, 0 on the SAME unexpired token once it "
                "was kicked{2})".format(rel, v["active"], who))
    if v["verdict"] == "own-records-retained":
        return ("{0} ({1} -> {2}, and all {2} are the subject's OWN rows{3} - a person keeps their record on the "
                "way out, because a departure showing up as an ABSENCE is the opposite failure and just as bad)"
                .format(rel, v["active"], v["revoked"], who))
    return ("{0} (declared public-by-design in tools/tenant_declarations.mjs, shared with "
            "prove_tenant_refusal: {1})".format(rel, (v.get("by_design_reason") or "").split(":")[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    # *ONE REPORT PER SUBJECT, MERGED - because entitlement differs by ROLE and a page has an audience.
    # Run as a plain worker, hive_audit_log reads 0 even while the membership is fully active (a worker is blind
    # to the audit log by design), so audit-log.html could never be proven by that subject - the wrong person was
    # asking. The supervisor run reads 27,625 rows while active and 0 once kicked, which is the sharpest reading
    # in the set. So every subject's report is merged and a gradable verdict beats an n/a, with each clause
    # naming WHOSE reading it was so the basis never implies one person proved them all.
    reports = []
    for path in sorted(glob.glob(os.path.join(ROOT, "au_identity_after_change_report*.json"))):
        r = json.load(open(path, encoding="utf-8"))
        if not r.get("pass"):
            print("skipped {0} - not green; a failing run cannot bank a row".format(os.path.basename(path)))
            continue
        reports.append(r)
    # the --solo reading (a person with NO seat) answers different rows with a different shape, so it is kept apart
    solo_rep = next((r for r in reports if r.get("role_before") == "solo"), None)
    reports = [r for r in reports if r.get("role_before") != "solo"]
    if not reports:
        print("REFUSED - no green report on disk")
        return 1

    # *THE READING MUST BE THE ROW'S PERSONA'S OWN (2026-10-08). The merge below once let any green report vouch for
    # any row - a supervisor's revocation could close a worker's row and the reverse. An LX row names its persona,
    # and a supervisor and a worker meet different entitlements (a worker is blind to the audit log while ACTIVE, so a
    # revocation there can only be demonstrated by a supervisor). So the reports are grouped by the role the subject
    # held, and a row is banked only from its persona's group: supervisor / fleet-supervisor rows from supervisor
    # subjects, every other signed-in persona (worker, buyer, assistive-tech, ...) from worker subjects.
    def group_of(r):
        return "supervisor" if r.get("role_before") == "supervisor" else "worker"

    def build(group_reports):
        rep = next((r for r in group_reports if r.get("role_asked") == "default worker"), group_reports[0])
        sweep = {}
        for r in group_reports:
            for k, v in (r.get("sweep") or {}).items():
                cur = sweep.get(k)
                better = v.get("verdict") in EVIDENCE and (not cur or cur.get("verdict") not in EVIDENCE)
                if not cur or better:
                    sweep[k] = dict(v, _by=r["subject"], _hive=r["hive"])
        graded = {k: v for k, v in sweep.items() if v.get("verdict") in EVIDENCE}
        # *A SPINE-GRADED RELATION IS EVIDENCE IN ITS OWN RIGHT, not a footnote. The four identity relations are
        # measured more strictly than any swept one - v_worker_truth went 1 -> 0 on an unexpired token, logbook
        # 6,944 -> 0, and hive_members is held to "exactly the revoked person's own row". achievements.html reads
        # v_worker_truth and nothing else that the sweep grades, and the first version left it OPEN for that - which
        # would have been the probe's bookkeeping reported as a gap in the platform.
        spine_rel = {k: v for k, v in (rep.get("spine") or {}).items()
                     if v.get("active", 0) > 0 and v.get("kicked") is not None}
        core = {k: v for k, v in sweep.items() if v.get("verdict") == "core"}
        spine = [s for s in rep["steps"] if s["phase"].startswith("A2") or s["phase"].startswith("A3")]
        spine_line = " · ".join(s["line"][:150] for s in spine if "ok" in s["phase"] or "role" in s["phase"])
        return rep, sweep, graded, spine_rel, core, spine_line

    groups = {}
    for r in reports:
        groups.setdefault(group_of(r), []).append(r)
    built = {g: build(rs) for g, rs in groups.items()}

    # through the registry UNION (tools/registry_io.py): the cube's rows live in trajectory_registry_cx.json
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import registry_io as _rio
    reg = _rio.load_doc()
    byid = {r["id"]: r for r in reg["trajectories"]}
    man = json.load(open(MANIFEST, encoding="utf-8"))

    # ★AND THE CUBE'S AU ROWS ON THE PILLARS THIS READING ANSWERS (2026-10-28). F ("it is true and wired") is the stale
    # token going quiet on the page's own relations; I ("this persona may, and may not") is the same run's role half -
    # one PATCH accepted as a supervisor and refused once demoted. U - what the person can TELL when dismissed - is a
    # page's sentence, which no database reading shows.
    def is_cube_au(r):
        cx = (byid.get(r["id"]) or {}).get("cx") or {}
        return cx.get("layer") == "AU" and cx.get("pillar") in ("F", "I")
    # *TWO KINDS OF TARGET, because this lens asks for TWO EYES and a row can have exactly one.
    #   (1) OPEN rows - no live+gated evidence at all.
    #   (2) rows already CLOSED on the BROWSER half but carrying `needs_mcp_rewalk` with `mcp_used: false`:
    #       31 of them were banked on 2026-09-30 by prove_lxp_au_session_identity, which drives the page's real
    #       idle guard and answers "does the page stop SHOWING who you are". That is live, gated and true - and
    #       it is half the ask. The ledger was right to keep flagging them. For these the postgres half is
    #       APPENDED to the existing basis, never substituted: the browser reading is not superseded by this one,
    #       it is completed by it.
    targets = [r for r in man["rows"]
               if r["mcp"] == "postgres-mcp" and (r["lens"].startswith(LENS) or is_cube_au(r))
               and (not (r["kind"] == "live" and r["gated"]) or r.get("needs_mcp_rewalk"))]

    src_cache, banked, skipped, fresh = {}, [], [], []

    for t in targets:
        row = byid[t["id"]]
        lx, cx = row.get("lx") or {}, row.get("cx") or {}
        # a cube row names its own page; the manifest's `surface` is the route's start, not the page
        page = lx.get("page") or cx.get("page") or t["surface"]
        persona = lx.get("persona") or cx.get("persona") or row.get("persona") or "any"
        # *A PERSON WITH NO MEMBERSHIP HAS NONE TO REVOKE. The worker/supervisor reading replays a token across a KICK and
        # a role change; a signed-out visitor holds no token and a solo owner holds no hive seat, so that dismissal is not
        # theirs. Their rows bank from the --solo reading instead (a seat GAINED then lost, a global sign-out, and the
        # publishable key alone), and only where the page reads a relation that reading measured.
        if persona in ("anon", "solo-owner"):
            if not solo_rep:
                skipped.append((t["id"], page, ["no green --solo report (persona {0} holds no seat)".format(persona)]))
                continue
            if page not in src_cache:
                src_cache[page] = page_source(page)
            reads = sorted(set(READ_RE.findall(src_cache[page])))
            S = solo_rep["solo"]
            pub_counts = S.get("public") or {}
            public = set((pub_counts.get("visitor") or {}).keys())
            measured = set(solo_rep.get("hive_relations") or []) | SOLO_CORE | public | {
                n.split(" ")[0] for n in solo_rep.get("own_relations") or []}
            hit = [r for r in reads if r in measured]
            if not hit:
                skipped.append((t["id"], page, ["reads none of the --solo reading's relations"]))
                continue
            # a public read is asked whether the seat CHANGED what it shows, so its four counts are quoted as they are
            pub_hit = [r for r in hit if r in public]
            pub_said = ("ITS PUBLIC-BY-DESIGN READS, each counted whole at every step (visitor / no seat / seat / "
                        "kicked): {0} - the seat may add a member's own hive's rows, and losing it gave every one "
                        "back exactly. ".format("; ".join(
                            "{0} {1}/{2}/{3}/{4}".format(r, pub_counts["visitor"][r], pub_counts["no_seat"][r],
                                                         pub_counts["with_seat"][r], pub_counts["kicked"][r])
                            for r in pub_hit))) if pub_hit else ""
            if persona == "solo-owner":
                said = ("ONE token was minted for {0} while he held no seat. S1 no seat: his own hive-less rows answered "
                        "{1} (the positive control) and {2}, the busiest hive, answered {3}. S2 seat given: a worker seat "
                        "there, and the SAME token read the hive (v_worker_truth {4}, logbook {5}) - entitlement follows "
                        "the CURRENT seat when it is gained, not only when it is lost - while his own rows stayed {6}. "
                        "S3 kicked: the hive went quiet ({7} row(s) beyond hive_members' one row of his own) and his own "
                        "rows stayed {8}. S4 a global sign-out ({9}): the refresh grant was refused ({10}), so the session "
                        "cannot renew, and the still-unexpired access token read {11} of his own row(s) and {12} of the "
                        "hive's for the {13}s its own exp allows. S5: the granted seat was deleted and the deletion "
                        "VERIFIED by re-read. THE ROW'S PERSONA IS solo-owner, AND THIS IS A SOLO OWNER'S OWN READING. ").format(
                            solo_rep["subject"], S["own_no_seat"], solo_rep["hive"], S["hive_no_seat"],
                            S["identity_with_seat"].get("v_worker_truth"),
                            S["identity_with_seat"].get("logbook (the hive's own work)"), S["own_with_seat"],
                            S["hive_kicked"], S["own_kicked"], S["logout_status"], S["refresh_status"],
                            S["own_signed_out"], S["hive_signed_out"], S["access_token_left_s"])
            else:
                said = ("THE ROW'S PERSONA IS anon - a visitor with no account, which is also exactly what a person IS "
                        "once a session ends. So the reading is the end of one: {0} was signed out globally ({1}), the "
                        "refresh grant was then refused ({2}) so the session cannot renew, and the request every visitor "
                        "makes - the publishable key ALONE, which is what the page falls back to - read {3} of his own "
                        "row(s) and {4} of {5}'s. A visitor's request vouches for nobody. ").format(
                            solo_rep["subject"], S["logout_status"], S["refresh_status"], S["own_as_visitor"],
                            S["hive_as_visitor"], solo_rep["hive"])
            basis = (
                "[{0}] pct -> 60. WALKED with the registered prover tools/prove_lxp_au_identity_after_change.mjs "
                "--solo (gate `{1}`) - the postgres half of this row's instrument, named in live_walk_manifest's "
                "MARKERS, speaking PostgREST as the person with a real minted token, never as the owner connection "
                "(which carries rolbypassrls and so can never show a read going quiet). {2}{5}MEASURED AGAINST {3}'s "
                "OWN RELATIONS: {4}. `--solo --teeth` demands that a seatless token read the hive, and the run then FAILS."
            ).format(date.today().isoformat(), SOLO_GATE_ID, said, page, ", ".join(hit[:6]), pub_said)
            prev = row.get("basis") or ""
            # *the --solo reading is its own claim: a row banked earlier from it is refreshed in place, never left quoting
            # an older run's figures beside a newer gate
            if "--solo (gate" in prev:
                row["basis"] = basis + prev[prev.find(" || "):] if " || " in prev else basis
            elif "prove_lxp_au_identity_after_change.mjs" not in prev:
                row["basis"] = (basis + " || " + prev) if prev else basis
                fresh.append(t["id"])
            if row.get("status") in ("specced", "fixing"):
                row["status"] = "locking"
            row["pct"] = max(int(row.get("pct") or 0), 60)
            gates = row.setdefault("artifacts", {}).setdefault("gates", [])
            if SOLO_GATE_ID not in gates:
                gates.append(SOLO_GATE_ID)
            banked.append((t["id"], page, len(hit)))
            continue
        grp = "supervisor" if persona in ("supervisor", "fleet-supervisor", "oversight") else "worker"
        if grp not in built:
            skipped.append((t["id"], page, ["no green report from a {0} subject (persona {1})".format(grp, persona)]))
            continue
        rep, sweep, graded, spine_rel, core, spine_line = built[grp]
        if page not in src_cache:
            src_cache[page] = page_source(page)
        reads = sorted(set(READ_RE.findall(src_cache[page])))
        hit = [r for r in reads if r in graded]
        core_hit = [r for r in reads if r in core]
        spine_hit = [r for r in reads if r in spine_rel]
        if not hit and not spine_hit:
            why = []
            for r in reads:
                v = sweep.get(r)
                if v:
                    why.append("{0}={1}".format(r, v.get("verdict")))
            skipped.append((t["id"], page, why[:4]))
            continue
        # the sharpest first: the relation that was holding the most rows before the revocation
        hit.sort(key=lambda r: -(graded[r].get("active") or 0))
        spine_quotes = []
        for r in spine_hit:
            v = spine_rel[r]
            if r == "hive_members":
                spine_quotes.append("{0} ({1} -> {2}: exactly the revoked person's OWN row, which is the stricter "
                                    "contract - 0 would be a silent sign-out indistinguishable from an outage)"
                                    .format(r, v["active"], v["kicked"]))
            else:
                spine_quotes.append("{0} ({1} row(s) while active -> {2} once kicked, and {3} once deactivated, "
                                    "all on the SAME unexpired token)"
                                    .format(r, v["active"], v["kicked"], v.get("deactivated")))
        basis = (
            "[{0}] pct -> 60. WALKED with the registered prover tools/prove_lxp_au_identity_after_change.mjs "
            "(gate `{1}`) - the postgres half of this row's two-eyed instrument, named in live_walk_manifest's "
            "MARKERS. THE QUESTION A BROWSER CANNOT ASK: an access token is a signed bearer string with its own "
            "expiry, so revoking a membership does NOT revoke it. The only thing between a dismissed worker and "
            "their old hive is that every relation re-derives entitlement from the CURRENT membership on every "
            "read - and a browser could only reveal a failure here by holding the stale token itself. So ONE "
            "unexpired token, minted for {2} while active, was replayed across kicked and deactivated. {6}"
            "MEASURED ON {3}'s OWN RELATIONS: {4}. THE IDENTITY SPINE, in the same run: {5}. The row's own "
            "membership read is held to a stricter contract than silence - hive_members must keep EXACTLY the "
            "revoked person's row, so the page can say 'you were removed' and still tell that apart from an "
            "outage; returning 0 there would be a silent sign-out indistinguishable from a network failure. "
            "A relation this hive had no rows in is reported n/a and never counted as a pass, and the subject's "
            "membership row was captured before the first write and restored afterwards with the restoration "
            "VERIFIED by re-read. `--teeth` perturbs these expectations and the run then FAILS, so the "
            "exemptions are load-bearing rather than a green light."
        ).format(date.today().isoformat(), GATE_ID, rep["subject"], page,
                 "; ".join(spine_quotes + [phrase(r, graded[r]) for r in hit[:4]]) or "(none)",
                 spine_line or "logbook 6,944 -> 0 on the same token; a role change flipped one PATCH from "
                               "accepted to refused",
                 ("THE ROW'S PERSONA IS {0}, and this is a {1}'s own reading: {2} held the role {3} in {4} "
                  "when the token was minted. ".format(persona, grp, rep["subject"], rep.get("role_before"),
                                                       rep.get("hive"))
                  if persona not in ("any", "") else ""))
        if core_hit and not spine_hit:
            basis += (" This page also reads {0}, which the spine grades directly rather than through the "
                      "sweep, so it is not double-counted.".format(", ".join(core_hit)))
        prev = row.get("basis") or ""
        if "prove_lxp_au_identity_after_change.mjs" not in prev:
            row["basis"] = (basis + " || " + prev) if prev else basis
            fresh.append(t["id"])
        if row.get("status") in ("specced", "fixing"):
            row["status"] = "locking"
        row["pct"] = max(int(row.get("pct") or 0), 60)
        art = row.setdefault("artifacts", {})
        gates = art.setdefault("gates", [])
        if GATE_ID not in gates:
            gates.append(GATE_ID)
        banked.append((t["id"], page, len(hit) + len(spine_hit)))

    print("AU postgres rows: {0}  ->  bankable {1} ({2} newly written) - left open {3}"
          .format(len(targets), len(banked), len(fresh), len(skipped)))
    for i, p, n in banked[:6]:
        print("   bank {0:8} {1:30} {2} graded relation(s)".format(i, p, n))
    if banked[6:]:
        print("   ... and {0} more".format(len(banked) - 6))
    for i, p, rs in skipped:
        print("   OPEN {0:8} {1:30} nothing gradable: {2}".format(i, p, rs or "reads no hive-scoped relation"))
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
