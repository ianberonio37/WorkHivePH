#!/usr/bin/env python3
"""alert-loop-closes - T29: acting on an alert must make the alert GO AWAY (2026-08-27).

An alert inbox that never empties is an inbox people stop reading. So the chain has to close: the
alert names an action, links to the surface where that action is taken, and DOING it removes the
alert - without anyone marking anything by hand.

★THE CLOSURE HERE IS STRUCTURAL, WHICH IS THE STRONGEST KIND. alert-hub's PM alerts are DERIVED, not
stored: they come from v_pm_scope_items_truth filtered `is_overdue = true`, so there is no status to
update and no second write to forget. Complete the PM and the row stops matching. Proven live rather
than reasoned - insert a 'done' completion for an overdue scope item inside a transaction and the
overdue count for it goes 1 -> 0 while days_until_due moves -34 -> +7, then roll it all back.

TWO ASSERTIONS, because either alone is a half-truth:
  1. THE LINK EXISTS - the PM alert carries an href to pm-scheduler for the NAMED asset and an
     action label, so the person can reach the place the condition is fixed. An alert that states a
     problem and offers no way to it is a notification, not an inbox item.
  2. THE CONDITION CLEARS - completing that PM really does remove the alert's source row. A link to
     a surface that does not resolve the alert would leave the loop open while looking closed.

SAFETY: the completion is written inside a transaction and ROLLED BACK; residue is re-counted after.

Self-test: `--selftest` (the link assertions).
"""
import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
PAGE = ROOT / "alert-hub.html"
PROBE = "WH-T29-LOOP-GATE"


def psql(sql: str):
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                        "-t", "-A", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=90)
    return (r.stdout or "").strip(), (r.stderr or "").strip(), r.returncode


def check_link(src: str) -> list:
    """The PM alert must offer a way to the surface that fixes it."""
    # A PLAIN FORWARD WINDOW, not a lazy match to the first "}". The alert literal contains nested
    # braces (template expressions, encodeURIComponent calls), so `[\s\S]{0,700}?\}` stopped inside
    # the FIRST of them - well before href and actionLabel - and reported a correctly-linked alert as
    # having no way to act. The block is read as a window because that is what it is.
    m = re.search(r"kind:\s*'pm'[\s\S]{0,700}", src)
    if not m:
        return ["alert-hub no longer builds a 'pm' alert - this gate is aimed at nothing"]
    block = m.group(0)
    out = []
    if "pm-scheduler.html?asset=" not in block:
        out.append("the PM alert carries no deep link to pm-scheduler for the named asset, so the "
                   "person is told a PM is overdue and left to find it")
    if not re.search(r"actionLabel:\s*'[^']{3,}'", block):
        out.append("the PM alert names no action, so the link (if any) is unlabelled")
    return out


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    good = ("all.push({ kind: 'pm', dedupeKey: 'pm:'+k, title: n, "
            "href: 'pm-scheduler.html?asset=' + encodeURIComponent(n), actionLabel: 'Open PM Scheduler' }")
    chk("a linked, labelled PM alert passes", len(check_link(good)), 0)

    nolink = good.replace("href: 'pm-scheduler.html?asset=' + encodeURIComponent(n), ", "")
    chk("a PM alert with no way to act fails", len(check_link(nolink)), 1)

    nolabel = good.replace(", actionLabel: 'Open PM Scheduler'", "")
    chk("an unlabelled link fails", len(check_link(nolabel)), 1)

    chk("the live page passes", check_link(io.open(PAGE, encoding='utf-8', errors='replace').read()), [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    print("T29 alert loop closes")
    problems = check_link(io.open(PAGE, encoding="utf-8", errors="replace").read())
    print(f"  PM alert offers a way to act: {'yes' if not problems else 'NO'}")

    row, err, _ = psql("SELECT scope_item_id FROM v_pm_scope_items_truth WHERE is_overdue LIMIT 1;")
    if not row:
        print(f"  SKIP db half — no overdue PM to act on ({err[:70]})")
        for p in problems:
            print(f"    {p}")
        return 1 if problems else 0

    out, err, _ = psql(f"""
begin;
select 'BEFORE|'||count(*) from v_pm_scope_items_truth where is_overdue and scope_item_id='{row}';
insert into pm_completions (id, scope_item_id, asset_id, hive_id, worker_name, status, completed_at)
select gen_random_uuid(), s.scope_item_id, s.pm_asset_id, s.hive_id, '{PROBE}', 'done', now()
from v_pm_scope_items_truth s where s.scope_item_id='{row}';
select 'AFTER|'||count(*) from v_pm_scope_items_truth where is_overdue and scope_item_id='{row}';
rollback;""")
    before = re.search(r"BEFORE\|(\d+)", out or "")
    after = re.search(r"AFTER\|(\d+)", out or "")
    resid, _, _ = psql(f"SELECT count(*) FROM pm_completions WHERE worker_name='{PROBE}';")

    b = int(before.group(1)) if before else -1
    a = int(after.group(1)) if after else -1
    print(f"  overdue rows for that PM: before={b} after completing={a}")
    print(f"  probe completions left behind: {resid}")

    if b < 1:
        problems.append("the chosen PM was not overdue to begin with - nothing was measured")
    elif a != 0:
        problems.append(f"completing the PM did NOT clear its alert source (still {a}) - the loop "
                        f"stays open and the inbox never empties")
    if (resid or "").strip() != "0":
        problems.append("the probe completion survived the rollback")

    if not problems:
        print("\n  PASS - the alert names the action, links to it, and doing it clears the alert.")
        return 0
    print("\n  FAIL")
    for p in problems:
        print(f"    {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
