"""validate_display_correctness_fixes.py — regression gate for the display-correctness
fixes shipped in the 2026-07-13 bug-hunt (BUGHUNT_2026-07-13.md).

Static "the fix is still present" gate (the platform's validate_revenue_surfaces pattern):
each fix leaves a distinctive code marker; a revert removes it → this gate FAILs. Complements
the LIVE validate_hive_write_isolation.py (RLS) — these defects are client-render logic that a
DB probe can't see. Cheap (file reads only), so it also runs under --fast.

Locks:
  1. achievements weekXP — "XP this week" summed from a dedicated 7-day window query
     (_weekXP), NOT the .limit(30) recent-activity list (limit-as-aggregate undercount).
  2. achievements init — a query ERROR surfaces whListError, not a fake "No achievements yet".
  3. asset-hub — "Total assets"/"Critical" tiles use an exact count:'exact' query, not the
     .limit(200)-capped _allNodes.length.
  4. ai-quality — loadCostLog/loadReplyFeedback throw on {error} instead of swallowing it as [].
  5. inventory — a supervisor fetches the full pending approval queue; stock counts exclude
     non-approved items.
  6. hive — adoption card shows a neutral "No data yet" tier when there's no snapshot (not a
     green "Healthy"); the PM-overdue count/banner reset on hive-switch.

Exit 0 = every marker present. Exit 1 = a fix regressed.
"""

import sys, re
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; BOLD = "\033[1m"; RESET = "\033[0m"
ROOT = Path(__file__).resolve().parent.parent

# (file, kind, needle, min_count, description)
#   kind 'sub' = substring must appear >= min_count times; 'not' = must NOT appear.
CHECKS = [
    ("achievements.html", "sub", "let _weekXP", 1,
     "weekXP: dedicated 7-day-sum global exists (not derived from the 30-row list)"),
    ("achievements.html", "sub", "_weekAgoIso", 1,
     "weekXP: dedicated window-scoped achievement_xp_log query"),
    ("achievements.html", "sub", "typeof _weekXP === 'number'", 1,
     "weekXP: summary prefers the dedicated sum over the capped list"),
    ("achievements.html", "sub", "if (achRes.error)", 1,
     "init: a query error surfaces whListError, not a fake 'No achievements yet'"),
    ("asset-hub.html", "sub", "_assetTotalCount", 3,
     "asset-hub: exact-count globals wired through render"),
    ("asset-hub.html", "sub", "count: 'exact', head: true", 1,
     "asset-hub: total/critical via an exact count, not the .limit(200) list length"),
    ("ai-quality.html", "sub", "if (error) throw error", 2,
     "ai-quality: both loaders throw on a query error instead of swallowing it as []"),
    ("ai-quality.html", "not", "schema_compliance, user_feedback", 1,
     "ai-quality: the unused/legacy user_feedback column was dropped from the cost-log select"),
    ("inventory.html", "sub", "['approved', 'pending', 'rejected']", 1,
     "inventory: supervisor fetch includes the full pending approval queue"),
    ("inventory.html", "sub", "!HIVE_ID || i.status === 'approved'", 1,
     "inventory: stock (out/low/critical) counts exclude non-approved items"),
    ("hive.html", "sub", "nodata", 2,
     "hive: adoption card has a neutral no-data tier and defaults to it (not 'healthy')"),
    ("hive.html", "sub", "reset PM-overdue count + banner on hive-switch", 1,
     "hive: _pmOverdueCount + banner reset on hive-switch (stale cross-hive count)"),
    # ── 2026-07-13 per-page bug-hunt (hive.html P1-P8) client-render fixes ──
    ("hive.html", "not", ".textContent = escHtml(", 1,
     "P4-01: no textContent=escHtml double-escape (escHtml into textContent renders &amp; literally)"),
    ("hive.html", "sub", "_pmHealthErr", 1,
     "P2-02: loadPMHealth distinguishes a read ERROR from empty (unavailable '—', not a fake-calm 0 hiding overdue PMs)"),
    ("hive.html", "sub", "_approvalReadErr", 1,
     "P2-01: loadApprovalQueue surfaces a read error ('couldn't load'), not a fake 'All caught up' empty"),
    ("hive.html", "sub", "Knowledge pipeline unavailable", 1,
     "P2-03: loadKnowledgePipeline honors {error} (load-error state), not a fake 'All corpora up to date'"),
    ("hive.html", "sub", "if (btn.disabled) return;", 1,
     "P7-01: createHive guards a double-submit (Enter+click) that minted duplicate/orphan hives"),
    ("hive.html", "sub", "eq('status', 'pending').select('id')", 2,
     "P6-C1: approveItem+rejectItem optimistic-lock on status='pending' (no concurrent re-flip of a resolved item)"),
    ("inventory.html", "sub", "&& !_invReadErr", 1,
     "inventory P2: a read error does NOT trigger the localStorage re-migration (would re-upsert stale local rows on a glitch)"),
    ("inventory.html", "sub", "&& !_assetReadErr", 1,
     "inventory P2: an asset read error does NOT trigger the localStorage asset re-migration"),
    ("inventory.html", "sub", "rpc('inventory_deduct'", 1,
     "inventory P6: Use routes through the ATOMIC inventory_deduct RPC (FOR UPDATE row-lock), not a client-computed absolute qty upsert (concurrent-Use lost-update fix, bug-hunt 2026-07-13)"),
    ("inventory.html", "sub", "rpc('inventory_restock'", 1,
     "inventory P6: Restock routes through the ATOMIC inventory_restock RPC (mig 20260713000008), not a client-computed absolute qty upsert (concurrent-Restock lost-update fix)"),
    ("asset-hub.html", "sub", "eq('status', 'pending').select('id')", 2,
     "P6-C1 sibling: approve/rejectAssetNode optimistic-lock on status='pending' (no cross-page concurrent re-flip)"),
    ("asset-hub.html", "sub", "is('acted_at', null)", 2,
     "P6-C1 sibling: staging accept/dismiss guard on acted_at (no double-act re-flip)"),
    ("project-manager.html", "sub", "eq('status', 'pending').select('id')", 2,
     "P6-C1 sibling: approveCO/rejectCO optimistic-lock (no reversal of an already-decided, cost-impacting change order)"),
    ("founder-console.html", "sub", "neq('status', 'resolved').select('id')", 1,
     "P6-C1 sibling: dispute-resolve optimistic-lock (no overwrite of an already-recorded admin decision)"),
]


def main() -> int:
    print(f"\n{BOLD}DISPLAY CORRECTNESS FIXES (static regression gate){RESET}")
    print("─" * 44)
    fails = 0
    cache = {}
    for fname, kind, needle, minc, desc in CHECKS:
        p = ROOT / fname
        if fname not in cache:
            cache[fname] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else None
        txt = cache[fname]
        if txt is None:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {fname}: file missing — {desc}")
            continue
        n = txt.count(needle)
        ok = (n == 0) if kind == "not" else (n >= minc)
        if ok:
            print(f"  {GREEN}PASS{RESET}  {fname}: {desc}")
        else:
            fails += 1
            want = "absent" if kind == "not" else f">={minc}"
            print(f"  {RED}FAIL{RESET}  {fname}: marker {needle!r} {want}, found {n} — {desc}")
    print(f"\n  Summary: {len(CHECKS) - fails} pass · {fails} fail")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
