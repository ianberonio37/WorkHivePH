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

SECOND LENS — A STRANDED **READ** (added 2026-08-04, after this gate's own blind spot cost us):
this file used to assert, in its self-test, that "a READ on a retired page is not a capability
deletion". That is true of CONTROLS and false of VISIBILITY. The credit treasury proved it: the
only reader of `issued_credits` / `v_credit_posture` was founder-console.html, so on a platform
whose whole design is "cash enters once and never leaves", nobody could see how much had been
issued or whether it was covered — and migration 42's correction of that number (0 -> PHP1,500)
landed where no human could look. This gate ran GREEN through all of it, because a dashboard
writes nothing.

So a read is stranded when NO live page reads the same surface. Two honest caveats, both handled
by evidence rather than cleverness:
  · a read can be RELOCATED INTO AN RPC (hive readiness moved to `get_hive_readiness_current`),
    which no table-name match will ever see. That is an ALLOWLIST entry citing the live caller,
    not a heuristic — guessing which RPC "covers" which table is how a gate swallows a real one.
  · a `.from(x).insert(...).select()` is a write echoing its own row back, not a reader of x. A
    `.from()` counts as a read only when the chain selects and does NOT write.

What a stranded read actually means is worth stating plainly: the platform is still PAYING to
write those rows — telemetry, traces, ledger entries — and no human can read them. Write-only
data is not a tidiness problem; it is a cost with no reader.

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
# A chain that selects and does NOT write is a reader. The `not WRITE_RE` half matters: an insert
# that echoes its row back with .select() is a write, and counting it as a read would let a live
# page's insert "cover" a retired page's dashboard.
SELECT_RE = re.compile(r"\.select\s*\(")

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
    ("marketplace-admin.html", "read:marketplace_disputes"):
        "the ghost queue's READER. It rendered 'No open disputes' for a queue no buyer could file "
        "into — the MK13 defect itself. Unreachable is the fix.",

    # ── vouchers: RETIRED BY DECISION, so both the control and its reader are correctly gone ──
    ("founder-console.html", "write:service_vouchers"):
        "Vouchers were retired by decision (Ian: no vouchers). mig 36 replaced the redeem path with a "
        "refusing stub and mig 45 repaired that stub's signature — so redemption REFUSES by design. A "
        "create/pause control for a mechanic that refuses would be the defect, not its absence. "
        "(Was BASELINE 'IAN'S CALL' until 2026-08-04; the call was made, so this is now deliberate.)",
    ("founder-console.html", "read:service_vouchers"):
        "reader for the same retired mechanic — see write:service_vouchers.",
    ("founder-console.html", "read:service_voucher_redemptions"):
        "redemption history for a mechanic that now refuses. No live surface should promise it.",

    # ── relocated into an RPC, which no table-name match can ever see ──
    ("founder-console.html", "read:v_hive_readiness_truth"):
        "NOT stranded: readiness relocated to an RPC. hive.html:2572 calls "
        "`get_hive_readiness_current`, and plant-connections / pm-scheduler / project-manager / "
        "shift-brain all surface readiness live. Verified by reading the call sites, not inferred "
        "from the name — an RPC whose name merely resembles a table is exactly how a gate would "
        "swallow a real stranding.",
}

# ── BASELINE: a REAL stranding, named and not yet resolved ──────────────────────────────────────────
# Deliberately NOT in the ALLOWLIST, because these are not deliberate deletions — they are the same
# collateral damage that hid the top-up queue, found by this gate on its first run. Baselined so the
# gate is a forward-only ratchet (any NEW stranding fails immediately) without pretending these are
# fine. Each must end in a decision: lift the control to a live surface, or retire the feature.
# RESOLVED and deliberately deleted from this dict, because a baseline that outlives its defect
# becomes a lie the next session believes:
#   · write:platform_feedback — LIFTED 2026-08-04 to platform-actions.html (triage card + drawer +
#     realtime + the OCC guard). The gate now sees it live and says nothing, which is correct.
#   · write:service_vouchers — DECIDED (no vouchers); moved to ALLOWLIST with the migration evidence.
BASELINE = {
    ("founder-console.html", "read:analytics_events"):
        "WRITE-ONLY TELEMETRY. Live pages still emit analytics_events; the only page that ever READ "
        "them back (hive reach over 30 days, event rollups) is retired. So the platform pays to "
        "store rows no human can see. Not money and not urgent — but it is the treasury shape "
        "exactly, and it stays printed until someone decides: surface it, or stop writing it.",
    ("agentic-rag-observability.html", "read:agentic_rag_traces"):
        "WRITE-ONLY TRACES. supabase/functions/agentic-rag-loop/index.ts writes a trace per RAG "
        "call and the only reader is retired, so RAG behaviour is unobservable while still being "
        "recorded. The page's own overlay says 'moved to Grafana' — if that is true the traces "
        "should flow there and this table should stop being written; if it is not, the reader "
        "needs a live home. Either way it is a decision, not a silence.",
}


def page_files():
    return sorted(f for f in os.listdir(ROOT) if f.endswith(".html"))


def capabilities(text):
    """-> set of 'write:<table>', 'rpc:<fn>' and 'read:<table>' the page reaches.

    Reads share the finding pipeline with writes on purpose: allowlist, baseline and ratchet all
    behave identically, and the only thing that differs is the sentence printed for a human.
    """
    caps = set()
    for table, tail in FROM_RE.findall(text):
        if WRITE_RE.search(tail):
            caps.add(f"write:{table}")
        elif SELECT_RE.search(tail):
            caps.add(f"read:{table}")
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

    # ── the READ lens. This block replaces a self-test that used to assert the OPPOSITE ("a read on
    # a retired page is not a deletion"). That assertion is what let the credit treasury hide.
    # a read nothing live performs = the only window onto that data is behind an overlay
    f, _ = scan({"old.html": overlay + "db.from('v_credit_posture').select('*')", "new.html": "x"})
    if not any(c == "read:v_credit_posture" for _, c in f):
        print(f"  {RED}FAIL{RST} — a stranded READ was not caught (the treasury blind spot)"); ok = False

    # the same read from a live page = relocated, not stranded
    f, _ = scan({
        "old.html": overlay + "db.from('v_credit_posture').select('*')",
        "new.html": "db.from('v_credit_posture').select('liability')",
    })
    if f:
        print(f"  {RED}FAIL{RST} — a relocated READ was reported as stranded: {f}"); ok = False

    # an insert that echoes its own row back is a WRITE, not a reader. If this regressed, a live
    # page's insert would silently "cover" a retired page's dashboard and the gate would go quiet.
    f, _ = scan({
        "old.html": overlay + "db.from('t').select('*')",
        "new.html": "db.from('t').insert({a:1}).select()",
    })
    if not any(c == "read:t" for _, c in f):
        print(f"  {RED}FAIL{RST} — an insert().select() was miscounted as a live READER"); ok = False

    if ok:
        print(f"  {GREEN}PASS{RST} — catches stranded writes, RPCs and READS; accepts relocated "
              f"ones; does not mistake an insert().select() for a reader")
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
            what = "the only READER of" if cap.startswith("read:") else "the only host of"
            print(f"    · {name} is {what} {BOLD}{cap}{RST}")
        if any(c.startswith("read:") for _, c in findings):
            print(f"\n  {DIM}A stranded READ means the data is still being WRITTEN and no human can "
                  f"see it. Give it a live reader, stop writing it, or allowlist it with the "
                  f"evidence — including 'relocated into an RPC', which needs the live call site.{RST}")
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
