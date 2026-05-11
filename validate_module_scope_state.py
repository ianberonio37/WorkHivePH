"""
Edge Function Module-Scope Mutable State -- WorkHive Platform
================================================================
Catches the per-warm-container memory leak: an edge fn declares a
module-level `let` / `Map` / `Array` / `Set` and mutates it from
within the request handler. Across warm container reuse, the state
grows unbounded until OOM.

Layer 1 -- Module-level mutable container that's appended/set                [WARN]
  Module-scope `let`/`const` initialised to `new Map()` / `new Set()` /
  `[]` and mutated via `.push` / `.set` / `.add` inside handler.

Layer 2 -- Bounded eviction adoption (informational)                         [INFO]
  Module-level containers that DO have a `.delete()` / `.clear()` /
  size-cap pattern in scope.

Layer 3 -- Per-fn container inventory (informational)                        [INFO]
  Counts of mutable module-scope containers per fn.

Layer 4 -- Const-only adoption (informational)                                [INFO]
  Fns with zero module-level mutable state -- the clean shape.

Skills consulted: devops (warm container reuse semantics), performance
(memory growth invisible until 503 in production).
"""
from __future__ import annotations

import re
import json
import sys
import os

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


FUNCTIONS_DIR = os.path.join("supabase", "functions")

MUTABLE_OK: dict[str, str] = {
    # Per-fn exemptions with justification
}

CONTAINER_DECL_RE = re.compile(
    r"""^(?:const|let)\s+(?P<name>\w+)\s*(?::\s*[\w<>,\s\[\]]+)?\s*=\s*
        (?:new\s+(?:Map|Set|WeakMap|WeakSet)\s*\(|\[)""",
    re.MULTILINE | re.VERBOSE,
)
SERVE_START_RE = re.compile(r"\bserve\s*\(")


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def find_module_containers(src: str) -> list[dict]:
    """Return module-scope mutable containers (declared BEFORE serve())."""
    serve_m = SERVE_START_RE.search(src)
    cutoff = serve_m.start() if serve_m else len(src)
    pre_serve = src[:cutoff]
    out: list[dict] = []
    for m in CONTAINER_DECL_RE.finditer(pre_serve):
        out.append({"name": m.group("name"), "pos": m.start()})
    return out


def is_mutated_in_handler(src: str, name: str) -> bool:
    """Heuristic: look for `<name>.push(` / `<name>.set(` / `<name>.add(` etc.
    anywhere in source (typically inside the handler since module-scope is small)."""
    patterns = [
        rf"\b{re.escape(name)}\.push\s*\(",
        rf"\b{re.escape(name)}\.set\s*\(",
        rf"\b{re.escape(name)}\.add\s*\(",
        rf"\b{re.escape(name)}\.unshift\s*\(",
    ]
    return any(re.search(p, src) for p in patterns)


def has_eviction(src: str, name: str) -> bool:
    patterns = [
        rf"\b{re.escape(name)}\.delete\s*\(",
        rf"\b{re.escape(name)}\.clear\s*\(",
        rf"\b{re.escape(name)}\.pop\s*\(",
        rf"\b{re.escape(name)}\.shift\s*\(",
        rf"\b{re.escape(name)}\.length\s*=",
        rf"\bif\s*\(\s*{re.escape(name)}\.size",
    ]
    return any(re.search(p, src) for p in patterns)


def check_unbounded_growth(fns):
    issues, report = [], []
    for name, path in fns:
        if name in MUTABLE_OK:
            continue
        src = read_file(path) or ""
        for c in find_module_containers(src):
            if not is_mutated_in_handler(src, c["name"]):
                continue
            if has_eviction(src, c["name"]):
                continue
            report.append({"fn": name, "container": c["name"]})
            issues.append({
                "check": "unbounded_growth", "skip": True,
                "reason": (
                    f"{name}/index.ts: module-level container `{c['name']}` "
                    f"is mutated inside the request handler with no "
                    f"eviction (.delete / .clear / .pop / .shift / size-cap). "
                    f"Warm container reuse grows it unbounded across "
                    f"requests until OOM. Add a size cap, move inside "
                    f"handler scope, or list '{name}' in MUTABLE_OK."
                ),
            })
    return issues, report


def check_eviction_adoption(fns):
    rows = []
    for name, path in fns:
        src = read_file(path) or ""
        for c in find_module_containers(src):
            if has_eviction(src, c["name"]):
                rows.append({"fn": name, "container": c["name"]})
    return [], rows


def check_inventory(fns):
    rows = []
    for name, path in fns:
        src = read_file(path) or ""
        containers = find_module_containers(src)
        if not containers:
            continue
        rows.append({"fn": name, "n_containers": len(containers),
                     "names": [c["name"] for c in containers]})
    rows.sort(key=lambda r: -r["n_containers"])
    return [], rows


def check_clean_fns(fns):
    rows = []
    for name, path in fns:
        src = read_file(path) or ""
        if find_module_containers(src):
            continue
        rows.append({"fn": name})
    return [], rows


CHECK_NAMES = ["unbounded_growth", "eviction_adoption", "inventory", "clean_fns"]
CHECK_LABELS = {
    "unbounded_growth":  "L1  No module-scope container mutated without eviction       [WARN]",
    "eviction_adoption": "L2  Containers with eviction (informational)                 [INFO]",
    "inventory":         "L3  Per-fn container inventory (informational)               [INFO]",
    "clean_fns":         "L4  Fns with zero module-level mutable state (informational) [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nEdge Function Module-Scope Mutable State (4-layer)"))
    print("=" * 60)
    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s) scanned.\n")
    l1_i, l1_r = check_unbounded_growth(fns)
    l2_i, l2_r = check_eviction_adoption(fns)
    l3_i, l3_r = check_inventory(fns)
    l4_i, l4_r = check_clean_fns(fns)
    all_issues = l1_i + l2_i + l3_i + l4_i
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)
    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")
    report = {"validator": "module_scope_state", "total_checks": total,
              "passed": n_pass, "warned": n_warn, "failed": n_fail,
              "unbounded_growth": l1_r, "eviction_adoption": l2_r,
              "inventory": l3_r, "clean_fns": l4_r,
              "issues": [i for i in all_issues if not i.get("skip")],
              "warnings": [i for i in all_issues if i.get("skip")]}
    with open("module_scope_state_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
