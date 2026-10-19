#!/usr/bin/env python3
"""offline-sync-in-order - SL AV2 (2026-10-19/20): what a page writes while offline is either QUEUED - and then synced
once, in the order it was made, with everything that belongs to it - or REFUSED before anything is sent, in the
platform's own sentence. Never fired at a dead network and dropped, never promised and forgotten.

WHAT THE AV2 WALK FOUND (receipts SL1574-SL1606: 33 pages, phone-390 and desktop-1280, each as its row's cast; every
write flow of tools/prove_offline_queued.mjs, tools/prove_offline_refusal.mjs and tools/prove_double_fire.mjs pressed
with the network cut, then the network restored and every write the queue sent answered in the page; then two items put
through each registered queue, the first with the LATER key):
  * the shared queue (offline-queue.js) and logbook's own both drained getAll() - IndexedDB KEY order. Keys are random
    UUIDs, so two items made offline synced in whatever order their ids sorted (measured: made 1 then 2, synced 2 then
    1), and a server-stamped created_at then showed them swapped.
  * inventory: a part added offline queued its row, while its opening stock entry (the ledger qty_on_hand is mirrored
    from) and its audit row were fired at the dead network and lost; a Use or Restock offline fell back to an ABSOLUTE
    qty write and a ledger insert, both lost, under "This part did not save to the hive... try again".
  * resume said "Offline: saved on this device, will sync later" - nothing synced on reconnect, and the next load
    preferred the older cloud copy, so the next keystroke overwrote the offline work.
  * four online-only actions fired at the dead network and blamed something else: project-manager's change order ("the
    change-order number could not be generated"), analytics' risk recompute ("Recompute failed. Try again shortly."),
    shift-brain's re-run ("Run npx supabase functions serve" - a developer command, in production too), and the hive's
    focus and asset-hub's Weibull fit had no guard at all.

WHAT THIS HOLDS (static; the live floor stays with offline-queued, queue-drain and cg_offline_views):
  1. QUEUE - offline-queue.js stamps queued_at on enqueue (keeping a re-queued row's place) and drains in that order; an
     item may name its own table; op 'rpc' runs only a function the queue lists, and a refused replay is asked whether
     its row already exists (item.check) before it is retried. logbook's queue stamps and sorts the same way.
  2. INVENTORY - the opening entry and audit row queue behind the part; Use and Restock queue the atomic functions.
  3. RESUME - an offline save is marked pending, synced on 'online', and preferred over the cloud copy on load.
  4. GUARDS - the five online-only actions refuse before sending; no developer command reaches a person.

    python tools/validate_offline_sync_in_order.py
    python tools/validate_offline_sync_in_order.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# (file, regex that must match the code with comments stripped, what breaks without it)
ANCHORS = [
    ("offline-queue.js", r"item = Object\.assign\(\{\}, item, \{ queued_at: \(prev && prev\.queued_at\) \|\| _nextSeq\(\) \}\);",
     "the shared queue no longer stamps when an item was made (or loses a re-queued row's place)"),
    ("offline-queue.js", r"const pending = \(await getPending\(\)\)\.slice\(\)\.sort\(\(a, b\) => \(\(a && a\.queued_at\) \|\| 0\) - \(\(b && b\.queued_at\) \|\| 0\)\);",
     "the shared queue drains in KEY order again - two items made offline sync in the order their random ids sort"),
    ("offline-queue.js", r"const tbl = item\.table \|\| cfg\.table;",
     "a queue item can no longer name its own table - an action's companion rows cannot wait with it"),
    ("offline-queue.js", r"if \(!Array\.isArray\(cfg\.rpcs\) \|\| cfg\.rpcs\.indexOf\(item\.fn\) < 0\)",
     "a queued function call runs without the queue's allowlist"),
    ("offline-queue.js", r"if \(error && item\.check && item\.check\.table && item\.check\.id != null\)",
     "a refused replay of a call that already landed is retried into the dead-letter as 'stuck'"),
    ("logbook.html", r"payload = \{ \.\.\.payload, _queued_at: \(prev && prev\._queued_at\) \|\| _lbQueueSeq \};",
     "logbook's queue no longer stamps when an entry was logged"),
    ("logbook.html", r"pending = pending\.slice\(\)\.sort\(\(a, b\) => \(\(a && a\._queued_at\) \|\| 0\) - \(\(b && b\._queued_at\) \|\| 0\)\);",
     "logbook drains its queue in key order again"),
    ("inventory.html", r"rpcs: \['inventory_deduct', 'inventory_restock'\]",
     "inventory's queue cannot run the atomic stock functions"),
    ("inventory.html", r"if \(last && !navigator\.onLine && _ensureInvQueue\(\)\) \{\s*window\._whInvQueue\.enqueue\(\{ id: String\(last\.id\), op: 'insert', table: 'inventory_transactions'",
     "a part added offline loses its opening stock entry again"),
    ("inventory.html", r"op: 'insert', table: 'hive_audit_log', payload: _row",
     "an offline action's audit row is dropped again"),
    ("inventory.html", r"op: 'rpc', fn: 'inventory_deduct', dedupOk: true, check: \{ table: 'inventory_transactions', id: txnId \}",
     "an offline Use falls back to an absolute qty write fired at a dead network"),
    ("inventory.html", r"op: 'rpc', fn: 'inventory_restock', dedupOk: true, check: \{ table: 'inventory_transactions', id: txnId \}",
     "an offline Restock falls back to an absolute qty write fired at a dead network"),
    ("resume.html", r"if \(!navigator\.onLine\) \{ _pendingCloudSync = true;",
     "an offline resume save is not marked as ahead of the account"),
    ("resume.html", r"window\.addEventListener\('online', \(\) => \{ updateOfflineUI\(\); syncPendingDraft\(\); \}\);",
     "resume promises a sync it never makes when the network returns"),
    ("resume.html", r"if \(draft && draft\._pendingSync && draft\.resume && draft\.resume\.basics\) \{",
     "the next load prefers the older cloud copy over the offline work"),
    ("project-manager.html", r"whRequireOnline\('Submitting this change order'",
     "an offline change order fires at a dead network and blames the change-order number"),
    ("hive.html", r"whRequireOnline\(\"Saving your hive's focus\"",
     "the hive's focus is fired at a dead network offline"),
    ("shift-brain.html", r"whRequireOnline\('Re-running this shift plan'",
     "an offline shift-plan re-run fires and tells a supervisor to run a developer command"),
    ("analytics.html", r"whRequireOnline\('Recomputing risk scores'",
     "an offline risk recompute fires and says 'Recompute failed. Try again shortly.'"),
    ("asset-hub.html", r"whRequireOnline\('Computing this Weibull fit'",
     "an offline Weibull fit is fired at a dead network"),
]
# words a person must never be shown (a developer command), anywhere in a string a page can display
FORBIDDEN = [
    ("shift-brain.html", r"showToast\([^)]*npx supabase functions serve", "a developer command is a supervisor's toast again"),
]


def _code(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    return re.sub(r"(?m)(?<![:\"'`\\/])//[^\n]*$", "", src)


def problems(files: dict[str, str]) -> list[str]:
    bad = []
    for f, rx, why in ANCHORS:
        if not re.search(rx, _code(files.get(f, ""))):
            bad.append(f"{f}: {why}")
    for f, rx, why in FORBIDDEN:
        if re.search(rx, _code(files.get(f, ""))):
            bad.append(f"{f}: {why}")
    return bad


def load() -> dict[str, str]:
    return {f: (ROOT / f).read_text(encoding="utf-8") for f in sorted({a[0] for a in ANCHORS} | {b[0] for b in FORBIDDEN})}


def run() -> int:
    bad = problems(load())
    if bad:
        for b in bad:
            print("  FAIL " + b)
        print(f"FAIL offline-sync-in-order - {len(bad)} problem(s)")
        return 1
    print(f"PASS offline-sync-in-order - the queues drain in the order made, an action's companion rows and atomic stock "
          f"calls wait with it, a landed replay is recognised, resume keeps its sync promise, and five online-only actions "
          f"refuse before sending; {len(ANCHORS)} anchors hold, no developer command reaches a person")
    return 0


def self_test() -> int:
    ok = True

    def expect(name, cond):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + name)
        ok = ok and cond
    files = load()
    expect("the real tree passes", not problems(files))
    def mut(f, a, b):
        m = dict(files)
        assert a in m[f], (f, a[:50])
        m[f] = m[f].replace(a, b, 1)
        return bool([x for x in problems(m) if x.startswith(f + ":")])
    expect("drain back in key order fails", mut("offline-queue.js",
        "const pending = (await getPending()).slice().sort((a, b) => ((a && a.queued_at) || 0) - ((b && b.queued_at) || 0));",
        "const pending = await getPending();"))
    expect("no per-item table fails", mut("offline-queue.js", "const tbl = item.table || cfg.table;", "const tbl = cfg.table;"))
    expect("an rpc without the allowlist fails", mut("offline-queue.js",
        "if (!Array.isArray(cfg.rpcs) || cfg.rpcs.indexOf(item.fn) < 0)", "if (false)"))
    expect("logbook back in key order fails", mut("logbook.html",
        "pending = pending.slice().sort((a, b) => ((a && a._queued_at) || 0) - ((b && b._queued_at) || 0));", ""))
    expect("inventory's opening entry fired again fails", mut("inventory.html",
        "if (last && !navigator.onLine && _ensureInvQueue()) {", "if (false) {"))
    expect("resume without the reconnect sync fails", mut("resume.html",
        "window.addEventListener('online', () => { updateOfflineUI(); syncPendingDraft(); });",
        "window.addEventListener('online', updateOfflineUI);"))
    expect("the change-order guard removed fails", mut("project-manager.html",
        "whRequireOnline('Submitting this change order'", "whRequireOnline('x'"))
    m = dict(files)
    m["shift-brain.html"] = m["shift-brain.html"].replace("showToast(_SB_PLANNER_UNREACHED);",
        "showToast('Shift planner is offline locally. Run \"npx supabase functions serve\".');", 1)
    expect("the developer command back in a toast fails", any(x.startswith("shift-brain.html:") for x in problems(m)))
    print("PASS self-test" if ok else "FAIL self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
