"""
Contact Consistency Validator — WorkHive Platform
==================================================
Enforces [[project-admin-email-setup]]: the ONLY public-facing contact address
is `admin@workhiveph.com`. Any reference to the old `hello@workhiveph.com`
(never wired) or the personal `ian.beronio37@gmail.com` in public files is a
regression.

Catches accidental copy-paste of stale addresses into new pages or new content.

Layer 1: hello@workhiveph.com must not appear in any public-facing HTML or
         markdown surface (llms.txt, sitemap.xml, etc.)
Layer 2: ian.beronio37@gmail.com must not appear in any public-facing surface
Layer 3: At least ONE admin@workhiveph.com reference must exist in:
         - index.html footer
         - llms.txt
         - the Organization JSON-LD on index.html
         (so the contact is always discoverable to humans + AI engines)

Usage:  python validate_contact_consistency.py
Output: contact_consistency_report.json
"""
import re, json, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result
from wh_pages import all_public_surfaces

# Public surfaces that humans / AI engines read. These must NEVER reference
# the stale addresses. Sourced from wh_pages.all_public_surfaces() so adding
# a new article auto-extends the scan list.
PUBLIC_SURFACES = all_public_surfaces()

CANONICAL_EMAIL = "admin@workhiveph.com"
STALE_HELLO     = "hello@workhiveph.com"
STALE_PERSONAL  = "ian.beronio37@gmail.com"


def check_no_hello(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if STALE_HELLO in content:
            count = content.count(STALE_HELLO)
            issues.append({"check": "no_hello", "page": page,
                           "reason": (f"{page} has {count} reference(s) to "
                                      f"stale {STALE_HELLO}. Replace with "
                                      f"{CANONICAL_EMAIL}.")})
    return issues


def check_no_personal(pages):
    issues = []
    for page in pages:
        content = read_file(page)
        if content is None:
            continue
        if STALE_PERSONAL in content:
            count = content.count(STALE_PERSONAL)
            issues.append({"check": "no_personal", "page": page,
                           "reason": (f"{page} has {count} reference(s) to "
                                      f"personal {STALE_PERSONAL}. Replace "
                                      f"with {CANONICAL_EMAIL}.")})
    return issues


def check_canonical_present():
    """admin@workhiveph.com must appear in at least 3 anchor surfaces so that
    humans, search engines, and AI engines can all discover it."""
    issues = []
    anchors = {
        "index.html": "landing page (footer + Organization JSON-LD)",
        "llms.txt":   "AI-engine attribution surface",
        "about/index.html": "about page contact section",
    }
    for path, role in anchors.items():
        content = read_file(path)
        if content is None:
            issues.append({"check": "canonical_present", "page": path,
                           "reason": f"{path} missing — {role}"})
            continue
        if CANONICAL_EMAIL not in content:
            issues.append({"check": "canonical_present", "page": path,
                           "reason": (f"{path} does not mention "
                                      f"{CANONICAL_EMAIL} ({role}). Add it.")})
    return issues


CHECK_NAMES  = ["no_hello", "no_personal", "canonical_present"]
CHECK_LABELS = {
    "no_hello":          "L1  No public reference to stale hello@workhiveph.com",
    "no_personal":       "L2  No public reference to personal ian.beronio37@gmail.com",
    "canonical_present": "L3  admin@workhiveph.com present in index.html + llms.txt + about/",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nContact Consistency Validator (3-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_no_hello(PUBLIC_SURFACES)
    all_issues += check_no_personal(PUBLIC_SURFACES)
    all_issues += check_canonical_present()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed across "
              f"{len(PUBLIC_SURFACES)} public surfaces.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":     "contact_consistency",
        "total_checks":  len(CHECK_NAMES),
        "surfaces_scanned": len(PUBLIC_SURFACES),
        "passed":        n_pass,
        "warned":        n_warn,
        "failed":        n_fail,
        "issues":        [i for i in all_issues if not i.get("skip")],
        "warnings":      [i for i in all_issues if i.get("skip")],
    }
    with open("contact_consistency_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
