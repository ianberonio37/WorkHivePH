#!/usr/bin/env python3
"""engineer-lens-covers-its-lane - T52: what the Engineer lens SELECTS (2026-08-27).

The sibling gate engineer-lens-is-one-lens asks whether the two switches called Engineer agree with
each other. This one asks the question T52 left open in its own note: whether the nav-hub engineer
filter selects the right tools - a content question about the TOOLS registry rather than a state
question about a toggle.

★THE INVARIANT THAT HAS TEETH: no tool may be tagged `engineer` WITHOUT also being tagged
`supervisor`.

That is not tidiness. There is no engineer ROLE on this platform - hive_members.role is
CHECK-constrained to worker | supervisor - so `roles: ['engineer']` alone puts a tool in NO role's
default spine. It would be reachable only by someone who had already gone into the hub and switched
the lens by hand, and invisible to the supervisors who ARE the engineers here. nav-hub.js says so
itself, at the line that added supervisor to Eng. Design: "no separate engineer auth exists (the
engineer persona IS supervisors in practice, T52); a supervisor needing a calc could not find Eng.
Design here." The same reasoning applies to every future tool, and nothing was holding it.

This is the retired-page class - a live control reachable only through a door most people never
open - caught at the registry instead of after someone loses a tool.

★AND THE LANE ITSELF: T52 established the engineer lane as the design-and-reliability set. Asserting
each member keeps its engineer TAG stops the reverse drift, where a tool quietly leaves the lens and
the lens still calls itself Engineer. Tagging, not visibility: the app's isVisibleInMode also drops
every `hidden: true` tool from EVERY mode, and two of this lane's six are hidden Phase-B pages
reached from a parent button, so a visibility check would fail them forever for a reason that has
nothing to do with engineers. The lane is a floor, not a ceiling: extra engineer-tagged tools are
allowed, because whether Reports belongs is a judgement the registry records with a reason, not
something a validator should overturn.

Self-test: `--selftest`.
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
NAV = ROOT / "nav-hub.js"

# The design-and-reliability lane, as T52 established it. Each must keep its engineer TAG.
LANE = {
    "engineering-design.html": "Eng. Design",
    "analytics.html":          "Analytics",
    "asset-hub.html":          "Asset Hub",
    "project-manager.html":    "Project Manager",
    "project-report.html":     "Project Report",
    "ph-intelligence.html":    "PH Intelligence",
}

TOOL_RE = re.compile(r"\{\s*label:\s*'([^']+)',\s*href:\s*'([^']+)'(.*?)\}\,?\s*\n", re.S)
ROLES_RE = re.compile(r"roles:\s*\[([^\]]*)\]")


def parse_tools(src: str):
    """(label, href, roles) for every tool literal. roles is None for a universal tool."""
    out = []
    for m in TOOL_RE.finditer(src):
        label, href, rest = m.group(1), m.group(2), m.group(3)
        rm = ROLES_RE.search(rest)
        roles = None
        if rm:
            roles = {x.strip().strip("'\"") for x in rm.group(1).split(",") if x.strip()}
        out.append((label, href, roles))
    return out


def scan_source(src: str):
    """Findings for one nav-hub source. Empty list = the lens is coherent."""
    tools = parse_tools(src)
    findings = []

    for label, href, roles in tools:
        if roles and "engineer" in roles and "supervisor" not in roles:
            findings.append({
                "kind": "engineer_only_orphan",
                "tool": label,
                "detail": (f"{label} ({href}) is tagged engineer without supervisor. No engineer "
                           f"ROLE exists, so it sits in no role's default spine and only a "
                           f"hand-switched lens reaches it."),
            })

    # TAGGED for the engineer lens = carries `engineer`, or is universal (no roles array).
    #
    # Deliberately NOT the app's isVisibleInMode, which also drops every `hidden: true` tool from
    # EVERY mode - those are Phase-B pages reached from a parent button (Project Report from
    # project-manager, PH Intelligence from its section), and two of this lane's six are hidden. A
    # check that mirrored isVisibleInMode would report them missing from the Engineer lens forever,
    # which is true of every lens and says nothing about engineers. Hidden-ness is an orthogonal
    # decision; what this gate holds is the TAGGING, so a tool cannot quietly lose its engineer tag.
    # Naming it "tagged" rather than "visible" keeps the claim equal to what is measured.
    tagged = {href for _l, href, roles in tools if roles is None or "engineer" in roles}
    for href, label in LANE.items():
        present = any(h == href for _l, h, _r in tools)
        if present and href not in tagged:
            findings.append({
                "kind": "lane_member_untagged",
                "tool": label,
                "detail": (f"{label} ({href}) is part of the design-and-reliability lane but is not "
                           f"tagged for the Engineer lens."),
            })
    return findings


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    base = ("{ label: 'Eng. Design', href: 'engineering-design.html', roles: ['engineer','supervisor'] },\n"
            "{ label: 'Analytics', href: 'analytics.html', roles: ['supervisor','engineer'] },\n"
            "{ label: 'Asset Hub', href: 'asset-hub.html', roles: ['supervisor','engineer'] },\n"
            "{ label: 'Project Manager', href: 'project-manager.html', roles: ['supervisor','engineer'] },\n"
            "{ label: 'Project Report', href: 'project-report.html', roles: ['supervisor','engineer'] },\n"
            "{ label: 'PH Intelligence', href: 'ph-intelligence.html', roles: ['supervisor','engineer'] },\n")
    chk("accepts the lane as tagged today", len(scan_source(base)), 0)

    orphan = base.replace("roles: ['engineer','supervisor'] }", "roles: ['engineer'] }")
    chk("catches an engineer-ONLY tool", len(scan_source(orphan)), 1)

    dropped = base.replace("{ label: 'Analytics', href: 'analytics.html', roles: ['supervisor','engineer'] }",
                           "{ label: 'Analytics', href: 'analytics.html', roles: ['supervisor'] }")
    chk("catches a lane member leaving the lens", len(scan_source(dropped)), 1)

    universal = base.replace("{ label: 'Asset Hub', href: 'asset-hub.html', roles: ['supervisor','engineer'] }",
                             "{ label: 'Asset Hub', href: 'asset-hub.html' }")
    chk("a universal tool is visible in every lens", len(scan_source(universal)), 0)

    absent = "\n".join(l for l in base.splitlines() if "ph-intelligence" not in l) + "\n"
    chk("a tool not in the registry is not a lane failure", len(scan_source(absent)), 0)

    # Two of the six lane members ship hidden:true, reached from a parent button rather than the
    # hub. The app's isVisibleInMode drops hidden tools from EVERY mode, so a check written against
    # visibility would fail them permanently for a reason that has nothing to do with engineers.
    hidden = base.replace("{ label: 'Project Report', href: 'project-report.html', roles: ['supervisor','engineer'] }",
                          "{ label: 'Project Report', href: 'project-report.html', hidden: true, roles: ['supervisor','engineer'] }")
    chk("a hidden lane member is still tagged, so still fine", len(scan_source(hidden)), 0)

    hidden_untagged = hidden.replace("{ label: 'Project Report', href: 'project-report.html', hidden: true, roles: ['supervisor','engineer'] }",
                                     "{ label: 'Project Report', href: 'project-report.html', hidden: true, roles: ['supervisor'] }")
    chk("a hidden lane member losing its tag still fails", len(scan_source(hidden_untagged)), 1)

    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    src = io.open(NAV, encoding="utf-8").read()
    findings = scan_source(src)
    tools = parse_tools(src)
    eng = [l for l, _h, r in tools if r is None or "engineer" in r]

    print("T52 engineer lens covers its lane")
    print(f"  tools in the registry:      {len(tools)}")
    print(f"  tagged for Engineer lens:   {len(eng)}")
    print(f"  lane members required:      {len(LANE)}")

    if not findings:
        print("\n  PASS - every lane member keeps its engineer tag, and no tool is engineer-only.")
        return 0

    print("\n  FAIL")
    for f in findings:
        print(f"    [{f['kind']}] {f['detail']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
