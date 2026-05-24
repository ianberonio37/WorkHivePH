"""
Agentic RAG Observability Validator (Phase 8 of AGENTIC_RAG_ROADMAP.md)
=======================================================================
Forward-only L0 ratchet locking the supervisor-facing observability page
that reads agentic_rag_traces.

  O01  agentic-rag-observability.html exists
  O02  Page declares calm-dashboard meta opt-in
  O03  Page loads utils.js (escHtml + debounce shared utilities)
  O04  Hive gate present (#hive-gate)
  O05  Reads agentic_rag_traces with hive scoping (.eq('hive_id', HIVE_ID))
  O06  Reads only narrow column selection (no select('*'))
  O07  Renders route breakdown, top-heavy, and recent traces tables
  O08  Uses escHtml on every dynamic value path
  O09  Bounded fetch (.limit(N)) on the trace query
  O10  Time-window filter (.gte('created_at', ...))
"""
from __future__ import annotations
import os, sys, re

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

PAGE = "agentic-rag-observability.html"


def _read() -> str:
    return read_file(PAGE) or ""


def check_file_exists() -> list[dict]:
    if not os.path.isfile(PAGE):
        return [{"check": "file_exists", "reason": f"{PAGE} not found"}]
    return []


def check_calm_meta(src: str) -> list[dict]:
    if 'name="calm-dashboard"' not in src:
        return [{"check": "calm_meta", "reason": 'Missing <meta name="calm-dashboard" content="1" /> opt-in'}]
    return []


def check_utils_loaded(src: str) -> list[dict]:
    if 'src="utils.js"' not in src:
        return [{"check": "utils_loaded", "reason": 'Must <script src="utils.js"> so escHtml + debounce are available'}]
    return []


def check_hive_gate(src: str) -> list[dict]:
    if 'id="hive-gate"' not in src and "id='hive-gate'" not in src:
        return [{"check": "hive_gate", "reason": "Missing #hive-gate overlay; the dashboard is hive-scoped"}]
    return []


def check_hive_scoping(src: str) -> list[dict]:
    if not re.search(r"\.eq\(\s*['\"]hive_id['\"]\s*,\s*HIVE_ID\s*\)", src):
        return [{"check": "hive_scoping", "reason": 'Trace query must .eq("hive_id", HIVE_ID)'}]
    return []


def check_narrow_select(src: str) -> list[dict]:
    # Find the .from('agentic_rag_traces').select(...) chain
    m = re.search(r"\.from\(\s*['\"]agentic_rag_traces['\"]\s*\)\s*\.select\(\s*['\"]([^'\"]+)['\"]", src)
    if not m:
        return [{"check": "narrow_select", "reason": 'No .from("agentic_rag_traces").select("...") chain found'}]
    cols = m.group(1).strip()
    if cols == "*":
        return [{"check": "narrow_select", "reason": 'Trace query uses select("*") — must enumerate columns per performance skill'}]
    return []


def check_render_blocks(src: str) -> list[dict]:
    issues = []
    for fn, why in [
        ("renderRouteTable",  "route breakdown table"),
        ("renderHeaviest",    "top-heavy queries table"),
        ("renderRecent",      "recent traces table"),
        ("renderSummary",     "summary cards"),
    ]:
        if fn not in src:
            issues.append({"check": "render_blocks", "reason": f"Missing render function {fn} ({why})"})
    return issues


def check_eschtml_used(src: str) -> list[dict]:
    if "escHtml" not in src:
        return [{"check": "eschtml", "reason": "escHtml must be used on every dynamic value path"}]
    # Heuristic: count escHtml uses; a real page renders many strings.
    count = len(re.findall(r"\bescHtml\s*\(", src))
    if count < 5:
        return [{"check": "eschtml", "reason": f"escHtml called only {count} times — too few for the number of rendered values"}]
    return []


def check_bounded_fetch(src: str) -> list[dict]:
    if not re.search(r"\.limit\(\s*\d+\s*\)", src):
        return [{"check": "bounded_fetch", "reason": ".limit(N) missing on agentic_rag_traces query — must be bounded per performance skill"}]
    return []


def check_window_filter(src: str) -> list[dict]:
    if not re.search(r"\.gte\(\s*['\"]created_at['\"]", src):
        return [{"check": "window_filter", "reason": '.gte("created_at", ...) missing — must filter to a time window'}]
    return []


CHECKS = [
    ("file_exists",   "O01 agentic-rag-observability.html exists",           check_file_exists),
    ("calm_meta",     "O02 calm-dashboard meta opt-in present",              lambda: check_calm_meta(_read())),
    ("utils_loaded",  "O03 utils.js loaded (escHtml)",                       lambda: check_utils_loaded(_read())),
    ("hive_gate",     "O04 Hive gate overlay (#hive-gate)",                  lambda: check_hive_gate(_read())),
    ("hive_scoping",  "O05 Trace query .eq(hive_id, HIVE_ID)",               lambda: check_hive_scoping(_read())),
    ("narrow_select", "O06 Narrow column .select() on agentic_rag_traces",   lambda: check_narrow_select(_read())),
    ("render_blocks", "O07 Render fns: route, heavy, recent, summary",       lambda: check_render_blocks(_read())),
    ("eschtml",       "O08 escHtml used on dynamic values",                  lambda: check_eschtml_used(_read())),
    ("bounded_fetch", "O09 .limit(N) bounded trace query",                   lambda: check_bounded_fetch(_read())),
    ("window_filter", "O10 .gte(created_at, ...) time-window filter",        lambda: check_window_filter(_read())),
]


def main() -> int:
    print("\033[1m\nAgentic RAG Observability Validator (Phase 8 of AGENTIC_RAG_ROADMAP.md)\033[0m")
    print("=" * 70)
    all_issues = []
    keys = [c[0] for c in CHECKS]
    labels = {c[0]: c[1] for c in CHECKS}
    for key, _label, fn in CHECKS:
        for issue in fn():
            issue.setdefault("check", key)
            all_issues.append(issue)
    n_pass, n_skip, n_fail = format_result(keys, labels, all_issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
