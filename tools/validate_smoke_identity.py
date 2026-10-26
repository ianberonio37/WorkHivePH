#!/usr/bin/env python3
"""validate_smoke_identity.py - the post-deploy smoke signs in as its own bench, as the server answers (BRH-AF, 2026-10-26).

The 2026-10-24 deploy's signed-in tier never ran: production had no account the smoke could use, and the smoke
seeded a LOCAL hive's id, a worker name and the supervisor role into storage instead of asking who the account is - so
against production it would have claimed a hive the account is not in. Fixed: tools/create_smoke_bench.mjs makes the
account and its own bench hive through the product's calls (credentials only in .env); the smoke reads the account's
membership from the server, refuses any hive but WH_SMOKE_HIVE, and its contexts send no analytics_events, so a
deploy check never counts in the founder's growth figures.

STATIC facts in tools/post_deploy_smoke.mjs (a revert of any one reddens this; teeth: the smoke as shipped in 27733934):
  - no hard-coded hive id or worker name is written into storage
  - the hive is read from hive_members for the signed-in account, and WH_SMOKE_HIVE bounds it
  - every context comes from quietContext, which answers analytics_events POSTs itself
  - tools/create_smoke_bench.mjs exists and writes only to .env

    python tools/validate_smoke_identity.py
    python tools/validate_smoke_identity.py --self-test
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SMOKE = "tools/post_deploy_smoke.mjs"
BENCH = "tools/create_smoke_bench.mjs"

FACTS = {
    "no hard-coded hive is seeded into storage": lambda s, b: not re.search(r"const HIVE\s*=\s*\{\s*id:\s*'[0-9a-f-]{36}'", s),
    "the hive is read from the server for the signed-in account": lambda s, b: re.search(
        r"from\('hive_members'\)[\s\S]{0,200}\.eq\('auth_uid',\s*auth\.user\.id\)", s) is not None,
    "WH_SMOKE_HIVE bounds the run to the bench": lambda s, b: "process.env.WH_SMOKE_HIVE" in s and "not an active member of the bench hive" in s,
    "every context sends no analytics_events": lambda s, b: re.search(r"async function quietContext[\s\S]{0,400}analytics_events", s) is not None
        and "browser.newContext(" not in s.replace("const c = await browser.newContext(", ""),
    "the bench is provisioned by a tool that writes only to .env": lambda s, b: bool(b) and "appendFileSync(ENV" in b and "WH_SMOKE_HIVE=" in b,
}


def findings(smoke: str, bench: str) -> list[str]:
    return [name for name, ok in FACTS.items() if not ok(smoke, bench)]


def self_test() -> int:
    cur = (ROOT / SMOKE).read_text(encoding="utf-8", errors="replace")
    bench = (ROOT / BENCH).read_text(encoding="utf-8", errors="replace") if (ROOT / BENCH).exists() else ""
    old = subprocess.run(["git", "show", f"27733934:{SMOKE}"], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
    ok = not findings(cur, bench)
    red = findings(old, "")
    print(f"  {'PASS' if ok else 'FAIL'} the current smoke and bench tool hold every fact")
    print(f"  {'PASS' if len(red) >= 4 else 'FAIL'} teeth: the smoke as shipped in 27733934 fails {len(red)}/{len(FACTS)}: {red}")
    ok = ok and len(red) >= 4
    print(("PASS" if ok else "FAIL") + " smoke-identity self-test")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    smoke = (ROOT / SMOKE).read_text(encoding="utf-8", errors="replace")
    bench = (ROOT / BENCH).read_text(encoding="utf-8", errors="replace") if (ROOT / BENCH).exists() else ""
    bad = findings(smoke, bench)
    print(f"smoke-identity (BRH-AF): {len(FACTS) - len(bad)}/{len(FACTS)} facts hold")
    for b in bad:
        print(f"  - {b}")
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
