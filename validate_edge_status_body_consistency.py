"""
Edge Function HTTP Status vs Body Semantics Validator (L0, ratcheted).
==========================================================================
Edge functions MUST keep HTTP status code and response body semantics
in sync. Two real bug classes this catches:

  CLASS A — body says ERROR but status is 200/OK:
    `new Response(JSON.stringify({ error: '...' }), { status: 200 })`
    Frontend `fetch().then(r => r.ok ? r.json() : ...)` thinks
    success → renders the error string as data.

  CLASS B — body says ok=true but status is >=400:
    `new Response(JSON.stringify({ ok: true }), { status: 500 })`
    Frontend goes to error branch even though server returned OK.
    Usually means the catch{} forgot to set status BEFORE returning.

Heuristic: scan `new Response(JSON.stringify({...}), { status: N })`
patterns and check JSON body's first key vs status range.

Output: edge_status_body_consistency_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "edge_status_body_consistency_report.json"
BASELINE_PATH = ROOT / "edge_status_body_consistency_baseline.json"

# new Response(<body>, { ... status: NNN ... })
RESP_RE = re.compile(
    r"new\s+Response\s*\(\s*(?P<body>[\s\S]{0,400}?)\s*,\s*\{(?P<opts>[^}]*)\}",
    re.IGNORECASE,
)
STATUS_RE   = re.compile(r"\bstatus\s*:\s*(\d{3})", re.IGNORECASE)
ERROR_KEY_RE = re.compile(r"""[\{\s,]error\s*:""", re.IGNORECASE)
# Look for ok: false / ok: true at the start of the body
OK_FALSE_RE = re.compile(r"""[\{\s,]ok\s*:\s*false""", re.IGNORECASE)
OK_TRUE_RE  = re.compile(r"""[\{\s,]ok\s*:\s*true""",  re.IGNORECASE)


# Sentinel binding: name the L2 test `test('edge_status_body_consistency: ...')` for coverage credit.
CHECK_NAMES = ["edge_status_body_consistency"]


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    for m in RESP_RE.finditer(body):
        b = m.group("body")
        opts = m.group("opts")
        st_match = STATUS_RE.search(opts)
        if not st_match:
            continue
        status = int(st_match.group(1))
        line_no = body.count("\n", 0, m.start()) + 1
        if "edge-status-allow" in body[max(0, m.start()-200): m.end()+200]:
            continue
        # CLASS A: body says error but status is success
        if 200 <= status < 300:
            if ERROR_KEY_RE.search(b) and not OK_TRUE_RE.search(b):
                issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                               "line": line_no, "status": status, "class": "A (error body + 2xx)"})
                continue
            if OK_FALSE_RE.search(b):
                issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                               "line": line_no, "status": status, "class": "A (ok:false + 2xx)"})
                continue
        # CLASS B: body says ok:true but status is error
        if status >= 400:
            if OK_TRUE_RE.search(b):
                issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                               "line": line_no, "status": status, "class": "B (ok:true + 4xx/5xx)"})
                continue
    return issues


def main() -> int:
    issues = []
    scanned = 0
    fn_dir = ROOT / "supabase" / "functions"
    if not fn_dir.exists():
        print("PASS — no edge functions directory.")
        return 0
    for path in sorted(fn_dir.rglob("*.ts")):
        if "_archive" in path.parts or "node_modules" in path.parts:
            continue
        scanned += 1
        issues.extend(_check_file(path))

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
        "summary": {"files_scanned": scanned, "drift": drift, "baseline": baseline},
        "issues": issues,
    }, indent=2), encoding="utf-8")

    print(f"\nEdge Status/Body Consistency Validator (L0)")
    print("=" * 56)
    print(f"  edge fn .ts files: {scanned}")
    print(f"  drift:             {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every edge fn Response has matching status + body semantics.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}  status={i['status']}  {i['class']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
