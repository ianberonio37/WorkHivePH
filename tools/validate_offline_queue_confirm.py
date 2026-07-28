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


# ── LG9: an affordance the database will always refuse ───────────────────────
# logbook_update / logbook_delete are owner-scoped (`auth_uid = auth.uid()`) with NO supervisor
# branch, while logbook_read is hive-scoped — so the team feed correctly lists entries nobody but
# their author may change, and the detail modal offered Edit and Delete on every one of them.
# Verified live 2026-07-28 that the boundary itself is REAL (a direct update AND delete on a
# teammate's row, with the client filter removed, both affected 0 rows), so this was a dead
# affordance rather than a hole. The fix keeps the glass honest; this keeps the fix.
def audit_write_affordance_gating(src: str):
    """The entry-detail Edit/Delete buttons must be gated on an ownership predicate."""
    for name, body in _find_functions(src):
        if "openEditModal('${entry.id}')" not in body:
            continue
        if not re.search(r"_canWriteEntry\s*\(|entry\.worker_name\s*===?\s*WORKER_NAME|"
                         r"entry\.auth_uid\s*===?\s*_authUid", body):
            return [f"logbook.html:{name}() renders Edit/Delete for every entry - the team feed "
                    f"shows teammates' rows that owner-scoped RLS will always refuse to write"]
        return []
    return []


# ── LG9b: a write that is followed by an AUDIT-LOG entry ─────────────────────
# The worst shape found in this arc. asset_nodes_write requires `auth_uid = auth.uid()` (or
# supervisor), while the page's client guard scopes by worker_name — not the same test, and every
# seeded asset has auth_uid NULL, so a worker whose NAME matches passes the client check and is
# still refused. The 0-row result is not an error, so saveEditAsset() fell through and wrote a
# hive_audit_log entry for an edit that never happened, repainted the local cache, and propagated
# the new tag/name to pm_assets. Walked live: the DB kept the old name while the screen and the
# DOLE/ISO audit trail both recorded the change. An audit trail that records refused actions is
# worse than no audit trail, so any write whose success path calls writeAuditLog must confirm first.
_AUDITED_WRITE_FNS = ("saveEditAsset", "deleteAsset")


def audit_audited_write_confirmation(src: str):
    problems = []
    for name, body in _find_functions(src):
        if name not in _AUDITED_WRITE_FNS or "writeAuditLog" not in body:
            continue
        if not re.search(r"\.select\(", body):
            problems.append(f"logbook.html:{name}() writes an audit-log entry after a write it never "
                            f"confirmed - a 0-row refusal would be recorded as a real amendment")
            continue
        if not re.search(r"(updatedRows|deletedRows|\w+Rows)\s*(\|\||\.length|===)", body):
            problems.append(f"logbook.html:{name}() calls .select(...) but never checks the returned "
                            f"rows before writing to the audit log")
    return problems


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

    # LG9 — the pre-fix modal offered Edit/Delete on every entry, including teammates'.
    prefix_modal = """
    function openModal(id) {
      const entry = _allEntries.find(e => e.id === id);
      el.innerHTML = `
        <div class="flex gap-2">
          <button onclick="openEditModal('${entry.id}')">Edit Entry</button>
          <button onclick="confirmDelete('${entry.id}')">Delete</button>
        </div>`;
    }
    """
    chk("ungated Edit/Delete is caught", len(audit_write_affordance_gating(prefix_modal)), 1)

    fixed_modal = prefix_modal.replace('el.innerHTML = `', 'el.innerHTML = `${_canWriteEntry(entry) ? `')
    chk("ownership-gated Edit/Delete passes", len(audit_write_affordance_gating(fixed_modal)), 0)

    # LG9b — an audited write that never confirmed the write landed.
    prefix_audited = """
    async function saveEditAsset() {
      let q = db.from('asset_nodes').update(updates).eq('id', id);
      const { error } = await q;
      if (error) { showErr(error.message); return; }
      writeAuditLog('edit_asset', 'assets', id, asset_id, { name: updates.name });
    }
    """
    chk("unconfirmed audited write is caught", len(audit_audited_write_confirmation(prefix_audited)), 1)

    fixed_audited = """
    async function saveEditAsset() {
      let q = db.from('asset_nodes').update(updates).eq('id', id);
      const { data: updatedRows, error } = await q.select('id');
      if (error) { showErr(error.message); return; }
      if (!updatedRows || updatedRows.length === 0) { showErr('not yours'); return; }
      writeAuditLog('edit_asset', 'assets', id, asset_id, { name: updates.name });
    }
    """
    chk("confirmed audited write passes", len(audit_audited_write_confirmation(fixed_audited)), 0)

    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def audit_retry_idempotency():
    """PM18: a retry after a LOST RESPONSE must not be reported as stuck work.

    The shared drain re-inserts a queued item whose reply never arrived. Where the table carries a
    dedup UNIQUE index, that second insert correctly raises 23505 — and treating it as an error sent
    the item through the backoff into the dead-letter, so the widget told the worker their PM was
    STUCK when it was already saved. That is the mirror of the 0-row bug this gate exists for: one
    claims a write that never happened, the other denies one that did.

    The handling is deliberately OPT-IN (`insertDedupIndexed`), because it is only sound when the
    unique index is a true idempotency key for the same logical write. Both halves are asserted: the
    shared drain still knows how, and pm_completions — whose index is
    (scope_item_id, worker_name, date) — still opts in.
    """
    problems = []
    q = (ROOT / "offline-queue.js")
    if q.exists():
        src = q.read_text(encoding="utf-8", errors="replace")
        if "insertDedupIndexed" not in src:
            problems.append("offline-queue.js no longer honours insertDedupIndexed — a retry after a "
                            "lost response would be dead-lettered as stuck work that is already saved")
        elif not re.search(r"23505", src):
            problems.append("offline-queue.js checks insertDedupIndexed but no longer recognises "
                            "23505, so the duplicate-on-retry is still treated as a failure")
        if re.search(r"insertDedupIndexed:\s*true", src):
            problems.append("offline-queue.js defaults insertDedupIndexed to TRUE — it must stay "
                            "opt-in: where a unique column can be owned by a DIFFERENT row "
                            "(skill_profiles.worker_name) a 23505 means the write did not land")
    # PM18 second persona (2026-07-28): the queue is per-DEVICE and this file names shared tablets as
    # the operating reality, but the identity guard was an .eq() on the update/delete WHERE clause
    # only — an insert has no WHERE. So a drain running under worker B attempted worker A's queued
    # completion, and the DB did not refuse it: bind_pm_completion_submitter sets
    # NEW.auth_uid := auth.uid() and overwrites worker_name from the session, so A's PM was recorded
    # as B's work. The trigger is correct (it is what stops forged attribution); the drain must not
    # offer it the choice. Asserted as a SKIP — the item stays queued for its owner rather than
    # erroring into the dead-letter.
    if q.exists():
        src = q.read_text(encoding="utf-8", errors="replace")
        drain = next((b for n, b in _find_functions(src) if n == "drain"), "")
        if not re.search(r"item\.payload\s*&&\s*item\.payload\[\s*cfg\.identityKey", drain):
            problems.append("offline-queue.js drain() no longer compares the item's CAPTURED "
                            "identity against the current one before attempting it — on a shared "
                            "tablet another worker's queued insert gets re-attributed to whoever "
                            "drains it")
        elif not re.search(r"captured\s*!==\s*current\s*\)\s*continue", drain):
            problems.append("offline-queue.js drain() compares identities but does not SKIP on a "
                            "mismatch — a foreign item must stay queued, not error into the "
                            "dead-letter")

    pm = (ROOT / "pm-scheduler.html")
    if pm.exists():
        src = pm.read_text(encoding="utf-8", errors="replace")
        if "whCreateQueue" in src and not re.search(r"insertDedupIndexed:\s*true", src):
            problems.append("pm-scheduler.html queues pm_completions but no longer opts in to "
                            "insertDedupIndexed — its dedup index would make every retry look stuck")
    return problems


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
            v += audit_write_affordance_gating(src)
            v += audit_audited_write_confirmation(src)
        checked += len(drains)
        all_violations += v
        status = f"{RED}FAIL{RESET}" if v else f"{GREEN}OK  {RESET}"
        names = ", ".join(n + "()" for n, _ in drains) or "no drain found"
        print(f"  {status}  {fname} — {names}  ({why})")
        for line in v:
            print(f"          {RED}->{RESET} {line}")

    retry = audit_retry_idempotency()
    if retry:
        print(f"  {RED}FAIL{RESET}  retry idempotency (PM18)")
        for line in retry:
            print(f"          {RED}->{RESET} {line}")
        all_violations += retry
    else:
        print(f"  {GREEN}OK  {RESET}  retry idempotency — a re-insert refused by a dedup index "
              f"drains instead of dead-lettering saved work")

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
