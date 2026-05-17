"""Standalone runner for the industry_standards seeder.

Runs ONLY the Day 2 Azure sprint additions (11 standards on top of the 10
already inserted by the Phase 6F migration). Idempotent — safe to re-run.

Use this when you don't want to trigger the full 1-3 minute reseed flow
but need to refresh just the industry_standards table.

Usage:
    cd test-data-seeder
    python run_industry_standards_seeder.py
"""
import sys
import io
from datetime import datetime

# Windows console UTF-8 fix
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from lib.supabase_client import get_client
from seeders.industry_standards import seed_industry_standards


def main() -> int:
    print("=" * 60)
    print("INDUSTRY STANDARDS SEEDER — Day 2 Azure Sprint Additions")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    client = get_client()
    print("[OK] Supabase client ready")

    def log(msg: str) -> None:
        print(msg)

    result = seed_industry_standards(client, log)

    print()
    print("=" * 60)
    print("RESULT:")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("=" * 60)

    if result.get("industry_standards_total", 0) == 0:
        print("\n[FAIL] No rows in industry_standards — check Supabase connection + migration.")
        return 1

    print(f"\n[OK] industry_standards now has {result['industry_standards_total']} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
