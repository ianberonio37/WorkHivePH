"""
Edge Function Unpinned Imports Validator (L0, ratcheted).
============================================================
Every `import ... from "https://..."` in an edge function MUST pin a
version. Without a pin, the upstream module owner can ship a new
version that breaks the function — or worse, a hostile takeover (e.g.
event-stream npm) deploys arbitrary code with the edge fn's privileges.

Acceptable pin forms (any one is enough):
  - https://deno.land/std@0.218.0/...
  - https://esm.sh/foo@1.2.3
  - https://deno.land/x/foo@v1.0.0/...
  - npm:foo@1.2.3 / jsr:@scope/foo@1.0.0
  - URL with @<version-like> token (digits, dots, hyphens)

Unpinned (flagged):
  - https://deno.land/std/...
  - https://esm.sh/foo
  - https://cdn.skypack.dev/foo (no @ver)

Output: edge_unpinned_imports_report.json. Exit 1 on regression.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "edge_unpinned_imports_report.json"
BASELINE_PATH = ROOT / "edge_unpinned_imports_baseline.json"

# Capture import / re-export specifiers — strings inside `import ... from "X"`
# and `export ... from "X"`.
IMPORT_RE = re.compile(
    r"""(?:import|export)\b[^"']*?\bfrom\s+["']([^"']+)["']""",
    re.IGNORECASE | re.DOTALL,
)
# Also catch dynamic imports: `import("X")`
DYN_IMPORT_RE = re.compile(r"""\bimport\s*\(\s*["']([^"']+)["']\s*\)""")
# A pinned URL has @<version-token>
PINNED_AT_RE  = re.compile(r"@[\w.\-]+(?:/|$|\?|#)")


# Sentinel binding: name the L2 test `test('edge_unpinned_imports: ...')` for coverage credit.
CHECK_NAMES = ["edge_unpinned_imports"]


def _is_remote(spec: str) -> bool:
    return spec.startswith(("http://", "https://", "npm:", "jsr:"))


def _is_pinned(spec: str) -> bool:
    # npm:/jsr: schemes — pin is the @version suffix on the package name
    if spec.startswith(("npm:", "jsr:")):
        # require @<digits or v> somewhere after the colon
        return bool(re.search(r"@\d", spec[4:]) or re.search(r"@v\d", spec[4:]))
    # URL schemes — require @<version-token> appearing before the path tail
    return bool(PINNED_AT_RE.search(spec))


def _check_file(path: Path) -> list:
    issues = []
    body = path.read_text(encoding="utf-8", errors="replace")
    if "edge-import-pin-allow" in body:
        return []
    # Strip block comments
    body_uncommented = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body_uncommented = re.sub(r"//[^\n]*", "", body_uncommented)
    for pat in (IMPORT_RE, DYN_IMPORT_RE):
        for m in pat.finditer(body_uncommented):
            spec = m.group(1)
            if not _is_remote(spec):
                continue
            if _is_pinned(spec):
                continue
            line_no = body_uncommented.count("\n", 0, m.start()) + 1
            issues.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                           "line": line_no, "spec": spec})
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

    print(f"\nEdge Unpinned Imports Validator (L0)")
    print("=" * 56)
    print(f"  edge fn .ts files: {scanned}")
    print(f"  drift:             {drift}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every remote import pins a version.")
        return 0
    for i in issues[:25]:
        print(f"  {i['file']}:{i['line']}  {i['spec']}")
    return 1 if drift > baseline else 0


if __name__ == "__main__":
    sys.exit(main())
