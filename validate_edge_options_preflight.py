"""
Edge Function OPTIONS Preflight Validator (L0, ratcheted).
=============================================================
Every edge function that handles a non-GET method (POST/PUT/PATCH/DELETE)
MUST handle the CORS preflight `OPTIONS` request. Browsers send OPTIONS
before any non-simple request (e.g. with Content-Type: application/json
or a custom Authorization header) — if the edge fn responds with 404
or anything other than 200/204 + CORS headers, the actual POST is never
sent.

Heuristic: if a serve() handler reads JSON bodies (req.json()) or
otherwise expects a non-GET, it MUST also check `req.method === 'OPTIONS'`
and return early with CORS headers.

Exemption: `edge-preflight-allow` marker.

Output: edge_options_preflight_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "edge_options_preflight_report.json"
BASELINE_PATH = ROOT / "edge_options_preflight_baseline.json"


# Sentinel binding: name the L2 test `test('edge_options_preflight: ...')` for coverage credit.
CHECK_NAMES = ["edge_options_preflight"]


# Heuristics: function reads JSON body OR uses non-GET method
WRITE_USE_RE = re.compile(
    r"(?:await\s+req\.json\s*\(|req\.method\s*===?\s*['\"](?:POST|PUT|PATCH|DELETE)['\"])"
)
OPTIONS_HANDLER_RE = re.compile(
    r"req\.method\s*===?\s*['\"]OPTIONS['\"]"
)
# Also recognise calling a shared CORS helper that's known to handle OPTIONS
CORS_HELPER_RE = re.compile(
    r"(?:handlePreflight|isPreflight|corsPreflight|withCors)\s*\("
)


def _check_file(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    if "edge-preflight-allow" in body:
        return []
    if not WRITE_USE_RE.search(body):
        return []
    if OPTIONS_HANDLER_RE.search(body):
        return []
    if CORS_HELPER_RE.search(body):
        return []
    return [{"file": str(path.relative_to(ROOT)).replace("\\", "/")}]


def main() -> int:
    fn_dir = ROOT / "supabase" / "functions"
    if not fn_dir.exists():
        print("PASS — no edge functions.")
        return 0
    issues = []
    scanned = 0
    # Only scan top-level index.ts of each function (the handler entry).
    for fn in sorted(fn_dir.iterdir()):
        if not fn.is_dir() or fn.name.startswith("_"): continue
        entry = fn / "index.ts"
        if not entry.exists(): continue
        scanned += 1
        issues.extend(_check_file(entry))

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
        "summary": {"functions_scanned": scanned, "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nEdge OPTIONS Preflight Validator (L0)")
    print("=" * 56)
    print(f"  functions scanned: {scanned}")
    print(f"  drift:             {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every body-consuming edge fn handles OPTIONS preflight.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}  → no OPTIONS handler / cors helper")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
