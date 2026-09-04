#!/usr/bin/env python3
"""validate_analytics_cache_freshness.py — T428's lock: a computed analytics/benchmark cache is never
served STALE after a write.

The failure T428 guards: an analytics or benchmark figure is expensive, so it is cached; if a reader
took whatever row it found, a value computed weeks ago (before the writes that changed it) would be
shown as current. The platform avoids this by making the cache FRESHNESS-TRACKED: every producer
stamps `computed_at` on each compute, and every reader (a) filters to a bounded recency window with
`.gte("computed_at"/"completed_at"/"created_at", now - N days)` so an out-of-window row is excluded,
and (b) takes the newest via `.order(..., { ascending: false })`. So a stale row is filtered out, not
served.

This gate holds those properties on the two producers/readers (benchmark-compute, analytics-
orchestrator):
  1. computed_at is STAMPED on write (`computed_at: ...toISOString()`),
  2. reads are RECENCY-BOUNDED (a `.gte(<ts col>, ... - N * 86400000 ...)` day-math window), and
  3. newest-first ORDERING is used (`.order(..., { ascending: false })`).

Static (source reads), browser-free. Registered in run_platform_checks (Platform)."""
from __future__ import annotations

import io
import re
import sys

CHECK_NAMES = ["analytics-cache-freshness"]
SRCS = [
    "supabase/functions/benchmark-compute/index.ts",
    "supabase/functions/analytics-orchestrator/index.ts",
]


def _read(path: str) -> str | None:
    try:
        return io.open(path, encoding="utf-8").read()
    except Exception:
        return None


def check(sources: dict[str, str]) -> list[str]:
    problems: list[str] = []
    if not sources:
        problems.append("no analytics/benchmark source files readable — cannot verify freshness")
        return problems
    stamps = any(re.search(r"computed_at\s*:\s*[^,\n]*toISOString\(\)", s) for s in sources.values())
    recency = any(re.search(r"\.gte\(\s*['\"](computed_at|completed_at|created_at)['\"].{0,140}86400000", s) for s in sources.values())
    ordering = any(re.search(r"\.order\([^)]*ascending\s*:\s*false", s) for s in sources.values())
    if not stamps:
        problems.append("no `computed_at: ...toISOString()` stamp on write — the cache is not freshness-tracked (a write's recency is unrecorded)")
    if not recency:
        problems.append("no recency-bounded read (`.gte(<ts>, now - N*86400000)`) — an out-of-window stale row would be served")
    if not ordering:
        problems.append("no newest-first `.order(..., { ascending: false })` read — a reader could take an older row over the latest")
    return problems


def main() -> int:
    sources = {p: s for p in SRCS if (s := _read(p)) is not None}
    problems = check(sources)
    if problems:
        print("FAIL analytics-cache-freshness — the cache could serve stale data after a write:")
        for p in problems:
            print(f"    {p}")
        return 1
    print(f"PASS analytics-cache-freshness — across {len(sources)} producer/reader(s), computed_at is stamped on "
          "write, reads are recency-bounded (an out-of-window row is excluded) and newest-first ordered: "
          "a fresh compute propagates and a stale row is never served.")
    return 0


def self_test() -> int:
    good = {"a": 'computed_at: now.toISOString(),\n .gte("computed_at", new Date(now.getTime() - 8 * 86400000).toISOString())\n .order("computed_at", { ascending: false })'}
    fails = []
    if check(good):
        fails.append("a freshness-tracked reader should PASS")
    if not any("freshness-tracked" in p for p in check({"a": good["a"].replace("computed_at: now.toISOString(),", "x")})):
        fails.append("missing computed_at stamp should FAIL")
    if not any("stale row would be served" in p for p in check({"a": good["a"].replace("86400000", "999")})):
        fails.append("missing recency window should FAIL")
    if not any("newest-first" in p for p in check({"a": good["a"].replace("ascending: false", "ascending: true")})):
        fails.append("missing newest-first ordering should FAIL")
    if not any("cannot verify" in p for p in check({})):
        fails.append("no sources should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_analytics_cache_freshness self-test (no-stamp / no-recency / no-ordering / no-sources redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
