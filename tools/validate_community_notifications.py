#!/usr/bin/env python3
"""community-notifications gate — T108's last three silent rows (2026-08-26).

Runs tools/prove_community_notifications.mjs against the local stack. Three
events that named a person and told them nothing now each enqueue a push, and —
just as important — stay silent where silence is correct:

  mention      -> the named member        | self-mention  -> nothing
  reply        -> the post's author       | self-reply    -> nothing
  best answer  -> the reply's author      | un-accepted   -> nothing

★THE NEGATIVES ARE HALF THE GATE. A notifier that fires on everything passes a
positive-only test and turns a hive into a spam engine. These RPCs exist to be
SELECTIVE, so three of the six assertions measure the silence.

★AND THE CALLER IS PART OF THE ORACLE. The probe drives each RPC as a signed-in
member (SET ROLE authenticated + jwt claims), never as postgres: these are
SECURITY DEFINER functions guarding on auth_worker_names(), and a proof run as
the owner would show they work for exactly the caller they must never trust.

Discipline carried from the sibling live gates: retry once (full-suite live
gates flake under load), node invoked directly (the repo path contains an
ampersand), utf-8 pinned, PASS matched line-anchored, SKIP — never PASS — when
node or the stack is absent. The prover ABORTs on dirty pre-state rather than
deleting rows it did not create, and verifies its own cleanup by re-counting.

Re-drive: node tools/prove_community_notifications.mjs
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


def _run(node: str):
    r = subprocess.run(
        [node, str(ROOT / "tools" / "prove_community_notifications.mjs")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180,
        encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    return bool(re.search(r"^\s*PASS", out, re.M)), out


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("SKIP community-notifications — node not on PATH")
        return 0
    if not _port_open(54321):
        print("SKIP community-notifications — local Supabase (:54321) down")
        return 0
    if not shutil.which("docker"):
        print("SKIP community-notifications — docker absent (psql is the oracle)")
        return 0

    try:
        ok, out = _run(node)
        if not ok:
            ok, out = _run(node)
    except subprocess.TimeoutExpired:
        print("FAIL community-notifications — timed out at 180s")
        return 1

    for line in out.strip().splitlines()[-8:]:
        print("  " + line.strip()[:200])
    if not ok:
        print("FAIL community-notifications — a named person was not told, or was told when they "
              "should not have been. Check notify_post_mentions / notify_reply_posted / "
              "notify_reply_accepted (mig 20260826000002) and their three call sites in community.html.")
        return 1
    print("PASS community-notifications — mention, reply and best-answer each reach the right person, "
          "and self-acts stay silent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
