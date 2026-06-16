"""
OpenAPI Sync Gate (Maturity Phase 4 — A-layer capability, 2026-06-16).
=======================================================================
Keeps openapi.json HONEST: every edge fn in the contract source of truth
(validate_edge_contracts.ALL_FUNCTIONS) must have a path in the published
OpenAPI spec, and the spec must not advertise a path for a fn that no longer
exists. A published contract that has drifted from reality is worse than none —
this gate makes the spec a living artefact, not a stale doc.

  L1  every edge fn has a /functions/v1/<fn> path in openapi.json
  L2  no spec path references a fn that isn't in ALL_FUNCTIONS (no ghost route)
  L3  openapi.json parses as valid JSON with the required top-level keys

Output:  openapi_sync_report.json
Exit code: 0 PASS / 1 FAIL (spec drifted — re-run tools/gen_openapi.py)
"""
from __future__ import annotations
import ast, io, json, re, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "openapi.json"

CHECK_NAMES = ["openapi_sync"]
GREEN = "\033[92m"; RED = "\033[91m"; BOLD = "\033[1m"; RESET = "\033[0m"
PATH_RE = re.compile(r"^/functions/v1/(.+)$")


def _all_functions() -> list[str]:
    """AST-extract ALL_FUNCTIONS from validate_edge_contracts.py — no execution."""
    tree = ast.parse((ROOT / "validate_edge_contracts.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "ALL_FUNCTIONS":
                    return list(ast.literal_eval(node.value))
    return []


def main() -> int:
    fails: list[str] = []
    if not SPEC.exists():
        print(f"{RED}FAIL: openapi.json missing — run tools/gen_openapi.py.{RESET}")
        return 1
    try:
        doc = json.loads(SPEC.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"{RED}FAIL: openapi.json is not valid JSON ({e}).{RESET}")
        return 1

    if not all(k in doc for k in ("openapi", "info", "paths")):
        fails.append("L3 openapi.json missing a required top-level key (openapi/info/paths).")

    spec_fns = set()
    for p in doc.get("paths", {}):
        m = PATH_RE.match(p)
        if m:
            spec_fns.add(m.group(1))

    all_fns = set(_all_functions())
    missing = sorted(all_fns - spec_fns)   # fn exists but not in spec
    ghosts  = sorted(spec_fns - all_fns)   # spec advertises a dead fn
    if missing:
        fails.append(f"L1 {len(missing)} edge fn(s) absent from openapi.json: {', '.join(missing[:6])} — re-run tools/gen_openapi.py")
    if ghosts:
        fails.append(f"L2 {len(ghosts)} ghost path(s) for non-existent fn(s): {', '.join(ghosts[:6])}")

    (ROOT / "openapi_sync_report.json").write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spec_paths": len(spec_fns), "contract_fns": len(all_fns),
        "missing": missing, "ghosts": ghosts, "fails": fails,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}OpenAPI Sync Gate (A-layer){RESET}")
    print(f"  spec paths: {len(spec_fns)}  ·  contract fns: {len(all_fns)}")
    if fails:
        print(f"{RED}FAIL: {len(fails)} sync issue(s):{RESET}")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"{GREEN}PASS — openapi.json covers every edge fn, no ghost routes.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
