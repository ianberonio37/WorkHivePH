"""
Duplicate HTML id="X" Validator (L0, ratcheted).
==================================================
The same `id="X"` MUST NOT appear twice within the same HTML file.
HTML IDs must be unique per document. When they aren't:
  - `document.getElementById('X')` returns ONLY the first match —
    later duplicates are dead to JS, leading to "why isn't the button
    working" mysteries.
  - `<label for="X">` links to only the first; screen readers ignore
    the others.
  - URL fragment links (#X) jump to the first only.
  - Some browsers' devtools highlight ID collisions, but most don't.

We scan id= attribute values per HTML file. Template literals like
`id="row-${row.id}"` are skipped (one-template-per-row is intentional).

Output: duplicate_html_id_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from collections import Counter

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "duplicate_html_id_report.json"
BASELINE_PATH = ROOT / "duplicate_html_id_baseline.json"

# Match id="<value>" on actual HTML tags only (avoid `id` in CSS / JS / comments).
# Crude heuristic: id= immediately inside an opening tag <... id=...>.
ID_ATTR_RE = re.compile(
    r"""<[a-zA-Z][^>]*?\sid\s*=\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
# Skip if value contains a template literal ${...}
TEMPLATE_RE = re.compile(r"\$\{")


# Sentinel binding: name the L2 test `test('duplicate_html_id: ...')` for coverage credit.
CHECK_NAMES = ["duplicate_html_id"]


def _check_page(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    if "duplicate-id-allow" in body:
        return []
    # Strip HTML comments
    body_uncommented = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    # Strip <script> and <template> blocks — IDs inside string templates
    # rendered into the DOM at runtime are dynamic and not part of the
    # static document.
    body_uncommented = re.sub(r"<script\b[^>]*>.*?</script>", "", body_uncommented, flags=re.DOTALL | re.IGNORECASE)
    body_uncommented = re.sub(r"<template\b[^>]*>.*?</template>", "", body_uncommented, flags=re.DOTALL | re.IGNORECASE)
    ids = []
    for m in ID_ATTR_RE.finditer(body_uncommented):
        val = m.group(1)
        if TEMPLATE_RE.search(val):
            continue
        ids.append(val)
    counts = Counter(ids)
    issues = []
    for val, n in counts.items():
        if n > 1:
            issues.append({"page": path.name, "id": val, "count": n})
    return issues


def main() -> int:
    issues = []
    pages = sorted(ROOT.glob("*.html"))
    scanned = 0
    for path in pages:
        if path.name.startswith("_"): continue
        if ".backup." in path.name or path.name.endswith("-test.html"): continue
        scanned += 1
        issues.extend(_check_page(path))

    drift = len(issues)
    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if drift < baseline:
        baseline = drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": scanned, "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nDuplicate HTML id Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {scanned}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every static HTML id is unique within its document.")
        return 0
    for i in issues[:25]:
        print(f"  {i['page']}  id='{i['id']}'  ×{i['count']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
