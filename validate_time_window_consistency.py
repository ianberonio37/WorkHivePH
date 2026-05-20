"""
Time-Window Consistency Validator (L0, ratcheted).
===================================================
Surfaces hardcoded `N * 86400000` / `N * 24 * 3600 * 1000` / `N * 24 * 60 * 60 * 1000`
millisecond-day windows. When multiple files use DIFFERENT N for what
sounds like the same metric (PM overdue, low stock, idle period),
the numbers diverge silently. The canonical contract is "windows live
in views; pages don't hardcode them".

Detection
  Find every `\d+\s*\*\s*86400000` (or equivalent) on every page +
  edge fn. Cluster by N. If 2+ distinct N appear across files (and
  the context tokens around them look related — e.g. both mention
  'overdue', 'completion', 'stale'), flag for review.

Output: time_window_consistency_report.json. Exit 1 on regression.
Allow with `// time-window-allow: <reason>` near the constant.
"""
from __future__ import annotations
import io, json, re, sys
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "time_window_consistency_report.json"
BASELINE_PATH = ROOT / "time_window_consistency_baseline.json"

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

# N * day_in_ms (4 common forms)
WINDOW_PATTERNS = [
    re.compile(r"(?P<n>\d+)\s*\*\s*86400000\b"),
    re.compile(r"(?P<n>\d+)\s*\*\s*24\s*\*\s*3600000\b"),
    re.compile(r"(?P<n>\d+)\s*\*\s*24\s*\*\s*60\s*\*\s*60\s*\*\s*1000\b"),
    re.compile(r"(?P<n>\d+)\s*\*\s*24\s*\*\s*3600\s*\*\s*1000\b"),
]

# Context keywords that suggest "same metric" — if two windows share
# a context keyword in their surrounding text, they should agree.
CONTEXT_KEYWORDS = [
    "overdue", "completed", "completion", "stale", "idle",
    "last_serviced", "last_completed", "due_soon", "anchor",
    "session", "expired", "stalled", "freshness", "recent",
]

ALLOW_RE = re.compile(r"time-window-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


# Sentinel binding: name the L2 test `test('time_window_consistency: ...')` for coverage credit.
CHECK_NAMES = ["time_window_consistency"]


def main() -> int:
    files: list[tuple[str, Path]] = [(n, ROOT / n) for n in PAGES]
    edge = ROOT / "supabase" / "functions"
    if edge.exists():
        for ts in sorted(edge.rglob("*.ts")):
            files.append((ts.relative_to(ROOT).as_posix(), ts))
    for js in sorted(ROOT.glob("*.js")):
        if js.name == "sw.js": continue
        files.append((js.name, js))

    # (context_keyword, N) → {filenames}
    occurrences: dict[tuple[str, int], set[str]] = defaultdict(set)
    # All raw hits
    all_hits = 0

    for fname, path in files:
        if not path.exists(): continue
        body = HTML_COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
        for pat in WINDOW_PATTERNS:
            for m in pat.finditer(body):
                n = int(m.group("n"))
                all_hits += 1
                # Allow window
                win = body[max(0, m.start() - 200):m.end() + 200]
                if ALLOW_RE.search(win): continue
                # Context keyword extraction — scan ±150 chars
                ctx_window = body[max(0, m.start() - 150):m.end() + 150].lower()
                for kw in CONTEXT_KEYWORDS:
                    if kw in ctx_window:
                        occurrences[(kw, n)].add(fname)

    # Drift: a keyword appears with MULTIPLE distinct N in distinct files
    drift: list[dict] = []
    by_keyword: dict[str, dict[int, set[str]]] = defaultdict(dict)
    for (kw, n), files_set in occurrences.items():
        by_keyword[kw][n] = files_set
    for kw, n_files in by_keyword.items():
        if len(n_files) < 2: continue
        # Distinct files across all N values
        all_files = {f for files_set in n_files.values() for f in files_set}
        if len(all_files) < 2: continue
        drift.append({
            "context":   kw,
            "variants":  {str(n): sorted(fs) for n, fs in sorted(n_files.items())},
        })

    drift.sort(key=lambda d: d["context"])

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = len(drift)
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if len(drift) < baseline:
        baseline = len(drift)
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"total_hits": all_hits, "drift_groups": len(drift), "baseline": baseline},
        "drift": drift,
    }, indent=2), encoding="utf-8")

    print(f"\nTime-Window Consistency Validator (L0)")
    print("=" * 56)
    print(f"  total ms-day hits: {all_hits}")
    print(f"  drift groups:      {len(drift)}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — no time-window drift across files sharing context keywords.")
        return 0
    for d in drift[:15]:
        print(f"  context='{d['context']}'")
        for n, files in d["variants"].items():
            print(f"    N={n}d → {', '.join(files[:5])}{'...' if len(files)>5 else ''}")
    return 1 if len(drift) > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
