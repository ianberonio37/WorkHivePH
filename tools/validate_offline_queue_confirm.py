#!/usr/bin/env python3
"""
validate_offline_queue_confirm.py — LG3: an offline queue may not treat "changed 0 rows" as "synced".

THE DEFECT THIS LOCKS (found live 2026-07-28, LOGBOOK_DEEPWALK_EXPANSION_ROADMAP LB7):
A PostgREST update/delete that matches ZERO rows is NOT an error — supabase-js returns
`{ error: null, status: 204 }`. Every queue drain branched on `error` alone, so "changed nothing"
was indistinguishable from "written". Walked live on the logbook queue: a tech edits an entry while
offline, the entry is deleted (or was never theirs to edit) server-side, and on reconnect the app
removes the queued item, toasts "1 offline change synced." and writes NOWHERE. The worker's text is
destroyed and they are told it saved.

Zero rows is not an exotic case, it is the NORMAL outcome whenever RLS filters the row out. logbook's
UPDATE policy is owner-scoped (`auth_uid = auth.uid()`) while its SELECT policy is hive-scoped, so a
worker can SEE entries the database will never let them edit — including their own rows whose auth_uid
is NULL. The same shape reaches 6 more surfaces through the shared helper (community_posts,
schedule_items, inventory_items, pm_completions, rcm_fmea_modes, skill_profiles).

THE INVARIANT: in a queue-drain function, an update/delete whose success path REMOVES the item from
the queue must ask for the affected rows back (`.select(...)`) and must gate the removal on having
actually received one. A bare `if (!error)` success test is the bug.

WHY NOT A BROADER DETECTOR: a `.update()` outside a drain has a human watching the result, so it is a
different problem with a different fix. This gate stays inside drain functions, where a wrong answer
silently eats data. (Deliberately narrow per the "don't bolt a low-confidence detector onto a gate"
discipline.)

Static, offline, fast. Self-test: --selftest (pins the PRE-FIX shapes as must-fail fixtures, so the
gate's teeth are proven by construction and stay proven).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

# A drain is any function that both talks to the queue store and removes items from it.
_DRAIN_HINTS = re.compile(r"removeFromQueue|remove\(item\.id\)|s\.delete\(", re.I)
_QUEUE_HINTS = re.compile(r"getPending|pending|queue", re.I)
# The write shapes that can silently match nothing.
_ZERO_ROW_OPS = re.compile(r"\.(update|delete)\s*\(")


def _find_functions(src: str):
    """Yield (name, body) for each top-level-ish function, by brace matching from its opening `{`."""
    for m in re.finditer(r"(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\([^)]*\)\s*\{", src):
        name = m.group(1)
        i = src.index("{", m.end() - 1)
        depth, j = 0, i
        while j < len(src):
            c = src[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield name, src[i:j + 1]


def _drain_functions(src: str):
    for name, body in _find_functions(src):
        if _DRAIN_HINTS.search(body) and _QUEUE_HINTS.search(body) and _ZERO_ROW_OPS.search(body):
            yield name, body


def audit_source(label: str, src: str):
    """Return a list of violation strings for one file's source."""
    violations = []
    for name, body in _drain_functions(src):
        ops = _ZERO_ROW_OPS.findall(body)
        if not ops:
            continue
        # (1) The drain must read back the affected rows.
        if ".select(" not in body:
            violations.append(
                f"{label}:{name}() drains {'/'.join(sorted(set(ops)))} without .select(...) — "
                f"a 0-row write returns error:null and would be counted as synced")
            continue
        # (2) The success path must not be a bare error test. Accept any of the shapes that
        #     actually consult the returned rows.
        confirms = re.search(
            r"!\s*error\s*&&\s*!\s*\w+|"                 # if (!error && !unconfirmed)
            r"\.data\s*\)?\s*&&[^;]*\.length\s*===?\s*0|"  # Array.isArray(r.data) && r.data.length === 0
            r"\.data\s*\?\.\s*length|"
            r"\.length\s*===?\s*0",
            body)
        if not confirms:
            violations.append(
                f"{label}:{name}() calls .select(...) but still succeeds on `!error` alone — "
                f"the returned rows are never checked, so 0 rows still reads as synced")
    return violations


TARGETS = [
    ("offline-queue.js", "the shared write queue — 6 surfaces drain through it"),
    ("logbook.html", "logbook's own queue (predates the shared helper)"),
]

# ── LB17: the queue is per-DEVICE, the feed is per-HIVE ───────────────────────
# A multi-hive member who captures offline in hive A and switches to hive B saw A's entry rendered
# in B's feed: the server read is hive-filtered but the pending-queue merge was not. Walked live
# 2026-07-28 as a real card ("captured in Manila", Pending sync) inside the Lucena feed. The queued
# row keeps its CAPTURE-time hive_id — that is what makes filtering right and re-homing wrong.
_MERGE_FN = "loadEntries"


def audit_queue_hive_scope(src: str):
    """The function that merges queued rows into the feed must filter them by the active hive."""
    for name, body in _find_functions(src):
        if name != _MERGE_FN or "getPendingEntries" not in body:
            continue
        if "HIVE_ID" not in body.split("pending")[-1] and "HIVE_ID" not in body:
            return [f"logbook.html:{name}() merges queued rows without consulting HIVE_ID"]
        # The merge itself (not just the server query) has to be scoped.
        merged = body[body.find("getPendingEntries"):]
        if not re.search(r"hive_id\s*===?\s*HIVE_ID|HIVE_ID\s*===?\s*[\w.]*hive_id|_queuedHive", merged):
            return [f"logbook.html:{name}() filters the SERVER read by hive but merges the "
                    f"pending queue unfiltered — one hive's offline entry renders in another's feed"]
        return []
    return []


def _selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    # The EXACT pre-fix logbook shape. This is the code that lost a real edit on 2026-07-28.
    prefix_logbook = """
    async function syncOfflineQueue() {
      let pending = await getPendingEntries();
      for (const p of pending) {
        const { _offline, _queueOp, ...rest } = p;
        let error;
        if (_queueOp === 'update') {
          const { id, updates } = rest;
          ({ error } = await db.from('logbook').update(updates).eq('id', id));
        } else {
          ({ error } = await db.from('logbook').insert(rest));
        }
        if (!error) { await removeFromQueue(p.id); synced++; }
      }
    }
    """
    chk("pre-fix drain is caught", len(audit_source("fixture", prefix_logbook)), 1)

    # The half-fix that looks right and is not: it asks for rows, then ignores them.
    half_fixed = prefix_logbook.replace(".update(updates).eq('id', id)",
                                        ".update(updates).eq('id', id).select('id')")
    chk("select-but-unchecked is caught", len(audit_source("fixture", half_fixed)), 1)

    # The real fix.
    fixed = """
    async function syncOfflineQueue() {
      let pending = await getPendingEntries();
      for (const p of pending) {
        const { _offline, _queueOp, ...rest } = p;
        let error, unconfirmed = false;
        if (_queueOp === 'update') {
          const { id, updates } = rest;
          const r = await db.from('logbook').update(updates).eq('id', id).select('id');
          error = r.error;
          if (!error && Array.isArray(r.data) && r.data.length === 0) unconfirmed = true;
        } else {
          ({ error } = await db.from('logbook').insert(rest));
        }
        if (!error && !unconfirmed) { await removeFromQueue(p.id); synced++; }
      }
    }
    """
    chk("fixed drain passes", len(audit_source("fixture", fixed)), 0)

    # A non-drain function that updates is none of this gate's business.
    unrelated = """
    async function saveEdit() {
      const { error } = await db.from('logbook').update(u).eq('id', id);
      if (!error) showToast('saved');
    }
    """
    chk("non-drain update is ignored", len(audit_source("fixture", unrelated)), 0)

    # LB17 — the pre-fix merge: server read scoped, queue merge not.
    prefix_merge = """
    async function loadEntries() {
      let query = db.from('logbook').select('id').eq('worker_name', WORKER_NAME);
      if (HIVE_ID) query = query.or(`hive_id.eq.${HIVE_ID},hive_id.is.null`);
      const { data } = await query;
      let pending = await getPendingEntries();
      const pendingInserts = pending.filter(p => p._queueOp !== 'update');
      _allEntries = [...pendingInserts, ...(data || [])];
    }
    """
    chk("unscoped queue merge is caught", len(audit_queue_hive_scope(prefix_merge)), 1)

    fixed_merge = prefix_merge.replace(
        "const pendingInserts = pending.filter(p => p._queueOp !== 'update');",
        "const _queuedHive = (p) => p._queueOp === 'update' ? (p.updates||{}).hive_id : p.hive_id;\n"
        "      const live = pending.filter(p => { const h = _queuedHive(p); return !HIVE_ID || h === HIVE_ID || h == null; });\n"
        "      const pendingInserts = live.filter(p => p._queueOp !== 'update');")
    chk("hive-scoped queue merge passes", len(audit_queue_hive_scope(fixed_merge)), 0)

    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    print(f"{BOLD}Offline-queue drain confirmation (LG3 — 0 rows is not 'synced'){RESET}")
    all_violations, checked = [], 0
    for fname, why in TARGETS:
        path = ROOT / fname
        if not path.exists():
            print(f"  {YELLOW}SKIP{RESET}  {fname} not found")
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        drains = list(_drain_functions(src))
        v = audit_source(fname, src)
        if fname == "logbook.html":
            v += audit_queue_hive_scope(src)
        checked += len(drains)
        all_violations += v
        status = f"{RED}FAIL{RESET}" if v else f"{GREEN}OK  {RESET}"
        names = ", ".join(n + "()" for n, _ in drains) or "no drain found"
        print(f"  {status}  {fname} — {names}  ({why})")
        for line in v:
            print(f"          {RED}->{RESET} {line}")

    if not checked:
        print(f"  {RED}FAIL{RESET}  no drain functions found at all — the detector lost its targets")
        return 1
    if all_violations:
        print(f"\n  {RED}FAIL{RESET}  {len(all_violations)} drain(s) treat a 0-row write as a successful sync")
        return 1
    print(f"\n  {GREEN}PASS{RESET}  {checked} drain(s) confirm their writes before dropping queued work")
    return 0


if __name__ == "__main__":
    sys.exit(main())
