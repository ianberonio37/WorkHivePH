#!/usr/bin/env python3
"""check_page_board_fresh.py - did THIS run write the page board, or was it already there?

★A BOARD THAT ALREADY EXISTED IS NOT A BOARD THIS RUN WROTE (2026-09-10). A sweep script asked
"does family_rubric_scoreboard.page.json carry graded dims?" as its go/no-go, and got YES from a file
written THREE DAYS EARLIER - so it green-lit nine batches while the sweep had measured nothing, and
each batch then re-banked the same stale board and printed progress that had not happened. Nothing
false was banked in the end, because critic_from_board dates a row from the BOARD's own ranAt rather
than from today and the re-banks were idempotent - but the script could not tell a measurement from a
memory, and that is the same blindness as reading a fossil CACHE_NAME out of a comment.

`family_rubric_sweep.mjs --page ...` gives UP when another job holds the browser slot, and a give-up
leaves the previous board untouched. So "the file exists and looks graded" can never be the test. The
test is whether its `summary.ranAt` MOVED.

  python tools/check_page_board_fresh.py --stamp     -> print the current ranAt (or NONE) to remember
  python tools/check_page_board_fresh.py <stamp>     -> "yes" if ranAt has moved since <stamp> AND the
                                                        board carries graded dims, else "no"
  python tools/check_page_board_fresh.py --self-test
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

BOARD = Path(__file__).resolve().parent.parent / "family_rubric_scoreboard.page.json"


def ran_at(path: Path | None = None) -> str:
    # ★READ THE GLOBAL AT CALL TIME, NOT AT DEFINITION TIME. `path: Path = BOARD` binds the value when
    # the function is DEFINED, so the self-test below could point BOARD at a temp file and this would
    # keep reading the real one - the test failed against its own fixture, which is the test doing its
    # job. A default argument is a snapshot; a lookup is a reference.
    path = path or BOARD
    try:
        b = json.loads(io.open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        return "NONE"
    return ((b.get("summary") or {}).get("ranAt") or "NONE")


def has_graded_dims(path: Path | None = None) -> bool:
    path = path or BOARD
    try:
        b = json.loads(io.open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        return False
    pages = b.get("pages") or {}
    return any(v.get("dims") and v.get("overall") is not None for v in pages.values())


def fresh(before: str) -> bool:
    """A board is this run's only if its stamp MOVED and it actually carries grades.

    Both halves matter: a moved stamp on an empty board is a sweep that ran and measured nothing, and
    graded dims under an unmoved stamp is the fossil this file exists to catch.
    """
    return ran_at() != before and has_graded_dims()


def _self_test() -> int:
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "board.json"

        def write(stamp, dims):
            p.write_text(json.dumps({
                "summary": {"ranAt": stamp},
                "pages": {"a.html": {"overall": 90, "dims": [{"dim": "A1"}] if dims else []}},
            }), encoding="utf-8")

        global BOARD
        keep, BOARD = BOARD, p

        write("2026-09-07T00:00:00Z", True)
        if fresh("2026-09-07T00:00:00Z"):
            fails.append("an UNMOVED stamp must not read as fresh - that is the three-day-old board")
        if not fresh("2026-09-06T00:00:00Z"):
            fails.append("a MOVED stamp on a graded board must read as fresh")
        write("2026-09-10T00:00:00Z", False)
        if fresh("2026-09-06T00:00:00Z"):
            fails.append("a moved stamp on a board with NO graded dims must not read as fresh")
        p.unlink()
        if ran_at() != "NONE":
            fails.append("a missing board must stamp as NONE")
        if fresh("NONE"):
            fails.append("a missing board must never read as fresh")
        BOARD = keep

    print("FAIL check_page_board_fresh self-test - " + "; ".join(fails) if fails
          else "self-test OK: an unmoved stamp, an ungraded board and a missing board all read NOT fresh")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    if "--stamp" in sys.argv:
        print(ran_at())
        raise SystemExit(0)
    before = sys.argv[1] if len(sys.argv) > 1 else "NONE"
    print("yes" if fresh(before) else "no")
