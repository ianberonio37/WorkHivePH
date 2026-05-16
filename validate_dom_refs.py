"""
DOM Reference Integrity Validator — WorkHive Platform
======================================================
Catches getElementById() calls that chain a method or property directly
(without optional chaining ?.) where the referenced element ID does not
exist anywhere in the same HTML file.

Root cause of the May 2026 hive.html crash:
  document.getElementById('btn-toggle-mttr').addEventListener(...)
  → no <button id="btn-toggle-mttr"> existed in the HTML
  → TypeError: Cannot read properties of null at page load
  → aborted the entire script block before any other code ran

Collects all id="..." occurrences in the file (both static HTML attrs
and JS template-literal innerHTML renders) so dynamically built sections
don't produce false positives.

  Layer 1 — Bare getElementById chains
    1.  No bare getElementById('id'). on a missing element  [FAIL]

Usage:  python validate_dom_refs.py
Output: dom_refs_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

LIVE_PAGES = [
    "logbook.html", "inventory.html", "pm-scheduler.html",
    "hive.html", "assistant.html", "skillmatrix.html",
    "dayplanner.html", "engineering-design.html", "index.html",
    "platform-health.html", "community.html", "public-feed.html",
    "analytics.html", "marketplace.html", "marketplace-admin.html", "marketplace-seller.html", "marketplace-seller-profile.html",
]

CHECK_NAMES = ["getelementbyid_null_trap", "undefined_canonical_globals"]
CHECK_LABELS = {
    "getelementbyid_null_trap":    "L1  No bare getElementById chain on a missing HTML element  [FAIL]",
    "undefined_canonical_globals": "L2  Canonical ops variables declared before use (WORKER_NAME/HIVE_ID/HIVE_ROLE)  [FAIL]",
}

# Variables that ops-home pages must declare (let/var/const X = ...) before using.
# Scripts loaded from utils.js or nav-hub.js do NOT define these — each page owns
# them, typically from a localStorage read at the top of its main <script> block.
CANONICAL_GLOBALS = ["WORKER_NAME", "HIVE_ID", "HIVE_ROLE", "HIVE_NAME"]


def check_getelementbyid_null_trap(pages):
    """
    getElementById('id'). (direct chain, no ?.) crashes with TypeError when the
    element is absent from the DOM.  getElementById('id') assigned to a variable
    is NOT flagged — only immediate method/property chains are dangerous on load.

    ID collection: scans all id="..." and id='...' in the file regardless of
    context so dynamically rendered sections (innerHTML template literals) don't
    produce false positives.
    """
    issues = []
    bare_re = re.compile(r"getElementById\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\.")

    for page in pages:
        content = read_file(page)
        if content is None:
            continue

        # All IDs defined anywhere in the file — HTML attrs and JS template strings
        all_ids = set(re.findall(r'id\s*=\s*["\']([^"\'> \t\n]+)["\']', content))

        lines = content.splitlines()
        seen = set()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for m in bare_re.finditer(line):
                id_ref = m.group(1)
                # Template literal IDs (e.g. `tool-row-${id}`) are runtime-constructed;
                # static analysis can't resolve them — skip to avoid false positives
                if "${" in id_ref:
                    continue
                if id_ref in all_ids:
                    continue
                key = (page, id_ref)
                if key in seen:
                    continue
                seen.add(key)
                issues.append({
                    "check": "getelementbyid_null_trap",
                    "page": page,
                    "line": i + 1,
                    "reason": (
                        f"{page}:{i + 1} bare getElementById('{id_ref}'). — "
                        f"no id=\"{id_ref}\" found in {page}; "
                        f"returns null at runtime and immediately throws TypeError, "
                        f"aborting the entire script block; "
                        f"add ?. for optional elements or add the missing HTML element"
                    )
                })
    return issues


def check_undefined_canonical_globals(pages):
    """Any page that USES WORKER_NAME / HIVE_ID / HIVE_ROLE / HIVE_NAME must also
    DECLARE it (let/var/const X = ... or X = ...).  A use-without-declaration
    throws ReferenceError at runtime, crashing the entire script block.

    Detection: checks each inline <script> block independently — externally
    loaded scripts (utils.js, nav-hub.js) do not declare these.
    """
    issues = []
    decl_re = re.compile(
        r'(?:let|var|const)\s+({vars})\s*=|({vars})\s*=\s*[^=]'
        .format(vars="|".join(CANONICAL_GLOBALS))
    )
    use_re_map = {v: re.compile(rf'\b{v}\b') for v in CANONICAL_GLOBALS}

    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        # Extract inline script blocks only (skip <script src="...">)
        script_blocks = re.findall(r'<script(?:\s(?!src)[^>]*)?>(.+?)</script>',
                                   content, re.DOTALL | re.IGNORECASE)
        combined_script = "\n".join(script_blocks)
        if not combined_script.strip():
            continue

        # Which canonical variables are declared anywhere in the page's inline scripts?
        declared = set()
        for m in decl_re.finditer(combined_script):
            for g in m.groups():
                if g and g in CANONICAL_GLOBALS:
                    declared.add(g)

        for var in CANONICAL_GLOBALS:
            if var in declared:
                continue
            if not use_re_map[var].search(combined_script):
                continue
            issues.append({
                "check": "undefined_canonical_globals",
                "page": page,
                "line": 0,
                "reason": (
                    f"{page} uses '{var}' but never declares it — "
                    f"add `const {var} = localStorage.getItem('wh_{var.lower()}') || '';` "
                    f"near the top of the main script block; "
                    f"missing declaration causes ReferenceError that aborts the script"
                ),
            })
    return issues


# ── Runner ────────────────────────────────────────────────────────────────────

def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nDOM Reference Integrity Validator"))
    print("=" * 40)

    all_issues = check_getelementbyid_null_trap(LIVE_PAGES)
    all_issues += check_undefined_canonical_globals(LIVE_PAGES)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "dom_refs",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("dom_refs_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
