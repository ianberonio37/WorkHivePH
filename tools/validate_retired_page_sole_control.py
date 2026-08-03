#!/usr/bin/env python3
"""validate_retired_page_sole_control.py — a retired page must not be the ONLY host of a write.

BORN FROM A LIVE DEFECT (2026-08-03). founder-console.html was retired in July behind
`#wh-retired-overlay` — position:fixed, inset:0, z-index:100000, and nothing removes it. A human
sees one "moved to Grafana" card and nothing else. The GCash top-up verify queue lived ONLY there.
That queue is the single control that mints every credit in the economy, so providers could file
top-ups forever and no reachable screen could approve one: **money could not enter the system.**
It sat like that for about two weeks.

WHY NOTHING CAUGHT IT:
  · MK13 (validate_reachable_capability) asks whether an EMPTY STATE promises a capability nothing
    can produce. A real control covered by an overlay is not an empty state. 0 findings, correctly.
  · The five founder specs call `window.svcTopupDecide(id, true)` by hand and read innerText off
    covered DOM. Both work perfectly through an overlay. 5/5 green, the whole time.
  · Every static validator still scans the page, because retiring it deliberately PRESERVES the
    markup so those ~35 validators keep passing. That preservation is what makes it dangerous:
    querySelector finds every element and innerText reads every number on a page no human can use.

THE INVARIANT: retiring a PAGE silently retires every control that only lives on it. So for each
retired page, every table it writes and every RPC it calls must ALSO be reachable from a page that
is not retired. If it is not, that capability was deleted, not relocated — and the deletion is
invisible, because the code is all still sitting right there.

Deterministic, offline, no browser. Forward-only: allowlist entries must carry a reason.

Usage:  python tools/validate_retired_page_sole_control.py [--selftest]
"""
import os
import re
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A page is RETIRED when it carries a full-viewport cover that nothing is expected to remove.
RETIRED_RE = re.compile(r"""id\s*=\s*["'][^"']*retired-overlay""", re.I)

# Writes a page performs. `.update(`/`.insert(`/`.upsert(`/`.delete(` chained off a db.from('table'),
# and db.rpc('fn'). Deliberately simple: this gate is about WHICH capability lives where, not about
# parsing JS properly.
FROM_RE = re.compile(r"""\.from\(\s*['"]([a-zA-Z0-9_]+)['"]\s*\)((?:[^;]|\n){0,400})""")
WRITE_RE = re.compile(r"\.(update|insert|upsert|delete)\s*\(")
RPC_RE = re.compile(r"""\.rpc\(\s*['"]([a-zA-Z0-9_]+)['"]""")

# ── ALLOWLIST: the capability is GONE ON PURPOSE, so its absence is the correct outcome ─────────────
# An entry without a reason is not an allowlist entry, it is a silenced failure.
ALLOWLIST = {
    ("marketplace-admin.html", "write:marketplace_disputes"):
        "RETIRED 2026-08-03 with the ghost lifecycle. marketplace_disputes held 0 rows and no client "
        "path ever wrote one; it described custody this platform refuses to have, and its console "
        "offered a 'Refund buyer' button for money that is never held. The capability SHOULD be "
        "unreachable — that is the fix, not the defect.",
    ("marketplace-admin.html", "write:marketplace_orders"):
        "same ghost lifecycle: 0 rows, no client writer, escrow states the platform cannot honour.",
}

# ── BASELINE: a REAL stranding, named and not yet resolved ──────────────────────────────────────────
# Deliberately NOT in the ALLOWLIST, because these are not deliberate deletions — they are the same
# collateral damage that hid the top-up queue, found by this gate on its first run. Baselined so the
# gate is a forward-only ratchet (any NEW stranding fails immediately) without pretending these are
# fine. Each must end in a decision: lift the control to a live surface, or retire the feature.
BASELINE = {
    ("founder-console.html", "write:service_vouchers"):
        "Voucher create/pause is unreachable. Vouchers mint `voucher_grant` — the only UNBACKED credits "
        "in the economy — so this is a money control, the same class as the top-up queue. Not lifted "
        "blindly: with commission now 0, validate_credit_solvency bounds total vouchers by everything "
        "ever EARNED, which is frozen at PHP360 of historical commission and will never grow. So the "
        "feature is nearly dead by arithmetic anyway. IAN'S CALL: lift the control, or retire vouchers.",
    ("founder-console.html", "write:platform_feedback"):
        "Feedback triage (status/disposition writes) is unreachable. Not money, but it means submitted "
        "feedback can be READ nowhere a human can act on. IAN'S CALL: lift to platform-actions, or "
        "accept that feedback is collected and never triaged.",
}


def page_files():
    return sorted(f for f in os.listdir(ROOT) if f.endswith(".html"))


def capabilities(text):
    """-> set of 'write:<table>' and 'rpc:<fn>' the page performs."""
    caps = set()
    for table, tail in FROM_RE.findall(text):
        if WRITE_RE.search(tail):
            caps.add(f"write:{table}")
    for fn in RPC_RE.findall(text):
        caps.add(f"rpc:{fn}")
    return caps


def scan(files_text):
    """files_text: {name: text} -> (findings, stats). Pure, so the self-test needs no disk."""
    retired = {n: t for n, t in files_text.items() if RETIRED_RE.search(t)}
    live = {n: t for n, t in files_text.items() if n not in retired}

    live_caps = set()
    for t in live.values():
        live_caps |= capabilities(t)

    findings, known = [], []
    for name, text in retired.items():
        for cap in sorted(capabilities(text)):
            if cap in live_caps or (name, cap) in ALLOWLIST:
                continue
            (known if (name, cap) in BASELINE else findings).append((name, cap))
    return findings, {"retired": len(retired), "live": len(live), "live_caps": len(live_caps),
                      "known": known}


def selftest():
    print("  selftest: a capability stranded on a retired page must FAIL; a relocated one must PASS")
    ok = True
    overlay = '<div id="wh-retired-overlay" style="position:fixed; inset:0; z-index:100000;">moved</div>'

    # stranded: only the retired page can verify a top-up
    f, _ = scan({
        "old.html": overlay + "db.from('service_credit_topups').update({status:'verified'}).eq('id',x)",
        "new.html": "db.from('marketplace_listings').update({status:'published'})",
    })
    if not any(c == "write:service_credit_topups" for _, c in f):
        print(f"  {RED}FAIL{RST} — a write stranded on a retired page was not caught"); ok = False

    # relocated: the same write exists on a live page -> not a finding
    f, _ = scan({
        "old.html": overlay + "db.from('service_credit_topups').update({status:'verified'}).eq('id',x)",
        "new.html": "db.from('service_credit_topups').update({status:'verified'}).eq('id',x)",
    })
    if f:
        print(f"  {RED}FAIL{RST} — a RELOCATED capability was reported as stranded: {f}"); ok = False

    # an RPC only the retired page calls is equally a deletion
    f, _ = scan({
        "old.html": overlay + "db.rpc('settle_everything', {})",
        "new.html": "db.from('x').update({})",
    })
    if not any(c == "rpc:settle_everything" for _, c in f):
        print(f"  {RED}FAIL{RST} — a stranded RPC was not caught"); ok = False

    # a page with no overlay is not retired, so nothing it hosts is stranded
    f, _ = scan({"a.html": "db.rpc('only_here', {})"})
    if f:
        print(f"  {RED}FAIL{RST} — a non-retired page was treated as retired: {f}"); ok = False

    # a READ on a retired page is not a capability deletion
    f, _ = scan({"old.html": overlay + "db.from('some_table').select('*')", "new.html": "x"})
    if f:
        print(f"  {RED}FAIL{RST} — a read-only reference was reported as a stranded write: {f}"); ok = False

    if ok:
        print(f"  {GREEN}PASS{RST} — catches stranded writes and RPCs, accepts relocated ones, "
              f"ignores reads and live pages")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Retired-page sole control{RST} — retiring a page must not silently delete a capability")
    if selftest() != 0:
        return 1

    files_text = {}
    for f in page_files():
        try:
            files_text[f] = open(os.path.join(ROOT, f), encoding="utf-8", errors="replace").read()
        except Exception:
            continue

    findings, stats = scan(files_text)
    print(f"  {DIM}pages: {stats['live']} live / {stats['retired']} retired · "
          f"{stats['live_caps']} capabilities reachable{RST}")

    # Known strandings are NOT silent. A baseline that prints nothing is an allowlist wearing a
    # ratchet's clothes, and the whole point of this gate is that the invisible stays visible.
    if stats["known"]:
        print(f"  {YEL}KNOWN{RST} — {len(stats['known'])} stranded capability(ies) awaiting a decision:")
        for name, cap in stats["known"]:
            print(f"    · {name}: {BOLD}{cap}{RST}")
            print(f"      {DIM}{BASELINE[(name, cap)]}{RST}")

    if findings:
        print(f"\n  {RED}FAIL{RST} — {len(findings)} capability(ies) exist ONLY on a retired page:")
        for name, cap in findings:
            print(f"    · {name} is the only host of {BOLD}{cap}{RST}")
        print(f"\n  {DIM}Retiring a page retires every control that only lives on it. Move the control "
              f"to a live surface, or add an ALLOWLIST entry stating why it is not a deletion.{RST}")
        return 1

    # The label is a claim. With known strandings outstanding, "everything is reachable" would be
    # flatly untrue — say what actually passed: no NEW stranding since the baseline.
    if stats["known"]:
        print(f"\n  {GREEN}PASS{RST} — no NEW stranding beyond the {len(stats['known'])} known above, "
              f"which are still awaiting a decision")
    else:
        print(f"\n  {GREEN}PASS{RST} — every write and RPC on a retired page is also reachable from a "
              f"live one")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
