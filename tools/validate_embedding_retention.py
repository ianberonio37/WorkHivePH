#!/usr/bin/env python3
"""validate_embedding_retention.py - FREE_TIER_QUOTA_ROADMAP Q5-b ratchet.

GROUNDED (Step 0): embeddings are the silent DB-size driver (19 vector tables ~62 MB;
voice_journal_entries alone 45 MB). Retention splits by table nature and this gate proves
BOTH halves are in place + can't regress:
  C1 cache-cron    embedding_cache has an LRU age-eviction cron (a cache that only grew)
  C2 prune-fn      prune_embedding_cache() exists (testable mirror of the cron policy)
  C3 gated-prune   cold_archive_prune.py exists, DRY-RUN by default, --commit double-gated
                   (--i-verified-snapshots) - the safe step-3 for the canonical big tables
  C4 safety-gate   the prune safety fn NEVER deletes without a sufficient verified snapshot
                   (imported + exercised directly - real teeth, not a text grep)

USAGE:      python tools/validate_embedding_retention.py
Self-test:  python tools/validate_embedding_retention.py --self-test
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
PRUNE_TOOL = ROOT / "tools" / "cold_archive_prune.py"
GREEN, RED = "\033[92m", "\033[91m"
RST = "\033[0m"


def _migrations_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(MIGRATIONS.glob("*.sql")))


def safety_gate_holds() -> bool:
    """Import the tool's isolated safety fn and assert it refuses every unsafe case."""
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        from cold_archive_prune import prune_decision  # type: ignore
    except Exception:
        return False
    unsafe = [(100, False, None), (100, True, None), (100, True, 40), (0, True, 100)]
    safe = [(100, True, 100), (100, True, 250)]
    return (all(not prune_decision(*c)[0] for c in unsafe)
            and all(prune_decision(*c)[0] for c in safe))


def evaluate(mig: str, tool_src: str, gate_ok: bool) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    c1 = bool(re.search(r"cron\.schedule\(\s*'embedding-cache-retention'", mig, re.I)) \
        and "embedding_cache" in mig and re.search(r"last_used\s*<\s*now\(\)\s*-", mig, re.I) is not None
    checks.append(("C1 cache-cron", c1, "embedding_cache LRU age-eviction cron"
                   if c1 else "missing embedding-cache-retention cron"))

    c2 = bool(re.search(r"CREATE OR REPLACE FUNCTION public\.prune_embedding_cache", mig, re.I)) \
        and bool(re.search(r"GRANT EXECUTE ON FUNCTION public\.prune_embedding_cache", mig, re.I))
    checks.append(("C2 prune-fn", c2, "prune_embedding_cache() present + granted"
                   if c2 else "prune_embedding_cache fn/grant missing"))

    dry_default = "--commit" in tool_src and "action=\"store_true\"" in tool_src
    double_gate = "i-verified-snapshots" in tool_src and bool(
        re.search(r"--commit requires --i-verified-snapshots", tool_src))
    c3 = bool(tool_src) and dry_default and double_gate
    checks.append(("C3 gated-prune", c3, "cold_archive_prune.py: dry-run default + --commit double-gated"
                   if c3 else f"prune tool not safely gated (dry={dry_default} double={double_gate})"))

    checks.append(("C4 safety-gate", gate_ok, "prune gate refuses without a sufficient verified snapshot"
                   if gate_ok else "SAFETY REGRESSION: gate would delete unverified rows"))
    return checks


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    mig = _migrations_text()
    tool_src = PRUNE_TOOL.read_text(encoding="utf-8", errors="replace") if PRUNE_TOOL.exists() else ""
    gate_ok = safety_gate_holds()
    checks = evaluate(mig, tool_src, gate_ok)

    print("=" * 74)
    print("  FREE_TIER_QUOTA_ROADMAP Q5-b - embedding/growth-table RETENTION")
    print("=" * 74)
    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        tag = f"{GREEN}ok{RST}  " if ok else f"{RED}FAIL{RST}"
        print(f"  {tag} {name:15s} {detail}")
    print(f"\n  {passed}/{len(checks)} checks green")

    if self_test:
        empty_all_fail = all(not ok for _, ok, _ in evaluate("", "", False))
        # a tool without the double gate -> C3 fails
        no_gate = 'args.commit = True  # no --i-verified-snapshots check'
        c3_tooth = dict((n, ok) for n, ok, _ in evaluate(mig, no_gate, gate_ok)).get("C3 gated-prune") is False
        good = empty_all_fail and c3_tooth and gate_ok  # gate_ok itself is the C4 teeth (real fn)
        print(f"  TEETH [{GREEN+'PASS'+RST if good else RED+'FAIL'+RST}] "
              f"empty=all-fail:{empty_all_fail}  no-double-gate->C3-fail:{c3_tooth}  safety-fn-holds:{gate_ok}")
        if not good:
            return 1

    print()
    failed = [n for n, ok, _ in checks if not ok]
    if failed:
        print(f"  {RED}FAIL{RST} - {len(failed)} check(s) regressed: {', '.join(failed)}")
        return 1
    print(f"  {GREEN}PASS{RST} - embedding retention: cache auto-pruned + canonical tables safely gated-prune")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
