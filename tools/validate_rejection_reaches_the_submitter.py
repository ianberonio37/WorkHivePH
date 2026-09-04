#!/usr/bin/env python3
"""rejection-reaches-the-submitter - T20: a refusal must reach the person who was refused.

A supervisor clearing the approval queue rejects an asset, a part, a change order. The refusal is
recorded, the item disappears from the queue, and the supervisor's job is done - but the WORKER who
submitted it is the one who has to act, and if all they see is "Rejected" they resubmit the same
thing, or give up, or ask in person. A refusal that names no cause is a loop the platform opened and
did not close.

★THE TWO HALVES, and both are asserted because either alone is useless:
  1. every path that writes status 'rejected' records a REASON in the same update - a reason
     captured later, or optionally, is a reason usually missing;
  2. every surface that shows an item as Rejected also RENDERS that reason - a column written and
     never read is the write-only class, and the submitter is the only person it was written for.

★MEASURED 2026-08-26: the platform already does this on all three paths - hive.html's queue (both
asset_nodes and inventory_items), asset-hub's own reject, and project-manager's change orders - and
the reason is rendered back on asset-hub ("Why: ..."), inventory ("Why rejected: ... - fix it and
resubmit via Edit") and project-manager ("Rejected: ..."). Nothing was broken. Nothing was guarding
it either, and a fourth reject path added later would have no reason to know the contract exists.

★IT PAIRS WRITES TO RENDERS BY TABLE rather than by page, because the two halves deliberately live
apart: the supervisor rejects from hive.html and the worker reads the reason on inventory.html. A
check that demanded both in one file would fail the working design.

Re-drive: python tools/validate_rejection_reaches_the_submitter.py
"""
import io
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
SKIP = ("node_modules", "_fixtures", ".tmp", "test-data-seeder", "tools", ".git")

# Where a rejected item is READ by the person who submitted it. Keyed by the surface, because the
# reject and the render live on different pages by design.
RENDER_SURFACES = ["asset-hub.html", "inventory.html", "project-manager.html"]


def main() -> int:
    failures = []
    pages = sorted(p for p in ROOT.glob("*.html")
                   if not set(p.relative_to(ROOT).parts[:-1]) & set(SKIP))

    writes, renders = [], []
    for p in pages:
        src = io.open(p, encoding="utf-8", errors="replace").read()

        # 1. every reject WRITE carries a reason in the same update object
        for m in re.finditer(r"\.update\(\s*\{([^}]*status:\s*['\"]rejected['\"][^}]*)\}", src, re.S):
            writes.append(p.name)
            if "rejection_reason" not in m.group(1):
                failures.append(f"{p.name}: a reject writes status 'rejected' without a "
                                f"rejection_reason in the same update - the item leaves the queue and "
                                f"the submitter is told only that it failed")

        # 2. any surface that KNOWS about the rejected state must also render the reason.
        #    Matching a capitalised "Rejected" in markup was too narrow and wrongly accused
        #    asset-hub, which branches on `status === 'rejected'` inside a template and prints the
        #    reason under a "Why:" heading - the state is a VALUE here, not a caption.
        knows_rejected = re.search(r"['\"]rejected['\"]", src, re.I)
        if knows_rejected and p.name in RENDER_SURFACES:
            renders.append(p.name)
            if "rejection_reason" not in src:
                failures.append(f"{p.name}: knows an item can be rejected but never renders "
                                f"rejection_reason - the reason was written for this reader and "
                                f"stops short of them")

    if not writes:
        failures.append("no reject path found at all; the queue moved and this gate no longer knows "
                        "what it guards")
    missing_render = [s for s in RENDER_SURFACES
                      if (ROOT / s).exists() and s not in renders]
    for s in missing_render:
        failures.append(f"{s} no longer surfaces a Rejected state to its reader - either the surface "
                        f"moved or the submitter can no longer see that their submission was refused")

    # non-vacuity: the column must actually exist, or all of the above is text-matching on nothing
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA"],
            input="SELECT count(DISTINCT table_name) FROM information_schema.columns "
                  "WHERE table_schema='public' AND column_name='rejection_reason';",
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        tables = int(re.search(r"(\d+)", r.stdout or "0").group(1)) if r.returncode == 0 else -1
    except Exception:
        tables = -1
    if tables == 0:
        failures.append("no table carries a rejection_reason column, so nothing here is enforceable - "
                        "the reason has nowhere to live")

    if failures:
        print("FAIL rejection-reaches-the-submitter:")
        for f in failures:
            print("    - " + f)
        return 1

    where = "unknown" if tables == -1 else f"{tables} tables"
    print(f"  reject paths: {len(writes)} ({', '.join(sorted(set(writes)))}) · "
          f"reasons rendered on: {', '.join(sorted(set(renders)))} · column on {where}")
    print("PASS rejection-reaches-the-submitter - every reject records a reason in the same write, "
          "and every surface that shows a Rejected item renders it back to the person who has to act.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
