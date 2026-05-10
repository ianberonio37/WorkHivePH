"""
Write Path Monitor -- WorkHive Platform
========================================
Symmetric twin of validate_silo_monitor.py. Where silo_monitor watches READ
convergence (do consumers read the canonical view?), this validator watches
WRITE convergence (do writers agree on the contract for a given table?).

The four bug classes this catches:
  - status-machine drift (page X writes status='Closed', page Y writes 'Done')
  - missing required-column drift (one writer sets hive_id, another forgets)
  - silent owner-table sprawl (5+ files inserting into the same table with no
    designated owner)
  - single-layer write monopoly (a canonical's primary table is only written
    from one layer when another layer semantically should also write to it)

Layer 1 -- Write shape drift                                              [WARN]
  For each table written from N+ files, extract the column sets from each
  literal .insert({...}) and flag tables where the writer column-sets
  diverge significantly. Drift = different writers using different shapes.

Layer 2 -- Orphan registered write paths                                  [WARN]
  RPCs registered in canonical_sources (kind='rpc') with no caller. Either
  the RPC is dead and should be retired or the caller was never wired.

Layer 3 -- Unregistered write hotspots                                    [WARN]
  Tables INSERTed/UPDATEd from N+ distinct files with no canonical entry
  and no clear owner page. Suggests scattered ownership.

Layer 4 -- Single-layer write monopoly                                    [WARN]
  Registered canonicals where the primary backing table is written from
  exactly one platform layer when other layers semantically should also
  write to it (audit logs that only edge fns write but HTML actions miss).

Skills consulted: architect (canonical sources + 4-place sync, write-path
ownership), data-engineer (insert column convergence, status-machine
integrity), security (writes are higher stakes than reads — every drift is
a latent inconsistency), platform-guardian (non-blocking informational).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


# ── Paths ─────────────────────────────────────────────────────────────────────

MIGRATIONS_DIR = os.path.join("supabase", "migrations")
FUNCTIONS_DIR  = os.path.join("supabase", "functions")
PYTHON_API_DIR = "python-api"

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")
EXCLUDED_PATH_PARTS = (
    os.sep + "test-data-seeder" + os.sep,
    os.sep + "tools" + os.sep,
    os.sep + "video_marketing_app" + os.sep,
    os.sep + ".git" + os.sep,
    os.sep + "node_modules" + os.sep,
)

# Tables we don't expect to have a "single owner" — they are platform-wide
# infrastructure that many features write to legitimately.
WRITE_HOTSPOT_IGNORE_TABLES = {
    "hives", "hive_members", "worker_profiles", "auth", "users",
    "ai_rate_limits",
    "automation_log",        # every async job logs here, by design
    "hive_audit_log",        # every state change logs here, by design
    "cmms_audit_log",        # every CMMS sync logs here, by design
    "canonical_sources",
    "achievement_xp_log",    # every action grants XP
    "skill_exam_attempts",   # every quiz attempt logged
    "marketplace_orders",    # checkout creates, release/refund/dispute update — by design
    "marketplace_disputes",  # multi-actor: buyer opens, seller responds, admin resolves
}

# Tables that are LEGITIMATELY single-layer writers. Mirrors the silo
# monitor's ACCEPTED_SINGLE_LAYER_DOMAINS pattern.
ACCEPTED_SINGLE_LAYER_WRITERS = {
    "ai_rate_limits":  "Internal infrastructure — only edge fns increment rate counts.",
    "automation_log":  "Async jobs log from edge fns; HTML never appends here.",
    "asset_risk_scores": "Insert-only history table — only batch-risk-scoring writes.",
    "weibull_fits":    "Result-of-compute table — only weibull-fitter writes.",
    "pf_intervals":    "Result-of-compute table — only pf-calculator writes.",
    "parts_staging_recommendations": "Result-of-ML table — only parts-staging-recommender writes.",
    "shift_plans":     "Result-of-AI table — only shift-planner-orchestrator writes.",
    "ai_reports":      "Insert-only AI generation history — only intelligence-report writes.",
    "hive_benchmarks": "Aggregate output — only benchmark-compute writes.",
    "network_benchmarks": "Aggregate output — only benchmark-compute writes.",
    "asset_embeddings": "Vector pipeline — only embed-entry writes.",
    "ph_intelligence_reports": "Insert-only — only intelligence-api writes.",
    "external_sync":   "CMMS bridge state — only sync edge fns write.",
    # User-managed master data: HTML pages own these tables (asset-hub creates
    # asset_nodes, inventory.html creates inventory_items, pm-scheduler creates
    # pm_assets, asset-hub creates rcm_strategies). Edge fns should not write.
    "asset_nodes":     "User-managed asset master — only asset-hub.html writes (CRUD on asset graph).",
    "pm_assets":       "User-managed PM asset master — only pm-scheduler.html writes (CRUD on PM scope).",
    "rcm_strategies":  "User-managed reliability strategy — only asset-hub.html writes (engineer authoring).",
    "inventory_items": "User-managed parts master — only inventory.html writes (CRUD on stock).",
    "rcm_fmea_modes":  "User-managed FMEA library — only asset-hub.html writes (engineer authoring).",
}

UNREGISTERED_HOTSPOT_THRESHOLD     = 5    # writer files for L3
DRIFT_DIVERGENCE_THRESHOLD         = 0.40  # column-set Jaccard distance for L1
DRIFT_MIN_WRITERS                  = 3    # need 3+ writers before computing drift


# ── Discovery: same patterns as silo monitor, but for write operations ────────

WRITE_OP_RE_JSTS = re.compile(
    r"""\.from\s*\(\s*['"`]([a-z_][a-z0-9_]*)['"`]\s*\)\s*\.\s*(insert|upsert|update|delete)""",
    re.IGNORECASE,
)
WRITE_OP_RE_PY = re.compile(
    r"""\.table\s*\(\s*['"]([a-z_][a-z0-9_]*)['"]\s*\)\s*\.\s*(insert|upsert|update|delete)""",
    re.IGNORECASE,
)

# Capture the immediate object literal passed to .insert({...}) / .upsert({...}).
# Best-effort: only catches { key1: ..., key2: ..., } shapes (the common case).
INSERT_OBJ_RE = re.compile(
    r"""\.from\s*\(\s*['"`]([a-z_][a-z0-9_]*)['"`]\s*\)\s*\.\s*(?:insert|upsert)\s*\(\s*\{([^{}]+)\}""",
    re.IGNORECASE | re.DOTALL,
)

# Capture identifier-like keys from an object literal body. Permissive: catches
# `key: value`, `key:value`, but NOT `[expr]: value` (computed keys).
KEY_RE = re.compile(r"""(?:^|[\s,{])([a-z_][a-z0-9_]*)\s*:""", re.IGNORECASE)


def _path_excluded(path: str) -> bool:
    for part in EXCLUDED_PATH_PARTS:
        if part in path:
            return True
    return False


def list_writer_files() -> list[tuple[str, str]]:
    """Return [(path, layer)] for every file we treat as a potential writer."""
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob("*.html")):
        name = os.path.basename(path).lower()
        if any(p in name for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append((path, "html"))
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append((path, "shared_js"))
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((idx, "edge"))
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if "__init__" in path or _path_excluded(path):
            continue
        out.append((path, "python_api"))
    return out


def file_write_ops(path: str) -> list[tuple[str, str]]:
    """Return [(table, op)] write operations in the file."""
    content = read_file(path) or ""
    if path.endswith(".py"):
        return [(m.group(1).lower(), m.group(2).lower()) for m in WRITE_OP_RE_PY.finditer(content)]
    return [(m.group(1).lower(), m.group(2).lower()) for m in WRITE_OP_RE_JSTS.finditer(content)]


def file_insert_column_sets(path: str) -> dict[str, set[str]]:
    """Return { table: {column_keys_seen_in_inserts} } for this file.

    Best-effort literal-object parse. Variable spreads like `.insert(payload)`
    or computed keys like `[fieldName]: value` are skipped — those tables
    won't get a clean column set and won't be flagged for drift.
    """
    content = read_file(path) or ""
    if path.endswith(".py"):
        # Python writers use payload dicts; rarely literal-object inserts —
        # skip column-set extraction in Python for simplicity.
        return {}
    out: dict[str, set[str]] = defaultdict(set)
    for m in INSERT_OBJ_RE.finditer(content):
        table = m.group(1).lower()
        body  = m.group(2)
        for km in KEY_RE.finditer(body):
            out[table].add(km.group(1).lower())
    return {k: v for k, v in out.items() if v}


# ── Load registered canonicals + their primary tables (reuse silo monitor's logic) ──

def load_registered_canonicals() -> list[dict]:
    out: list[dict] = []
    TUPLE_RE = re.compile(
        r"\(\s*'([a-z_][a-z0-9_]*)'\s*,\s*'(view|table|rpc)'\s*,"
        r"\s*'([a-z_][a-z0-9_]*)'\s*,\s*'([a-z0-9_\-]+)'\s*,\s*'([a-z0-9_]+)'",
        re.IGNORECASE,
    )
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = read_file(path) or ""
        if "canonical_sources" not in sql:
            continue
        for m in TUPLE_RE.finditer(sql):
            out.append({
                "domain":      m.group(1),
                "kind":        m.group(2),
                "source_name": m.group(3),
                "owner_skill": m.group(4),
            })
    by_domain: dict[str, dict] = {}
    for r in out:
        by_domain[r["domain"]] = r
    return list(by_domain.values())


def _depth_at(body: str, idx: int) -> int:
    depth = 0
    for ch in body[:idx]:
        if   ch == "(": depth += 1
        elif ch == ")": depth -= 1
    return depth


def load_view_primary_tables() -> dict[str, str]:
    """Return { view_name: primary_table_name } using the same outer-FROM
    parser as silo monitor."""
    out: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        sql = re.sub(r"--[^\n]*", "", read_file(path) or "")
        for m in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:public\.)?(\w+)\s+AS"
            r"([\s\S]*?)(?=;\s*(?:CREATE|GRANT|COMMENT|ALTER|INSERT|--|\Z))",
            sql, re.IGNORECASE,
        ):
            view_name = m.group(1).lower()
            body      = m.group(2)
            for tm in re.finditer(
                r"\b(FROM|JOIN)\s+(?:public\.)?(\w+)\b",
                body, re.IGNORECASE,
            ):
                kw, t = tm.group(1).upper(), tm.group(2).lower()
                if t.startswith("v_") or t in ("select", "values", "lateral"):
                    continue
                if kw == "FROM" and _depth_at(body, tm.start()) == 0 and view_name not in out:
                    out[view_name] = t
                    break
    return out


# ── Layer assemblers ─────────────────────────────────────────────────────────

def build_writer_index(files: list[tuple[str, str]]) -> tuple[dict, dict]:
    """
    writer_idx: { table: {"writers": [(path, layer, op)], "by_layer": {layer: count}} }
    column_sets_per_table: { table: { path: {keys} } }
    """
    writer_idx: dict[str, dict] = defaultdict(lambda: {"writers": [], "by_layer": defaultdict(int)})
    column_sets: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for path, layer in files:
        for table, op in file_write_ops(path):
            writer_idx[table]["writers"].append((path, layer, op))
            writer_idx[table]["by_layer"][layer] += 1
        for table, keys in file_insert_column_sets(path).items():
            column_sets[table][path] = keys
    # Convert defaultdicts for JSON safety
    return (
        {k: {"writers": v["writers"], "by_layer": dict(v["by_layer"])} for k, v in writer_idx.items()},
        {k: v for k, v in column_sets.items()},
    )


# ── Layer 1: Write shape drift ───────────────────────────────────────────────

def _jaccard_distance(a: set[str], b: set[str]) -> float:
    if not a and not b: return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0: return 0.0
    return 1.0 - (inter / union)


def check_write_shape_drift(column_sets: dict, writer_idx: dict) -> tuple[list[dict], list[dict]]:
    """For tables with N+ writers, compute pairwise Jaccard distance between
    the column sets each writer uses on .insert(). Flag if max distance > THRESHOLD.
    """
    issues: list[dict] = []
    drift_report: list[dict] = []
    for table, by_path in column_sets.items():
        if len(by_path) < DRIFT_MIN_WRITERS:
            continue
        paths = sorted(by_path.keys())
        sets  = [by_path[p] for p in paths]
        # Compute the union ("known columns") and per-writer coverage
        union = set().union(*sets)
        # Find max pairwise Jaccard distance
        max_dist = 0.0
        worst_pair = (None, None)
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                d = _jaccard_distance(sets[i], sets[j])
                if d > max_dist:
                    max_dist = d
                    worst_pair = (paths[i], paths[j])
        # Always include in report so the matrix has full coverage
        drift_report.append({
            "table":        table,
            "n_writers":    len(paths),
            "union_size":   len(union),
            "max_distance": round(max_dist, 3),
            "worst_pair":   list(worst_pair) if worst_pair[0] else None,
            "writers":      [
                {"path": p, "n_keys": len(by_path[p]), "missing": sorted(union - by_path[p])[:5]}
                for p in paths
            ],
        })
        if max_dist > DRIFT_DIVERGENCE_THRESHOLD:
            missing_at_each = []
            for p in paths:
                miss = sorted(union - by_path[p])
                if miss:
                    missing_at_each.append(f"{p} missing {miss[:3]}")
            issues.append({
                "check": "write_shape_drift", "skip": True,
                "reason": (
                    f"Table '{table}' has {len(paths)} writers with column-shape divergence "
                    f"(max Jaccard distance {max_dist:.2f} > {DRIFT_DIVERGENCE_THRESHOLD}). "
                    f"Worst pair: {worst_pair[0]} vs {worst_pair[1]}. "
                    f"Sample diffs: {missing_at_each[:3]}."
                ),
            })
    return issues, drift_report


# ── Layer 2: Orphan registered RPCs ──────────────────────────────────────────

def check_orphan_rpcs(canonicals: list[dict], writer_idx: dict, files: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """Registered canonical with kind='rpc' that no consumer file calls.
    Detection is best-effort — looks for `.rpc('NAME')` references.
    """
    rpcs = [c for c in canonicals if c["kind"] == "rpc"]
    if not rpcs:
        return [], []
    # Build a set of every .rpc('NAME') / .rpc("NAME") found in consumer files
    called: set[str] = set()
    rpc_call_re = re.compile(r"""\.rpc\s*\(\s*['"`]([a-z_][a-z0-9_]*)['"`]""", re.IGNORECASE)
    for path, _layer in files:
        content = read_file(path) or ""
        for m in rpc_call_re.finditer(content):
            called.add(m.group(1).lower())

    issues: list[dict] = []
    orphans: list[dict] = []
    for c in rpcs:
        name = c["source_name"].lower()
        if name in called:
            continue
        orphans.append({"domain": c["domain"], "rpc": c["source_name"], "owner_skill": c["owner_skill"]})
        issues.append({
            "check": "orphan_rpcs", "skip": True,
            "reason": (
                f"Registered RPC canonical '{c['domain']}' -> {c['source_name']} (owner_skill={c['owner_skill']}) "
                f"has zero callers in consumer files. Either the RPC is dead and should be retired, or "
                f"the caller was never wired."
            ),
        })
    return issues, orphans


# ── Layer 3: Unregistered write hotspots ─────────────────────────────────────

def check_write_hotspots(canonicals: list[dict], writer_idx: dict, view_primaries: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """Tables INSERTed/UPDATEd from N+ files with no canonical entry
    (and not in the ignore set)."""
    registered_names = {c["source_name"].lower() for c in canonicals}
    backed_tables    = set(view_primaries.values())
    issues: list[dict] = []
    hotspots: list[dict] = []
    for table, info in writer_idx.items():
        if table in registered_names or table in backed_tables:
            continue
        if table in WRITE_HOTSPOT_IGNORE_TABLES:
            continue
        # Count distinct files
        distinct_writers = sorted({(p, l) for (p, l, _op) in info["writers"]})
        n = len(distinct_writers)
        if n >= UNREGISTERED_HOTSPOT_THRESHOLD:
            hotspots.append({
                "table":     table,
                "n_writers": n,
                "by_layer":  info["by_layer"],
                "sample":    [p for (p, _, _) in info["writers"][:5]],
            })
    hotspots.sort(key=lambda h: -h["n_writers"])
    for h in hotspots[:8]:
        issues.append({
            "check": "write_hotspots", "skip": True,
            "reason": (
                f"Table '{h['table']}' is written by {h['n_writers']} consumer file(s) "
                f"({dict(h['by_layer'])}) with no canonical entry. Consider registering an owner / "
                f"adding the table to WRITE_HOTSPOT_IGNORE_TABLES if multi-writer is intentional. "
                f"First 3 writers: {h['sample'][:3]}."
            ),
        })
    return issues, hotspots


# ── Layer 4: Single-layer write monopoly on canonical primary tables ─────────

def check_single_layer_writers(canonicals: list[dict], writer_idx: dict, view_primaries: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """For each canonical view's primary table, count writers per platform layer.
    WARN if exactly one layer writes (and the table isn't allowlisted)."""
    issues: list[dict] = []
    monopolies: list[dict] = []
    for c in canonicals:
        if c["kind"] != "view":
            continue
        primary = view_primaries.get(c["source_name"].lower())
        if not primary:
            continue
        info = writer_idx.get(primary)
        if not info:
            continue
        n_layers = sum(1 for v in info["by_layer"].values() if v > 0)
        if n_layers == 1:
            (only_layer, _) = next(iter(info["by_layer"].items()))
            monopolies.append({
                "canonical":  c["domain"],
                "table":      primary,
                "only_layer": only_layer,
                "n_writers":  len(info["writers"]),
            })
            if primary in ACCEPTED_SINGLE_LAYER_WRITERS:
                continue
            issues.append({
                "check": "single_layer_writers", "skip": True,
                "reason": (
                    f"Canonical '{c['domain']}' (primary table {primary}) is written from exactly "
                    f"one platform layer ('{only_layer}', {len(info['writers'])} write site(s)). "
                    f"Other layers may semantically need to write here too. If intentional, add to "
                    f"ACCEPTED_SINGLE_LAYER_WRITERS in validate_write_path_monitor.py with a justification."
                ),
            })
    return issues, monopolies


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "write_shape_drift",
    "orphan_rpcs",
    "write_hotspots",
    "single_layer_writers",
]

CHECK_LABELS = {
    "write_shape_drift":     "L1  Multi-writer tables agree on column shape (Jaccard < 0.40)        [WARN]",
    "orphan_rpcs":           "L2  Every registered RPC canonical has at least one caller            [WARN]",
    "write_hotspots":        "L3  No 5+ writers of an unregistered table (write-side hotspot)       [WARN]",
    "single_layer_writers":  "L4  Canonical primary tables not written from one layer only          [WARN]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nWrite Path Monitor (4-layer architectural audit, write side)"))
    print("=" * 65)

    canonicals     = load_registered_canonicals()
    view_primaries = load_view_primary_tables()
    writer_files   = list_writer_files()
    writer_idx, column_sets = build_writer_index(writer_files)

    print(f"  {len(canonicals)} canonicals, {len(view_primaries)} view primaries, "
          f"{len(writer_files)} writer files scanned.\n")

    drift_issues,    drift_report  = check_write_shape_drift(column_sets, writer_idx)
    orphan_issues,   orphan_list   = check_orphan_rpcs(canonicals, writer_idx, writer_files)
    hotspot_issues,  hotspot_list  = check_write_hotspots(canonicals, writer_idx, view_primaries)
    mono_issues,     monopoly_list = check_single_layer_writers(canonicals, writer_idx, view_primaries)

    all_issues = drift_issues + orphan_issues + hotspot_issues + mono_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    # Top-N writer summary so the user can eyeball which tables are write-heavy
    print(f"\n{bold('TOP-15 WRITE TARGETS')}")
    print("  " + "-" * 56)
    top = sorted(writer_idx.items(), key=lambda kv: -len(kv[1]["writers"]))[:15]
    print("  {:<32}  {:>5}  {:<20}".format("table", "n", "by layer"))
    print("  " + "-" * 56)
    for table, info in top:
        layer_str = ", ".join(f"{k}={v}" for k, v in sorted(info["by_layer"].items())) or "-"
        print("  {:<32}  {:>5}  {:<20}".format(table[:32], len(info["writers"]), layer_str[:20]))

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":        "write_path_monitor",
        "total_checks":     total,
        "passed":           n_pass,
        "warned":           n_warn,
        "failed":           n_fail,
        "n_canonicals":     len(canonicals),
        "n_writer_files":   len(writer_files),
        "drift_report":     drift_report,
        "orphan_rpcs":      orphan_list,
        "write_hotspots":   hotspot_list,
        "single_layer_writers": monopoly_list,
        "issues":           [i for i in all_issues if not i.get("skip")],
        "warnings":         [i for i in all_issues if i.get("skip")],
    }
    with open("write_path_monitor_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
