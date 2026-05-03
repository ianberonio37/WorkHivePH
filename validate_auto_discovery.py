"""
Auto-discovery Validator — WorkHive Platform
=============================================
Catches the "I forgot to register this new thing" mistake before it
silently degrades the platform. Three layers:

  Layer 1 — HTML page classification
    Every *.html in the project root must be classified as one of:
      - LIVE_TOOL_PAGES    (in validate_assistant.py LIVE_TOOL_PAGES)
      - RETIRED_PAGES      (in validate_assistant.py RETIRED_PAGES)
      - NON_TOOL_PAGES     (declared here: landing, satellite, dev variants)
      - test/backup variants (skipped by suffix pattern)
    A new HTML file that's none of the above triggers FAIL with the
    exact registries to update.

  Layer 2 — Edge function config coverage
    Every supabase/functions/<dir>/index.ts (or .py) must have a
    matching [functions.<dir>] block in supabase/config.toml.

  Layer 3 — Validator registration
    Every validate_*.py at the project root must be referenced in
    run_platform_checks.py's VALIDATORS list. Catches the case where
    you write a new validator and forget to wire it to the gate.

Usage:  python validate_auto_discovery.py
Output: auto_discovery_report.json
"""
import os
import re
import sys
import glob
import json

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Pages that exist for a reason but are not "tools" ─────────────────────────
# Landing pages, marketing, marketplace satellites, special-purpose viewers.
# Add a comment whenever you extend this list so the why doesn't get lost.
NON_TOOL_PAGES = {
    "index.html",                    # landing page
    "architecture.html",             # public architecture overview
    "marketplace-admin.html",        # platform admin only, not a worker tool
    "marketplace-seller.html",       # seller dashboard, gated separately
    "marketplace-seller-profile.html",  # seller profile editor
    "public-feed.html",              # public community feed (no auth required)
    "symbol-gallery.html",           # asset/symbol reference page
    "platform-health.html",          # retired Phase 7, deprecated banner only
}

# ── Suffix patterns for test/scratch variants (skipped without complaint) ─────
SKIP_SUFFIX_PATTERNS = [
    re.compile(r"-test\.html$"),
    re.compile(r"\.backup\d*\.html$"),
    re.compile(r"^index-[\w-]+-test\.html$"),  # index-hive-test, index-v3-test
    re.compile(r"^index-[\w-]+\.html$"),       # index-native, etc.
]


def _is_test_or_backup(filename: str) -> bool:
    return any(p.search(filename) for p in SKIP_SUFFIX_PATTERNS)


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


# ── Layer 1: HTML page classification ─────────────────────────────────────────

def check_html_classified() -> dict:
    # Pull canonical lists from validate_assistant.py so they stay in sync.
    assistant_src = _read(os.path.join(ROOT, "validate_assistant.py"))
    live = _extract_string_list(assistant_src, "LIVE_TOOL_PAGES")
    retired = _extract_string_list(assistant_src, "RETIRED_PAGES")
    if not live:
        return {
            "id": "html_classified",
            "status": "WARN",
            "message": "Could not parse LIVE_TOOL_PAGES from validate_assistant.py — skipping classification check",
            "details": [],
        }

    # Convert "logbook" -> "logbook.html"
    live_set    = {f"{p}.html" for p in live}
    retired_set = {f"{p}.html" for p in retired}

    html_files = sorted(
        os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "*.html"))
    )
    unclassified = []
    for f in html_files:
        if _is_test_or_backup(f):
            continue
        if f in live_set or f in retired_set or f in NON_TOOL_PAGES:
            continue
        unclassified.append(f)

    if not unclassified:
        return {
            "id": "html_classified",
            "status": "PASS",
            "message": f"all {len(html_files)} HTML files classified (live/retired/non-tool/scratch)",
            "details": [],
        }

    return {
        "id": "html_classified",
        "status": "FAIL",
        "message": f"{len(unclassified)} HTML file(s) not classified — add to LIVE_TOOL_PAGES, RETIRED_PAGES, or NON_TOOL_PAGES: {', '.join(unclassified)}",
        "details": unclassified,
    }


def _extract_string_list(src: str, varname: str) -> list:
    """Pull a Python list-of-strings literal by variable name."""
    m = re.search(
        rf"{re.escape(varname)}\s*=\s*\[([^\]]*)\]",
        src,
        re.DOTALL,
    )
    if not m:
        return []
    body = m.group(1)
    return re.findall(r'"([^"]+)"', body) + re.findall(r"'([^']+)'", body)


# ── Layer 2: Edge function config coverage ────────────────────────────────────

def check_edge_function_config() -> dict:
    fns_dir = os.path.join(ROOT, "supabase", "functions")
    config_toml = os.path.join(ROOT, "supabase", "config.toml")
    if not os.path.isdir(fns_dir):
        return {
            "id": "edge_function_config",
            "status": "PASS",
            "message": "no supabase/functions/ dir — skipping",
            "details": [],
        }
    if not os.path.exists(config_toml):
        return {
            "id": "edge_function_config",
            "status": "FAIL",
            "message": "supabase/config.toml missing",
            "details": [],
        }
    config_text = _read(config_toml)
    missing = []
    for entry in sorted(os.listdir(fns_dir)):
        fn_dir = os.path.join(fns_dir, entry)
        if not os.path.isdir(fn_dir):
            continue
        if entry.startswith("_") or entry == "tests":
            continue  # _shared, _common, tests/
        # Has an index.ts or index.py?
        has_entry = (
            os.path.exists(os.path.join(fn_dir, "index.ts"))
            or os.path.exists(os.path.join(fn_dir, "index.py"))
        )
        if not has_entry:
            continue
        # Look for [functions.<entry>] block (TOML section)
        if not re.search(rf"\[functions\.{re.escape(entry)}\]", config_text):
            missing.append(entry)

    if not missing:
        return {
            "id": "edge_function_config",
            "status": "PASS",
            "message": "every edge function has a config.toml entry",
            "details": [],
        }
    return {
        "id": "edge_function_config",
        "status": "FAIL",
        "message": f"{len(missing)} edge function(s) missing from supabase/config.toml: {', '.join(missing)}. "
                   f"Add a [functions.<name>] block with verify_jwt = true/false.",
        "details": missing,
    }


# ── Layer 3: Validator registration ───────────────────────────────────────────

def check_validator_registration() -> dict:
    # The platform orchestrator runs validate_*.py directly OR invokes a
    # suite (like run_all_checks.py for engineering calcs) which in turn
    # registers its own sub-validators. Scan both.
    REGISTRY_FILES = ["run_platform_checks.py", "run_all_checks.py"]

    referenced = set()
    found_any_registry = False
    for rel in REGISTRY_FILES:
        src = _read(os.path.join(ROOT, rel))
        if src:
            found_any_registry = True
            referenced.update(re.findall(r'"script"\s*:\s*"(validate_[\w_]+\.py)"', src))

    if not found_any_registry:
        return {
            "id": "validator_registered",
            "status": "WARN",
            "message": "no validator-registry files found (run_platform_checks.py / run_all_checks.py) — skipping",
            "details": [],
        }

    # Files validate_X.py at root, excluding utilities/helpers and the
    # auto-discovery validator itself (it's registered separately below).
    EXCLUDE = {"validator_utils.py"}
    actual = sorted(
        os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "validate_*.py"))
        if os.path.basename(p) not in EXCLUDE
    )

    missing = [f for f in actual if f not in referenced]
    if not missing:
        return {
            "id": "validator_registered",
            "status": "PASS",
            "message": f"all {len(actual)} validators registered (in run_platform_checks.py or run_all_checks.py)",
            "details": [],
        }
    return {
        "id": "validator_registered",
        "status": "FAIL",
        "message": f"{len(missing)} validator(s) not registered in run_platform_checks.py or run_all_checks.py: "
                   f"{', '.join(missing)}. The gate won't run them until you add an entry.",
        "details": missing,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    checks = [
        check_html_classified(),
        check_edge_function_config(),
        check_validator_registration(),
    ]

    fails = [c for c in checks if c["status"] == "FAIL"]
    warns = [c for c in checks if c["status"] == "WARN"]
    passes = [c for c in checks if c["status"] == "PASS"]

    print("=" * 70)
    print("AUTO-DISCOVERY VALIDATOR")
    print("=" * 70)
    for c in checks:
        icon = {"PASS": "[OK]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[c["status"]]
        print(f"  {icon} {c['id']:30} {c['message']}")
    print()
    print(f"  Summary: {len(passes)} pass · {len(warns)} warn · {len(fails)} fail")

    report = {
        "ok": len(fails) == 0,
        "summary": {"pass": len(passes), "warn": len(warns), "fail": len(fails)},
        "checks": checks,
    }
    out_path = os.path.join(ROOT, "auto_discovery_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  Report: {out_path}")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
