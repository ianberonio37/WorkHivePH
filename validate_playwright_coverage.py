"""
Playwright Coverage Validator — WorkHive Platform
==================================================
Catches the "I added a new tool page but no .spec.ts exists for it"
mistake. Without this gate, new pages silently lack any UI test coverage
even if validate_tester_coverage.py says the Python smoke/visual/mobile/perf
flow lists were updated — those flows are coarse-grained smoke walkers; the
new Node @playwright/test suite under `tests/` is where per-page interaction
locks live (silent-failure regression, form-submit blocks, etc).

Source of truth: validate_assistant.py LIVE_TOOL_PAGES (the canonical roster
of live tool pages). Every entry there must have a matching tests/<page>.spec.ts
file with at least one `test(` block — otherwise it's a coverage gap.

Layer 1 — Spec file present
  Every LIVE_TOOL_PAGE has tests/<page>.spec.ts on disk.

Layer 2 — Spec is non-empty
  The file contains at least one `test(` call (not just an empty stub
  or commented-out scaffold).

Layer 3 — Spec navigates to its page
  The file's goto() / .navigate() lines reference '/workhive/<page>.html'
  somewhere. Prevents the copy-paste mistake of duplicating logbook.spec.ts
  as inventory.spec.ts but forgetting to swap the URL.

Layer 4 — Listed in playwright.config.ts
  The tests/ directory is covered by the testDir glob. Otherwise the
  spec exists but Playwright never picks it up.

Pages explicitly opted-out (rare; e.g. retired pages) are listed in
OPT_OUT below with a reason.

Usage:  python validate_playwright_coverage.py
Output: playwright_coverage_report.json
"""
from __future__ import annotations

import json
import os
import re
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import format_result

ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(ROOT, "tests")
CONFIG_FILE = os.path.join(ROOT, "playwright.config.ts")

# Pages allowed to skip the new Node Playwright suite for a documented reason.
# Today: none — the legacy Python smoke walker covers assistant.html, but the
# Node suite has its own assistant.spec.ts too, so no exemption is needed.
OPT_OUT: dict = {}


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _live_tool_pages() -> list:
    src = _read(os.path.join(ROOT, "validate_assistant.py"))
    m = re.search(r"LIVE_TOOL_PAGES\s*=\s*\[([^\]]*)\]", src, re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    return re.findall(r'["\']([\w\-]+)["\']', body)


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nPlaywright Coverage Validator"))
    print("=" * 60)

    CHECK_NAMES = ["spec_present", "spec_nonempty", "spec_navigates", "config_picks_up_tests"]
    CHECK_LABELS = {
        "spec_present":          "L1  Every LIVE_TOOL_PAGE has tests/<page>.spec.ts",
        "spec_nonempty":         "L2  Each spec contains at least one test(...) block",
        "spec_navigates":        "L3  Each spec navigates to /workhive/<page>.html",
        "config_picks_up_tests": "L4  playwright.config.ts covers the tests/ dir",
    }
    issues = []

    live = _live_tool_pages()
    if not live:
        print("[FAIL] Could not parse LIVE_TOOL_PAGES from validate_assistant.py")
        sys.exit(1)

    # L1: spec_present + L2/L3 follow only for pages that pass L1
    missing_specs = []
    empty_specs = []
    wrong_url_specs = []

    for page in live:
        if OPT_OUT.get(page):
            continue
        spec_path = os.path.join(TESTS_DIR, f"{page}.spec.ts")
        if not os.path.exists(spec_path):
            missing_specs.append(page)
            continue

        src = _read(spec_path)
        # L2: non-empty — must have a test() call
        if not re.search(r"\btest\s*\(\s*['\"`]", src):
            empty_specs.append(page)
            continue

        # L3: navigates to its page — accepts any of:
        #   goto('/workhive/<page>.html')
        #   navigate('/workhive/<page>.html')
        #   smokePage(whPage, '/workhive/<page>.html', ...)   ← shared template
        # The page slug must appear inside a string literal that's the URL arg
        # of one of these calls. Catches the copy-paste mistake of cloning
        # logbook.spec.ts as inventory.spec.ts but forgetting to swap the URL.
        nav_pattern = re.compile(
            rf"(?:goto|navigate|smokePage)\s*\([^)]*['\"`][^'\"`]*{re.escape(page)}\.html",
            re.DOTALL,
        )
        if not nav_pattern.search(src):
            wrong_url_specs.append(page)

    if missing_specs:
        issues.append({
            "check": "spec_present", "skip": False,
            "reason": (
                f"{len(missing_specs)} live page(s) have no Playwright spec: "
                f"{', '.join(missing_specs)}. "
                f"Run `python tools/gen_smoke_specs.py` to scaffold, or "
                f"hand-write tests/<page>.spec.ts for richer interaction coverage."
            ),
        })

    if empty_specs:
        issues.append({
            "check": "spec_nonempty", "skip": False,
            "reason": (
                f"{len(empty_specs)} spec(s) exist but contain no test(...) block: "
                f"{', '.join(empty_specs)}. "
                f"Add at least one smoke test or delete the empty file."
            ),
        })

    if wrong_url_specs:
        issues.append({
            "check": "spec_navigates", "skip": False,
            "reason": (
                f"{len(wrong_url_specs)} spec(s) never call goto() on a URL "
                f"containing their page slug: {', '.join(wrong_url_specs)}. "
                f"Likely a copy-paste leftover from another spec — update the goto()."
            ),
        })

    # L4: playwright config exists and references tests/
    config_src = _read(CONFIG_FILE)
    if not config_src:
        issues.append({
            "check": "config_picks_up_tests", "skip": False,
            "reason": f"{CONFIG_FILE} not found — Playwright can't discover any spec",
        })
    elif not re.search(r"testDir\s*:\s*['\"`]\.?/?tests", config_src):
        # Default testDir is the project root, which still picks up tests/*.spec.ts
        # via the glob; only flag if testDir is set AND points elsewhere.
        if re.search(r"testDir\s*:", config_src):
            issues.append({
                "check": "config_picks_up_tests", "skip": False,
                "reason": "playwright.config.ts has testDir but does not point at tests/",
            })

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print(f"\n  Live pages: {len(live)} (from validate_assistant.py)")
    print(f"  Spec files: {len([p for p in live if os.path.exists(os.path.join(TESTS_DIR, f'{p}.spec.ts'))])} matching")

    with open(os.path.join(ROOT, "playwright_coverage_report.json"), "w", encoding="utf-8") as f:
        json.dump({
            "validator":     "playwright_coverage",
            "live_pages":    live,
            "missing_specs": missing_specs,
            "empty_specs":   empty_specs,
            "wrong_url_specs": wrong_url_specs,
            "issues":        [i for i in issues if not i.get("skip")],
        }, f, indent=2, default=str)

    if n_fail == 0 and n_warn == 0:
        print(f"\n  \033[92mAll {len(CHECK_NAMES)} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\n  \033[93m{n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\n  \033[91m{n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
