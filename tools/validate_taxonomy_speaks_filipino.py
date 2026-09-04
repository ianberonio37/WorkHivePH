#!/usr/bin/env python3
"""taxonomy-speaks-filipino - T45: the shared failure voice is bilingual (2026-08-27).

Runs tools/prove_taxonomy_speaks_filipino.mjs. Every page is bilingual through _t(en, fil); the
error taxonomy they all delegate to was not, so a worker on the FIL toggle got Filipino chrome and
an ENGLISH sentence at the exact moment something failed and precision mattered most.

Driven IN THE PAGE, twice per branch, once under each WH_LANG - because a source grep for "_t(" only
proves the call was written, not that the returned string changes.

★TWO BRANCHES MUST NOT TRANSLATE, and are asserted as SAME rather than skipped: the caller-supplied
fallback (the PAGE's own English sentence to own) and whWriteError's deliberate-guard passthrough,
which carries a policy refusal that explained itself. Rewriting someone else's explanation in
another language is replacement, not translation - and a gate that only checked "everything differs"
would call both of those defects.

Read-only. 14 branches: 12 must differ, 2 must not.

Re-drive: node tools/prove_taxonomy_speaks_filipino.mjs
"""
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _run(node: str):
    r = subprocess.run([node, str(ROOT / "tools" / "prove_taxonomy_speaks_filipino.mjs")],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=200,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    return bool(re.search(r"^PASS", out, re.M)), (out.strip().splitlines() or ["<no output>"])[-1]


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP taxonomy-speaks-filipino - node not on PATH (live browser gate)")
        return 0
    if not _port_open(5000):
        print("SKIP taxonomy-speaks-filipino - local stack down (Flask :5000)")
        return 0
    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL taxonomy-speaks-filipino - timed out at 200s")
        return 1
    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:200]}")
    if not ok:
        print("FAIL taxonomy-speaks-filipino - a failure sentence does not change with the language, "
              "or one that must stay English changed.")
        return 1
    print("PASS taxonomy-speaks-filipino - the shared failure voice speaks Filipino, and the two "
          "passthroughs correctly do not.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
