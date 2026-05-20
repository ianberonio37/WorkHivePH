"""
Duplicate <script src=> Tags Validator (L0, ratcheted).
=========================================================
The same `<script src="X">` MUST NOT appear twice in the same HTML
file. Duplicates cause:
  - The same module's top-level side effects to run twice (double
    listeners, double-init of singletons, doubled timers).
  - Browser still fetches both (cache hit on the second, but still
    parses + executes again).
  - Hard-to-debug "why is my init firing twice" symptoms.

Also flags duplicate `<link rel="stylesheet" href="X">`.

Output: duplicate_script_tags_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from collections import Counter

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "duplicate_script_tags_report.json"
BASELINE_PATH = ROOT / "duplicate_script_tags_baseline.json"

SCRIPT_SRC_RE = re.compile(r"""<script\b[^>]*\bsrc\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)
STYLE_HREF_RE = re.compile(r"""<link\b[^>]*\brel\s*=\s*['"]stylesheet['"][^>]*\bhref\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)


# Sentinel binding: name the L2 test `test('duplicate_script_tags: ...')` for coverage credit.
CHECK_NAMES = ["duplicate_script_tags"]


def _check_page(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    if "duplicate-script-allow" in body:
        return []
    # Strip HTML comments to avoid false positives from commented-out scripts
    body_uncommented = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    for kind, pat in (("script", SCRIPT_SRC_RE), ("stylesheet", STYLE_HREF_RE)):
        srcs = pat.findall(body_uncommented)
        # Normalise: strip query strings (cache busters) and leading ./
        norm = [re.sub(r"\?.*$", "", s).lstrip("./") for s in srcs]
        counts = Counter(norm)
        for src, n in counts.items():
            if n > 1:
                issues.append({"page": path.name, "kind": kind, "src": src, "count": n})
    return issues


def main() -> int:
    issues = []
    pages = sorted(ROOT.glob("*.html"))
    for path in pages:
        if path.name.startswith("_"):
            continue
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
        "summary": {"pages_scanned": len(pages), "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nDuplicate <script>/<link> Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(pages)}")
    print(f"  drift:            {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no duplicate <script src> or <link href> per page.")
        return 0
    for i in issues[:20]:
        print(f"  {i['page']}  ({i['kind']}) {i['src']}  ×{i['count']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
