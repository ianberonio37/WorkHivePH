"""
Tier G / Layer 9: Capability Catalog & Dedup Validator
=======================================================
The forward-anchor gate for canonical_capabilities. Where Tier F locks
INPUT contracts and Tier C locks BRAIN OUTPUT contracts, Tier G locks
USER-FACING FUNCTIONS — every distinct capability on the platform has
ONE primary surface (edge fn / page / shared helper) and zero or more
documented secondary surfaces.

The validator runs in three layers + an interactive catalog mode:

  L1  Coverage     Every registered primary_surface exists in the codebase
  L2  Annotation   Every registered primary surface carries a
                   `// capability: <id>` comment so AI agents and
                   reviewers can find the catalog entry from the code
  L3  Dedup        No file claims `// capability: <id>, role: primary`
                   for a capability_id that already has a different
                   primary_surface registered

Plus a planning helper:
  --catalog [category]   Print the registry grouped by category so
                         a developer (or AI agent) can find an existing
                         surface to extend BEFORE building a new one.

Usage:
  python validate_capability_dedup.py                # run gate
  python validate_capability_dedup.py --catalog      # full catalog
  python validate_capability_dedup.py --catalog ai   # one category

Skills consulted: architect (registry + primary uniqueness), ai-engineer
(catalog surfaces existing entry points to prevent parallel orchestrators),
frontend (shared UI primitives documented + discoverable), designer
(one canonical answer per user job).
"""
from __future__ import annotations

import json
import os
import re
import sys
import glob
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import format_result, read_file


MIGRATIONS_DIR = os.path.join("supabase", "migrations")


# ── Catalog loader ────────────────────────────────────────────────────────────

def _walk_capability_tuples(block: str):
    """Yield (capability_id, category, primary_surface, secondary_surfaces[],
    retired_surfaces[], description, extension_pattern, hive_isolation)
    per tuple in a VALUES block. Quote-aware paren/bracket walker.

    Column order in canonical_capabilities:
      0=capability_id, 1=category, 2=primary_surface,
      3=ARRAY[secondary_surfaces], 4=ARRAY[retired_surfaces],
      5=description, 6=extension_pattern, 7=jsonb related_canonicals,
      8=hive_isolation
    """
    i = 0
    n = len(block)
    while i < n:
        while i < n and block[i] != "(":
            i += 1
        if i >= n: break
        i += 1
        # Per-tuple state — capture TOP-LEVEL strings AND ARRAY-bracket strings
        # separately so the column order stays consistent.
        top_strings: list[str] = []
        array_strings: list[list[str]] = []   # one list per top-level position
        cur_array: list[str] = []
        paren_depth = 1
        bracket_depth = 0
        in_str = False
        cur_str: list[str] = []
        str_origin = None   # 'top' | 'array'
        while i < n and paren_depth > 0:
            c = block[i]
            if in_str:
                if c == "'" and i + 1 < n and block[i + 1] == "'":
                    cur_str.append("'"); i += 2; continue
                if c == "'":
                    s = "".join(cur_str)
                    if str_origin == 'top':
                        top_strings.append(s)
                    elif str_origin == 'array':
                        cur_array.append(s)
                    cur_str = []
                    in_str = False
                else:
                    cur_str.append(c)
                i += 1; continue
            if c == "'":
                in_str = True
                str_origin = 'array' if bracket_depth > 0 else ('top' if paren_depth == 1 else None)
                i += 1; continue
            if c == "(": paren_depth += 1
            elif c == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    i += 1; break
            elif c == "[": bracket_depth += 1
            elif c == "]":
                bracket_depth = max(0, bracket_depth - 1)
                if bracket_depth == 0 and cur_array:
                    array_strings.append(cur_array)
                    cur_array = []
            i += 1

        if len(top_strings) >= 5:
            yield {
                "capability_id":      top_strings[0],
                "category":           top_strings[1],
                "primary_surface":    top_strings[2],
                "secondary_surfaces": array_strings[0] if len(array_strings) >= 1 else [],
                "retired_surfaces":   array_strings[1] if len(array_strings) >= 2 else [],
                "description":        top_strings[3] if len(top_strings) >= 4 else "",
                "extension_pattern":  top_strings[4] if len(top_strings) >= 5 else "",
                "hive_isolation":     top_strings[-1] if top_strings else "",
            }


def load_capabilities() -> list[dict]:
    """Parse canonical_capabilities migrations and return the full registry."""
    capabilities: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        if "canonical_capabilities" not in sql: continue
        sql_clean = re.sub(r"--[^\n]*", "", sql)
        m = re.search(
            r"INSERT\s+INTO\s+(?:public\.)?canonical_capabilities[^;]*?\bVALUES\b([\s\S]*?)(?:\bON\s+CONFLICT\b|\Z)",
            sql_clean, re.IGNORECASE)
        if not m: continue
        for cap in _walk_capability_tuples(m.group(1)):
            capabilities[cap["capability_id"]] = cap
    return list(capabilities.values())


# ── Surface resolution helpers ───────────────────────────────────────────────

# Primary surfaces that resolve to a DATABASE OBJECT (view / table / function)
# rather than a file on disk. They're still "primary" in the architectural
# sense (every consumer reads through this canonical), but their annotation
# lives in the registry instead of a code comment.
DB_RESIDENT_SURFACES = {
    "v_knowledge_truth", "v_audit_unified", "v_worker_truth", "v_asset_truth",
    "v_risk_truth", "v_kpi_truth", "v_logbook_truth", "v_pm_compliance_truth",
    "v_inventory_items_truth", "v_marketplace_sellers_truth", "v_fmea_truth",
    "v_rcm_truth", "v_weibull_truth", "v_pf_truth", "v_project_truth",
    "v_sensor_recent", "v_worker_skill_truth", "v_worker_assignment_truth",
    "v_pm_scope_items_truth", "v_worker_achievements", "v_achievement_xp_log",
    "agent_memory",
}


def _surface_path(surface: str) -> list[str]:
    """Return candidate file paths for a primary_surface string. Surfaces
    use patterns like:
      - 'ai-gateway'              -> supabase/functions/ai-gateway/index.ts
      - 'alert-hub.html'          -> ./alert-hub.html
      - 'utils.js#renderKpiTile'  -> utils.js (check substring)
      - 'worker-drawer.js'        -> ./worker-drawer.js
      - 'voice-journal.html#speak'-> voice-journal.html
    """
    if "#" in surface:
        surface = surface.split("#", 1)[0]
    if surface.endswith((".html", ".js", ".ts", ".py")):
        return [surface]
    # Edge function shorthand
    return [
        os.path.join("supabase", "functions", surface, "index.ts"),
        f"{surface}.html",
        f"{surface}.js",
    ]


def find_surface_file(surface: str) -> str | None:
    """Return the first existing candidate file for the surface, or None.
    DB-resident surfaces (view / table / agent_memory) return None
    because there's no file to read — Layer 1+2 skip these.
    """
    base = surface.split("#", 1)[0]
    if base in DB_RESIDENT_SURFACES:
        return None
    for cand in _surface_path(surface):
        if os.path.exists(cand):
            return cand
    return None


def is_db_resident(surface: str) -> bool:
    base = surface.split("#", 1)[0]
    return base in DB_RESIDENT_SURFACES


# ── Layer 1: Coverage — every primary_surface exists in the codebase ─────────

def check_coverage(capabilities: list[dict]) -> list[dict]:
    issues = []
    for cap in capabilities:
        # DB-resident surfaces skip the file-existence check (they live
        # in canonical_sources / migrations, not as code files).
        if is_db_resident(cap["primary_surface"]): continue
        path = find_surface_file(cap["primary_surface"])
        if path is None:
            issues.append({
                "check": "primary_surface_exists", "skip": False,
                "reason": f"Capability '{cap['capability_id']}' declares primary_surface "
                          f"'{cap['primary_surface']}' but no matching file exists. "
                          f"Either build the surface, or remove the capability from canonical_capabilities."
            })
    return issues


# ── Layer 2: Annotation — primary surface carries // capability: <id> ────────

def check_annotation(capabilities: list[dict]) -> list[dict]:
    issues = []
    for cap in capabilities:
        path = find_surface_file(cap["primary_surface"])
        if not path: continue   # Layer 1 already flagged
        content = read_file(path) or ""
        marker = f"capability: {cap['capability_id']}"
        if marker not in content:
            issues.append({
                "check": "primary_surface_annotated", "skip": True,
                "reason": f"Primary surface {path} lacks `// capability: {cap['capability_id']}` "
                          f"comment. Add it so AI agents + reviewers can find this entry from the code."
            })
    return issues


# ── Layer 3: Dedup — no two files claim primary for the same capability ──────

# Pattern matches both `// capability: foo` and `<!-- capability: foo -->`
CAP_RE = re.compile(r"(?://|<!--)\s*capability:\s*([a-z_][a-z0-9_]*)")


def _list_consumer_files() -> list[str]:
    out = []
    out.extend(sorted(glob.glob("*.html")))
    out.extend(sorted(glob.glob("*.js")))
    out.extend(sorted(glob.glob(os.path.join("supabase", "functions", "*", "index.ts"))))
    # Filter test/backup
    return [p for p in out if not any(t in p.lower() for t in ("backup", "test", "symbol-gallery"))]


def check_dedup(capabilities: list[dict]) -> list[dict]:
    """For each capability, the primary file is the one registered in
    canonical_capabilities. If ANY OTHER file in the codebase carries
    the same `// capability: <id>` annotation, that's fine — they're
    secondary surfaces (which is allowed). The L3 catch is more subtle:
    if a file claims `// capability: <id>, role: primary` but it's NOT
    the registered primary_surface, that's a parallel-primary attempt
    and FAILs CI.
    """
    issues = []
    files = _list_consumer_files()
    by_capability = defaultdict(list)
    for path in files:
        content = read_file(path) or ""
        for m in CAP_RE.finditer(content):
            by_capability[m.group(1)].append(path)

    primary_by_cap = {c["capability_id"]: find_surface_file(c["primary_surface"]) for c in capabilities}

    for cap_id, files_using in by_capability.items():
        # Check for `role: primary` claims
        for f in files_using:
            content = read_file(f) or ""
            # Look for "capability: <cap_id>, role: primary" or "role:primary"
            role_pat = re.compile(
                rf"(?://|<!--)\s*capability:\s*{re.escape(cap_id)}[^,\n]*,\s*role:\s*primary",
                re.IGNORECASE,
            )
            if role_pat.search(content):
                expected = primary_by_cap.get(cap_id)
                if expected and os.path.abspath(f) != os.path.abspath(expected):
                    issues.append({
                        "check": "no_parallel_primary", "skip": False,
                        "reason": f"{f} claims primary role for capability '{cap_id}' but the registered "
                                  f"primary is {expected}. Either retire one or change the registry."
                    })
    return issues


# ── Catalog mode (--catalog) ─────────────────────────────────────────────────

def print_catalog(capabilities: list[dict], category_filter: str | None = None):
    """Print the registry grouped by category for use as a planning catalog."""
    by_cat = defaultdict(list)
    for cap in capabilities:
        by_cat[cap["category"]].append(cap)

    def bold(s): return f"\033[1m{s}\033[0m"
    def dim(s):  return f"\033[2m{s}\033[0m"

    print(bold("\nWORKHIVE CANONICAL CAPABILITIES CATALOG"))
    print("=" * 72)
    print(dim("Read this BEFORE building a new feature. If an existing primary "
              "surface\nalready does what you need, EXTEND it instead of adding a new one."))
    print()

    cats = [category_filter] if category_filter else sorted(by_cat.keys())
    for cat in cats:
        items = by_cat.get(cat, [])
        if not items: continue
        print(bold(f"━━ {cat.upper()} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
        for cap in items:
            print(f"\n  \033[96m{cap['capability_id']}\033[0m")
            print(f"    primary:    {cap['primary_surface']}")
            if cap['secondary_surfaces']:
                print(f"    secondary:  {', '.join(cap['secondary_surfaces'])}")
            if cap['retired_surfaces']:
                print(f"    retired:    {', '.join(cap['retired_surfaces'])}")
            if cap['description']:
                # wrap at 70 chars
                desc = cap['description']
                while desc:
                    print(f"    {dim(desc[:68])}")
                    desc = desc[68:]
            if cap['extension_pattern']:
                print(f"    \033[93mextend:\033[0m     {cap['extension_pattern']}")
        print()
    print(dim("Run `validate_capability_dedup.py` without --catalog to enforce."))


# ── Main ─────────────────────────────────────────────────────────────────────

CHECK_NAMES = ["primary_surface_exists", "primary_surface_annotated", "no_parallel_primary"]
CHECK_LABELS = {
    "primary_surface_exists":    "L1  Every registered primary_surface resolves to a file on disk",
    "primary_surface_annotated": "L2  Every primary surface carries `// capability: <id>` annotation [WARN]",
    "no_parallel_primary":       "L3  No file claims role:primary for an existing different primary_surface",
}


def main():
    args = sys.argv[1:]
    if "--catalog" in args:
        idx = args.index("--catalog")
        category = args[idx + 1] if idx + 1 < len(args) else None
        caps = load_capabilities()
        print_catalog(caps, category)
        return

    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nCapability Catalog & Dedup Validator (Tier G / Layer 9)"))
    print("=" * 60)

    capabilities = load_capabilities()
    print(f"  {len(capabilities)} capabilities registered\n")

    issues = []
    issues += check_coverage(capabilities)
    issues += check_annotation(capabilities)
    issues += check_dedup(capabilities)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print(f"\n{bold('CATEGORY BREAKDOWN')}")
    print("  " + "-" * 40)
    by_cat = defaultdict(int)
    for c in capabilities:
        by_cat[c["category"]] += 1
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat:<14} {n:>3}")

    if n_fail == 0 and n_warn == 0:
        print(f"\n  \033[92mAll {len(CHECK_NAMES)} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\n  \033[93m{n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\n  \033[91m{n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "capability_dedup",
        "n_capabilities": len(capabilities),
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "by_category":  dict(by_cat),
        "capabilities": capabilities,
        "issues":       [i for i in issues if not i.get("skip")],
        "warnings":     [i for i in issues if i.get("skip")],
    }
    with open("capability_dedup_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  Saved capability_dedup_report.json")
    print(f"  Run \033[96mpython validate_capability_dedup.py --catalog\033[0m to browse the registry.\n")

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
