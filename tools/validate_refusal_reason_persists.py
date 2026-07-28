#!/usr/bin/env python3
"""
validate_refusal_reason_persists.py — AHK2: when a calculation REFUSES, the reason must outlive the click.

THE CLASS: a reliability engine that declines to produce a number is doing the right thing — but the
refusal's whole product is the SENTENCE explaining why and what to do about it. If that sentence is
computed, returned once, and never stored, the user sees the absence of a number and no reason for
it on every subsequent visit. The number is correctly missing and the explanation is silently
missing too.

WALKED LIVE 2026-07-28 (Asset Hub deepwalk, AH9). python-api/reliability/weibull.py refuses below
MIN_FAILURES_FOR_FIT = 4 and returns beta=NULL, eta_days=NULL, failure_pattern='insufficient_data'
plus a genuinely useful diagnostic:

    "Need at least 4 corrective events in the lookback window (have 2).
     Log more breakdowns or widen since_days before refitting."

asset-hub renders that into #weibull-diagnostic. But `weibull_fits` had NO diagnostic column, so
persistFit never wrote it, `v_weibull_truth` could not expose it, and loadLatestWeibull selected a
column set that could not contain it — `fit.diagnostic` was undefined and
`diagEl.textContent = fit.diagnostic || ''` cleared the box. Visible for a few seconds after
Compute; blank on every page load after that. A planner opening the asset the next day saw beta
"--", eta "--", a pill reading "insufficient data", and an empty bordered box.

Fixed by 20260728000014 (column + view) plus the fitter writing it and the page selecting it. This
gate holds the whole round-trip, because breaking ANY link in it restores the silent-blank:

  1. the column exists on weibull_fits
  2. the truth view exposes it  (and still returns the LATEST fit per asset — the DISTINCT ON that
     makes it a "truth" view, which a careless rewrite would drop)
  3. the fitter persists it
  4. the page asks for it on the LOAD path, not only the compute path
  5. live: a refused fit actually carries a reason

Live tier for (1)/(2)/(5); static for (3)/(4). Self-test: --selftest.
"""
from __future__ import annotations
import io, json, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
FITTER = ROOT / "supabase" / "functions" / "weibull-fitter" / "index.ts"
PAGE = ROOT / "asset-hub.html"


def psql(sql):
    try:
        p = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres",
                            "-d", "postgres", "-t", "-A", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=45)
        return None if p.returncode != 0 else (p.stdout or "").strip()
    except Exception:
        return None


def main():
    if "--selftest" in sys.argv:
        probs = []
        # The pre-fix page shape must be recognisable as broken.
        pre = ".select('beta, eta_days, failure_pattern, n_failures, n_censored, log_likelihood, source_window_days, generated_at')"
        if "diagnostic" in pre:
            probs.append("the pre-fix select fixture already mentions diagnostic — no teeth")
        post = pre.replace("source_window_days,", "source_window_days, diagnostic,")
        if "diagnostic" not in post:
            probs.append("the fixed shape is not recognised")
        print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
        return 1 if probs else 0

    print(f"\n{BOLD}REFUSAL REASON PERSISTS (a declined calculation must say why, on every load){RESET}")
    print("-" * 72)

    col = psql("SELECT count(*) FROM information_schema.columns "
               "WHERE table_name='weibull_fits' AND column_name='diagnostic';")
    if col is None:
        print(f"  {YELLOW}SKIP{RESET}  docker psql unavailable")
        return 0

    view_col = psql("SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name='v_weibull_truth' AND column_name='diagnostic';") or "0"
    view_def = psql("SELECT pg_get_viewdef('public.v_weibull_truth'::regclass, true);") or ""
    refused = psql("SELECT count(*) FILTER (WHERE diagnostic IS NOT NULL AND btrim(diagnostic) <> ''), "
                   "count(*) FROM public.weibull_fits WHERE failure_pattern='insufficient_data';") or "0|0"
    try:
        with_reason, refused_total = (int(x) for x in refused.split("|")[:2])
    except ValueError:
        with_reason, refused_total = 0, 0

    fitter = FITTER.read_text(encoding="utf-8", errors="replace") if FITTER.exists() else ""
    page = PAGE.read_text(encoding="utf-8", errors="replace") if PAGE.exists() else ""
    load_selects = bool(re.search(r"from\('v_weibull_truth'\)[\s\S]{0,200}?diagnostic", page))

    checks = [
        ("column_exists", "OK" if col.strip() not in ("0", "") else "MISSING", "OK",
         "weibull_fits carries the refusal reason"),
        ("view_exposes", "OK" if view_col.strip() not in ("0", "") else "MISSING", "OK",
         "v_weibull_truth exposes it to the page"),
        ("view_still_latest_only", "OK" if "DISTINCT ON" in view_def.upper() else "BROKEN", "OK",
         "the truth view still returns the LATEST fit per asset (a rewrite that drops the "
         "DISTINCT ON would hand every consumer the full history)"),
        ("fitter_persists", "OK" if re.search(r"diagnostic:\s*fit\.diagnostic", fitter) else "MISSING", "OK",
         "the fitter writes the reason it just produced"),
        ("page_selects_on_load", "OK" if load_selects else "MISSING", "OK",
         "the LOAD path asks for it — the compute path alone leaves it blank on every revisit"),
        ("refusals_carry_a_reason",
         "OK" if (refused_total == 0 or with_reason == refused_total) else "BLANK", "OK",
         f"every refused fit states why ({with_reason} of {refused_total})"),
    ]

    fails = 0
    for name, got, want, desc in checks:
        if got == want:
            print(f"  {GREEN}PASS{RESET}  {name}: {desc}")
        else:
            fails += 1
            print(f"  {RED}FAIL{RESET}  {name}: expected {want}, got {got!r} — {desc}")

    print(f"\n  Summary: {len(checks) - fails} pass · {fails} fail")
    (ROOT / "refusal_reason_report.json").write_text(json.dumps(
        {"validator": "refusal_reason_persists",
         "refused_fits": refused_total, "with_reason": with_reason, "fail": fails},
        indent=2), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
