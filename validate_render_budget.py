"""
Render Budget Validator (L0, P1 roadmap 2026-05-26).
======================================================
Ratchets per-page compressed-JS payload + total HTML size so growth is
visible early. Today pages can silently grow 200KB before anyone notices;
mobile-3G users feel it as a 1-2s LCP regression.

Budgets (defaults — override via render_budget_overrides.json):
  HTML file size      ≤  150 KB
  inline <script>     ≤   80 KB total per page
  external script ref ≤  20 per page

The validator does NOT measure browser-loaded JS or network waterfall —
that's Layer 2 territory. This is the cheap structural pre-check.

Exit codes:
  0  every page within budget OR baseline holds
  1  one or more pages over budget (FAIL with page + size)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "render_budget_report.json"
BASELINE = ROOT / "render_budget_baseline.json"
OVERRIDES = ROOT / "render_budget_overrides.json"

CHECK_NAMES = ["render_budget"]

DEFAULT_BUDGETS = {
    "html_kb":         150,
    "inline_script_kb": 80,
    "external_scripts": 20,
}

SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
SCRIPT_TAG_RE   = re.compile(r"<script\b[^>]*\bsrc=", re.IGNORECASE)


def load_budgets():
    if OVERRIDES.exists():
        try:
            data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = DEFAULT_BUDGETS.copy()
                merged.update({k: v for k, v in data.get("global", {}).items() if k in DEFAULT_BUDGETS})
                return merged, data.get("per_page", {})
        except Exception:
            pass
    return DEFAULT_BUDGETS, {}


def measure(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    inline_bytes = 0
    for m in SCRIPT_BLOCK_RE.finditer(raw):
        # Skip script tags that have a src= attribute — those are external.
        opener_end = raw.rfind(">", 0, m.start() + len(m.group(0)) - len(m.group(1)) - len("</script>"))
        opener = raw[m.start():opener_end + 1] if opener_end > 0 else ""
        if 'src=' in opener.lower(): continue
        inline_bytes += len(m.group(1).encode("utf-8", errors="replace"))
    external = len(SCRIPT_TAG_RE.findall(raw))
    return {
        "html_kb":          round(len(raw.encode("utf-8", errors="replace")) / 1024, 1),
        "inline_script_kb": round(inline_bytes / 1024, 1),
        "external_scripts": external,
    }


def main() -> int:
    pages = sorted(ROOT.glob("*.html"))
    # Exclude *.backup.html and test fixtures.
    pages = [p for p in pages if ".backup" not in p.name and not p.name.startswith("index-")]
    budgets_global, per_page_overrides = load_budgets()

    rows, breaches = [], []
    for p in pages:
        m = measure(p)
        b = {**budgets_global, **per_page_overrides.get(p.name, {})}
        violation = {}
        for k, v in m.items():
            if v > b.get(k, DEFAULT_BUDGETS[k]):
                violation[k] = {"actual": v, "budget": b[k]}
        row = {"page": p.name, "metrics": m, "budget": b, "violation": violation}
        rows.append(row)
        if violation:
            breaches.append(row)

    REPORT.write_text(json.dumps({"rows": rows, "breaches": breaches}, indent=2), encoding="utf-8")

    # Baseline ratchet — first run captures the current breach count so the
    # validator can land green even on a fat codebase. New breaches above
    # baseline FAIL.
    baseline = len(breaches)
    if BASELINE.exists():
        try: baseline = int(json.loads(BASELINE.read_text(encoding="utf-8")).get("breaches", baseline))
        except Exception: pass
    else:
        BASELINE.write_text(json.dumps({"breaches": len(breaches)}), encoding="utf-8")

    n_pages = len(rows)
    n_breach = len(breaches)
    print(f"Render budget: {n_pages} pages scanned, {n_breach} over budget (baseline {baseline}).")
    if n_breach > baseline:
        print(f"\033[91mFAIL: regressed +{n_breach - baseline} above baseline\033[0m")
        for b in breaches[:10]:
            keys = ", ".join(f"{k}={v['actual']}>{v['budget']}" for k, v in b['violation'].items())
            print(f"  - {b['page']}: {keys}")
        return 1
    if n_breach < baseline:
        BASELINE.write_text(json.dumps({"breaches": n_breach}), encoding="utf-8")
        print(f"\033[92mPASS: baseline tightened {baseline} → {n_breach}\033[0m")
        return 0
    print("\033[92mPASS\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
