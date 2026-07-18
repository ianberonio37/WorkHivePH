"""
KPI Source Registry Validator -- WorkHive Platform Guardian (Phase 5, 2026-06-10)
=================================================================================
Closes the F4-class gap the OTHER kpi gates can't see: two pages reading two
DIFFERENT canonical views for the SAME metric. Home's PM-overdue tile read
`v_pm_compliance_truth.is_due` (flat 30-day proxy, =26) while pm-scheduler --
the page the tile links to -- read `v_pm_scope_items_truth.is_overdue`
(frequency-aware, =4). BOTH views are canonical, source chips were truthful,
no raw-table reads -- so source-chip-truth, canonical-sources and the TIER-A
gate all stayed green while the user clicked "26" and landed on "4".

`kpi_source_registry.json` declares ONE official derivation per metric
(established by the 2026-06-09/10 cross-page parity audits). Per metric this
gate asserts, on COMMENT-STRIPPED text (a retirement comment mentioning the
old source must not count):

  R1  every declared consumer references >=1 allowed_source token
      (and the required_signal column when declared);
  R2  NO consumer matches a forbidden re-derivation pattern (the documented
      wrong ways this metric was computed before canonicalization);
  R3  anti-rot: every allowed_source that looks like a view/RPC exists in the
      live DB (information_schema / pg_proc); degrades to SKIP offline.

Self-test:  python validate_kpi_source_registry.py --self-test  (synthetic, never live-drift)
Output:     kpi_source_registry_report.json
Sentinel binding: name the L2 test "test('kpi_source_registry: ...')".
"""
import json, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import format_result  # noqa: E402

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "kpi_source_registry.json"
REPORT = ROOT / "kpi_source_registry_report.json"
DB_CONTAINER = "supabase_db_workhive"

CHECK_NAMES = [
    "kpi_consumers_read_official_source",
    "kpi_consumers_avoid_forbidden_derivations",
    "kpi_registry_sources_exist",
]
CHECK_LABELS = {
    "kpi_consumers_read_official_source":
        "L0  Every registered KPI consumer references the metric's official source "
        "(one metric = one derivation; catches the F4 26-vs-4 class)",
    "kpi_consumers_avoid_forbidden_derivations":
        "L0  No registered KPI consumer re-derives the metric a documented wrong way "
        "(flat is_due proxy, ontrack/total compliance, unbanded top-risk)",
    "kpi_registry_sources_exist":
        "L0  Registry anti-rot: every declared view/RPC source exists in the live DB",
}

RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
RE_JS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
RE_JS_LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*")
RE_SQL_LINE_COMMENT = re.compile(r"--[^\n]*")


def stripped(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if path.suffix == ".html":
        text = RE_HTML_COMMENT.sub("", text)
    text = RE_JS_BLOCK_COMMENT.sub("", text)
    text = RE_JS_LINE_COMMENT.sub("", text)
    return text


def load_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["metrics"]


def check_consumers(root: Path, metrics: dict):
    """-> (r1_violations, r2_violations) as 'metric: detail' strings."""
    r1, r2 = [], []
    for mid, m in metrics.items():
        for consumer in m.get("consumers", []):
            f = root / consumer
            text = stripped(f)
            if not text:
                r1.append(f"{mid}: consumer {consumer} missing/unreadable")
                continue
            if not any(src in text for src in m.get("allowed_sources", [])):
                r1.append(f"{mid}: {consumer} references none of {m['allowed_sources']}")
            sig = m.get("required_signal")
            if sig and sig not in text:
                r1.append(f"{mid}: {consumer} never references required signal '{sig}'")
            for fb in m.get("forbidden", []):
                if re.search(fb["pattern"], text, re.S):
                    r2.append(f"{mid}: {consumer} matches forbidden derivation ({fb['why'][:70]})")
    return r1, r2


def live_objects():
    """set of relation + function names from the live DB, or None offline."""
    sql = ("SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
           "UNION SELECT table_name FROM information_schema.views WHERE table_schema='public' "
           "UNION SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
           "WHERE n.nspname='public';")
    try:
        out = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
             "-tAc", sql],
            capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            return None
        return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}
    except Exception:
        return None


def main():
    print("KPI Source Registry Validator")
    print("=============================")
    metrics = load_registry(REGISTRY)
    r1, r2 = check_consumers(ROOT, metrics)

    # NOTE: format_result (validator_utils) prints iss['reason']; use that key (not 'detail')
    # so a real finding renders as a readable FAIL instead of crashing the formatter with a
    # KeyError (which masked which violation fired — Asset/Alert/Shift arc, 2026-07-12).
    issues = []
    for v in r1:
        issues.append({"check": CHECK_NAMES[0], "reason": v})
    for v in r2:
        issues.append({"check": CHECK_NAMES[1], "reason": v})

    objs = live_objects()
    missing_sources = []
    if objs is None:
        issues.append({"check": CHECK_NAMES[2], "skip": True,
                       "reason": "live DB unreachable -> SKIP (no false alarms offline)"})
    else:
        for mid, m in metrics.items():
            for src in m.get("allowed_sources", []):
                if src not in objs:
                    missing_sources.append(f"{mid}: source '{src}' not in live DB")
        for v in missing_sources:
            issues.append({"check": CHECK_NAMES[2], "reason": v})

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    REPORT.write_text(json.dumps({
        "metrics": sorted(metrics.keys()),
        "r1_violations": r1, "r2_violations": r2,
        "missing_sources": missing_sources, "n_fail": n_fail,
    }, indent=2), encoding="utf-8")
    print(f"\nKPI source registry: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    sys.exit(1 if n_fail else 0)


def self_test():
    """Synthetic fixtures: teeth for R1 + R2, comment immunity."""
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        metrics = {
            "m_good": {"allowed_sources": ["v_good_truth"], "required_signal": "is_x",
                       "consumers": ["good.html"], "forbidden": [
                           {"pattern": r"\.from\(\s*['\"]v_bad_truth['\"]", "why": "retired proxy"}]},
            "m_bad_src": {"allowed_sources": ["v_good_truth"], "required_signal": None,
                          "consumers": ["bad-src.html"], "forbidden": []},
            "m_bad_deriv": {"allowed_sources": ["v_good_truth"], "required_signal": None,
                            "consumers": ["bad-deriv.html"], "forbidden": [
                                {"pattern": r"\.from\(\s*['\"]v_bad_truth['\"]", "why": "retired proxy"}]},
            "m_comment_ok": {"allowed_sources": ["v_good_truth"], "required_signal": None,
                             "consumers": ["comment-ok.html"], "forbidden": [
                                 {"pattern": r"\.from\(\s*['\"]v_bad_truth['\"]", "why": "retired proxy"}]},
        }
        (root / "good.html").write_text(
            "<script>db.from('v_good_truth').select('is_x')</script>", encoding="utf-8")
        (root / "bad-src.html").write_text(
            "<script>db.from('v_other_truth').select('*')</script>", encoding="utf-8")
        (root / "bad-deriv.html").write_text(
            "<script>db.from('v_good_truth');db.from('v_bad_truth').select('y')</script>",
            encoding="utf-8")
        (root / "comment-ok.html").write_text(
            "<script>db.from('v_good_truth');// was db.from('v_bad_truth') - retired\n</script>",
            encoding="utf-8")
        r1, r2 = check_consumers(root, metrics)
        t1 = any("m_bad_src" in v for v in r1) and not any("m_good" in v for v in r1)
        print(("PASS" if t1 else "FAIL") + f"  R1 teeth: wrong-source flagged, good consumer clean ({r1})")
        ok &= t1
        t2 = any("m_bad_deriv" in v for v in r2)
        print(("PASS" if t2 else "FAIL") + f"  R2 teeth: forbidden derivation flagged ({r2})")
        ok &= t2
        t3 = not any("m_comment_ok" in v for v in r2)
        print(("PASS" if t3 else "FAIL") + "  comment immunity: retired-source COMMENT not flagged")
        ok &= t3
    print("Self-test:", "ALL GREEN" if ok else "FAILURES")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    self_test() if "--self-test" in sys.argv else main()
