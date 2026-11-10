#!/usr/bin/env python3
"""validate_schedule_claims_match_cron.py - a page may only say a job runs on a schedule if a cron job schedules it.

★WHAT WAS FALSE (2026-11-10, found rewriting the autonomous-shift-planning guide). Migration 20260610000005 retired the
three shift-handover cron jobs: Ian's compute rule moved Shift Brain to "first open of a planless shift builds the plan;
NO scheduled jobs". Five months later the copy still described the cron: the learn guide said seven times that Shift
Brain "runs on a cron schedule at 06:00, 14:00 and 22:00 PHT" (and drew "Schedule cron job" as step 1 of its figure);
shift-brain.html told a worker "the automatic schedule runs at 06:00, 14:00, and 22:00 PHT once enabled" and a
supervisor "the shift planner runs on the hour"; the AI assistant's hint said "Briefings auto-generate at 06:00, 14:00,
and 22:00 PHT". Nothing runs any of it on a clock.

Each CLAIM below names a subject, the scheduled-run wording, and the edge function a cron job would have to call for the
wording to be true. The scheduler is read from cron.job (the live database) when the stack is up, else replayed from the
migrations' cron.schedule / cron.unschedule history - newest action per job wins.

    python tools/validate_schedule_claims_match_cron.py
    python tools/validate_schedule_claims_match_cron.py --self-test
"""
from __future__ import annotations

import glob
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = ("tools/", "tests/", "test-data-seeder/", "_fixtures/", "node_modules/", ".claude/", "supabase/")

CLAIMS = [
    {
        "name": "Shift Brain runs on a schedule",
        # the SHIFT brief, never the AMC daily brief - amc-orchestrator really is on a 06:00 PHT cron
        "subject": re.compile(r"shift brain|shift planner|shift[- ]plan|shift'?s brief|briefs? per shift|no briefing yet", re.I),
        "except": re.compile(r"\bAMC\b|amc-orchestrator", re.I),
        "wording": re.compile(r"cron schedule|runs? on (?:a|the) (?:schedule|hour)|automatic schedule|auto-?generate[sd]? at \d|"
                              r"(?:runs?|generat\w+)[^.<]{0,40}\bat 06:00|three briefs a day|on a fixed cadence|"
                              r"\bpg_cron\b|triggered by (?:a )?cron|at each shift change \(\d", re.I),
        "needs_function": "shift-planner-orchestrator",
    },
]


def _scheduled_functions_live() -> set[str] | None:
    if not shutil.which("docker"):
        return None
    try:
        r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tAq",
                            "-c", "select command from cron.job"], capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return None
        return set(re.findall(r"functions/v1/([\w-]+)|'([\w-]+)',\s*net\.http_post", r.stdout or "")) and \
            {a or b for a, b in re.findall(r"functions/v1/([\w-]+)|note_scheduled_call\('[^']*',\s*'([\w-]+)'", r.stdout or "")}
    except Exception:
        return None


def _scheduled_functions_from_migrations() -> set[str]:
    jobs: dict[str, str | None] = {}
    for f in sorted(glob.glob(str(ROOT / "supabase" / "migrations" / "*.sql"))):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"cron\.(schedule|unschedule)\(\s*'([^']+)'([\s\S]{0,900}?)\)\s*;", src):
            kind, job, rest = m.group(1), m.group(2), m.group(3)
            if kind == "unschedule":
                jobs[job] = None
            else:
                fn = re.search(r"functions/v1/([\w-]+)|note_scheduled_call\('[^']*',\s*'([\w-]+)'", rest)
                jobs[job] = (fn.group(1) or fn.group(2)) if fn else "?"
    return {fn for fn in jobs.values() if fn}


def scheduled_functions() -> tuple[set[str], str]:
    live = _scheduled_functions_live()
    if live is not None:
        return live, "cron.job (live)"
    return _scheduled_functions_from_migrations(), "migrations"


def _strip_comments(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", " ", src)
    return "\n".join("" if re.match(r"\s*(//|\*|/\*|#)", ln) else ln for ln in src.splitlines())


def check_text(src: str, scheduled: set[str]) -> list[str]:
    out = []
    body = _strip_comments(src)
    for c in CLAIMS:
        if c["needs_function"] in scheduled:
            continue
        for m in c["wording"].finditer(body):
            win = body[max(0, m.start() - 220):m.end() + 60]
            near = body[max(0, m.start() - 120):m.end() + 40]
            if c.get("except") and c["except"].search(near):
                continue
            if c["subject"].search(win):
                out.append(f"{c['name']}, but no cron job calls {c['needs_function']}: "
                           + repr(body[max(0, m.start() - 70):m.end() + 30].replace("\n", " ")))
    return out


def shipped() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.html", "*.js", "*.md"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    keep = []
    for p in out:
        if p.startswith(SKIP_DIRS) or "survey_ufai_rubric" in p:
            continue
        if p.endswith(".md") and not p.endswith(".html.md"):
            continue                              # only the published markdown twins, not repo docs
        keep.append(ROOT / p)
    return keep


def _self_test() -> int:
    fails = []
    stale = "Shift Brain runs on a cron schedule at 06:00, 14:00 and 22:00 PHT."
    if not check_text(stale, set()):
        fails.append("the retired schedule must fail when nothing schedules the planner")
    if check_text(stale, {"shift-planner-orchestrator"}):
        fails.append("the same sentence must pass if a cron job does call the planner")
    if check_text("The first time someone opens Shift Brain in a shift, it builds that shift's plan.", set()):
        fails.append("the true wording must pass")
    if check_text("A 24-hour plant runs three shifts: 06:00, 14:00 and 22:00.", set()):
        fails.append("shift times alone are not a claim that a job runs")
    if not check_text("Your supervisor needs to generate one. The automatic schedule runs at 06:00 once enabled. No briefing yet.", set()):
        fails.append("the old empty-state wording must fail")
    if not check_text("- Shift Brain (shift-brain.html): Autonomous shift planner. Triggered by pg_cron at the Filipino "
                      "3-shift boundaries (06:00 / 14:00 / 22:00 PHT).", set()):
        fails.append("the assistant's old platform-context line (Triggered by pg_cron) must fail")
    if not check_text("- Shift Brain (shift-brain.html): Autonomous shift planner. At each shift change (06:00, 14:00, "
                      "22:00 PHT) the orchestrator runs four sub-agents in parallel.", set()):
        fails.append("the companion's old line (At each shift change (06:00 ...) the orchestrator runs) must fail")
    if check_text("The AMC brief is generated daily at 06:00 PHT by amc-orchestrator.", set()):
        fails.append("the AMC daily brief is a different job, and it is scheduled")
    print("FAIL schedule-claims-match-cron self-test - " + "; ".join(fails) if fails
          else "self-test OK: a retired schedule fails, a scheduled one passes, the true wording and bare shift times pass")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    sched, via = scheduled_functions()
    hits = {}
    for p in shipped():
        try:
            errs = check_text(p.read_text(encoding="utf-8", errors="replace"), sched)
        except Exception:
            continue
        if errs:
            hits[p.relative_to(ROOT).as_posix()] = errs
    for f, errs in sorted(hits.items()):
        for e in errs[:3]:
            print(f"  BAD {f}: {e[:220]}")
    if hits:
        print(f"FAIL schedule-claims-match-cron - {sum(len(v) for v in hits.values())} sentence(s) in {len(hits)} file(s) "
              f"say a job runs on a clock that no cron job runs (scheduler read from {via})")
        return 1
    print(f"PASS schedule-claims-match-cron - no shipped page claims a schedule the cron table does not run "
          f"({len(CLAIMS)} claim(s), scheduler read from {via})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
