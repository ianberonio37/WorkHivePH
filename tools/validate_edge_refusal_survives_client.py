#!/usr/bin/env python3
"""edge-refusal-survives-client - T82: the function's words must reach the person (2026-08-26).

The live half of edge-refusal-reaches-user. That one counts call sites; this one drives the
actual pane and reads what a worker would read.

With the Asset Brain endpoints forced to the REAL refusal a drained hive gets - 429 plus
rate-limit.ts's own body, "AI call limit reached for this hive. Try again in an hour." - the
answer pane must show that sentence, and must never show supabase-js's placeholder.

MEASURED before the fix: "Could not reach Asset Brain: Edge Function returned a non-2xx status
code". A CONNECTION-flavoured sentence for a QUOTA event, so a rate-limited worker goes to check
their signal instead of waiting an hour. The cause is that supabase-js collapses every non-2xx
into that one message; the status and body survive only on error.context, which nothing here
read. Fixed centrally by utils.js whFnError().

★THE 429 IS INJECTED, NOT WAITED FOR - deterministic, and it spends no AI call. (The bug was
first met by genuinely exhausting the hive's hourly quota, which is how the placeholder surfaced
at all.)

Re-drive: node tools/prove_edge_refusal_survives_the_client.mjs
"""
import io
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP edge-refusal-survives-client - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)):
        print("SKIP edge-refusal-survives-client - local stack down")
        return 0

    def run():
        r = subprocess.run([node, str(ROOT / "tools" / "prove_edge_refusal_survives_the_client.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=420,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        if re.search(r"^\s*SKIP", out, re.M):
            return None, out
        return bool(re.search(r"^\s*PASS", out, re.M)), out

    try:
        ok, out = run()
        if ok is False:
            ok, out = run()
    except subprocess.TimeoutExpired:
        print("FAIL edge-refusal-survives-client - timed out at 420s")
        return 1

    for line in out.strip().splitlines()[-3:]:
        print("  " + line.strip()[:170])
    if ok is None:
        print("SKIP edge-refusal-survives-client - the probe could not resolve its hive/asset fixture")
        return 0
    if not ok:
        print("FAIL edge-refusal-survives-client - the backend named the cause and when it clears, and the")
        print("    pane did not repeat it. Showing \"Edge Function returned a non-2xx status code\" tells a")
        print("    rate-limited worker to check their connection; the truth was that they need to wait an")
        print("    hour. Route invoke errors through whFnError(error, fallback).")
        return 1
    print("PASS edge-refusal-survives-client - a quota refusal reaches the worker in the function's own "
          "words, cause and clearing time intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
