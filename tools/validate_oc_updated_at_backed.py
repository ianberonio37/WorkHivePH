#!/usr/bin/env python3
"""validate_oc_updated_at_backed.py — every client `updated_at` write must be backed by a real column.

Born from a live bug-hunt (bughunt roadmap P6, 2026-07-17): pm-scheduler.html guarded pm_assets edits
with optimistic concurrency —
    _pmAssetUpdatedAt = currentAsset.updated_at || null;   // null: pm_assets had NO updated_at column
    .from('pm_assets').update({ ...updates, updated_at: now })  // phantom-column write
    if (_pmAssetUpdatedAt) q = q.eq('updated_at', snap);         // SKIPPED -> DEAD OC guard, lost-update OPEN
— static analysis saw "OC present" and missed it; only the live DB revealed the missing column.

This LIVE gate scans client pages for `.from('T')…​.update({…updated_at…})` (same-chain) and asserts
each table T has an `updated_at` column in the DB. A write to a column-less table = a dead OC guard +
a phantom-column write (a lost-update race + a likely 400 on the edit). FIX: ADD the column + reuse the
canonical `touch_updated_at()` trigger (as logbook / resume_documents / asset_nodes do).

Skips cleanly if docker/DB is unreachable (live gate). Exit 0 pass / 1 findings. --selftest = deterministic.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
EXCLUDE = ("node_modules", "remotion", "-test.", ".backup")
# same-statement .from('T') ... .update({ ...updated_at... }) — the reliable "writes updated_at to T" signal
WRITE_RE = re.compile(r"\.from\(\s*['\"]([a-z_]+)['\"]\s*\)[\s\S]{0,300}?\.update\(\s*\{[^{}]*\bupdated_at\b", re.I)


def scan_text(text: str) -> set[str]:
    return {m.group(1) for m in WRITE_RE.finditer(text)}


def scan_files() -> dict[str, set[str]]:
    hits: dict[str, set[str]] = {}
    for p in list(REPO.glob("*.html")) + list(REPO.glob("*.js")):
        if any(x in p.name for x in EXCLUDE):
            continue
        try:
            for t in scan_text(p.read_text(encoding="utf-8", errors="ignore")):
                hits.setdefault(t, set()).add(p.name)
        except Exception:
            continue
    return hits


def db_col(table: str) -> tuple[bool, bool]:
    """(db_reachable, has_updated_at_column)."""
    try:
        r = subprocess.run(
            ["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tAc",
             "SELECT 1 FROM information_schema.columns WHERE table_schema='public' "
             f"AND table_name='{table}' AND column_name='updated_at';"],
            capture_output=True, text=True, timeout=25)
        return r.returncode == 0, r.stdout.strip() == "1"
    except Exception:
        return False, False


def main() -> int:
    hits = scan_files()
    if not hits:
        print("OC updated_at backing: no client writes an updated_at payload — nothing to check.")
        return 0
    reachable, _ = db_col("pm_assets")
    if not reachable:
        print("OC updated_at backing: docker/DB unreachable — SKIPPED (live gate).")
        return 0
    missing = []
    for t in sorted(hits):
        _, has = db_col(t)
        if not has:
            missing.append((t, sorted(hits[t])))
    print(f"OC updated_at backing: {len(hits)} table(s) written with an updated_at payload; "
          f"{len(missing)} lack the column.")
    for t, files in missing:
        print(f"  ✗ {t}: client writes `updated_at` (in {', '.join(files)}) but the table has NO "
              f"updated_at column — DEAD optimistic-concurrency guard + phantom-column write (lost-update).")
    if missing:
        print("  FIX: ALTER TABLE public.<t> ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(); "
              "+ a BEFORE UPDATE trigger EXECUTE FUNCTION public.touch_updated_at().")
        return 1
    print("  ✓ every client updated_at write is backed by a real column.")
    return 0


def selftest() -> int:
    fails = []
    if "pm_assets" not in scan_text("db.from('pm_assets').update({ location: x, updated_at: now })"):
        fails.append("should capture a .from().update({...updated_at}) write")
    if scan_text("db.from('logbook').select('*').eq('id', x)"):
        fails.append("a pure select must NOT be captured")
    if scan_text("db.from('pm_assets').update({ location: x })"):
        fails.append("an update WITHOUT updated_at must NOT be captured")
    if "resume_documents" not in scan_text("await db.from('resume_documents').update({\n  doc: d, updated_at: t\n})"):
        fails.append("should capture across a short newline window")
    if fails:
        print("✗ validate_oc_updated_at_backed selftest FAILED:")
        for f in fails:
            print("   - " + f)
        return 1
    print("✓ validate_oc_updated_at_backed selftest passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
