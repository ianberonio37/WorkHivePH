"""
Edge Function Response Content-Type Validator (L0, ratcheted).
====================================================================
Every `new Response(JSON.stringify(...), { ... })` MUST also set
`Content-Type: application/json` in its headers. Without it:
  - Some browsers/fetch wrappers refuse to parse the body as JSON
    (resp.json() throws — silent UI failure)
  - PostgREST clients return raw text instead of parsed object
  - CORS preflight may relax `Content-Type` validation but the
    response still needs the header for safe interpretation

Acceptable headers shape:
  - `{ "Content-Type": "application/json" }` (any casing)
  - Spread of a `cors` constant: `{ ...cors, "Content-Type": "application/json" }`
  - Spread of a helper that adds it (we accept any spread of a known
    headers helper if the file imports `corsJson`, `jsonHeaders`, etc.)

Output: edge_response_content_type_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "edge_response_content_type_report.json"
BASELINE_PATH = ROOT / "edge_response_content_type_baseline.json"

# new Response(JSON.stringify(...), { ... })  — non-greedy
RESPONSE_RE = re.compile(
    r"new\s+Response\s*\(\s*JSON\.stringify\([\s\S]{0,600}?\)\s*,\s*\{(?P<opts>[^}]*)\}",
    re.IGNORECASE,
)
CT_RE = re.compile(r"""["']?[Cc]ontent-[Tt]ype["']?\s*:\s*["']application/json""", re.IGNORECASE)
SPREAD_RE = re.compile(r"\.\.\.([A-Za-z_][\w]*)")


# Sentinel binding: name the L2 test `test('edge_response_content_type: ...')` for coverage credit.
CHECK_NAMES = ["edge_response_content_type"]


def _file_helpers_set_ct(body: str) -> set:
    """Find headers constants in the file that themselves set Content-Type.
    A spread of one of these is acceptable evidence of the header."""
    out = set()
    # Pattern: const NAME = { ... "Content-Type": "application/json" ... }
    for m in re.finditer(
        r"(?:const|let|var)\s+([A-Za-z_][\w]*)\s*=\s*\{[^}]*[Cc]ontent-[Tt]ype[^}]*\}",
        body,
        re.IGNORECASE | re.DOTALL,
    ):
        out.add(m.group(1))
    # Imported helper names that conventionally set Content-Type
    for m in re.finditer(
        r"import\s+\{[^}]*(corsJson|jsonHeaders|jsonResp|jsonResponse)[^}]*\}",
        body,
    ):
        out.add(m.group(1))
    return out


def _strip_comments_keep_lines(src: str) -> str:
    def _block_rep(m):
        return "\n" * m.group(0).count("\n")
    out = re.sub(r"/\*.*?\*/", _block_rep, src, flags=re.DOTALL)
    out = re.sub(r"//[^\n]*", "", out)
    return out


def _check_file(path: Path) -> list:
    body = path.read_text(encoding="utf-8", errors="replace")
    if "edge-content-type-allow" in body:
        return []
    issues = []
    ct_helpers = _file_helpers_set_ct(body)
    src = _strip_comments_keep_lines(body)
    for m in RESPONSE_RE.finditer(src):
        opts = m.group("opts")
        if CT_RE.search(opts):
            continue
        # Allow spread of a helper that sets Content-Type
        spreads = set(SPREAD_RE.findall(opts))
        if spreads & ct_helpers:
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
        if "_archive" in path.parts or "node_modules" in path.parts: continue
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

    print(f"\nEdge Response Content-Type Validator (L0)")
    print("=" * 56)
    print(f"  edge fn .ts files: {scanned}")
    print(f"  drift:             {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every new Response(JSON.stringify(...)) sets Content-Type: application/json.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
