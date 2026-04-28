"""
Analytics Live Integration Test
================================
Calls the deployed analytics-orchestrator edge function with all 4 phases
and verifies each returns HTTP 200 with expected response shape.

This is the test that static validators can't do:
  - Confirms auth headers are accepted (not just present in code)
  - Confirms the deployed function matches what's in the codebase
  - Confirms the Python API on Render responds to analytics requests
  - Catches runtime errors that only appear with real (or minimal) data

Run separately or via platform guardian (skip_if_fast: True).
Usage: python validate_analytics_live.py
Output: analytics_live_report.json
"""
import json, sys, os, re, urllib.request

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE          = os.path.dirname(os.path.abspath(__file__))
HTML_FILE     = os.path.join(BASE, "analytics.html")

ANALYTICS_URL = "https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/analytics-orchestrator"
PHASES        = ["descriptive", "diagnostic", "predictive", "prescriptive"]

# Minimum keys each phase response must contain
EXPECTED_KEYS = {
    "descriptive":  ["phase", "mtbf", "mttr", "availability", "pm_compliance"],
    "diagnostic":   ["phase", "failure_mode_distribution", "pm_failure_correlation"],
    "predictive":   ["phase", "next_failure_dates", "pm_due_calendar", "health_scores"],
    "prescriptive": ["phase", "priority_ranking", "pm_interval_optimization"],
}

TIMEOUT = 90  # seconds — matches edge function AbortSignal.timeout


def green(s): return f"\033[92m{s}\033[0m"
def red(s):   return f"\033[91m{s}\033[0m"
def cyan(s):  return f"\033[96m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"


def extract_supabase_key():
    """Read SUPABASE_KEY from analytics.html so we don't hardcode it here."""
    try:
        with open(HTML_FILE, encoding="utf-8") as f:
            html = f.read()
        m = re.search(r"const SUPABASE_KEY\s*=\s*['\"]([^'\"]+)['\"]", html)
        return m.group(1) if m else None
    except Exception:
        return None


def call_phase(phase, supabase_key):
    payload = json.dumps({
        "phase":       phase,
        "hive_id":     None,
        "worker_name": "__validator_test__",
        "period_days": 90,
    }).encode()
    req = urllib.request.Request(
        ANALYTICS_URL,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "apikey":        supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, json.loads(r.read().decode())


def run_checks():
    issues = []
    supabase_key = extract_supabase_key()

    if not supabase_key:
        issues.append({
            "check":  "key_extracted",
            "reason": "Could not extract SUPABASE_KEY from analytics.html",
            "skip":   True,
        })
        return issues

    for phase in PHASES:
        # ── HTTP 200 + no error key ──────────────────────────────────────────
        try:
            status, data = call_phase(phase, supabase_key)

            if status != 200:
                issues.append({
                    "check":  f"live_{phase}",
                    "phase":  phase,
                    "reason": f"HTTP {status} — expected 200",
                })
                continue

            if data.get("error"):
                issues.append({
                    "check":  f"live_{phase}",
                    "phase":  phase,
                    "reason": f"Response contains error key: {str(data['error'])[:120]}",
                })
                continue

        except Exception as ex:
            issues.append({
                "check":  f"live_{phase}",
                "phase":  phase,
                "reason": f"Request failed: {str(ex)[:120]}",
            })
            continue

        # ── Response shape ───────────────────────────────────────────────────
        missing = [k for k in EXPECTED_KEYS.get(phase, []) if k not in data]
        if missing:
            issues.append({
                "check":  f"live_{phase}_shape",
                "phase":  phase,
                "reason": f"Missing keys in response: {missing}",
            })

    return issues


def main():
    print(bold("\nAnalytics Live Integration Test"))
    print("=" * 55)

    issues    = run_checks()
    failed    = {i["check"] for i in issues if not i.get("skip")}
    skipped   = {i["check"] for i in issues if i.get("skip")}

    check_names = (
        [f"live_{p}" for p in PHASES] +
        [f"live_{p}_shape" for p in PHASES]
    )
    check_labels = {
        **{f"live_{p}":        f"LIVE  {p}: HTTP 200, no error" for p in PHASES},
        **{f"live_{p}_shape":  f"LIVE  {p}: response shape"     for p in PHASES},
    }

    n_pass = n_fail = n_skip = 0

    for name in check_names:
        if name in skipped:
            print(f"  {cyan('SKIP')}  {check_labels[name]}")
            n_skip += 1
        elif name in failed:
            matching = next((i for i in issues if i["check"] == name), None)
            print(f"  {red('FAIL')}  {check_labels[name]}")
            if matching:
                print(f"         {matching['reason'][:90]}")
            n_fail += 1
        else:
            print(f"  {green('PASS')}  {check_labels[name]}")
            n_pass += 1

    if n_fail == 0 and n_skip == 0:
        print(f"{green(chr(10) + f'  All {n_pass} live checks passed.')}")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_skip} SKIP\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_fail} FAIL  {n_skip} SKIP\033[0m")

    report = {
        "validator": "analytics-live",
        "passed":    n_pass,
        "failed":    n_fail,
        "skipped":   n_skip,
        "issues":    [i for i in issues if not i.get("skip")],
        "skips":     [i for i in issues if i.get("skip")],
    }
    with open("analytics_live_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
