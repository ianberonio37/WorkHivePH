#!/usr/bin/env python3
"""validate_announcement_reach_moderation.py — T149's lock: a hive announcement's REACH respects
moderation — a removed post does not keep announcing itself.

T149 (broadcast semantics) walked the reach test and found the failure: an announcement is a
supervisor-only post category whose ONLY standing reach is the nav-hub badge (there is no
notify-on-post trigger; notify_post_mentions fires only on explicit @mentions at creation). The bug
was that the badge counted posts that had been MODERATED (soft-deleted), so a removed announcement
still lit the badge for every worker. And it must be the QUERY that excludes them, because — as the
code comment records — the member branch of community_posts_read RLS does not filter soft-deletes.

This gate holds two properties:
  1. the nav-hub badge count query filters `.is('deleted_at', null)` on the posts source, so a
     moderated post cannot inflate the badge (its reach is revoked with the moderation); and
  2. the announcement category is guarded supervisor-only (trg_guard_community_announcement enforces
     the supervisor constraint), so only a supervisor can broadcast in the first place.

Static (nav-hub.js) + DB (trigger); browser-free. SKIPs the DB half if unreachable. Registered in
run_platform_checks (Platform)."""
from __future__ import annotations

import io
import re
import subprocess
import sys

CHECK_NAMES = ["announcement-reach-moderation"]
NAVHUB = "nav-hub.js"


def _read(path: str) -> str | None:
    try:
        return io.open(path, encoding="utf-8").read()
    except Exception:
        return None


def _guard_enforces_supervisor() -> bool | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A",
             "-c", "select (pg_get_functiondef((select p.oid from pg_trigger t join pg_proc p on p.oid=t.tgfoid "
                   "join pg_class c on c.oid=t.tgrelid where c.relname='community_posts' "
                   "and t.tgname='trg_guard_community_announcement')) ilike '%supervisor%')::text;"],
            capture_output=True, text=True, timeout=45)
        if r.returncode != 0:
            return None
        return (r.stdout or "").strip() == "true"
    except Exception:
        return None


def check(navhub: str | None, guard: bool | None) -> list[str]:
    problems: list[str] = []
    if navhub is None:
        problems.append("nav-hub.js not found — cannot verify the badge (the announcement's only reach)")
    else:
        # the badge query must both count posts AND exclude soft-deleted ones
        counts_posts = "v_community_posts_truth" in navhub or "community_posts" in navhub
        excludes_deleted = bool(re.search(r"\.is\(\s*['\"]deleted_at['\"]\s*,\s*null\s*\)", navhub))
        if not counts_posts:
            problems.append("nav-hub badge no longer reads community_posts — its reach source is unclear")
        elif not excludes_deleted:
            problems.append("nav-hub badge query does not filter .is('deleted_at', null) — a MODERATED post still lights the badge for every worker (RLS does not exclude soft-deletes for members)")
    if guard is None:
        pass  # DB unreachable — do not fail on the DB half
    elif guard is False:
        problems.append("trg_guard_community_announcement does not enforce supervisor-only — anyone could broadcast an announcement")
    return problems


def main() -> int:
    navhub = _read(NAVHUB)
    guard = _guard_enforces_supervisor()
    problems = check(navhub, guard)
    if problems:
        print("FAIL announcement-reach-moderation — a moderated announcement can still reach workers:")
        for p in problems:
            print(f"    {p}")
        return 1
    tail = "" if guard is not None else " (supervisor-guard check skipped — DB unreachable)"
    print("PASS announcement-reach-moderation — the nav-hub badge counts community posts but excludes "
          "soft-deleted ones (a moderated announcement's reach is revoked), and the announcement category is "
          f"supervisor-guarded: a removed post does not keep announcing itself.{tail}")
    return 0


def self_test() -> int:
    good = "db.from('v_community_posts_truth').eq('hive_id', h).is('deleted_at', null).gt('created_at', since)"
    fails = []
    if check(good, True):
        fails.append("badge excluding deleted + supervisor guard should PASS")
    if not any("MODERATED post still lights" in p for p in check(good.replace(".is('deleted_at', null)", ""), True)):
        fails.append("badge not excluding deleted should FAIL")
    if not any("supervisor-only" in p for p in check(good, False)):
        fails.append("guard not enforcing supervisor should FAIL")
    if check(good, None):
        fails.append("DB-unreachable should not fail the file half")
    if not any("not found" in p for p in check(None, True)):
        fails.append("missing nav-hub should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_announcement_reach_moderation self-test (no-deleted-filter / non-supervisor-guard / missing redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
