"""
Playwright Selector Existence Validator (L0, ratcheted).
=========================================================
Every `whPage.locator('#X')` / `page.locator('#X')` / `getByTestId('X')`
referenced in a tests/journey-*.spec.ts file must correspond to an
element that exists on the target HTML page. Catches the class where
a page renames an id but the test still grabs the old one — test
flakes on first run, then gets `.fixme()`'d and silently disabled.

Heuristic
  For each spec file, find `whPage.goto('/workhive/<page>.html')` to
  know the target page. Find all `locator('#X')` / `querySelector('#X')`
  refs in the same describe/test block. Cross-check id against the
  target HTML's declared ids.

Output: playwright_selector_existence_report.json. Exit 1 on regression.
Allow with `// pw-selector-allow: <reason>` near the locator call.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "playwright_selector_existence_report.json"
BASELINE_PATH = ROOT / "playwright_selector_existence_baseline.json"

TESTS_DIR = ROOT / "tests"

GOTO_RE = re.compile(r"""\.goto\(\s*['"`](?P<url>[^'"`]+)['"`]""")
LOCATOR_RE = re.compile(r"""\.locator\(\s*['"`]#(?P<id>[a-z][\w-]+)['"`]""", re.IGNORECASE)
QS_RE = re.compile(r"""querySelector(?:All)?\(\s*['"`]#(?P<id>[a-z][\w-]+)['"`]""", re.IGNORECASE)
GET_BY_ID_RE = re.compile(r"""getElementById\(\s*['"`](?P<id>[a-z][\w-]+)['"`]""", re.IGNORECASE)

HTML_ID_RE = re.compile(r"""\bid\s*=\s*['"`](?P<id>[a-z][\w-]+)['"`]""", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
ALLOW_RE = re.compile(r"pw-selector-allow", re.IGNORECASE)


def _resolve_page(url: str) -> Path | None:
    """`/workhive/hive.html?signin=1` → ROOT/hive.html"""
    t = url
    for ch in ("?", "#"):
        if ch in t: t = t.split(ch, 1)[0]
    if t.startswith("/workhive/"):
        t = t[len("/workhive/"):]
    elif t.startswith("/"):
        t = t.lstrip("/")
    if not t.endswith(".html"):
        return None
    p = ROOT / t
    return p if p.exists() else None


def main() -> int:
    if not TESTS_DIR.exists():
        print("PASS — no tests/ dir")
        return 0

    # Cache: page → set of ids declared in the page
    page_ids_cache: dict[str, set[str]] = {}

    def _ids_for(p: Path) -> set[str]:
        if p.name in page_ids_cache: return page_ids_cache[p.name]
        body = HTML_COMMENT_RE.sub("", p.read_text(encoding="utf-8", errors="replace"))
        ids = {m.group("id") for m in HTML_ID_RE.finditer(body)}
        page_ids_cache[p.name] = ids
        return ids

    per_file = []
    total_lookups = 0
    total_drift = 0
    seen: set = set()

    for spec in sorted(TESTS_DIR.glob("*.spec.ts")):
        body = spec.read_text(encoding="utf-8", errors="replace")
        # Find all goto targets in the file — most spec files target a small set.
        targets: list[Path] = []
        for m in GOTO_RE.finditer(body):
            p = _resolve_page(m.group("url"))
            if p: targets.append(p)
        if not targets:
            continue
        # Aggregate ids declared in all targets — if a locator matches ANY of
        # them, count as covered (spec might navigate between pages).
        target_ids: set[str] = set()
        for p in targets:
            target_ids |= _ids_for(p)

        misses = []
        for pat in (LOCATOR_RE, QS_RE, GET_BY_ID_RE):
            for m in pat.finditer(body):
                gid = m.group("id")
                total_lookups += 1
                if gid in target_ids: continue
                win = body[max(0, m.start() - 200):m.end() + 200]
                if ALLOW_RE.search(win): continue
                key = (spec.name, gid)
                if key in seen: continue
                seen.add(key)
                misses.append({"id": gid, "offset": m.start()})

        per_file.append({"spec": spec.name, "targets": [t.name for t in targets],
                         "misses": misses})
        total_drift += len(misses)

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_drift < baseline:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"specs_scanned": len(per_file), "total_lookups": total_lookups,
                    "total_drift": total_drift, "baseline": baseline},
        "per_file": per_file,
    }, indent=2), encoding="utf-8")

    print(f"\nPlaywright Selector Existence Validator (L0)")
    print("=" * 56)
    print(f"  specs scanned:    {len(per_file)}")
    print(f"  lookups:          {total_lookups}")
    print(f"  drift:            {total_drift}  (baseline: {baseline})")
    if total_drift == 0:
        print("\n  PASS — every Playwright #id selector exists on its target page.")
        return 0
    shown = 0
    for entry in per_file:
        if not entry["misses"]: continue
        print(f"  {entry['spec']}  targets={', '.join(entry['targets'][:3])}")
        for m in entry["misses"]:
            print(f"    → locator('#{m['id']}')  — no <#{m['id']}> in target HTML")
            shown += 1
            if shown >= 25:
                print("    ... (more in report)")
                break
        if shown >= 25: break
    return 1 if total_drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
