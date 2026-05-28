"""
Supabase Object Existence Validator (L0, ratcheted).
=====================================================
Every Supabase object a page/JS/edge-fn references MUST exist in the canonical
registry: `.from('T')` and `/rest/v1/T` -> a real table or view; `.rpc('fn')`
and `/rest/v1/rpc/fn` -> a real RPC function.

Closes the BLIND SPOT in validate_query_column_existence.py, which does
`cols = table_cols.get(table); if cols is None: continue` — i.e. a reference to
a table/view/rpc that does NOT exist at all is silently skipped. This validator
makes object existence explicit.

Discovered 2026-05-27 via the MCP cockpit flywheel: a Playwright sweep found
404s on founder-console / marketplace / public-feed; the Postgres MCP confirmed
the objects exist locally but were missing in prod. That specific case is a
local->prod deploy gap (separate concern); THIS validator guards the local
contract — no page may reference an object absent from the local registry.

Output: supabase_object_existence_report.json. Exit 1 on regression.
Allow with `// obj-exist-allow: <reason>` (or `<!-- obj-exist-allow: ... -->`)
within 200 chars of the reference.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "supabase_object_existence_report.json"
BASELINE_PATH = ROOT / "supabase_object_existence_baseline.json"
REGISTRY_PATH = ROOT / "canonical_registry.json"

# Objects that live outside the public schema / are provided by the platform
# and won't appear in the canonical registry. Referencing them is legitimate.
EXTERNAL_OBJECTS = {
    "rpc",                      # the /rest/v1/rpc/ prefix segment itself
    "users", "sessions",        # auth.* surfaced names sometimes used directly
}

# .from('t')  /  .rpc('fn')  — literal string args only (dynamic names can't be checked).
FROM_RE = re.compile(r"""\.from\(\s*['"`](?P<name>[a-z_][\w]*)['"`]\s*\)""")
RPC_RE  = re.compile(r"""\.rpc\(\s*['"`](?P<name>[a-z_][\w]*)['"`]""")
# REST URLs:  /rest/v1/<obj>?...   and   /rest/v1/rpc/<fn>
REST_RE = re.compile(r"""/rest/v1/(?:rpc/)?(?P<name>[a-z_][\w]*)""")
REST_IS_RPC_RE = re.compile(r"""/rest/v1/rpc/(?P<name>[a-z_][\w]*)""")

ALLOW_RE = re.compile(r"obj-exist-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _load_registry():
    r = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    tables = {t.lower() for t in r.get("tables", {})}
    views  = {v.lower() for v in r.get("views", {})}
    rpcs_raw = r.get("rpcs", {})
    rpcs = {x.lower() for x in (rpcs_raw.keys() if isinstance(rpcs_raw, dict) else rpcs_raw)}
    return tables | views, rpcs


def _scan_files():
    files: list[tuple[str, Path]] = []
    for html in sorted(ROOT.glob("*.html")):
        n = html.name
        if re.search(r"(test|backup|archived|\.bak)", n, re.I):
            continue
        files.append((n, html))
    for js in sorted(ROOT.glob("*.js")):
        files.append((js.name, js))
    edge = ROOT / "supabase" / "functions"
    if edge.exists():
        for ts in sorted(edge.rglob("*.ts")):
            files.append((ts.relative_to(ROOT).as_posix(), ts))
    return files


def _allowed_near(body: str, pos: int) -> bool:
    return bool(ALLOW_RE.search(body[max(0, pos - 200): pos + 200]))


def main() -> int:
    relations, rpcs = _load_registry()
    files = _scan_files()

    per_file = []
    total_refs = 0
    total_drift = 0
    seen: set = set()

    for name, path in files:
        if not path.exists():
            continue
        body = HTML_COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
        issues = []

        # collect RPC names hit via /rest/v1/rpc/ so we don't double-flag them as relations
        rest_rpc_spans = {m.start(): m.group("name").lower() for m in REST_IS_RPC_RE.finditer(body)}

        def check(name_str: str, pos: int, valid: set, kind: str):
            nonlocal total_refs, total_drift
            total_refs += 1
            obj = name_str.lower()
            if obj in EXTERNAL_OBJECTS or obj in valid:
                return
            if _allowed_near(body, pos):
                return
            key = (name, obj, kind)
            if key in seen:
                return
            seen.add(key)
            issues.append({"object": obj, "kind": kind})
            total_drift += 1

        for m in FROM_RE.finditer(body):
            check(m.group("name"), m.start(), relations, "from")
        for m in RPC_RE.finditer(body):
            check(m.group("name"), m.start(), rpcs, "rpc")
        for m in REST_RE.finditer(body):
            # is this the /rpc/ form?
            if m.start() in rest_rpc_spans or REST_IS_RPC_RE.match(body[m.start():m.start()+80]):
                check(m.group("name"), m.start(), rpcs, "rest_rpc")
            else:
                check(m.group("name"), m.start(), relations, "rest")

        if issues:
            per_file.append({"file": name, "issues": issues})

    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception:
            baseline = total_drift
    else:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_drift < baseline:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"files_with_issues": len(per_file), "total_refs": total_refs,
                    "total_drift": total_drift, "baseline": baseline,
                    "relations_known": len(relations), "rpcs_known": len(rpcs)},
        "per_file": per_file,
    }, indent=2), encoding="utf-8")

    print("\nSupabase Object Existence Validator (L0)")
    print("=" * 56)
    print(f"  object refs scanned: {total_refs}")
    print(f"  relations known:     {len(relations)}   rpcs known: {len(rpcs)}")
    print(f"  drift:               {total_drift}  (baseline: {baseline})")
    if total_drift == 0:
        print("\n  PASS — every referenced Supabase object exists in the registry.")
        return 0
    shown = 0
    for entry in per_file:
        print(f"  {entry['file']}")
        for i in entry["issues"]:
            print(f"    {i['kind']:8s} -> '{i['object']}'  — not in canonical registry")
            shown += 1
            if shown >= 40:
                print("    ... (more in report)")
                break
        if shown >= 40:
            break
    status = "PASS (at baseline)" if total_drift <= baseline else "FAIL (regression)"
    print(f"\n  {status}")
    return 1 if total_drift > baseline else 0


# Sentinel binding: name the L2 test `test('supabase_object_existence: ...')`.
CHECK_NAMES = ["supabase_object_existence"]

if __name__ == "__main__":
    sys.exit(main())
