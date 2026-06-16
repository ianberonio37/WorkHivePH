#!/usr/bin/env python3
"""verify_backups.py - Pillar DR (Delivery & Recovery): backup / restore integrity.
================================================================================
In a Supabase stack the SCHEMA backup IS the migration set: the database is fully
reproducible from `supabase/migrations/*.sql` + the `migration_hashes.json` lock.
A "backup is verified" claim therefore means: the migration set is COMPLETE,
UNCHANGED (would reproduce prod byte-for-byte), and a documented restore path
exists. This tool proves exactly that - locally, reading files only, $0.

Checks:
  L1  Coverage   - every migration .sql has a recorded sha256 (untracked = WARN:
                   a new migration not yet locked; a restore from the lock would
                   miss it).
  L2  Integrity  - no hash DRIFT: recorded migrations still hash to their locked
                   value (FAIL: a changed applied migration = a restore would NOT
                   reproduce prod = the immutability/backup guarantee is broken).
  L3  Orphans    - no recorded hash whose file is gone (FAIL: a deleted migration
                   the lock still expects).
  L4  Runbook    - ROLLBACK_RUNBOOK.md present (FAIL: no documented restore path).

Exit 0 = backup verified; 1 = an integrity failure (L2/L3/L4) was found.
Local-first; never touches prod. Companion to validate_migration_immutability.
"""
from __future__ import annotations
import hashlib
import io
import json
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
HASHES = ROOT / "migration_hashes.json"
RUNBOOK = ROOT / "ROLLBACK_RUNBOOK.md"
REPORT = ROOT / "backup_verify_report.json"

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    print(f"{BOLD}\nBackup / Restore Integrity (Pillar DR){RESET}")
    print("=" * 60)

    if not HASHES.exists():
        print(f"{RED}FAIL{RESET}: migration_hashes.json missing - no backup lock to verify.")
        return 1
    locked: dict[str, str] = json.loads(HASHES.read_text(encoding="utf-8"))
    on_disk = {p.name: p for p in sorted(MIGRATIONS.glob("*.sql"))} if MIGRATIONS.exists() else {}

    drift, orphan, untracked, ok = [], [], [], 0
    for name, want in locked.items():
        p = on_disk.get(name)
        if p is None:
            orphan.append(name)
            continue
        got = _sha256(p)
        if got != want:
            drift.append({"file": name, "locked": want[:12], "actual": got[:12]})
        else:
            ok += 1
    for name in on_disk:
        if name not in locked:
            untracked.append(name)

    runbook_ok = RUNBOOK.exists()

    print(f"  migrations locked: {len(locked)} · on disk: {len(on_disk)} · verified clean: {ok}")
    if untracked:
        print(f"  {YEL}WARN{RESET}  {len(untracked)} untracked (not yet locked): {', '.join(untracked[:5])}{' ...' if len(untracked) > 5 else ''}")
    if drift:
        print(f"  {RED}FAIL{RESET}  {len(drift)} DRIFTED (changed since lock - a restore would NOT reproduce prod):")
        for d in drift[:8]:
            print(f"         {d['file']}  locked {d['locked']}.. != actual {d['actual']}..")
    if orphan:
        print(f"  {RED}FAIL{RESET}  {len(orphan)} ORPHAN (locked but file gone): {', '.join(orphan[:5])}")
    print(f"  rollback runbook: {(GREEN + 'present' + RESET) if runbook_ok else (RED + 'MISSING' + RESET)}")

    failed = bool(drift) or bool(orphan) or not runbook_ok
    REPORT.write_text(json.dumps({
        "locked": len(locked), "on_disk": len(on_disk), "verified_clean": ok,
        "drift": drift, "orphan": orphan, "untracked": untracked,
        "runbook_present": runbook_ok, "result": "FAIL" if failed else "PASS",
    }, indent=2), encoding="utf-8")

    if failed:
        print(f"\n{RED}{BOLD}  BACKUP VERIFY: FAIL{RESET} - fix drift/orphan/runbook before trusting a restore.")
        return 1
    print(f"\n{GREEN}{BOLD}  BACKUP VERIFY: PASS{RESET} - schema reproducible from the locked migration set; runbook present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
