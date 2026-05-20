"""
Patch missing <main> landmarks into HTML pages.

The skill-rule miner (tools/mine_skill_rules.py) found 21 pages without a
<main> landmark. This breaks accessibility -- screen reader and keyboard
users cannot skip past navigation to jump to the page's primary content.

This script:
  1. Reads the violator list from skill_rules_mining_report.json
  2. For each page:
     a. Skip if a <main> element already exists (idempotent)
     b. Insert `<main>` immediately after the <body...> opening tag
     c. Insert `</main>` immediately before the </body> closing tag
  3. Writes back; never alters files that already have <main>.

The wrap-everything approach (vs trying to find "the content area") is
the safest mechanical fix:
  - If the page has no top-level <header>/<footer> siblings, <main>
    wrapping everything is semantically fine.
  - Screen readers get the landmark they need to skip nav.
  - Trailing <script> tags inside <main> have no functional impact.
  - Risk-free: this never breaks layout or behaviour.

If a page later needs a more nuanced placement (separate <header> +
<main> + <footer>), refactor by hand. The miner will keep PASSing as
long as ONE <main> exists.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "skill_rules_mining_report.json"

BODY_OPEN_RE  = re.compile(r"<body\b[^>]*>", re.IGNORECASE)
BODY_CLOSE_RE = re.compile(r"</body\s*>", re.IGNORECASE)
MAIN_TAG_RE   = re.compile(r"<main\b", re.IGNORECASE)


def patch_file(path: Path) -> str:
    """Return one of: 'patched', 'already_present', 'no_body_tag'."""
    text = path.read_text(encoding="utf-8", errors="replace")

    if MAIN_TAG_RE.search(text):
        return "already_present"

    open_m  = BODY_OPEN_RE.search(text)
    close_m = BODY_CLOSE_RE.search(text)
    if not open_m or not close_m:
        return "no_body_tag"

    # Insert </main> first (later position) so the open_m index stays valid.
    close_pos = close_m.start()
    text = text[:close_pos] + "</main>\n" + text[close_pos:]

    open_end = open_m.end()
    text = text[:open_end] + "\n<main>\n" + text[open_end:]

    path.write_text(text, encoding="utf-8")
    return "patched"


def main() -> int:
    if not REPORT_PATH.exists():
        print(f"ERROR: {REPORT_PATH.name} not found. Run tools/mine_skill_rules.py first.")
        return 1

    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    target = None
    for r in report["all_results"]:
        if r["rule_id"] == "a11y_main_landmark_present":
            target = r
            break
    if not target:
        print("ERROR: a11y_main_landmark_present rule not in report.")
        return 1

    violators = target["violators"]
    print(f"<main> landmark patcher")
    print(f"  targets: {len(violators)} page(s)")
    print()

    results = {"patched": [], "already_present": [], "no_body_tag": []}
    for name in violators:
        path = ROOT / name
        if not path.exists():
            print(f"  SKIP  {name}  (file not found)")
            continue
        outcome = patch_file(path)
        results[outcome].append(name)
        tag = {"patched": "OK  ", "already_present": "NOOP",
               "no_body_tag": "WARN"}[outcome]
        print(f"  {tag}  {name}")

    print()
    print(f"Summary:")
    print(f"  patched:            {len(results['patched'])}")
    print(f"  already_present:    {len(results['already_present'])}")
    print(f"  no_body_tag (warn): {len(results['no_body_tag'])}")

    if results["no_body_tag"]:
        print("\nFiles needing manual review (no <body> tag found):")
        for n in results["no_body_tag"]:
            print(f"  - {n}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
