#!/usr/bin/env python3
"""cold-page-teaches - T175: every page introduces itself to a first-time reader (2026-08-26).

A brand-new account has no assets, no PMs, no history. Every list on every page is
empty, and an empty page has one job: say what it is FOR and what the first action is.
Get it wrong and the reader concludes the product is broken or not for them - on the
one visit they are guaranteed to make.

WALKED 19 PAGES with a genuinely cold account (created, walked, deleted, residue
re-counted at 0 across auth.users, worker_profiles, voice_journal_entries and
hive_members - the CASCADE from erasure-path-intact doing exactly what it promises).
RESULT: every page speaks. Two bounce, and they bounce to hive.html, which is the right
destination for someone with no hive rather than a dead end.

THE ONE REAL GAP, now fixed: analytics-report presented a fully-armed generator -
period chips, audience toggle, "Generate Report" - to a reader with no hive and so no
data, stating no precondition. Its siblings already refuse that state by name, so it
now carries the same gate in the same words ("Reports need a hive... Go to Hive"),
hiding BOTH <main> and #ar-print-wrapper, the latter a deliberate sibling of <main> for
the print rule whose empty-state hint otherwise told a hive-less reader to "Click
Generate Report" directly beneath a gate saying Go to Hive.

★THREE INSTRUMENT ERRORS ON THE WAY, NONE BANKED, and they are the reason this file
exists in this shape:
  1. The probe cleared wh_last_worker as well as the hive, and 14 of 19 pages promptly
     bounced to the marketing page - a dramatic finding that was pure artifact. Signup
     SETS that key (index.html:3196) and the shared guard redirects on a missing WORKER
     NAME, not a missing hive. COLD means no hive, not no identity.
  2. The pass/fail threshold was `chars < 200`, which flagged four of the BEST cold
     states on the platform - hive.html at 134 ("Create a Hive | Join with Code"),
     asset-hub at 188, shift-brain at 137, integrations at 193. Those pages are short
     BECAUSE they are focused. Brevity is not emptiness.
  3. It read document.querySelector('main'), and innerText on a display:none element
     still returns its raw text - so on the very page it had just gated, it captured the
     HIDDEN generator and missed the VISIBLE gate outside <main>. It now reads body
     innerText, which respects visibility, i.e. what a person actually sees.

It asserts only what is objective - something rendered, nothing threw, the account
cleaned up - and PRINTS each page's cold text, because whether prose teaches is a
judgement for a reader, and an oracle that grades prose is an oracle that will be wrong
about prose.

Re-drive: node tools/prove_cold_page_teaches.mjs   (WH_COLD_PAGES=a.html,b.html to scope)
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
        print("SKIP cold-page-teaches - node not on PATH (live gate)")
        return 0
    if not (_port_open(5000) and _port_open(54321)) or not shutil.which("docker"):
        print("SKIP cold-page-teaches - local stack / docker down (it creates and deletes an account)")
        return 0

    try:
        r = subprocess.run([node, str(ROOT / "tools" / "prove_cold_page_teaches.mjs")],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        print("FAIL cold-page-teaches - timed out at 900s")
        return 1

    if "ABORT:" in out:
        print("FAIL cold-page-teaches - a previous probe account was still present; refused to measure "
              "on dirty state. Remove it and re-run.")
        return 1
    ok = bool(re.search(r"^\s*PASS", out, re.M))
    for line in out.strip().splitlines()[-4:]:
        print("  " + line.strip()[:160])
    if not ok:
        print("FAIL cold-page-teaches - a page shows a first-time reader nothing, throws on a cold "
              "account, or the probe account was left behind. An empty first visit is the one visit "
              "every user is guaranteed to make.")
        return 1
    print("PASS cold-page-teaches - every page walked with a hive-less account says what it is for, "
          "nothing threw, and the probe account was removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
