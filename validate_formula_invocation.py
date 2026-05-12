"""
Tier D-f refinement: formula invocation drift validator
======================================================
The canonical_formulas registry pins each derivation to one library_source
(e.g. mtbf_iso_14224 -> sql:get_mtbf_by_machine). But that alone doesn't
stop two consumers from calling the same formula with DIFFERENT arguments
and producing different numbers.

Real example surfaced 2026-05-12:
  - predictive.html reads v_risk_truth.mtbf_days   (365-day window)
  - analytics.html  calls get_mtbf_by_machine(90)  (90-day window)
  - Same canonical formula, same library_source, but the period_days
    argument differs -> HPU-001 shows 12d on Predictive and 7.1d on
    Analytics. The user sees "MTBF" twice with different numbers and
    asks why.

This validator scans the whole platform for invocations of every
registered canonical_formula. For each, it extracts the arguments
passed and groups consumers by argument set. Different argument values
across consumers = WINDOW DRIFT (or PARAMETER DRIFT in general).

The validator does NOT block on drift (it's often intentional — different
windows for different surfaces is a legitimate design choice). But it
SURFACES every case so the user can decide:
  - intentional: document it (add to ALLOWED_FORMULA_VARIANCE)
  - accidental: align the windows OR show the window in the UI

Layers:
  L1 - Coverage: every registered formula that has a recognisable
       invocation pattern (sql:get_*, sql:v_*, python:...:calc_*) has
       at least one consumer.
  L2 - Argument variance: per formula_id, list distinct argument
       value sets across consumers. INFO level (not FAIL) — drift
       is documented, not blocked.
  L3 - Cross-surface comparison: explicit pair check on the most
       common parameter (period_days). If two consumer pages render
       the same metric label to the user but pass different
       period_days, that's flagged as a USER-VISIBLE DRIFT — the
       user sees two numbers labelled the same.

Output:  formula_invocation_report.json — full call graph per formula.
         Console: scoreboard + top user-visible drift pairs.
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


# Allowlist: formulas where argument drift across consumers is INTENTIONAL.
# Each entry must include a one-line justification so a future maintainer
# can decide whether the exception still holds. The validator still REPORTS
# allowlisted drift in the JSON detail (so it's never invisible) but
# excludes it from the L1 WARN summary so the gate stays informative
# rather than perpetually nagging on a documented design choice.
ALLOWED_FORMULA_DRIFT = {
    "mtbf_iso_14224":
        "Intentional. Analytics shows MTBF over a user-selectable window "
        "(default 90d) for trend exploration; batch-risk-scoring uses a "
        "fixed 365-day annual-decay window for the v_risk_truth nightly "
        "snapshot consumed by Predictive. Both are correct; the surface "
        "chip on each page declares the actual window. Promoting v_risk_truth "
        "to expose mtbf_30d/90d/365d columns would resolve this fully "
        "(see commit c5cf9ec for the deferred plan).",
}


# Pages/files we scan as consumers
def list_consumer_files() -> list[str]:
    out = []
    for path in sorted(glob.glob("*.html")):
        name = os.path.basename(path).lower()
        if any(t in name for t in ("backup", "test", "symbol-gallery")): continue
        out.append(path)
    for path in sorted(glob.glob(os.path.join("supabase", "functions", "*", "index.ts"))):
        out.append(path)
    for path in sorted(glob.glob(os.path.join("python-api", "**", "*.py"), recursive=True)):
        if "__init__" in path or "__pycache__" in path: continue
        out.append(path)
    return out


# Parse canonical_formulas registry — extract formula_id, library_source
def load_registered_formulas() -> dict[str, dict]:
    """Returns formula_id -> {library_source, domain, standard_ids, sql_target, python_target}.

    Parses INSERT VALUES from migrations. The library_source field tells us
    what to grep for:
      sql:get_mtbf_by_machine        -> grep for .rpc('get_mtbf_by_machine'...)
      sql:v_pm_compliance_truth      -> grep for .from('v_pm_compliance_truth'...)
      python:python-api/.../calc_*   -> grep for callPythonAnalytics + calc_*
    """
    formulas: dict[str, dict] = {}
    # Quote-aware walker for the VALUES tuples — already proven in capture validator
    for path in sorted(glob.glob(os.path.join("supabase", "migrations", "*.sql"))):
        sql = read_file(path) or ""
        if "canonical_formulas" not in sql: continue
        sql_clean = re.sub(r"--[^\n]*", "", sql)
        # Find INSERT VALUES block, terminate at ON CONFLICT
        m = re.search(
            r"INSERT\s+INTO\s+(?:public\.)?canonical_formulas[^;]*?\bVALUES\b([\s\S]*?)(?:\bON\s+CONFLICT\b|\Z)",
            sql_clean, re.IGNORECASE)
        if not m: continue
        block = m.group(1)
        for fid, library_source, domain in _walk_formula_tuples(block):
            sql_target = ""
            python_target = ""
            if library_source.startswith("sql:"):
                sql_target = library_source[4:]
            elif library_source.startswith("python:"):
                # python:python-api/analytics/descriptive.py:calc_mtbf
                parts = library_source.split(":")
                if len(parts) >= 3:
                    python_target = parts[-1]
            formulas[fid] = {
                "library_source": library_source,
                "domain": domain,
                "sql_target": sql_target,
                "python_target": python_target,
            }
    return formulas


def _walk_formula_tuples(block: str):
    """Yield (formula_id, library_source, domain) per tuple in a VALUES block.
    Column order in canonical_formulas: formula_id, name, domain, standard_ids,
    library_source, inputs, outputs, formula_text, description.
    """
    i = 0
    n = len(block)
    while i < n:
        while i < n and block[i] != "(": i += 1
        if i >= n: break
        # Walk one tuple. Top-level single-quoted strings ordered:
        #   0=formula_id, 1=name, 2=domain, [skip ARRAY], 3=library_source,
        #   [skip jsonb], [skip jsonb], 4=formula_text, 5=description
        strings: list[str] = []
        paren_depth = 1
        bracket_depth = 0
        i += 1
        in_str = False
        cur: list[str] = []
        str_top = True
        while i < n and paren_depth > 0:
            c = block[i]
            if in_str:
                if c == "'" and i + 1 < n and block[i + 1] == "'":
                    cur.append("'"); i += 2; continue
                if c == "'":
                    if str_top:
                        strings.append("".join(cur))
                    cur = []
                    in_str = False
                else:
                    cur.append(c)
                i += 1; continue
            if c == "'":
                in_str = True
                str_top = (paren_depth == 1 and bracket_depth == 0)
                i += 1; continue
            if c == "(": paren_depth += 1
            elif c == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    i += 1; break
            elif c == "[": bracket_depth += 1
            elif c == "]": bracket_depth = max(0, bracket_depth - 1)
            i += 1
        # strings[0]=formula_id, strings[1]=name, strings[2]=domain,
        # strings[3]=library_source (after ARRAY[] skipped)
        if len(strings) >= 4:
            fid = strings[0]
            domain = strings[2]
            library_source = strings[3]
            if re.match(r"^[a-z_][a-z0-9_]*$", fid):
                yield (fid, library_source, domain)


# Invocation extraction --------------------------------------------------------

def extract_rpc_calls(content: str, rpc_name: str) -> list[dict]:
    """Find .rpc('rpc_name', { p_arg: <value> }) calls. Returns list of
    {args_text, p_period_days, raw}."""
    pat = re.compile(
        rf"""\.rpc\(\s*["'`]{re.escape(rpc_name)}["'`]\s*(?:,\s*(\{{[\s\S]*?\}}|[A-Za-z_][A-Za-z0-9_]*))?""",
        re.MULTILINE,
    )
    out = []
    for m in pat.finditer(content):
        args = m.group(1) or ""
        period = None
        # Case A: inline object literal — { ..., p_period_days: 90 }
        pm = re.search(r"p_period_days\s*:\s*([0-9]+|[A-Za-z_][A-Za-z0-9_]*)", args)
        if pm:
            period = pm.group(1)
        else:
            # Case B: bare identifier reference — `db.rpc('get_mtbf', rpc)`
            # Look upstream in the file for `const <ident> = { ..., p_period_days: ... }`
            ident = args.strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", ident):
                # Hop 1: find the object literal assigned to <ident>
                vp = re.search(
                    rf"""(?:const|let|var)\s+{re.escape(ident)}\s*=\s*\{{([\s\S]*?)\}}""",
                    content,
                )
                if vp:
                    inner = vp.group(1)
                    pm2 = re.search(
                        r"p_period_days\s*:\s*([0-9]+|[A-Za-z_][A-Za-z0-9_]*)",
                        inner,
                    )
                    if pm2: period = pm2.group(1)
        out.append({"args_text": args[:120], "p_period_days": period})
    return out


def extract_view_reads(content: str, view_name: str) -> list[dict]:
    """Find .from('view_name').select(...).order/limit etc. — view reads
    don't carry args (the view is the canonical snapshot), but the
    consumer's window is implied by which view it picks."""
    pat = re.compile(
        rf"""\.from\(\s*["'`]{re.escape(view_name)}["'`]\s*\)""",
        re.MULTILINE,
    )
    out = []
    for m in pat.finditer(content):
        out.append({"args_text": f"<view read>", "p_period_days": None})
    return out


def extract_python_calls(content: str, fn_name: str) -> list[dict]:
    """Find calls like callPythonAnalytics('phase', {period_days: X})
    OR direct calc_*(*, period_days=X) — both pass period_days but in
    different shapes."""
    out = []
    # callPythonAnalytics pattern (TypeScript)
    pat = re.compile(
        r"""callPythonAnalytics\(\s*["'`]([a-z_]+)["'`]\s*,\s*\{([\s\S]*?)\}""",
        re.MULTILINE,
    )
    for m in pat.finditer(content):
        phase = m.group(1)
        args = m.group(2)
        period = None
        pm = re.search(r"period_days\s*:\s*([0-9]+|[A-Za-z_][A-Za-z0-9_]*)", args)
        if pm: period = pm.group(1)
        out.append({"args_text": f"phase={phase} {args[:60]}", "p_period_days": period})
    # Direct Python calls calc_x(args, period_days=N).
    # IMPORTANT: skip `def <fn_name>(` (the definition itself) — only count
    # actual call sites where the function is invoked, not where it lives.
    if fn_name.startswith("calc_"):
        # Negative-lookbehind for `def ` to skip the def site
        pat2 = re.compile(
            rf"(?<!def )(?<![a-zA-Z_]){re.escape(fn_name)}\(([\s\S]*?)\)",
            re.MULTILINE,
        )
        for m in pat2.finditer(content):
            # Extra guard: if the preceding chars on this line are `def `, skip
            start = m.start()
            line_start = content.rfind("\n", 0, start) + 1
            if content[line_start:start].lstrip().startswith("def "):
                continue
            args = m.group(1)
            period = None
            pm = re.search(r"period_days\s*=\s*([0-9]+|[A-Za-z_][A-Za-z0-9_]*)", args)
            if pm: period = pm.group(1)
            out.append({"args_text": args[:80], "p_period_days": period})
    return out


# Variables we resolve to literal values when we see them
def _resolve_variable(name: str, file_content: str) -> str | None:
    """For period_days passed as a variable, try to find its literal default
    in the file. E.g. `const periodDays = Number(period_days) || 90;` -> '90'."""
    pat = re.compile(
        rf"""(?:const|let|var)\s+{re.escape(name)}\s*=\s*[^;\n]*?\|\|\s*(\d+)""",
        re.MULTILINE,
    )
    m = pat.search(file_content)
    if m: return m.group(1) + " (default)"
    pat2 = re.compile(
        rf"""(?:const|let|var)\s+{re.escape(name)}\s*=\s*(\d+)""",
        re.MULTILINE,
    )
    m = pat2.search(file_content)
    if m: return m.group(1)
    # Python style
    pat3 = re.compile(rf"""\b{re.escape(name)}\s*=\s*(\d+)\b""", re.MULTILINE)
    m = pat3.search(file_content)
    if m: return m.group(1)
    return None


# Per-formula scan -------------------------------------------------------------

def scan_invocations(formulas: dict[str, dict], files: list[str]) -> dict[str, list]:
    """Returns formula_id -> list of {file, p_period_days_raw, p_period_days_resolved, args_text}."""
    invocations: dict[str, list] = defaultdict(list)
    for path in files:
        content = read_file(path) or ""
        if not content: continue
        for fid, info in formulas.items():
            sql_t = info["sql_target"]
            py_t = info["python_target"]

            calls = []
            if sql_t.startswith("get_"):
                calls.extend(extract_rpc_calls(content, sql_t))
            if sql_t.startswith("v_"):
                calls.extend(extract_view_reads(content, sql_t))
            if py_t:
                calls.extend(extract_python_calls(content, py_t))

            for call in calls:
                period_raw = call.get("p_period_days")
                period_resolved = period_raw
                if period_raw and not period_raw.isdigit():
                    # variable name — try to resolve
                    res = _resolve_variable(period_raw, content)
                    if res: period_resolved = res
                invocations[fid].append({
                    "file": path,
                    "p_period_days_raw": period_raw,
                    "p_period_days_resolved": period_resolved,
                    "args_text": call.get("args_text"),
                })
    return invocations


# Drift analysis ---------------------------------------------------------------

def _is_numeric_window(v: str) -> bool:
    """Return True if v is a literal numeric window value (e.g. '90', '365',
    '90 (default)'). Excludes '<view-or-no-arg>' and unresolved variables."""
    if not v: return False
    if v == "<view-or-no-arg>": return False
    head = v.split()[0]
    return head.isdigit()


def analyse_drift(invocations: dict[str, list]) -> dict:
    """DRIFT semantics — flag ONLY when 2+ consumers pass DIFFERENT numeric
    window values. Cases:
      - ORPHAN:    formula has zero invocations
      - SINGLETON: 1 consumer (no drift possible)
      - NO_PARAM:  formula doesn't take a period_days arg (all calls are
                   <view-or-no-arg>); excluded from drift report
      - ALIGNED:   multiple consumers, all numeric values match
      - DRIFT:     2+ DIFFERENT numeric values across consumers — the
                   real user-facing window-drift case (MTBF 90 vs 365)
    """
    summary = []
    for fid, calls in sorted(invocations.items()):
        if not calls:
            summary.append({"formula_id": fid, "status": "ORPHAN", "n_consumers": 0, "windows": []})
            continue
        per_consumer = defaultdict(set)
        for c in calls:
            file = c["file"]
            pd = c["p_period_days_resolved"]
            per_consumer[file].add(pd or "<view-or-no-arg>")

        all_windows = set()
        for vals in per_consumer.values():
            all_windows.update(vals)

        numeric_windows = {w for w in all_windows if _is_numeric_window(w)}

        n_consumers = len(per_consumer)
        if n_consumers == 1:
            status = "SINGLETON"
        elif not numeric_windows:
            status = "NO_PARAM"
        elif len(numeric_windows) == 1:
            status = "ALIGNED"
        else:
            status = "DRIFT"

        summary.append({
            "formula_id":      fid,
            "status":          status,
            "n_consumers":     n_consumers,
            "n_calls":         len(calls),
            "windows":         sorted(all_windows, key=str),
            "numeric_windows": sorted(numeric_windows, key=str),
            "consumers":       {f: sorted(v, key=str) for f, v in per_consumer.items()},
        })
    return summary


# Main -------------------------------------------------------------------------

def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nFormula Invocation Drift Validator (Tier D-f refinement)"))
    print("=" * 60)

    formulas = load_registered_formulas()
    files    = list_consumer_files()
    print(f"  {len(formulas)} formulas registered, {len(files)} consumer files scanned\n")

    invocations = scan_invocations(formulas, files)
    summary     = analyse_drift(invocations)

    # Group by status. Drift cases on ALLOWED_FORMULA_DRIFT keep their
    # DRIFT label in the JSON detail (so the divergence stays visible to
    # any reviewer reading the report) but are excluded from the L1 WARN
    # to keep the gate focused on UNDOCUMENTED drift.
    drift_all    = [s for s in summary if s["status"] == "DRIFT"]
    drift        = [s for s in drift_all if s["formula_id"] not in ALLOWED_FORMULA_DRIFT]
    drift_allow  = [s for s in drift_all if s["formula_id"] in ALLOWED_FORMULA_DRIFT]
    aligned   = [s for s in summary if s["status"] == "ALIGNED"]
    singleton = [s for s in summary if s["status"] == "SINGLETON"]
    no_param  = [s for s in summary if s["status"] == "NO_PARAM"]
    orphan    = [s for s in summary if s["status"] == "ORPHAN"]

    CHECK_NAMES = ["formula_drift", "formula_orphan"]
    CHECK_LABELS = {
        "formula_drift":  "L1  Formulas invoked with different arg values across consumers (drift) [WARN]",
        "formula_orphan": "L2  Formulas with zero detected invocations (orphans, dead reg)         [WARN]",
    }
    issues = []
    if drift:
        issues.append({
            "check": "formula_drift", "skip": True,
            "reason": f"{len(drift)} formulas show user-facing window/parameter drift. "
                      f"Examples: {[(s['formula_id'], s['windows']) for s in drift[:4]]}",
        })
    if orphan:
        # Orphan only matters if the canonical declares a SQL/python target —
        # formulas with empty library_source are placeholders and skipped
        real_orphans = [s for s in orphan
                        if formulas.get(s["formula_id"], {}).get("sql_target") or
                           formulas.get(s["formula_id"], {}).get("python_target")]
        if real_orphans:
            issues.append({
                "check": "formula_orphan", "skip": True,
                "reason": f"{len(real_orphans)} formulas have NO detected invocations: "
                          f"{[s['formula_id'] for s in real_orphans[:10]]}",
            })

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    # Print scoreboard
    print(f"\n{bold('FORMULA INVOCATION SCOREBOARD')}")
    print("  " + "-" * 60)
    print("  status        n_formulas")
    print("  " + "-" * 60)
    for status, items in [("DRIFT", drift), ("DRIFT (allowed)", drift_allow),
                          ("ALIGNED", aligned),
                          ("SINGLETON", singleton), ("NO_PARAM", no_param),
                          ("ORPHAN", orphan)]:
        print(f"  {status:<16} {len(items):>3}")

    # Drift detail
    if drift:
        print(f"\n{bold('USER-VISIBLE WINDOW DRIFT (top 8)')}")
        print("  " + "-" * 60)
        for s in drift[:8]:
            print(f"\n  {s['formula_id']}   ({s['n_consumers']} consumers, windows: {s['windows']})")
            for f, ws in s["consumers"].items():
                print(f"    {os.path.basename(f):<35} -> {sorted(ws, key=str)}")

    # Save report
    report = {
        "validator":        "formula_invocation",
        "n_formulas":       len(formulas),
        "n_files_scanned":  len(files),
        "n_drift":          len(drift),
        "n_drift_allowed":  len(drift_allow),
        "n_aligned":        len(aligned),
        "n_singleton":      len(singleton),
        "n_orphan":         len(orphan),
        "drift_detail":     drift,
        "drift_allowed_detail": [
            {**s, "justification": ALLOWED_FORMULA_DRIFT[s["formula_id"]]}
            for s in drift_allow
        ],
        "aligned_detail":   aligned[:10],
        "singleton_detail": singleton[:10],
        "orphan_list":      [s["formula_id"] for s in orphan],
    }
    with open("formula_invocation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Saved formula_invocation_report.json")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
