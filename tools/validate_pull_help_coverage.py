#!/usr/bin/env python3
"""validate_pull_help_coverage.py — T174's lock: pull-help is everywhere a worker works, and every
guide link it offers is REAL.

T174 ("the help system: pull-help everywhere") found the help gap was a WIRING problem, not a content
one: learn-link.js offers a one-tap link from a tool page to its /learn/ guide, driven by
learn_links.json (generated from wh_pages.LEARN_ARTICLES). Two ways this silently rots:
  1. COVERAGE — a core worker-facing tool page drops out of learn_links.json, so the worker on it has
     no guide affordance; and
  2. DANGLING GUIDE — an entry points at a /learn/<slug>/ article that does not exist, so the pull-help
     pill links to nothing (worse than absent: it promises help and 404s).

This gate holds both: learn_links.json covers at least the core worker-facing tool pages, and EVERY
guide slug it lists resolves to a real /learn/<slug>/index.html. (Founder/utility sub-pages —
founder-console, symbol-gallery, report-sender, etc. — are intentionally not worker guide targets.)

Static (file + fs), browser-free. Registered in run_platform_checks (Platform)."""
from __future__ import annotations

import io
import json
import os
import sys

CHECK_NAMES = ["pull-help-coverage"]
# core worker-facing tool pages that MUST offer a guide (a floor, not the full list)
CORE_PAGES = [
    "index.html", "logbook.html", "pm-scheduler.html", "inventory.html", "asset-hub.html",
    "alert-hub.html", "analytics.html", "hive.html", "skillmatrix.html", "community.html",
    "marketplace.html", "engineering-design.html", "shift-brain.html", "dayplanner.html",
    "project-manager.html", "resume.html", "achievements.html", "voice-journal.html",
]


def _load() -> dict | None:
    try:
        return json.load(io.open("learn_links.json", encoding="utf-8"))
    except Exception:
        return None


def check(links: dict | None) -> list[str]:
    problems: list[str] = []
    if links is None:
        problems.append("learn_links.json missing/unreadable — pull-help has no data source")
        return problems
    for p in CORE_PAGES:
        if not links.get(p):
            problems.append(f"core page {p} has no pull-help guide entry — a worker there gets no guide affordance")
    for page, guides in links.items():
        for g in (guides or []):
            slug = g.get("slug", "")
            if not slug or not os.path.exists(os.path.join("learn", slug, "index.html")):
                problems.append(f"{page} -> /learn/{slug}/ is a DANGLING guide link (the article does not exist)")
    return problems


def generated_drift() -> list[str]:
    """The file must BE what the catalog generates (ENH-L, 2026-10-23): it claimed to be generated and
    nothing generated it, so it still filed the LOTO guide under Audit weeks after the catalog moved it."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_learn_links
    return [f"learn_links.json is not what the catalog generates - {d} (run python tools/build_learn_links.py)"
            for d in build_learn_links.drift()]


def main() -> int:
    links = _load()
    problems = check(links) + (generated_drift() if links is not None else [])
    if problems:
        print("FAIL pull-help-coverage — pull-help is incomplete or points at missing guides:")
        for p in problems[:12]:
            print(f"    {p}")
        return 1
    total = sum(len(v or []) for v in links.values())
    print(f"PASS pull-help-coverage — all {len(CORE_PAGES)} core worker-facing pages have a pull-help guide, and all "
          f"{total} guide links across {len(links)} pages resolve to real /learn/ articles: help is everywhere a worker works, and real.")
    return 0


def self_test() -> int:
    fails = []
    good = {p: [{"slug": "x", "title": "T"}] for p in CORE_PAGES}
    import unittest.mock as m
    with m.patch("os.path.exists", return_value=True):
        if check(good):
            fails.append("full coverage + resolving slugs should PASS")
        bad = dict(good); del bad["logbook.html"]
        if not any("logbook.html" in p for p in check(bad)):
            fails.append("a missing core page should FAIL")
    with m.patch("os.path.exists", return_value=False):
        if not any("DANGLING" in p for p in check({"index.html": [{"slug": "gone", "title": "T"}]})):
            fails.append("a dangling guide link should FAIL")
    if not any("no data source" in p for p in check(None)):
        fails.append("missing learn_links.json should FAIL")
    import build_learn_links as bl
    real = bl.OUT.read_text(encoding="utf-8")
    drifted = json.loads(real)
    drifted["audit-log.html"] = drifted.get("audit-log.html", []) + [{"slug": "loto-procedures-dole-oshs-template", "title": "T"}]
    with m.patch.object(bl.Path, "read_text", return_value=json.dumps(drifted)):
        if not bl.drift():
            fails.append("a file that differs from the catalog should FAIL")
    if bl.drift():
        fails.append("the shipped learn_links.json should match the catalog")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_pull_help_coverage self-test (missing-core-page / dangling-guide / no-data-source / "
          "drift-from-the-catalog redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
