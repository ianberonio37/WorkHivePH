"""
Frequency-Map Consistency Validator -- WorkHive Platform Guardian
==================================================================
Catches the bug class found 2026-06-10 (analytics deep-walk): a PM
frequency -> interval-days map that does not cover the real vocabulary, so
some frequencies silently fall through to a default.

  v_pm_scope_items_truth.frequency_days CASE matched {Monthly,Quarterly,
  Semi-Annual,Yearly} but the seeder/UI emit {Weekly,Monthly,Quarterly,
  Semi-annual,Annual} -> Weekly/Semi-annual/Annual ALL fell to ELSE 90.
  next_due_date / is_overdue / is_due_soon derive from frequency_days, so
  every PM-due surface inherited wrong due dates (Weekly PM "due in 90 days"
  instead of 7). prescriptive.py FREQ_DAYS had the identical drift (weekly->30).

WHY THE GATE MISSED IT: the canonical validators check STRUCTURE (column
existence, source-chip tokens, query columns) but nothing checked the SEMANTIC
correctness of a frequency map, nor that the ~6 independent copies of it across
the platform (view, descriptive.py, prescriptive.py, pm.py seeder, JS) AGREE.

This validator closes both gaps:
  1. LIVE-DB (primary): SELECT DISTINCT frequency, frequency_days FROM
     v_pm_scope_items_truth -- every distinct live frequency must map to its
     canonical day-count. Catches the view bug + any future reseed-vocabulary
     drift. Degrades to SKIP if the DB is unreachable.
  2. STATIC: scans the analytics calcs / migrations / key pages for
     frequency->days literal pairs that CONTRADICT the canonical map (e.g.
     "Weekly": 30, WHEN 'Weekly' THEN 90). Catches the code copies.

Canonical map (case-insensitive): daily=1, weekly=7, biweekly=14, monthly=30,
quarterly=90, semi-annual=180, annual/yearly=365.

2026-06-13 (S1 / STREAMLINE_ROADMAP P7): added a third, SEMANTIC check --
frequency_map_COVERAGE. The contradiction scan only flags WRONG values on keys a
map HAS; it was blind to MISSING vocabulary absorbed by a numeric default
(predictive.py's {Monthly,Quarterly,Semi-Annual,Yearly} silently sent
Weekly/Semi-annual/Annual to .get(...,30) -- this validator PASSED despite it).
Coverage asserts every executable freq->days map COVERS the real seeder/UI
vocabulary (case-insensitive) so no live frequency can fall to a default.

Output: frequency_map_consistency_report.json. Exit 1 on any violation.
Sentinel binding: name the L2 test 'test('frequency_map_consistency: ...')'.
Self-test:  python validate_frequency_map_consistency.py --self-test
"""
import re, json, sys, subprocess
from pathlib import Path

from validator_utils import format_result  # noqa: E402

ROOT = Path(__file__).resolve().parent
DB_CONTAINER = "supabase_db_workhive"

# Canonical frequency -> interval days (lowercase keys; the one true map).
CANON = {
    "daily": 1, "weekly": 7, "biweekly": 14, "fortnightly": 14,
    "monthly": 30, "quarterly": 90,
    "semi-annual": 180, "semiannual": 180, "semi annual": 180,
    "annual": 365, "yearly": 365,
}

CHECK_NAMES = ["frequency_map_canonical", "frequency_map_coverage"]
CHECK_LABELS = {
    "frequency_map_canonical":
        "L0/L1  Every PM frequency maps to its canonical interval days "
        "(live view + code copies agree; catches seeder-vocabulary drift)",
    "frequency_map_coverage":
        "L0/L1  Every executable freq->days map COVERS the real vocabulary "
        "(no live frequency falls to a numeric default; catches the predictive.py P5 class)",
}

# Files that carry a frequency -> days mapping (static scan target).
STATIC_GLOBS = [
    "python-api/analytics/*.py",
    "test-data-seeder/seeders/pm.py",
    "supabase/functions/analytics-orchestrator/index.ts",
    "supabase/migrations/*v_pm_scope*.sql",
    "supabase/migrations/*pm_compliance*.sql",
    "supabase/migrations/*frequency*.sql",
]

# The real PM-frequency vocabulary the seeder + UI emit (test-data-seeder/seeders/
# pm.py PM_FREQUENCIES; confirmed live via SELECT DISTINCT frequency FROM
# v_pm_scope_items_truth). Any EXECUTABLE freq->days map must cover every one of
# these case-insensitively, or the missing ones silently hit a numeric default.
REQUIRED_VOCAB = {"weekly", "monthly", "quarterly", "semi-annual", "annual"}

# EXECUTABLE freq->days map copies (run at request time). Excludes the append-only
# SQL migrations in STATIC_GLOBS — a superseded migration's old CASE is history,
# and the LIVE view's correctness is already asserted by live_view_violations().
COVERAGE_GLOBS = [
    "python-api/analytics/*.py",
    "test-data-seeder/seeders/pm.py",
    "supabase/functions/analytics-orchestrator/index.ts",
]

# A quoted frequency label immediately followed (within ~25 chars, no other
# frequency word between) by an integer -> treat as a (freq, days) mapping pair.
FREQ_WORDS = r"(daily|weekly|biweekly|fortnightly|monthly|quarterly|semi-?annual|semi annual|annual|yearly)"
RE_PAIR = re.compile(
    r"['\"]" + FREQ_WORDS + r"['\"]\s*(?::|=>|=|,|\bthen\b|interval\s*['\"]?)\s*(\d{1,3})",
    re.I,
)


def live_view_violations():
    """[(frequency, frequency_days, expected)] from the canonical view, or None if DB unreachable."""
    try:
        r = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tAc",
             "SELECT DISTINCT frequency, frequency_days FROM public.v_pm_scope_items_truth "
             "WHERE frequency IS NOT NULL;"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return None
    except Exception:
        return None
    bad = []
    for line in r.stdout.splitlines():
        if "|" not in line:
            continue
        freq, days = line.split("|", 1)
        freq, days = freq.strip(), days.strip()
        if not freq or not days.lstrip("-").isdigit():
            continue
        expected = CANON.get(freq.strip().lower())
        if expected is not None and int(days) != expected:
            bad.append((freq, int(days), expected))
    return bad


def static_violations():
    """[(file:line, 'Freq->got (want)')] for contradictory frequency->days literals in code."""
    out = []
    for g in STATIC_GLOBS:
        for f in ROOT.glob(g):
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                for m in RE_PAIR.finditer(line):
                    freq = m.group(1).lower().replace("semiannual", "semi-annual")
                    got = int(m.group(2))
                    want = CANON.get(freq) or CANON.get(freq.replace("-", ""))
                    if want is not None and got != want:
                        rel = f.relative_to(ROOT).as_posix()
                        out.append(f"{rel}:{i}  '{m.group(1)}'->{got} (canonical {want})")
    return sorted(set(out))


def live_vocabulary():
    """set of distinct lowercased frequencies in the live view, or None offline."""
    try:
        r = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tAc",
             "SELECT DISTINCT frequency FROM public.v_pm_scope_items_truth WHERE frequency IS NOT NULL;"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return None
    except Exception:
        return None
    return {ln.strip().lower() for ln in r.stdout.splitlines() if ln.strip()}


def coverage_violations(required: set, globs=COVERAGE_GLOBS, root: Path = ROOT):
    """[(file  reason)] for executable freq->days maps that don't cover `required`.

    A file is treated as defining a frequency map when >=3 distinct (freq, days)
    literal pairs are present (so a one-off mention is not flagged). Every map must
    have a key (case-insensitive, exact token) for each required frequency, else
    that frequency falls through to a numeric default at runtime -- the P5 class.
    """
    out = []
    for g in globs:
        for f in root.glob(g):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            keys = {m.group(1).strip().lower() for m in RE_PAIR.finditer(text)}
            if len(keys) < 3:
                continue  # not a frequency map, just an incidental mention
            missing = sorted(t for t in required if t not in keys)
            if missing:
                rel = f.relative_to(root).as_posix()
                out.append(f"{rel}  freq-map missing {missing} -> those frequencies hit the numeric default")
    return sorted(set(out))


def main():
    print("Frequency-Map Consistency Validator")
    print("===================================")
    issues = []

    # 1) Live canonical view
    view_bad = live_view_violations()
    if view_bad is None:
        print("  live DB unreachable -> view check SKIPPED (static scan still runs)")
    elif view_bad:
        offenders = ", ".join(f"{f}->{d} (want {e})" for f, d, e in view_bad)
        issues.append({"check": "frequency_map_canonical",
                       "reason": f"v_pm_scope_items_truth.frequency_days is non-canonical for: {offenders}. "
                                 f"next_due_date/is_overdue/is_due_soon are derived from this -> wrong PM due dates."})
        print(f"  LIVE VIEW VIOLATIONS ({len(view_bad)}): {offenders}")
    else:
        print("  live view OK: every distinct frequency maps to its canonical interval days")

    # 2) Static code copies
    static_bad = static_violations()
    if static_bad:
        issues.append({"check": "frequency_map_canonical",
                       "reason": f"{len(static_bad)} code frequency->days literal(s) contradict the canonical map: "
                                 + "; ".join(static_bad[:10]) + (" ..." if len(static_bad) > 10 else "")})
        print(f"  STATIC VIOLATIONS ({len(static_bad)}):")
        for s in static_bad[:20]:
            print(f"    {s}")
    else:
        print("  static scan OK: no contradictory frequency->days literals in analytics/migrations/seeder")

    # 3) Coverage: every executable freq->days map covers the real vocabulary.
    #    Required = the seeder/UI vocabulary, widened with the live distinct set
    #    (so a future reseed that adds e.g. 'Daily' is enforced automatically).
    live_vocab = live_vocabulary()
    required = set(REQUIRED_VOCAB) | (live_vocab or set())
    coverage_bad = coverage_violations(required)
    if coverage_bad:
        issues.append({"check": "frequency_map_coverage",
                       "reason": f"{len(coverage_bad)} executable freq->days map(s) don't cover the required "
                                 f"vocabulary {sorted(required)} (missing keys fall to a numeric default -> the P5 class): "
                                 + "; ".join(coverage_bad[:10]) + (" ..." if len(coverage_bad) > 10 else "")})
        print(f"  COVERAGE VIOLATIONS ({len(coverage_bad)}):")
        for s in coverage_bad[:20]:
            print(f"    {s}")
    else:
        print(f"  coverage OK: every executable freq->days map covers {sorted(required)}")

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print(f"\nFrequency-map consistency: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    json.dump({"view_violations": view_bad, "static_violations": static_bad,
               "coverage_violations": coverage_bad, "required_vocab": sorted(required),
               "n_fail": n_fail},
              open("frequency_map_consistency_report.json", "w", encoding="utf-8"), indent=2)
    sys.exit(1 if n_fail > 0 else 0)


def self_test():
    """Synthetic fixtures proving the coverage check has teeth (qa-tester rule)."""
    import tempfile
    ok = True
    required = set(REQUIRED_VOCAB)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "python-api" / "analytics").mkdir(parents=True)
        # Stale 4-key map (the predictive.py P5 shape) -> must be flagged.
        (root / "python-api" / "analytics" / "stale.py").write_text(
            'FREQ_DAYS = {"Monthly": 30, "Quarterly": 90, "Semi-Annual": 180, "Yearly": 365}\n',
            encoding="utf-8")
        # Canonical full-vocabulary map -> must be clean.
        (root / "python-api" / "analytics" / "good.py").write_text(
            'FREQ_DAYS = {"daily":1,"weekly":7,"monthly":30,"quarterly":90,'
            '"semi-annual":180,"semiannual":180,"annual":365,"yearly":365}\n',
            encoding="utf-8")
        bad = coverage_violations(required, globs=["python-api/analytics/*.py"], root=root)
        t1 = any("stale.py" in v for v in bad)
        print(("PASS" if t1 else "FAIL") + f"  coverage teeth: stale 4-key map flagged ({bad})")
        ok &= t1
        t2 = not any("good.py" in v for v in bad)
        print(("PASS" if t2 else "FAIL") + "  coverage clean: canonical full map not flagged")
        ok &= t2
    print("Self-test:", "ALL GREEN" if ok else "FAILURES")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    self_test() if "--self-test" in sys.argv else main()
