#!/usr/bin/env python3
"""validate_data_moves.py - BRH.10 AL (2026-10-26): a release never ships ahead of the data move its pages read.

BRH-AB moved photos out of their rows. The 2026-10-24 release shipped pages that read only a photo's stored path
(whRowCols leaves the inline column out), while production's copy pass had not run: 22 logbook photos and 5 part
photos showed nothing on production until the owner's step ran on 2026-10-26. Nothing between the commit and the push
knew that the code depended on a data move, or asked production whether it was done.

This gate names each data move, the code fact that makes a release depend on it, and the production rows that still
owe it. When the tree being pushed carries the code fact, production is asked how many rows are still owed; any owed
row - or a production that cannot be asked - BLOCKS the push ("could not ask" is not "done").

Production is read through PostgREST with the project's service key. The key comes from WH_PROD_URL /
WH_PROD_SERVICE_KEY when set, otherwise from the linked Supabase CLI (`supabase projects api-keys`, the account that
already runs Leg A); it is held in this process only, never printed or stored.

    python tools/validate_data_moves.py              # ask production
    python tools/validate_data_moves.py --self-test  # teeth, no network
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# one entry per data move a shipped page depends on. `owed` filters are PostgREST query strings: a row matching one
# still needs the move. A move whose code fact is absent from the tree is not this release's concern.
MOVES = [
    {
        "id": "BRH-AB photos out of their rows (entry-photos bucket)",
        "depends": ("utils.js", r"function whRowCols\("),
        "owed": [
            ("logbook", "photo=like.data:image*&photo_path=is.null"),
            ("inventory_items", "photo=like.data:image*&photo_path=is.null"),
        ],
        "run": "python tools/move_inline_photos_to_storage.py --target prod",
    },
]


def depends(move: dict, read=lambda p: (ROOT / p).read_text(encoding="utf-8", errors="replace")) -> bool:
    path, rx = move["depends"]
    try:
        return re.search(rx, read(path)) is not None
    except OSError:
        return False


def prod_endpoint() -> tuple[str, str]:
    url, key = os.environ.get("WH_PROD_URL", ""), os.environ.get("WH_PROD_SERVICE_KEY", "")
    if url and key:
        return url.rstrip("/"), key
    ref = (ROOT / "supabase" / ".temp" / "project-ref").read_text(encoding="utf-8").strip()
    r = subprocess.run(["supabase", "projects", "api-keys", "--project-ref", ref, "-o", "json"],
                       capture_output=True, text=True, timeout=60)
    keys = json.loads(r.stdout or "[]")
    key = next((k.get("api_key") for k in keys if k.get("name") == "service_role"), "")
    if not key:
        raise RuntimeError("the linked Supabase CLI returned no service key (supabase login)")
    return f"https://{ref}.supabase.co", key


def owed_count(url: str, key: str, table: str, flt: str) -> int:
    import requests
    r = requests.head(f"{url}/rest/v1/{table}?select=id&{flt}", timeout=30,
                      headers={"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact"})
    rng = r.headers.get("content-range", "")
    if r.status_code >= 400 or "/" not in rng:
        raise RuntimeError(f"{table}: HTTP {r.status_code}, no count")
    return int(rng.split("/")[-1])


def findings(moves: list[dict], dep, count) -> tuple[list[str], list[str]]:
    """(blocking findings, report lines). dep(move) -> bool; count(table, filter) -> int, may raise."""
    out, lines = [], []
    for m in moves:
        if not dep(m):
            lines.append(f"  n/a   {m['id']} - the tree does not read it")
            continue
        for table, flt in m["owed"]:
            try:
                n = count(table, flt)
            except Exception as e:  # could not ask is not "done"
                out.append(f"{m['id']}: production could not be asked for {table} ({e}) - the push waits until it can")
                continue
            lines.append(f"  {'ok' if n == 0 else 'OWED':5} {m['id']} · {table}: {n} row(s) still owe the move")
            if n:
                out.append(f"{m['id']}: {n} {table} row(s) on production still owe the move this release reads - run: {m['run']}")
    return out, lines


def self_test() -> int:
    move = dict(MOVES[0])
    yes, no = (lambda m: True), (lambda m: False)
    def fail_count(t, f): raise RuntimeError("offline")
    cases = [
        (findings([move], yes, lambda t, f: 0)[0] == [], "done -> pass"),
        (len(findings([move], yes, lambda t, f: 3)[0]) == 2, "owed -> block, one finding per table"),
        (len(findings([move], yes, fail_count)[0]) == 2, "production unreachable -> block"),
        (findings([move], no, fail_count)[0] == [], "the tree does not read it -> not asked"),
        (depends(move, read=lambda p: "function whRowCols(source) {}"), "the code fact is found"),
        (not depends(move, read=lambda p: "// whRowCols is gone"), "a removed code fact is not"),
    ]
    for ok, name in cases:
        print(f"  {'PASS' if ok else 'FAIL'} {name}")
    ok = all(c[0] for c in cases)
    print(("PASS" if ok else "FAIL") + " data-moves self-test")
    return 0 if ok else 1


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--self-test" in sys.argv:
        return self_test()
    print("data-moves (§BRH.10 AL): a release never ships ahead of the data move its pages read")
    # the pre-push gate passes --require-prod: there, a production that cannot be asked blocks. Elsewhere (CI has no
    # Supabase login) a run with no way to ask says so and passes, because the push is where the answer is binding.
    try:
        ep = list(prod_endpoint())
    except Exception as e:  # noqa: BLE001
        if "--require-prod" in sys.argv:
            print(f"  - production could not be asked ({e}) - the push waits until it can")
            print("FAIL")
            return 1
        print(f"  SKIP: no way to ask production here ({e}); the pre-push release gate asks with --require-prod")
        print("PASS")
        return 0
    def count(table, flt):
        return owed_count(ep[0], ep[1], table, flt)
    out, lines = findings(MOVES, depends, count)
    for line in lines:
        print(line)
    for f in out:
        print(f"  - {f}")
    print("PASS" if not out else "FAIL")
    return 0 if not out else 1


if __name__ == "__main__":
    sys.exit(main())
