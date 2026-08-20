#!/usr/bin/env python3
"""Gate milestone ledger — record WHEN the platform gate suite crossed 80% / 90% / 95% / 100% green,
and make those crossings forward-only so a later run cannot re-claim a milestone by shrinking the set.

WHY THIS EXISTS (Ian, 2026-08-17): "can we just save for all the platform gates if we achieve
considerable percentage green, like 80% of green, and 100% green". `platform_baseline.json` is only
written when EVERYTHING passes, so the whole road up to that point is unrecorded — there is no way to
say when the suite reached 80%, or to notice it slipping back under. This is that record.

★THE DENOMINATOR IS THE ENTIRE PROBLEM, AND IT IS NOT THEORETICAL HERE.
The current run reads pass 572 · fail 8 · warn 0 · skip 158 over 738 registered gates. That is:

    77.5%   if skips count against you   (572 / 738)
    98.6%   if skips are excluded        (572 / 580)

Two defensible-sounding percentages, twenty-one points apart, from ONE run — and 158 skipped gates is
21% of the suite. A milestone claimed on the lenient number would be a claim about the gates that
happened to run, dressed as a claim about the platform. Worse, the lenient number IMPROVES when a gate
starts skipping (DB down, tool missing, no baseline yet): the suite gets quieter and the score goes up.
So:

  - The MILESTONE is claimed on the STRICT denominator: pass / total_registered. A skip is not a pass.
  - The lenient number is recorded beside it, labelled, because it is genuinely useful for "of the
    gates that could run, how many are green" — it is just not what "80% green" may ever mean.
  - Every milestone stores `total_registered`, and a new milestone is REFUSED if the registry shrank
    since the last one. Deleting gates until the fraction looks good is the one way to fake this, and
    it is the way that has actually happened on this platform before
    ([[feedback_short_denominator_is_a_false_100]], [[feedback_four_exclusions_shrank_the_denominator]],
    [[feedback_coverage_improved_by_deleting_obligations]]).
  - Skips are ENUMERATED, never averaged away ([[feedback_a_skipped_partition_reads_as_a_covered_one]]).
    A milestone that hides which 158 gates did not run is a milestone nobody can audit.

FORWARD-ONLY, BOTH AXES. `--check` fails when the strict percentage falls below the highest milestone
already earned, AND when total_registered falls below the level that milestone was earned at. The
second is the one that matters: without it, dropping 100 gates would RAISE the percentage and the
ratchet would applaud.

This reads `platform_health.json`, which `run_platform_checks.py` already writes. It never re-runs the
suite — the suite takes ~36 minutes and re-running it to compute a percentage it just printed is pure
waste.

Usage:
    python tools/gate_milestone_ledger.py              # standing vs milestones (reads, writes nothing)
    python tools/gate_milestone_ledger.py --record     # record a newly-reached milestone
    python tools/gate_milestone_ledger.py --check      # CI: fail on regression below an earned milestone
    python tools/gate_milestone_ledger.py --selftest   # teeth, no files touched
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEALTH_FILE = os.path.join(ROOT, "platform_health.json")
LEDGER_FILE = os.path.join(ROOT, "gate_milestone_ledger.json")

# The rungs. 100 is the target; the rest exist so the climb is recorded rather than only its summit.
MILESTONES = [80, 90, 95, 100]

GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def _bank_pct():
    """The page test bank's green share, on the same denominator the bank gate uses (green / green+owed,
    stale excluded so drift shows rather than being absorbed). Returns None if the banks are absent —
    an unavailable figure is recorded as unknown, never as zero."""
    import glob
    g = o = 0
    for f in glob.glob(os.path.join(ROOT, "banks", "*_live_mcp_bank.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                for r in (json.load(fh).get("scenarios") or []):
                    st = r.get("status")
                    g += st == "green"
                    o += st == "owed"
        except Exception:
            continue
    return round(100.0 * g / (g + o), 2) if (g + o) else None


def _git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()[:12] or "unknown"
    except Exception:
        return "unknown"


def read_health(path=HEALTH_FILE):
    """Pull the counts out of platform_health.json, and derive the registry size from the summary
    rather than from len(validators): the two can disagree (a validator may appear more than once, or
    a run may be partial), and the count the percentage is claimed on must be the one that was
    actually tallied."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        h = json.load(f)
    s = h.get("summary") or {}
    p, fl = int(s.get("pass", 0)), int(s.get("fail", 0))
    w, sk = int(s.get("warn", 0)), int(s.get("skip", 0))
    total = p + fl + w + sk
    return {
        "timestamp": h.get("timestamp"),
        "mode": h.get("mode"),
        "overall": h.get("overall"),
        "passed": p, "failed": fl, "warned": w, "skipped": sk,
        "total_registered": total,
        # STRICT: a skip is not a pass. This is the number a milestone is claimed on.
        "pct_strict": round(100.0 * p / total, 2) if total else 0.0,
        # LENIENT: of the gates that could run. Recorded, labelled, never the milestone.
        "pct_of_ran": round(100.0 * p / (p + fl + w), 2) if (p + fl + w) else 0.0,
        "validators": h.get("validators") or [],
    }


def _non_green(health):
    """The gates that are not green, named. A milestone whose shortfall is anonymous cannot be worked."""
    failing, skipping = [], []
    for v in health.get("validators") or []:
        if not isinstance(v, dict):
            continue
        st = str(v.get("status", "")).upper()
        name = v.get("id") or v.get("name") or v.get("script") or "?"
        if st in ("FAIL", "ERROR"):
            failing.append(name)
        elif st == "SKIP":
            skipping.append({"gate": name, "reason": (v.get("detail") or v.get("reason") or "")[:160]})
    return failing, skipping


def load_ledger():
    if not os.path.exists(LEDGER_FILE):
        return {"milestones": [], "highest": 0, "highest_total_registered": 0}
    with open(LEDGER_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_ledger(led):
    # Atomic: a truncated ledger is a lost record of work that genuinely happened
    # ([[feedback_open_w_truncates_before_write_use_atomic]]).
    tmp = LEDGER_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(led, f, indent=1, ensure_ascii=False)
    os.replace(tmp, LEDGER_FILE)


def earned(pct):
    """The highest rung this percentage clears."""
    got = 0
    for m in MILESTONES:
        if pct >= m:
            got = m
    return got


def cmd_record(health, led, quiet=False):
    # ★A FAST RUN MAY NOT CLAIM A MILESTONE, AND THIS IS NOT A TECHNICALITY.
    # The live health file reads mode=fast with 158 skips, every one at elapsed=0 — they are
    # `skip_if_fast` gates that were deliberately never attempted. Counting them as not-green
    # understates the platform (they were not asked), and excluding them overstates it (some would
    # genuinely fail). Neither number is a fact about the platform; both are facts about the MODE.
    # So a milestone is recordable only from a FULL run, where a skip means something real — the DB
    # was down, a tool was missing, a baseline did not exist yet — and is therefore worth naming.
    if str(health.get("mode", "")).lower() == "fast":
        if not quiet:
            print(f"  {YEL}NOT RECORDABLE{RST} — this run was mode=fast, which skipped "
                  f"{health['skipped']} gates without attempting them (all at elapsed=0). A milestone "
                  f"from a fast run would be a claim about the mode, not the platform. Re-run "
                  f"run_platform_checks.py WITHOUT --fast, then record.")
        return 0
    pct, total = health["pct_strict"], health["total_registered"]
    rung = earned(pct)
    prev_rung = int(led.get("highest", 0))
    prev_total = int(led.get("highest_total_registered", 0))

    if rung == 0:
        if not quiet:
            print(f"  {DIM}no milestone reached yet — {pct}% strict, first rung is {MILESTONES[0]}%{RST}")
        return 0
    if rung <= prev_rung:
        if not quiet:
            print(f"  {DIM}already at {prev_rung}% — this run earns {rung}%, nothing new to record{RST}")
        return 0
    # THE SHRINKING-DENOMINATOR REFUSAL. A higher percentage over a SMALLER registry is not progress,
    # and recording it would launder a deletion into an achievement.
    if prev_total and total < prev_total:
        print(f"  {RED}REFUSED{RST} — {rung}% is over {total} gates but the {prev_rung}% milestone was "
              f"earned over {prev_total}. The suite SHRANK by {prev_total - total}; a rising percentage "
              f"over a falling denominator is not an improvement. Restore the gates or explain the "
              f"removal, then re-record.")
        return 1

    failing, skipping = _non_green(health)
    entry = {
        "milestone_pct": rung,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "run_timestamp": health.get("timestamp"),
        "run_mode": health.get("mode"),
        "pct_strict": pct,
        "pct_of_ran": health["pct_of_ran"],
        "passed": health["passed"], "failed": health["failed"],
        "warned": health["warned"], "skipped": health["skipped"],
        "total_registered": total,
        # WHY THIS RUN HAPPENED. Ian's cadence (2026-08-17): drive the page test bank from owed to
        # green, and run the platform gates at the 80% and 100% bank milestones — not continuously,
        # because a 36-minute suite re-run between edits buys nothing and costs real money. Stamping
        # the bank figure onto the gate milestone is what lets a later reader see WHICH bank state a
        # given gate run was validating, instead of two unrelated percentages in two files.
        "bank_green_pct_at_run": _bank_pct(),
        # Named, not counted. This is what makes the milestone auditable a year from now.
        "failing_gates": failing,
        "skipped_gates": skipping,
    }
    led.setdefault("milestones", []).append(entry)
    led["highest"] = rung
    led["highest_total_registered"] = total
    save_ledger(led)
    print(f"  {GREEN}RECORDED{RST} milestone {GREEN}{rung}%{RST} — {health['passed']}/{total} gates green "
          f"(strict), {health['pct_of_ran']}% of the {health['passed'] + health['failed'] + health['warned']} "
          f"that ran. {len(failing)} failing, {len(skipping)} skipped, both named in {os.path.basename(LEDGER_FILE)}.")
    return 0


def cmd_check(health, led):
    rung = int(led.get("highest", 0))
    if not rung:
        print(f"  {DIM}no milestone earned yet — nothing to hold{RST}")
        return 0
    pct, total = health["pct_strict"], health["total_registered"]
    prev_total = int(led.get("highest_total_registered", 0))
    bad = []
    if pct < rung:
        bad.append(f"strict green fell to {pct}% — below the earned {rung}% milestone")
    if prev_total and total < prev_total:
        bad.append(f"the registry shrank {prev_total} -> {total} gates; the {rung}% milestone was "
                   f"earned over the larger set, so the current percentage is not comparable")
    if bad:
        print(f"  {RED}FAIL{RST} — milestone regression:")
        for b in bad:
            print(f"    · {b}")
        return 1
    print(f"  {GREEN}PASS{RST} — holding {rung}% (now {pct}% strict over {total} gates)")
    return 0


def cmd_report(health, led):
    pct = health["pct_strict"]
    rung, held = earned(pct), int(led.get("highest", 0))
    print(f"\n  {DIM}from {os.path.basename(HEALTH_FILE)} · run {health.get('timestamp')} "
          f"· mode {health.get('mode')}{RST}")
    print(f"  gates: {GREEN}{health['passed']} pass{RST} · {RED}{health['failed']} fail{RST} · "
          f"{health['warned']} warn · {YEL}{health['skipped']} skip{RST} "
          f"= {health['total_registered']} registered")
    print(f"  {'STRICT  (pass / all registered)':38} {pct:6.2f}%   <- milestones are claimed on this")
    print(f"  {DIM}{'of-those-that-ran (skips excluded)':38} {health['pct_of_ran']:6.2f}%   "
          f"informational only{RST}")
    if health["skipped"]:
        print(f"  {DIM}the {health['skipped']} skipped gates are {health['skipped'] * 100.0 / health['total_registered']:.1f}% "
              f"of the suite — excluding them would move the headline by "
              f"{health['pct_of_ran'] - pct:+.1f} points{RST}")
    print()
    for m in MILESTONES:
        if held >= m:
            e = next((x for x in led.get("milestones", []) if x["milestone_pct"] == m), None)
            when = (e or {}).get("recorded_at", "")[:10]
            print(f"    {GREEN}[x] {m}%{RST}  earned {when} over {(e or {}).get('total_registered','?')} gates")
        elif pct >= m:
            print(f"    {YEL}[!] {m}%{RST}  reached but NOT recorded — run --record")
        else:
            need = int((m / 100.0) * health["total_registered"]) - health["passed"]
            print(f"    {DIM}[ ] {m}%   {need} more gate(s) to go{RST}")
    print()
    return 0


def selftest():
    """Teeth. The refusals are the point, so both of them must be proven to fire."""
    fails = 0

    def H(p, f, w, s):
        t = p + f + w + s
        return {"passed": p, "failed": f, "warned": w, "skipped": s, "total_registered": t,
                "pct_strict": round(100.0 * p / t, 2), "pct_of_ran": round(100.0 * p / (p + f + w), 2),
                "validators": [], "timestamp": "t", "mode": "test"}

    # 1. strict vs lenient genuinely differ — the whole reason this file exists
    h = H(572, 8, 0, 158)
    if not (h["pct_strict"] < 80 <= h["pct_of_ran"]):
        print("  FAIL — the real run's two denominators should straddle 80%"); fails += 1
    else:
        print(f"  ok — strict {h['pct_strict']}% vs of-ran {h['pct_of_ran']}%: a milestone on the "
              f"lenient number would claim 80% while 158 gates never ran")

    # 2. a skip must not read as a pass
    if earned(H(600, 0, 0, 138)["pct_strict"]) != 80 or earned(H(600, 0, 0, 138)["pct_of_ran"]) != 100:
        print("  FAIL — skip accounting wrong"); fails += 1
    else:
        print("  ok — 600 pass / 138 skip earns 80% strict, not the 100% the lenient view would give")

    # 3. shrinking denominator is REFUSED
    led = {"milestones": [{"milestone_pct": 80}], "highest": 80, "highest_total_registered": 738}
    rc = cmd_record(H(500, 0, 0, 20), dict(led), quiet=True)   # 96% but over 520 gates
    if rc != 1:
        print("  FAIL — a higher % over a SHRUNKEN registry was accepted"); fails += 1
    else:
        print("  ok — 96% over 520 gates REFUSED against an 80% earned over 738")

    # 4. regression below an earned rung fails --check
    if cmd_check(H(500, 100, 0, 138), led) != 1:
        print("  FAIL — a fall below the earned milestone passed --check"); fails += 1
    else:
        print("  ok — falling under an earned milestone fails --check")

    # 5. holding steady passes
    if cmd_check(H(600, 0, 0, 138), led) != 0:
        print("  FAIL — holding the milestone was reported as a regression"); fails += 1
    else:
        print("  ok — holding at or above the earned rung passes")

    print("\n  SELFTEST FAILED" if fails else
          "\n  SELFTEST PASSED — strict/lenient separated, skips not credited, and BOTH refusals fire "
          "(shrunken denominator, and regression below an earned rung)")
    return 1 if fails else 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()

    health = read_health()
    if health is None:
        print(f"  {YEL}SKIP{RST} — no {os.path.basename(HEALTH_FILE)} yet; run run_platform_checks.py first")
        return 0
    led = load_ledger()
    if a.record:
        return cmd_record(health, led)
    if a.check:
        return cmd_check(health, led)
    return cmd_report(health, led)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
