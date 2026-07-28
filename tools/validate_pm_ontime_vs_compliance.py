#!/usr/bin/env python3
"""
validate_pm_ontime_vs_compliance.py — PMK1: on-time is not the same as done.

THE CLASS: a compliance metric that counts a PM whenever it lands inside the period, regardless of
whether it was done ON SCHEDULE, flatters the program to the person least able to check it.

WALKED LIVE 2026-07-28, two personas, two hives:
  supervisor / Lucena : "0 of 31 on track now  ·  88% PM compliance (SMRP)"   (20 overdue)
  worker     / Manila : "3 of 30 on track now  ·  86% PM compliance (SMRP)"   (24 overdue)
Both read as near-world-class against the 90% benchmark while almost nothing is actually on track.

MEASURED AT THE DB, which explains how both can be true at once: of 1,224 consecutive-completion
intervals, 331 (27.0%) ran past `frequency_days` and 14.5% ran past 1.5x it. `get_pm_compliance_smrp`
counts every one of those as compliant.

HARVESTED (Engine B, on a genuine bag miss — the external corpus held 144 chunks and NOT ONE on
maintenance): PM compliance = completed / scheduled x 100, world-class 90%, and the metric
"does not account for late PMs".  substrate/external/external-pm-schedule-compliance-metric.md

WHAT THIS GATE DOES, AND DELIBERATELY DOES NOT DO. It does NOT change get_pm_compliance_smrp: that
RPC implements a NAMED standard (SMRP 2.1.1) and holds verified parity with analytics, so silently
redefining it would break a documented contract and move a number a plant acts on. Instead it
MEASURES the gap between what compliance claims and what on-time delivery actually was, and holds
that gap as a FORWARD-ONLY ratchet. The day the program drifts further from on-time, this fails —
before anyone reads a healthy percentage and relaxes.

Live-tier; SKIPS cleanly (exit 0) when the local DB is down. Self-test: --selftest.
"""
from __future__ import annotations
import io, json, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "pm_ontime_baseline.json"
DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c"]

# On-time = the gap to the PREVIOUS completion of the same scope item did not exceed its frequency.
# Interval-based on purpose: it needs no stored due-date history and cannot be gamed by a later
# reschedule, so it measures the delivery that actually happened.
ONTIME_SQL = """
WITH gaps AS (
  SELECT pc.scope_item_id, s.frequency_days, pc.completed_at,
         LAG(pc.completed_at) OVER (PARTITION BY pc.scope_item_id ORDER BY pc.completed_at) AS prev_at
  FROM public.pm_completions pc
  JOIN public.v_pm_scope_items_truth s ON s.scope_item_id = pc.scope_item_id
  WHERE pc.status = 'done'
)
SELECT
  count(*) FILTER (WHERE prev_at IS NOT NULL),
  count(*) FILTER (WHERE prev_at IS NOT NULL
                     AND completed_at <= prev_at + (frequency_days || ' days')::interval)
FROM gaps;
"""

# The same weighted figure the RPC reports, recomputed here so the two are compared like for like.
COMPLIANCE_SQL = """
WITH per_item AS (
  SELECT GREATEST(1, (90 / s.frequency_days)) AS scheduled,
         LEAST((SELECT count(*) FROM public.pm_completions pc
                 WHERE pc.scope_item_id = s.scope_item_id AND pc.status = 'done'
                   AND pc.completed_at >= now() - interval '90 days'),
               GREATEST(1, (90 / s.frequency_days))) AS completed
  FROM public.v_pm_scope_items_truth s
)
SELECT round(100.0 * sum(completed) / NULLIF(sum(scheduled), 0), 1) FROM per_item;
"""


# PARITY (added 2026-07-28, when the PM Scheduler card began SHOWING on-time beside compliance).
# The measure now has two readers — this validator and get_pm_ontime_delivery, which the page calls —
# so it must have exactly ONE definition. This recomputes the RPC's scope inline and asserts the two
# agree per hive. It is the logbook arc's LG2 disposition applied before the divergence exists rather
# than after: three ways of saying "corrective" agreed for months purely by luck of vocabulary.
PARITY_SQL = """
WITH gaps AS (
  SELECT pc.hive_id, pc.completed_at, s.frequency_days,
         LAG(pc.completed_at) OVER (PARTITION BY pc.scope_item_id ORDER BY pc.completed_at) AS prev_at
  FROM public.pm_completions pc
  JOIN public.v_pm_scope_items_truth s ON s.scope_item_id = pc.scope_item_id
  WHERE pc.status = 'done'
), inline AS (
  SELECT hive_id,
         count(*) FILTER (WHERE prev_at IS NOT NULL
                            AND completed_at >= now() - interval '90 days') AS total,
         count(*) FILTER (WHERE prev_at IS NOT NULL
                            AND completed_at >= now() - interval '90 days'
                            AND completed_at <= prev_at + (frequency_days || ' days')::interval) AS ontime
  FROM gaps GROUP BY hive_id
)
SELECT h.name,
       CASE WHEN i.total = 0 OR i.total IS NULL THEN NULL
            ELSE round(100.0 * i.ontime::numeric / i.total, 1) END AS inline_pct,
       (public.get_pm_ontime_delivery(h.id, 90)->>'ontime_pct')::numeric AS rpc_pct
FROM public.hives h LEFT JOIN inline i ON i.hive_id = h.id
ORDER BY h.name;
"""


# PM9 (PM deepwalk, 2026-07-28): a SKIPPED PM must credit nothing. Walked and proven in a
# rolled-back transaction — inserting a status='skipped' completion moved neither the hive's
# compliance (85.7 → 85.7) nor the item's next_due_date — so the numbers are honest today. That
# honesty rests entirely on three independent `status = 'done'` filters, any one of which could be
# dropped by a later edit, at which point declining to do a PM would start counting as doing it.
# Asserted here rather than left to luck, in the same spirit as the corrective-vocabulary parity
# ratchet: the invariant is cheap to state and expensive to rediscover.
SKIP_GUARDED = {
    "get_pm_compliance_smrp": "the compliance RPC — a skip would count as completed work",
    "get_pm_ontime_delivery": "the on-time RPC — a skip would count as an on-time interval",
    "v_pm_scope_items_truth": "the truth view's last_completed_at — a skip would push next_due_date "
                              "forward, so declining a PM would clear its own overdue flag",
}


# PM10 (PM deepwalk, 2026-07-28): the hive board's overdue count is ASSET-scoped on purpose — an
# asset is overdue if >=1 of its scope items is, so the tile matches the PM Scheduler it deep-links
# to (a deliberate 2026-06-09 disposition, documented at the derivation; counting items there once
# showed "9 overdue" against the scheduler's "6"). The COUNT was never the bug. The NOUN was: the
# tile said "PM tasks overdue", the nudge "29 PMs overdue", the CTA "Assign 29 overdue PMs". Measured
# in Lucena: 29 overdue ASSETS but 40 overdue scope items, so a supervisor reading "29 PMs" planned
# for 29 jobs against 40. Only the banner had the right noun. Same class as PMK1 — a label claiming
# something the number does not support — so it is asserted here.
_OVERDUE_NOUN_RE = re.compile(r"\$\{overdue\}[^`]{0,60}?PM\s*(?:task|s\b)", re.I)


def _check_briefing_counts_assets():
    """PM17: the AI proactive briefing must report the SAME canonical asset count as the tiles.

    It head-counted `v_pm_scope_items_truth` rows filtered `is_overdue` — which counts SCOPE ITEMS —
    and said "40 PM tasks overdue" where every screen said 29 assets. agentic-rag-loop already had
    it right (DISTINCT pm_asset_id, with a "Matches the tiles" comment); ai-gateway was the outlier.
    The companion is the surface a user can least verify, so it is the worst place to hold the
    minority definition.
    """
    fn = ROOT / "supabase" / "functions" / "ai-gateway" / "index.ts"
    if not fn.exists():
        return []
    src = fn.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'from\("v_pm_scope_items_truth"\)\.select\(([^)]*)\)[^;\n]*is_overdue', src)
    if not m:
        return []
    if "count:" in m.group(1) or '"*"' in m.group(1):
        return ["ai-gateway/index.ts head-counts v_pm_scope_items_truth rows for the proactive "
                "briefing — that counts SCOPE ITEMS, while the tiles, the PM Scheduler card and "
                "agentic-rag-loop all report DISTINCT pm_asset_id. The briefing would quote a "
                "number no screen the user can check agrees with."]
    return []


# PMK2 (PM deepwalk, 2026-07-28): the schedule DENOMINATOR is an approximation.
# get_pm_compliance_smrp charges GREATEST(1, period/frequency_days) scheduled events, so inside a
# 90-day window a Semi-annual item counts as 1 when it is truly due 0.5 times and an Annual as 1
# against a true 0.25. Measured: 122 of 416 scope items (29%) are structurally over-counted.
#
# NOT "compliance is wrong", and not a redefinition either — the same disposition as PMK1 and the
# logbook arc's LG2: the approximation is defensible (you cannot do half a PM, and SMRP counts
# scheduled EVENTS), so allow it and make divergence DETECTABLE. Measured today the two agree to
# 0.17 points (86.3 as-implemented vs 86.2 fractional), because those long-period items happen to
# carry completions in the window. That is luck of the data, exactly like the 'corrective' vocabulary
# agreeing by luck. This holds the flattery as a FORWARD-ONLY ceiling, so the day the data shifts and
# the approximation starts materially inflating the headline, the build fails first.
DENOMINATOR_SQL = """
WITH per_item AS (
  SELECT GREATEST(1, (90 / s.frequency_days))  AS sched_impl,
         (90.0 / s.frequency_days)             AS sched_true,
         LEAST((SELECT count(*) FROM public.pm_completions pc
                 WHERE pc.scope_item_id = s.scope_item_id AND pc.status = 'done'
                   AND pc.completed_at >= now() - interval '90 days'),
               GREATEST(1, (90 / s.frequency_days))) AS done_impl
  FROM public.v_pm_scope_items_truth s
)
SELECT round(100.0 * sum(done_impl) / NULLIF(sum(sched_impl), 0), 2),
       round(100.0 * sum(LEAST(done_impl, sched_true)) / NULLIF(sum(sched_true), 0), 2),
       count(*) FILTER (WHERE sched_true < 1),
       count(*)
FROM per_item;
"""


def check_denominator_flattery():
    """[] when the scheduled-count approximation flatters no more than its accepted ceiling."""
    out = psql(DENOMINATOR_SQL)
    if out is None:
        return None
    try:
        impl, true_, over, total = out.splitlines()[0].split("|")
        gap = round(float(impl) - float(true_), 2)
    except (ValueError, IndexError):
        return None
    base = _baseline().get("denominator_gap")
    if base is None:
        return []          # not yet accepted; --accept records it
    if gap > base + 0.05:
        return [f"the scheduled-count approximation now flatters compliance by {gap} points "
                f"(was {base}): {over} of {total} scope items are charged a whole scheduled event "
                f"for a period longer than the window. The headline is drifting above what the "
                f"program is actually due to deliver."]
    return []


def check_overdue_noun_scope():
    bad = _check_briefing_counts_assets()
    hive = ROOT / "hive.html"
    if not hive.exists():
        return bad
    src = hive.read_text(encoding="utf-8", errors="replace")
    for m in _OVERDUE_NOUN_RE.finditer(src):
        frag = m.group(0)
        # "asset(s) ... have overdue PMs" is the CORRECT shape — the noun being counted is asset.
        if re.search(r"\$\{overdue\}[^`]{0,40}asset", frag, re.I):
            continue
        line = src[:m.start()].count("\n") + 1
        bad.append(f"hive.html:{line} counts ASSETS but labels them PMs: {frag.strip()[:70]!r} — "
                   f"the hive has more overdue scope items than overdue assets, so this under-states "
                   f"the work a supervisor is planning for")
    return bad


def check_skip_credits_nothing():
    problems = []
    for obj, why in SKIP_GUARDED.items():
        if obj.startswith("v_"):
            ddl = psql(f"SELECT pg_get_viewdef('public.{obj}'::regclass, true);")
        else:
            ddl = psql("SELECT pg_get_functiondef(p.oid) FROM pg_proc p "
                       "JOIN pg_namespace n ON n.oid=p.pronamespace "
                       f"WHERE n.nspname='public' AND p.proname='{obj}' LIMIT 1;")
        if ddl is None:
            return None  # DB down -> caller skips
        if not re.search(r"status\s*=\s*'done'", ddl):
            problems.append(f"{obj} no longer filters status = 'done' — {why}")
    return problems


def check_parity():
    """[] when the RPC and an independent inline computation agree for every hive."""
    out = psql(PARITY_SQL)
    if out is None:
        return None  # DB down; the caller already skips
    bad = []
    for ln in out.splitlines():
        if "|" not in ln:
            continue
        name, inline_pct, rpc_pct = (c.strip() for c in ln.split("|")[:3])
        if inline_pct != rpc_pct:
            bad.append(f"{name}: inline {inline_pct or 'NULL'} vs get_pm_ontime_delivery "
                       f"{rpc_pct or 'NULL'} — the page and this gate would show different numbers")
    return bad


def psql(sql):
    try:
        r = subprocess.run(DOCKER_DB + [sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return None if r.returncode != 0 else (r.stdout or "").strip()
    except Exception:
        return None


def analyze():
    ot = psql(ONTIME_SQL)
    if ot is None:
        return {"skipped": True, "reason": "local DB unreachable (docker supabase_db_workhive)"}
    try:
        total, ontime = (int(x) for x in ot.splitlines()[0].split("|")[:2])
    except (ValueError, IndexError):
        return {"skipped": True, "reason": f"unparseable on-time counts: {ot[:80]!r}"}
    if total == 0:
        return {"skipped": True, "reason": "no completion intervals yet (a fresh PM program)"}

    comp_raw = psql(COMPLIANCE_SQL)
    try:
        compliance = float((comp_raw or "").splitlines()[0].strip())
    except (ValueError, IndexError):
        compliance = None

    ontime_pct = round(100.0 * ontime / total, 1)
    gap = round(compliance - ontime_pct, 1) if compliance is not None else None
    return {"skipped": False, "intervals": total, "ontime": ontime,
            "ontime_pct": ontime_pct, "compliance_pct": compliance, "gap": gap}


def _baseline():
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def run_selftest():
    problems = []
    for frag in ("LAG(", "frequency_days", "status = 'done'"):
        if frag not in ONTIME_SQL:
            problems.append(f"ONTIME_SQL must use {frag!r} — otherwise it is not measuring lateness "
                            f"against each item's own schedule and would false-PASS")
    if "GREATEST(1," not in COMPLIANCE_SQL:
        problems.append("COMPLIANCE_SQL must mirror the RPC's scheduled-count, or the two figures "
                        "are not comparable")
    if "get_pm_ontime_delivery" not in PARITY_SQL:
        problems.append("PARITY_SQL must call the RPC the page reads, or it is not proving the page "
                        "and this gate share one definition")
    live = analyze()
    if not live.get("skipped"):
        base = _baseline()
        if base.get("gap") is not None and live["gap"] is not None and live["gap"] > base["gap"] + 0.05:
            problems.append(f"gap widened {base['gap']} -> {live['gap']} (forward-only ratchet)")
        drift = check_parity()
        if drift:
            problems.extend(drift)
        skip = check_skip_credits_nothing()
        if skip:
            problems.extend(skip)
        denom = check_denominator_flattery()
        if denom:
            problems.extend(denom)
    problems.extend(check_overdue_noun_scope())
    return problems


def main():
    as_json = "--json" in sys.argv
    if "--selftest" in sys.argv:
        probs = run_selftest()
        print(json.dumps({"selftest_problems": probs}, indent=2) if as_json
              else ("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs)))
        return 1 if probs else 0

    res = analyze()
    if as_json:
        print(json.dumps(res, indent=2))
        return 0

    print("PMK1 on-time vs compliance (a PM done LATE still counts as compliant)")
    if res.get("skipped"):
        print(f"  SKIP -- {res['reason']}")
        return 0

    base = _baseline()
    print(f"  compliance (SMRP 2.1.1) : {res['compliance_pct']}%   <- what the page shows")
    print(f"  on-time delivery        : {res['ontime_pct']}%   ({res['ontime']}/{res['intervals']} intervals)")
    print(f"  the gap                 : {res['gap']} points")

    # A RATCHET must stay re-baselineable. Running --accept behind the checks meant that once
    # the ceiling was exceeded the accept path was unreachable, so the only way to re-accept a
    # deliberately-changed baseline was to hand-edit the json. Accept is an explicit operator
    # action; it runs before any check can short-circuit.

    if "--accept" in sys.argv:
        _dn = psql(DENOMINATOR_SQL)
        _dgap = None
        if _dn:
            try:
                _i, _t = _dn.splitlines()[0].split("|")[:2]
                _dgap = round(float(_i) - float(_t), 2)
            except (ValueError, IndexError):
                _dgap = None
        BASELINE_PATH.write_text(json.dumps(
            {"gap": res["gap"], "ontime_pct": res["ontime_pct"],
             "compliance_pct": res["compliance_pct"],
             "denominator_gap": _dgap,
             "_note": "forward-only ceiling on how far compliance may flatter on-time delivery"},
            indent=2), encoding="utf-8")
        print(f"  ACCEPTED  baseline gap -> {res['gap']} points")
        return 0

    denom = check_denominator_flattery()
    if denom:
        print("  FAIL: the scheduled-count approximation is flattering the headline —")
        for d_ in denom:
            print(f"        {d_}")
        return 1
    if denom is not None:
        print("  PASS: the scheduled-count approximation flatters within its accepted ceiling")

    noun = check_overdue_noun_scope()
    if noun:
        print("  FAIL: an ASSET count is labelled as PMs —")
        for n_ in noun:
            print(f"        {n_}")
        return 1
    print("  PASS: the hive board's asset-scoped overdue count is labelled as assets everywhere")

    skip = check_skip_credits_nothing()
    if skip:
        print("  FAIL: a SKIPPED PM would now credit the program —")
        for s_ in skip:
            print(f"        {s_}")
        return 1
    if skip is not None:
        print("  PASS: a skipped PM credits no compliance, no on-time interval, and does not move "
              "next_due_date")

    drift = check_parity()
    if drift:
        print("  FAIL: the on-time measure has drifted into two different answers —")
        for d in drift:
            print(f"        {d}")
        return 1
    if drift is not None:
        print("  PASS: get_pm_ontime_delivery (what the card shows) matches an independent "
              "recomputation, every hive")


    if base.get("gap") is None:
        print("  NOTE: no baseline yet — run with --accept to set the forward-only ceiling.")
        return 0
    if res["gap"] is not None and res["gap"] > base["gap"] + 0.05:
        print(f"  FAIL: the gap WIDENED {base['gap']} -> {res['gap']} points. Compliance is "
              f"flattering the program more than it did: PMs are being completed later while the "
              f"headline percentage holds up. A supervisor reading {res['compliance_pct']}% against "
              f"the 90% world-class benchmark would not see it.")
        return 1
    print(f"  PASS: gap {res['gap']} <= baseline {base['gap']} points")
    return 0


if __name__ == "__main__":
    sys.exit(main())
