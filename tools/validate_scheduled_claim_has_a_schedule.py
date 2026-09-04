#!/usr/bin/env python3
"""scheduled-claim-has-a-schedule - T63/T66: don't promise a cadence nothing runs on.

A page that tells a buyer something happens "daily" or "monthly" is making a claim about a
SCHEDULER, and cron.job is the oracle that settles it. This one is settled against the live
database, not against prose.

FOUND 2026-08-26 on integrations.html: "New SAP work orders then flow in daily" and "WorkHive polls
your CMMS API daily". Measured: 26 cron jobs, not one touching cmms-sync, which runs only when a
person presses Sync now. Worse than copy - the Sync Schedule control DEFAULTED to "Daily", saved
sync_freq, and plant-connections rendered that value in its status table: three surfaces agreeing
on a cadence nothing runs, and nothing anywhere reads sync_freq.

★WHAT WAS REAL STAYED: the webhook address in that tab, which a customer's CMMS can post to as work
orders are raised, and the push back, which cmms-push-completion fires as each job is closed. The
fix was to say those two things and stop promising the poll - not to weaken a true claim.

★AND THEN THE SAME DEFECT ON A SECOND PAGE, which is why the scope moved. ph-intelligence.html
claimed a monthly rhythm in EIGHT places - "Published monthly", "refreshes monthly", "Reports are
generated monthly", and worst, "next monthly refresh due soon", a promise about a future event
nothing would deliver - with no cron touching intelligence-report either. Scoping a gate to where a
bug was NOTICED rather than where the CLASS lives is the failure this session kept finding in other
people's checks; leaving it pointed at one page would have been the same mistake with my name on it.

★AND A SAMPLE IS NOT A CENSUS. The first pass on ph-intelligence read a slice of visible text,
caught four claims, and declared it done; a grep for the actual word found four more. Count the
term across the artifact before believing a page is clean.

★SCOPED, STILL. It checks pages whose cadence promise is a purchasing or trust input, each against
the cron vocabulary that could legitimately back it. A blanket "any page saying daily" sweep would
drown in true claims (the 6am brief IS cron-backed by amc-brief-0600pht) and get switched off.

★SKIPS WITHOUT ITS ORACLE. No database, no cron table, so SKIP - never PASS.

Usage: python tools/validate_scheduled_claim_has_a_schedule.py
"""
import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# page -> the cron vocabulary that could legitimately back its promise
PAGES = {
    "integrations.html": r"cmms|integration|external[_-]?sync",
    "ph-intelligence.html": r"intelligence|ph[_-]?intel|benchmark",
}

# a cadence promise: an automatic rhythm, not "run one whenever you like"
CADENCE = re.compile(
    r"\b(?:flow(?:s)?\s+in|sync(?:s|ed|ing)?|arrive(?:s)?|import(?:s|ed)?|pull(?:s|ed)?"
    r"|update(?:s|d)?|publish(?:ed|es)?|refresh(?:es|ed)?|generate(?:s|d)?|unlock(?:s)?)\b"
    r"[^.<>]{0,60}?\b(daily|nightly|hourly|weekly|monthly"
    r"|every\s+(?:hour|day|night|morning|week|month)"
    r"|each\s+(?:day|night|morning|week|month))\b",
    re.I)

# A sentence that DENIES the cadence is not a claim of it. Without this the gate charges a page for
# saying "nothing regenerates it automatically" - the most honest sentence it could carry.
DENIAL = re.compile(r"\bnot (?:yet )?(?:available|scheduled|running|enabled|live|automatic\w*)\b"
                    r"|\bnothing regenerates\b|\bcoming soon\b|\bnot yet\b|\bcan be generated\b", re.I)


def visible_text(html: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    # ★A SELECT OFFERS A CHOICE; IT DOES NOT PROMISE THE CHOICE RUNS. An earlier version flattened
    # option labels into the prose and flagged "Sync Schedule ... Daily" - and flagged its own fix,
    # since the honest label reads "Daily (scheduled sync not available yet)".
    s = re.sub(r"<select\b.*?</select>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s)


def cron_rows():
    try:
        r = subprocess.run(
            ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             # ★ONE LINE PER JOB. Selecting `command` raw turned a 26-job table into "51 total",
             # because a multi-line command became several lines. A gate that miscounts what it
             # measures cannot be trusted about what it judges, even when the verdict survives.
             "-t", "-A", "-c",
             "SELECT jobname || ' :: ' || replace(replace(command, chr(10), ' '), chr(13), ' ') "
             "FROM cron.job;"],
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return None
        return [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
    except (OSError, subprocess.SubprocessError):
        return None


def main() -> int:
    jobs = cron_rows()
    if jobs is None:
        print("SKIP scheduled-claim-has-a-schedule - database unreachable, and cron.job IS the oracle")
        return 0

    checked, failures = 0, []
    for name, backer in PAGES.items():
        page = ROOT / name
        if not page.exists():
            continue
        checked += 1
        text = visible_text(page.read_text(encoding="utf-8", errors="replace"))
        claims = []
        for m in CADENCE.finditer(text):
            lo, hi = max(0, m.start() - 140), min(len(text), m.end() + 140)
            if DENIAL.search(text[lo:hi]):
                continue
            claims.append(m.group(0).strip())
        backers = [j for j in jobs if re.search(backer, j, re.I)]
        print(f"  {name:24} claims: {len(claims):2} | cron jobs that could back them: {len(backers)}")
        for c in claims[:4]:
            print(f"      \"{c[:90]}\"")
        if claims and not backers:
            failures.append((name, len(claims)))

    if not checked:
        print("SKIP scheduled-claim-has-a-schedule - none of the checked pages are present")
        return 0
    if failures:
        print(f"FAIL scheduled-claim-has-a-schedule - {len(failures)} page(s) promise a cadence and nothing")
        print("    runs on it:")
        for name, n in failures:
            print(f"      - {name}: {n} unbacked claim(s)")
        print("    A reader takes \"daily\" or \"monthly\" as a scheduler. There is none, so it happens when")
        print("    someone remembers to press a button. Say what is true, or add the schedule.")
        return 1
    print(f"PASS scheduled-claim-has-a-schedule - {checked} page(s) checked against {len(jobs)} cron jobs; "
          "no unbacked cadence promise.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
