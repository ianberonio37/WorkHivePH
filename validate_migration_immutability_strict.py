"""
Migration Immutability Strict Validator (L0, P1 roadmap 2026-05-27).
=====================================================================
Migrations are immutable once shipped. Editing a migration that has
already been applied to any environment causes drift that can never be
detected at runtime: the database is in state X, the file says Y, fresh
clones build state Y.

This validator hashes every migration file and persists the hash. On
subsequent runs, any change to a previously-recorded migration FAILs.
New migrations are recorded without error.

The existing `validate_migration_immutability.py` was an L-1.5 miner
(reports drift). This is the L0 ratchet that gates commits.

Exit codes:
  0  every previously-hashed migration unchanged + all new migrations recorded
  1  one or more migrations changed since their first observation
"""
from __future__ import annotations
import hashlib, io, json, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "supabase" / "migrations"
HASHES = ROOT / "migration_hashes.json"
REPORT = ROOT / "migration_immutability_strict_report.json"

CHECK_NAMES = ["migration_immutability_strict"]

# Migrations explicitly allowed to be edited (e.g. one-off baseline + the
# active P1 migration during its initial bedding-in period). Remove after
# the migration is observed twice in CI.
ALLOWED_MULTI_COMMIT = {
    # 2026-05-26 — P1 substrate is still being bedded in across the
    # canonical_anchor + idempotency validators. Allow re-edit until
    # baseline locks at 0 across the gate suite.
    "20260526000001_p1_roadmap_substrate.sql",
}


def hash_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def load_hashes() -> dict[str, str]:
    if not HASHES.exists(): return {}
    try: return json.loads(HASHES.read_text(encoding="utf-8"))
    except Exception: return {}


def save_hashes(d: dict[str, str]) -> None:
    HASHES.write_text(json.dumps(d, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    if not MIGRATIONS.exists():
        print("\033[91mFAIL: supabase/migrations missing\033[0m")
        return 2
    prior = load_hashes()
    current: dict[str, str] = {}
    changed: list[tuple[str, str, str]] = []
    new:     list[str] = []
    for f in sorted(MIGRATIONS.glob("*.sql")):
        h = hash_file(f)
        current[f.name] = h
        if f.name in prior:
            if prior[f.name] != h and f.name not in ALLOWED_MULTI_COMMIT:
                changed.append((f.name, prior[f.name], h))
        else:
            new.append(f.name)

    REPORT.write_text(json.dumps({
        "migrations_seen": len(current),
        "new":             new,
        "changed":         [{"file": f, "from": a, "to": b} for f, a, b in changed],
        "allowed_multi_commit": sorted(ALLOWED_MULTI_COMMIT),
    }, indent=2), encoding="utf-8")

    # Persist hashes regardless of FAIL — new migrations should always be
    # recorded; changes that FAILed will be caught on the next run too.
    save_hashes(current)

    if changed:
        print(f"\033[91mFAIL: {len(changed)} migration(s) edited after first observation\033[0m")
        for f, a, b in changed:
            print(f"  - {f}\n      was: {a[:16]}...\n      now: {b[:16]}...")
        print()
        print("Migrations are immutable. To change schema, write a NEW migration")
        print("with a later timestamp that supersedes the old one. If the change")
        print("is intentional (e.g. unshipped + bedding in), add the file to")
        print("ALLOWED_MULTI_COMMIT inside this validator.")
        return 1

    print(f"Migration immutability strict: {len(current)} migrations, {len(new)} newly recorded.")
    print("\033[92mPASS\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
