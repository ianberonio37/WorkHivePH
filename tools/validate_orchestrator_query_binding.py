#!/usr/bin/env python3
"""validate_orchestrator_query_binding.py — every read of an RLS-DISABLED truth view must be BOUND.

FOUND 2026-09-10, walking analytics as a solo owner (jun.vanowner@workhive.test, no hive, 0 assets).
`analytics-orchestrator`'s scope query bound on `assetIds` OR `hiveId` and had no third leg, while
every sibling fetch in the same file uses the pair `if (hiveId) ... else if (workerName) ...`. Because
`v_pm_scope_items_truth` is RLS-DISABLED BY DESIGN — it expects an explicit filter — the read came
back UNFILTERED: 69 rows belonging to Baguio Textile Mills rendered on a stranger's analytics page,
asset ids unresolved but task text ("Visual + amp draw check", "Vibration trend reading at DE/NDE")
fully legible.

WHY A GATE AND NOT JUST A FIX. The hole existed because the ONE query that differed from its
neighbours looked reasonable in isolation: it had two filters, both conditional, and no line of it was
wrong on its own. Only the CALLER STATE that satisfies neither condition exposes it, and that state —
signed in, no hive, no assets — could not be cast at all until the solo personas were seeded. A
reviewer cannot be relied on to imagine an un-castable persona; a checker can be told to look.

WHAT IT ASSERTS, per query built on a view this file declares RLS-disabled:
  1. a hive binding exists            (.eq("hive_id", ...))
  2. AND a non-hive caller is handled: either an `else if (workerName)` leg, or an explicit
     "unbound" guard whose name contains `Unbound` that short-circuits the query.
A query with neither is REFUSED by name.

It also refuses a raw-id display fallback (`|| x.asset_id` in an `asset_name:` position), which is how
the same defect SHOWED itself: a 36-character UUID where a person expects an asset's name.

  python tools/validate_orchestrator_query_binding.py --check
  python tools/validate_orchestrator_query_binding.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions" / "analytics-orchestrator" / "index.ts"

# Views this file itself documents as RLS-disabled / explicitly-filtered. Kept as a literal list so
# adding a new one is a deliberate edit, not something a regex quietly starts or stops covering.
RLS_DISABLED_VIEWS = ["v_pm_scope_items_truth"]

QUERY_RE = re.compile(r'const\s+(\w+)\s*=\s*db\s*\.from\(\s*"([^"]+)"\s*\)')
# `|| s.asset_id` used to fill an asset_name — the display half of the same defect.
RAW_ID_FALLBACK_RE = re.compile(r'asset_name:\s*[^,\n]*\|\|\s*\w+\.asset_id\b')


def strip_comments(src: str) -> str:
    """Comments quote the very patterns we look for, so they must not count as code."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l for l in src.splitlines() if not l.strip().startswith("//"))


def audit(src: str) -> list[str]:
    problems: list[str] = []
    code = strip_comments(src)

    for m in QUERY_RE.finditer(code):
        var, view = m.group(1), m.group(2)
        if view not in RLS_DISABLED_VIEWS:
            continue
        # the query's own filter block: from its declaration to the next blank-line-separated stanza
        tail = code[m.end():]
        block = tail[: tail.find("\n\n") if "\n\n" in tail else len(tail)]
        has_hive = f'{var}.eq("hive_id"' in block
        has_worker = f'{var}.eq("worker_name"' in block
        has_unbound = re.search(rf"\b\w*Unbound\b", block) is not None
        if not has_hive:
            problems.append(f"{var} reads RLS-disabled {view} with no hive binding")
        elif not (has_worker or has_unbound):
            problems.append(
                f"{var} reads RLS-disabled {view} and binds ONLY when a hive is present — "
                f"a signed-in caller with no hive and no asset list would read every tenant's rows. "
                f"Add an `else if (workerName)` leg or an explicit `{var}Unbound` short-circuit.")

    for m in RAW_ID_FALLBACK_RE.finditer(code):
        problems.append("asset_name falls back to a raw asset_id: " + m.group(0).strip()[:70])

    return problems


def self_test() -> int:
    bad = '''
  const scopeQ = db.from("v_pm_scope_items_truth")
    .select("id, asset_id");
  if (assetIds.length) scopeQ.in("asset_id", assetIds);
  if (hiveId) scopeQ.eq("hive_id", hiveId);

  const other = 1;
'''
    good_worker = '''
  const scopeQ = db.from("v_pm_scope_items_truth")
    .select("id, asset_id");
  if (hiveId) scopeQ.eq("hive_id", hiveId);
  else if (workerName) scopeQ.eq("worker_name", workerName);

  const other = 1;
'''
    good_unbound = '''
  const scopeQ = db.from("v_pm_scope_items_truth")
    .select("id, asset_id");
  if (assetIds.length) scopeQ.in("asset_id", assetIds);
  if (hiveId) scopeQ.eq("hive_id", hiveId);
  const scopeUnbound = !hiveId && !assetIds.length;

  const other = 1;
'''
    commented_only = '''
  // if (hiveId) scopeQ.eq("hive_id", hiveId);  — a comment must not satisfy the check
  const scopeQ = db.from("v_pm_scope_items_truth").select("id");

  const other = 1;
'''
    raw_id = 'asset_name:   assetMap[s.asset_id] || s.asset_id,'
    cases = [
        ("unbound solo path is REFUSED", bad, True),
        ("worker_name leg passes", good_worker, False),
        ("explicit Unbound guard passes", good_unbound, False),
        ("a commented-out binding does NOT pass", commented_only, True),
        ("raw asset_id fallback is REFUSED", raw_id, True),
    ]
    fails = 0
    for name, src, expect_problem in cases:
        got = bool(audit(src))
        ok = got == expect_problem
        print(("  PASS " if ok else "  FAIL ") + name)
        if not ok:
            fails += 1
    print(f"self-test: {len(cases) - fails}/{len(cases)} passed")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if not FN.exists():
        print(f"SKIP orchestrator-query-binding — {FN.name} not found")
        return 0
    problems = audit(io.open(FN, encoding="utf-8").read())
    if problems:
        print("FAIL orchestrator-query-binding — an RLS-disabled view can be read unbound:")
        for p in problems:
            print("  " + p)
        return 1
    print("PASS orchestrator-query-binding — every read of an RLS-disabled truth view binds the "
          "hive AND handles a caller who has none; no asset_name falls back to a raw id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
