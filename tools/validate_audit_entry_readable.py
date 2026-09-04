#!/usr/bin/env python3
"""audit-entry-readable - T28: an audit entry must read as a change, not as JSON (2026-08-27).

Runs tools/prove_audit_entry_readable.mjs. audit-log's own meta description promises "every CRUD +
approval + permission change with actor, BEFORE/AFTER, and timestamp", and the data can deliver it -
hive_audit_log rows carry changed_fields: {"sw": {"from": 768, "to": 1920}}, literally a before and
an after. The page rendered the whole payload as `<pre>JSON.stringify(detail, null, 2)</pre>`, so a
supervisor reconstructing a disputed change had to read a JSON blob to find the two values that
mattered. The claim was on the page; the delivery was not.

Asserted on the RENDERED DOM, not the source, because the question is what a person sees: expand a
real entry and check the block carries no braces and no quoted keys, and that a from/to pair reads
as "768 -> 1920".

★IT MUST RUN AS A SUPERVISOR. audit-log is supervisor-gated and a worker sees ZERO entries - which
the first run of the probe reported as "0 entries with details", a verdict about the ACCOUNT rather
than the page. The gate treats an empty feed as a failure to measure, never as a pass.

Teeth: the oracle's own regex, run against the pre-fix string, flags it (True) and leaves the
current render alone (False) - so the check demonstrably separates the two worlds.

Read-only: signs in, reads, asserts. Writes nothing.

Re-drive: node tools/prove_audit_entry_readable.mjs
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
    r = subprocess.run([node, str(ROOT / "tools" / "prove_audit_entry_readable.mjs")],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=240,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    return bool(re.search(r"^PASS", out, re.M)), " | ".join(
        l.strip() for l in (out.strip().splitlines()[-3:] or ["<no output>"]))


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP audit-entry-readable — node not on PATH (live browser gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP audit-entry-readable — local stack down (Flask :5000 / Supabase :54321)")
        return 0
    try:
        ok, tail = _run(node)
        if not ok:
            ok, tail = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL audit-entry-readable — timed out at 240s")
        return 1
    print(f"  {'PASS' if ok else 'FAIL'}  {tail[:220]}")
    if not ok:
        print("FAIL audit-entry-readable — the entry details are not readable as a change.")
        return 1
    print("PASS audit-entry-readable — details render as labelled rows with before -> after, no JSON.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
