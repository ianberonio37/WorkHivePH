"""
Tester Coverage Validator — WorkHive Platform
==============================================
Catches the "I added a new tool page but forgot to register it in the
WorkHive Tester" mistake. Without this gate, new pages drift out of:
  - the Tester's served-page menu (you can't open them through the Tester)
  - smoke / visual / mobile / performance flow coverage
which means new pages silently lose their continuous testing.

Source of truth: validate_assistant.py LIVE_TOOL_PAGES (the canonical roster
of live tool pages). Every entry there must be present in ALL FIVE Tester
lists below — otherwise it's a registration gap that will silently degrade
test coverage on the next feature.

Layer 1 — PUBLIC_PAGES in test-data-seeder/app.py
  Controls whether the Tester serves the page to the browser at all.

Layer 2 — PAGES in flows/smoke.py
  Page-load smoke check (console errors, body selector).

Layer 3 — PAGES in flows/visual.py
  Visual regression baseline + diff.

Layer 4 — PAGES in flows/mobile.py
  Mobile viewport (375x667) + tap target checks.

Layer 5 — PAGES in flows/performance.py
  Page-load performance budget checks.

Pages explicitly opted-out (e.g. assistant.html — separate AI test path)
are listed in OPT_OUT below with a reason.

Usage:  python validate_tester_coverage.py
Output: tester_coverage_report.json
"""
import os
import re
import sys
import json

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))


# ── Pages allowed to skip specific Tester layers ─────────────────────────────
# Each entry: page name (without .html) -> {layer_id: reason}
# Layer ids: "public", "smoke", "visual", "mobile", "performance"
OPT_OUT: dict = {
    "assistant": {
        "smoke":       "AI assistant — has its own AI test pack (ai_assistant.py)",
        "visual":      "AI chat page — visual diffs are inherently noisy",
        "mobile":      "AI assistant — covered by AI test pack",
        "performance": "AI assistant — chat latency tested via AI flows, not page-load budget",
    },
}


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _extract_string_list(src: str, varname: str) -> list:
    """Pull the string entries from a Python list/set literal by variable name.
    Tolerant of tuples and dicts inside the list — pulls the first quoted token of each row."""
    m = re.search(rf"{re.escape(varname)}\s*=\s*[\[\{{]([^\]\}}]*)[\]\}}]", src, re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    return re.findall(r'["\']([\w\-]+)\.html["\']', body)


# ── Source of truth: LIVE_TOOL_PAGES from validate_assistant.py ──────────────

def _live_tool_pages() -> list:
    src = _read(os.path.join(ROOT, "validate_assistant.py"))
    m = re.search(r"LIVE_TOOL_PAGES\s*=\s*\[([^\]]*)\]", src, re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    return re.findall(r'["\']([\w\-]+)["\']', body)


# ── The 5 Tester lists ───────────────────────────────────────────────────────

TESTER_LAYERS = [
    {
        "id":       "public",
        "label":    "PUBLIC_PAGES in test-data-seeder/app.py (page is servable through the Tester)",
        "path":     os.path.join("test-data-seeder", "app.py"),
        "varname":  "PUBLIC_PAGES",
    },
    {
        "id":       "smoke",
        "label":    "PAGES in test-data-seeder/flows/smoke.py (page-load smoke flow)",
        "path":     os.path.join("test-data-seeder", "flows", "smoke.py"),
        "varname":  "PAGES",
    },
    {
        "id":       "visual",
        "label":    "PAGES in test-data-seeder/flows/visual.py (visual regression flow)",
        "path":     os.path.join("test-data-seeder", "flows", "visual.py"),
        "varname":  "PAGES",
    },
    {
        "id":       "mobile",
        "label":    "PAGES in test-data-seeder/flows/mobile.py (mobile viewport flow)",
        "path":     os.path.join("test-data-seeder", "flows", "mobile.py"),
        "varname":  "PAGES",
    },
    {
        "id":       "performance",
        "label":    "PAGES in test-data-seeder/flows/performance.py (perf budget flow)",
        "path":     os.path.join("test-data-seeder", "flows", "performance.py"),
        "varname":  "PAGES",
    },
]


def _check_layer(layer: dict, live_pages: list) -> dict:
    abs_path = os.path.join(ROOT, layer["path"])
    src = _read(abs_path)
    if not src:
        return {
            "id":      f"tester_{layer['id']}",
            "status":  "FAIL",
            "message": f"file not found: {layer['path']}",
            "details": [],
        }

    listed = set(_extract_string_list(src, layer["varname"]))
    missing = []
    for p in live_pages:
        if p in listed:
            continue
        # Allow opt-out
        if OPT_OUT.get(p, {}).get(layer["id"]):
            continue
        missing.append(p)

    if not missing:
        return {
            "id":      f"tester_{layer['id']}",
            "status":  "PASS",
            "message": f"{len(live_pages)} live tool page(s) covered by {layer['label'].split(' (')[0]}",
            "details": [],
        }

    return {
        "id":      f"tester_{layer['id']}",
        "status":  "FAIL",
        "message": (
            f"{len(missing)} page(s) not in {layer['varname']} ({layer['path']}): "
            f"{', '.join(missing)}. "
            f"Add them so the Tester gates cover the new feature, "
            f"or add an OPT_OUT entry to validate_tester_coverage.py with a reason."
        ),
        "details": missing,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    live = _live_tool_pages()
    if not live:
        print("[FAIL] Could not parse LIVE_TOOL_PAGES from validate_assistant.py")
        sys.exit(1)

    checks = [_check_layer(layer, live) for layer in TESTER_LAYERS]

    fails  = [c for c in checks if c["status"] == "FAIL"]
    passes = [c for c in checks if c["status"] == "PASS"]

    print("=" * 70)
    print("TESTER COVERAGE VALIDATOR")
    print(f"Source of truth: {len(live)} LIVE_TOOL_PAGES from validate_assistant.py")
    print("=" * 70)
    for c in checks:
        icon = {"PASS": "[OK]", "FAIL": "[FAIL]"}[c["status"]]
        print(f"  {icon} {c['id']:24} {c['message']}")
    print()
    print(f"  Summary: {len(passes)} pass / {len(fails)} fail (across {len(TESTER_LAYERS)} Tester layers)")

    report = {
        "ok": len(fails) == 0,
        "live_tool_pages": live,
        "summary": {"pass": len(passes), "fail": len(fails)},
        "checks": checks,
    }
    out_path = os.path.join(ROOT, "tester_coverage_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  Report: {out_path}")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
