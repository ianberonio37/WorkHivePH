"""
Companion Launcher Page Coverage Validator (L0, forward-only ratchet)
=====================================================================
Every page that loads nav-hub.js MUST also load companion-launcher.js.
This ensures Zaniah & Hezekiah companions are available to all users
across the entire WorkHive platform.

Allowlisted intentional exclusions:
  - assistant.html (has dedicated AI, guard in companion-launcher init())
  - index.html (landing page, companion via wh-persona.js inline)
  - agentic-rag-observability.html (dev/ops tool, not user-facing)
  - Any file not ending in .html (e.g., .php, .txt)

Output: companion_page_coverage_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "companion_page_coverage_report.json"
BASELINE_PATH = ROOT / "companion_page_coverage_baseline.json"

# Allowlisted pages that intentionally do NOT load companion-launcher.js
ALLOWLIST = {
    "assistant.html",                  # dedicated AI, guard in companion-launcher init()
    "index.html",                      # landing page — companion via wh-persona.js inline
    "agentic-rag-observability.html",  # dev/ops tool
    "platform-health.html",            # already has companion (platform health board)
    "engineering-design-test.html",    # test/staging page, not user-facing
    "index-hive-test.html",            # test/staging page, not user-facing
    "index-native-test.html",          # test/staging page, not user-facing
}

# Sentinel binding: name L2 test `test('companion_page_coverage: ...')` for coverage credit.
CHECK_NAMES = ["companion_page_coverage"]


def _check_html_file(path: Path) -> tuple[bool, str | None]:
    """
    Returns (passes, issue_description).
    - passes=True if companion-launcher.js is present OR file is allowlisted
    - passes=False if file loads nav-hub.js but NOT companion-launcher.js
    """
    body = path.read_text(encoding="utf-8", errors="replace")

    # Check if file is in allowlist
    if path.name in ALLOWLIST:
        return True, None

    # Check if file loads nav-hub.js
    has_nav_hub = "nav-hub.js" in body
    if not has_nav_hub:
        # File doesn't load nav-hub, so it's out of scope for this check
        return True, None

    # File loads nav-hub.js, so it MUST load companion-launcher.js
    has_companion = "companion-launcher.js" in body
    if has_companion:
        return True, None

    # Failed: has nav-hub but no companion
    return False, f"loads nav-hub.js but missing companion-launcher.js"


def main() -> int:
    root_dir = ROOT
    if not root_dir.exists():
        print("PASS — root directory not found.")
        return 0

    issues = []
    scanned = 0
    in_scope = 0

    for path in sorted(root_dir.glob("*.html")):
        scanned += 1
        passes, issue_desc = _check_html_file(path)

        # Check if this file is in scope (loads nav-hub.js)
        body = path.read_text(encoding="utf-8", errors="replace")
        if "nav-hub.js" in body and path.name not in ALLOWLIST:
            in_scope += 1

        if not passes:
            issues.append({
                "file": path.name,
                "issue": issue_desc,
            })

    drift = len(issues)
    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")

    # Forward-only ratchet: drift can only decrease or stay same, never increase
    if drift < baseline:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {
            "html_files_scanned": scanned,
            "nav_hub_pages_in_scope": in_scope,
            "companion_required_pages": in_scope,
            "companion_missing": drift,
            "baseline": baseline,
        },
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nCompanion Launcher Page Coverage Validator (L0)")
    print("=" * 56)
    print(f"  HTML files scanned:              {scanned}")
    print(f"  Pages that load nav-hub.js:      {in_scope}")
    print(f"  Companion-launcher.js required:  {in_scope}")
    print(f"  Companion-launcher.js missing:   {drift}  (baseline: {baseline})")

    if not drift:
        print("\n  PASS — every nav-hub page has companion-launcher.js.")
        return 0

    print("\n  FAILING pages (load nav-hub.js but missing companion-launcher.js):")
    for i in issues[:25]:
        print(f"    {i['file']:40} — {i['issue']}")

    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
