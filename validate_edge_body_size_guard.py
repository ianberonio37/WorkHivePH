"""
Edge Function Body Size Guard Validator (L0, ratcheted).
==========================================================
Every edge function that reads a request body with `await req.json()`
SHOULD have a size-bound mechanism — either:
  - a Content-Length check before parsing
  - a maxBodySize / sizeLimit in shared helper invocation
  - a try/catch around req.json() to handle truncation gracefully

Without a size guard, an attacker can post a multi-GB JSON body that
exhausts the runtime's memory or CPU budget. Deno's req.json() reads
the entire body before parsing — there's no streaming cap.

Heuristic: flag fns that call req.json() without ANY of:
  - try { ... } catch around it
  - Content-Length / content-length check
  - sizeLimit / maxBody helper symbol
  - inline marker `edge-body-size-allow`

Output: edge_body_size_guard_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "edge_body_size_guard_report.json"
BASELINE_PATH = ROOT / "edge_body_size_guard_baseline.json"

REQ_JSON_RE = re.compile(r"await\s+req\.json\s*\(\s*\)")
SIZE_HINTS = ("content-length", "Content-Length", "sizeLimit", "maxBody",
              "MAX_BODY", "MAX_PAYLOAD", "bodyLimit", "withBodyGuard")


# Sentinel binding: name the L2 test `test('edge_body_size_guard: ...')` for coverage credit.
CHECK_NAMES = ["edge_body_size_guard"]


def _is_in_try(src: str, idx: int) -> bool:
    window = src[max(0, idx-800): idx]
    depth = 0
    in_try = []
    i = 0
    while i < len(window):
        m = re.match(r"\btry\s*\{", window[i:])
        if m:
            in_try.append(depth); i += m.end(); depth += 1; continue
        c = window[i]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            in_try = [d for d in in_try if d < depth]
        i += 1
    return bool(in_try)


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    if "edge-body-size-allow" in body:
        return []
    has_size_hint = any(h in body for h in SIZE_HINTS)
    src = re.sub(r"//[^\n]*", "", body)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    for m in REQ_JSON_RE.finditer(src):
        if _is_in_try(src, m.start()):
            continue
        if has_size_hint:
            continue
        line_no = src.count("\n", 0, m.start()) + 1
        issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                       "line": line_no})
    return issues


def main() -> int:
    fn_dir = ROOT / "supabase" / "functions"
    if not fn_dir.exists():
        print("PASS — no edge functions.")
        return 0
    issues = []
    scanned = 0
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

    print(f"\nEdge Body Size Guard Validator (L0)")
    print("=" * 56)
    print(f"  edge fn .ts files: {scanned}")
    print(f"  drift:             {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every req.json() is guarded by try/catch or size check.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
