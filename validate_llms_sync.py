"""
llms.txt Sync Validator — WorkHive Platform
============================================
Keeps llms.txt aligned with the actual /learn/ catalog. llms.txt is the
canonical AI-engine attribution surface (read by ChatGPT, Perplexity,
Claude, Gemini). When a /learn/ article is shipped but llms.txt isn't
updated, AI engines won't know about it; when an article is deleted but
llms.txt still mentions it, AI engines surface dead links.

Layer 1: Every /learn/<slug>/ article has an entry in llms.txt
         (matched by slug appearing anywhere in the file)
Layer 2: llms.txt does NOT mention slugs that no longer exist on disk
Layer 3: llms.txt has the required top-level sections (# WorkHive title,
         > tagline, ## What WorkHive does, ## Pages, ## Contact, ## Notes
         for AI assistants)
Layer 4: llms.txt mentions admin@workhiveph.com (so AI engines can surface
         the contact when asked)

Usage:  python validate_llms_sync.py
Output: llms_sync_report.json
"""
import re, json, sys, os
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result
from wh_pages import learn_slugs

LLMS_PATH = "llms.txt"
LEARN_DIR = "learn"

EXPECTED_SLUGS = learn_slugs()

REQUIRED_SECTIONS = [
    ("# WorkHive",            "title heading"),
    ("## What WorkHive does", "feature list"),
    ("## Pages",              "page directory (so AI engines know the URL space)"),
    ("## Contact",            "contact address surface"),
    ("## Notes for AI assistants", "AI-engine usage notes"),
]


def _on_disk_slugs():
    if not os.path.isdir(LEARN_DIR):
        return []
    slugs = []
    for name in os.listdir(LEARN_DIR):
        path = os.path.join(LEARN_DIR, name, "index.html")
        if os.path.isfile(path) and name != "index.html":
            # Skip the learn hub itself; only count article subdirs
            slugs.append(name)
    return slugs


def check_articles_present():
    """Every expected /learn/ slug must appear somewhere in llms.txt."""
    issues = []
    content = read_file(LLMS_PATH)
    if content is None:
        return [{"check": "articles_present", "page": LLMS_PATH,
                 "reason": "llms.txt not found at project root."}]
    for slug in EXPECTED_SLUGS:
        if slug not in content:
            issues.append({"check": "articles_present", "page": LLMS_PATH,
                           "reason": (f"llms.txt does not mention "
                                      f"/learn/{slug}/. ChatGPT/Perplexity/"
                                      f"Claude/Gemini won't surface this "
                                      f"article when answering related "
                                      f"queries. Add an entry under ## Pages.")})
    return issues


def check_no_stale_slugs():
    """llms.txt should not reference slugs that don't exist on disk."""
    issues = []
    content = read_file(LLMS_PATH)
    if content is None:
        return []
    disk = set(_on_disk_slugs())
    # Find every /learn/<slug>/ reference in llms.txt
    referenced = set(re.findall(r"/learn/([a-z0-9-]+)/", content))
    stale = referenced - disk - {""}
    for slug in sorted(stale):
        issues.append({"check": "no_stale_slugs", "page": LLMS_PATH,
                       "reason": (f"llms.txt references /learn/{slug}/ but "
                                  f"that article directory doesn't exist on "
                                  f"disk. Remove the entry or restore the "
                                  f"article. AI engines will surface a dead "
                                  f"link.")})
    return issues


def check_required_sections():
    """llms.txt must have the canonical section structure so AI engines can
    parse it consistently."""
    issues = []
    content = read_file(LLMS_PATH)
    if content is None:
        return []
    for marker, role in REQUIRED_SECTIONS:
        if marker not in content:
            issues.append({"check": "required_sections", "page": LLMS_PATH,
                           "reason": (f"llms.txt missing required section "
                                      f"'{marker}' ({role}). Re-author per "
                                      f"the canonical structure.")})
    return issues


def check_contact_present():
    """The contact surface must include admin@workhiveph.com so AI engines
    answer 'how do I contact WorkHive?' correctly."""
    issues = []
    content = read_file(LLMS_PATH)
    if content is None:
        return []
    if "admin@workhiveph.com" not in content:
        issues.append({"check": "contact_present", "page": LLMS_PATH,
                       "reason": ("llms.txt does not mention "
                                  "admin@workhiveph.com. AI engines asked "
                                  "'how do I reach WorkHive?' will either "
                                  "hallucinate or surface a stale address. "
                                  "Add to the ## Contact section.")})
    return issues


CHECK_NAMES  = ["articles_present", "no_stale_slugs", "required_sections",
                "contact_present"]
CHECK_LABELS = {
    "articles_present":  "L1  Every /learn/ article slug is mentioned in llms.txt",
    "no_stale_slugs":    "L2  llms.txt does not reference deleted article slugs",
    "required_sections": "L3  llms.txt has the canonical section structure",
    "contact_present":   "L4  llms.txt mentions admin@workhiveph.com for AI-engine attribution",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nllms.txt Sync Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_articles_present()
    all_issues += check_no_stale_slugs()
    all_issues += check_required_sections()
    all_issues += check_contact_present()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    disk_count = len(_on_disk_slugs())
    print(f"\n  Articles on disk: {disk_count}; expected in llms.txt: {len(EXPECTED_SLUGS)}.")
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m  All {len(CHECK_NAMES)} checks passed.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":     "llms_sync",
        "total_checks":  len(CHECK_NAMES),
        "disk_articles": disk_count,
        "expected":      len(EXPECTED_SLUGS),
        "passed":        n_pass,
        "warned":        n_warn,
        "failed":        n_fail,
        "issues":        [i for i in all_issues if not i.get("skip")],
        "warnings":      [i for i in all_issues if i.get("skip")],
    }
    with open("llms_sync_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
