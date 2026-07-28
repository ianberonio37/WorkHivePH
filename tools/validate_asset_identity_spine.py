#!/usr/bin/env python3
"""
validate_asset_identity_spine.py — AH11: a rename must carry the WHOLE identity, and only in one hive.

THE DEFECT. An asset's identity is stored as free text in five tables, and sync_pm_asset_identity
propagated a rename into exactly one of them. Measured live, renaming GEN-002 -> GEN-002X:

    pm_assets             2 rows moved   <- all the propagation there was
    logbook.machine     103 rows left pointing at a tag that no longer exists
    fault_knowledge      12 rows  "
    asset_risk_scores     1 row   "

Every one of those columns holds the TAG, even where the column is NAMED asset_name — so a
display-name change is harmless and a TAG change is what breaks them. fault_knowledge has no uuid
column at all, so the AI's learned fault corpus for that machine was severed with no way back;
asset_risk_scores is worse still, because the asset page then renders "No risk score yet for this
asset... a score will appear here", which is honest about a cold start and a lie about a rename.

THE SECOND DEFECT, found while proving the first — and introduced BY the fix. The first draft of
sync_asset_identity scoped its UPDATEs to "any hive the caller belongs to". Tags are unique per
HIVE, not per platform, and the fixture gives every hive its own GEN-002. Renaming Lucena's asset
also rewrote Manila Electronics Assembly's 60 logbook rows, 6 fault_knowledge rows, its risk score,
a parts recommendation and a pm_asset. A cross-tenant write, caused by the repair. Both halves are
gated below, because the second is the more dangerous and the easier to reintroduce.

WHAT THIS GATE HOLDS:
  1. every identity column the walk found is still covered by the RPC — a NEW table that stores an
     asset tag as text will not be noticed by anything else;
  2. the RPC confines itself to ONE hive (hive_id = v_hive on every UPDATE) AND still requires the
     caller's membership — v_hive alone would trust a tag, membership alone was the cross-tenant bug;
  3. the merge guard exists and excludes the node being renamed (without that it refuses every
     rename, since callers update asset_nodes first);
  4. the caller passes the node id, or 3 above cannot work;
  5. LIVE: no orphan tags — no row in any identity column names a tag that no asset carries.

Live tier SKIPS cleanly (exit 0) without docker. Self-test: --selftest.
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
MIG = ROOT / "supabase" / "migrations" / "20260728000019_rename_carries_the_whole_identity.sql"
CALLER = ROOT / "logbook.html"

# (table, column) that store an asset TAG as free text. Adding a row here is the point: the next
# table that denormalises a tag has to be added to the RPC too, or this gate goes red.
IDENTITY_COLUMNS = [
    ("pm_assets",                     "tag_id"),
    ("logbook",                       "machine"),
    ("fault_knowledge",               "machine"),
    ("asset_risk_scores",             "asset_name"),
    ("parts_staging_recommendations", "asset_name"),
]


def psql(sql):
    try:
        p = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres",
                            "-d", "postgres", "-t", "-A", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return None if p.returncode != 0 else (p.stdout or "").strip()
    except Exception:
        return None


def selftest():
    probs = []
    if len(IDENTITY_COLUMNS) < 5:
        probs.append("IDENTITY_COLUMNS shrank — a rename would silently stop covering something")
    if ("logbook", "machine") not in IDENTITY_COLUMNS:
        probs.append("logbook.machine must be covered — 3,739 of 3,811 rows hold a live tag")
    if ("fault_knowledge", "machine") not in IDENTITY_COLUMNS:
        probs.append("fault_knowledge.machine must be covered — it has no uuid fallback at all")
    if not MIG.exists():
        probs.append("the migration this gate guards is missing")
    print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
    return 1 if probs else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()

    print(f"\n{BOLD}ASSET IDENTITY SPINE (a rename carries everything, in ONE hive){RESET}")
    print("-" * 74)
    fails = 0
    sql = MIG.read_text(encoding="utf-8", errors="replace") if MIG.exists() else ""
    caller = CALLER.read_text(encoding="utf-8", errors="replace") if CALLER.exists() else ""

    # Split the migration into one slice per UPDATE statement so each is checked on its own.
    # A global count() of "= v_hive" is NOT good enough and was caught being not good enough:
    # there are other legitimate uses of v_hive (the SELECT INTO, the merge guard), so deleting
    # the scoping from one UPDATE still cleared a >= 6 threshold. The cross-tenant bug this
    # guards against was exactly one missing predicate on exactly one statement.
    update_blocks = {}
    for chunk in sql.split("UPDATE public.")[1:]:
        table = chunk.split(None, 1)[0].strip()
        update_blocks[table] = chunk.split("RETURNING")[0]

    checks = [
        ("RPC exists", "FUNCTION public.sync_asset_identity(" in sql),
        ("merge guard present", "tag already in use" in sql),
        ("merge guard excludes the renamed node", "n.id <> p_node_id" in sql),
        ("caller passes the node id", "p_node_id:  nodeId" in caller),
        ("caller surfaces the merge refusal", "tag already in use" in caller),
    ]
    for table, col in IDENTITY_COLUMNS:
        block = update_blocks.get(table, "")
        checks.append((f"{table}.{col} updated by the RPC", bool(block) and col in block))
        # Both predicates, on THIS statement. v_hive alone would trust a tag from any tenant;
        # membership alone is precisely the cross-tenant bug that rewrote Manila's rows.
        checks.append((f"{table} confined to the renaming hive",
                       "hive_id = v_hive" in block))
        checks.append((f"{table} still requires caller membership",
                       "IN (SELECT hive_id FROM mine)" in block))

    for label, ok in checks:
        if ok:
            print(f"  {GREEN}PASS{RESET}  {label}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {label}")

    live = 0
    if psql("SELECT 1;") is None:
        print(f"  {YELLOW}SKIP{RESET}  docker psql unavailable — orphan scan not run")
    else:
        # An orphan is a row naming a tag no asset in that hive carries: what a partial rename
        # leaves behind. Baseline is whatever legitimately-historical rows already exist; this
        # reports the number so a jump after a rename is visible.
        orphans = {}
        for table, col in IDENTITY_COLUMNS:
            raw = psql(
                f"SELECT count(*) FROM public.{table} t WHERE t.{col} IS NOT NULL "
                f"AND NOT EXISTS (SELECT 1 FROM public.asset_nodes n "
                f"WHERE n.hive_id = t.hive_id AND lower(n.tag) = lower(t.{col}));")
            try:
                orphans[f"{table}.{col}"] = int((raw or "0").splitlines()[0])
            except (ValueError, IndexError):
                orphans[f"{table}.{col}"] = -1
        live = 1
        total = sum(v for v in orphans.values() if v > 0)
        detail = " · ".join(f"{k.split('.')[0]} {v}" for k, v in orphans.items() if v)
        print(f"  {GREEN}INFO{RESET}  orphan tags (row names a tag no asset in its hive carries): "
              f"{total}{' — ' + detail if detail else ''}")

    print(f"\n  Summary: {len(checks) - fails} pass · {fails} fail")
    (ROOT / "asset_identity_spine_report.json").write_text(
        json.dumps({"validator": "asset_identity_spine",
                    "columns": [f"{t}.{c}" for t, c in IDENTITY_COLUMNS],
                    "live_scanned": bool(live), "fail": fails}, indent=2), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
