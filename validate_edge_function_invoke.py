"""
Edge Function Invoke Validator (L0, ratcheted).
================================================
Every `db.functions.invoke('name', ...)` / `supabase.functions.invoke('name', ...)`
call must point at a real directory under `supabase/functions/<name>/`.

Caught class: page calls `functions.invoke('ai-orchestrator')` but the
edge fn was renamed to `assistant-orchestrator` — the call returns a
404 silently because graceful-degrade catch blocks swallow the error.

Output: edge_function_invoke_report.json. Exit 1 on regression.
Allow with `// edge-fn-allow: <reason>` near the call.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "edge_function_invoke_report.json"
BASELINE_PATH = ROOT / "edge_function_invoke_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

INVOKE_RE = re.compile(r"""\bfunctions\.invoke\(\s*['"`](?P<name>[a-z0-9_-]+)['"`]""", re.IGNORECASE)
ALLOW_RE = re.compile(r"edge-fn-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


# Sentinel binding: name the L2 test `test('edge_function_invoke: ...')` for coverage credit.
CHECK_NAMES = ["edge_function_invoke"]


def main() -> int:
    edge_dir = ROOT / "supabase" / "functions"
    existing = {p.name for p in edge_dir.iterdir() if p.is_dir() and p.name != "_shared"} if edge_dir.exists() else set()

    per_page = []
    total_drift = 0
    total_calls = 0

    files = [(name, ROOT / name) for name in PAGES]
    # Also scan shared JS modules (utils.js, voice-handler.js, etc.) since
    # they often invoke edge fns on behalf of pages.
    for p in sorted(ROOT.glob("*.js")):
        if p.name == "sw.js":
            continue
        files.append((p.name, p))

    seen: set[tuple[str, str]] = set()
    for name, path in files:
        if not path.exists():
            continue
        body = HTML_COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
        broken = []
        for m in INVOKE_RE.finditer(body):
            fn_name = m.group("name")
            total_calls += 1
            win = body[max(0, m.start() - 200):m.end() + 200]
            if ALLOW_RE.search(win):
                continue
            if fn_name not in existing:
                key = (name, fn_name)
                if key in seen: continue
                seen.add(key)
                broken.append({"function": fn_name, "offset": m.start()})
        per_page.append({"page": name, "broken": broken})
        total_drift += len(broken)

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
        "summary": {"files_scanned": len(per_page), "total_calls": total_calls,
                    "total_drift": total_drift, "baseline": baseline,
                    "edge_fns_known": len(existing)},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nEdge Function Invoke Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {len(per_page)}")
    print(f"  edge fns known:   {len(existing)}")
    print(f"  total calls:      {total_calls}")
    print(f"  broken:           {total_drift}  (baseline: {baseline})")
    if total_drift == 0:
        print("\n  PASS — every functions.invoke() target exists.")
        return 0
    for entry in per_page:
        if not entry["broken"]: continue
        print(f"  {entry['page']}")
        for b in entry["broken"]:
            print(f"    → functions.invoke('{b['function']}')  — no such edge fn")
    return 1 if total_drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
