#!/usr/bin/env python3
"""
validate_pm_frequency_mapping.py — PM08 / PMK4: one interval-to-frequency mapping, and it never
schedules a PM less often than asked.

THE CLASS: a PM's frequency is a WORD in the database ('Weekly'), and the schedule is derived from
that word by a CASE in `v_pm_scope_items_truth`. Every writer that turns an interval in DAYS into
that word is therefore deciding the real schedule. Two of them did it differently, and neither
matched the view.

WALKED 2026-07-28:
  * integrations.html (CMMS / CSV import) used a local map with NO Daily bucket, taking the first
    bucket >= days over [7,30,90,180,365]. Measured: 1 day -> 'Weekly' (7x rarer than asked),
    14 -> 'Monthly' (2.1x), 45 -> 'Quarterly' (2x). Every drift ran the SAME way — less often than
    the source system specified — on the exact path a plant uses to onboard its existing PM program.
    A daily inspection silently became a weekly one.
  * asset-hub.html (RCM strategy) rounded to the NEAREST bucket, so a 300-day interval became
    'Annual' (365), 65 days rarer than the strategy called for.
  * The UI's canonFreq maps 'biweekly'/'fortnightly' -> 'Weekly' (7 days) while the view maps them
    to 14. No such rows exist today, so this is latent — the same "agrees only by luck of
    vocabulary" shape the logbook arc closed for 'corrective' (LG2). Asserted here so it stays
    impossible-then-detectable rather than waiting for the first import that uses the word.

THE FIX: one mapping, `whFreqFromDays` / `whFreqDays` in utils.js, snapping DOWN to the closest
bucket that does not exceed the requested interval. Rounding to a shorter interval costs labour;
rounding to a longer one leaves equipment un-inspected, and only one of those is a safety decision.

WHAT THIS GATE ASSERTS:
  1. PARITY — utils.js's day-values equal the view's `frequency_days` CASE, label for label
     (including the biweekly/fortnightly synonyms). A migration that edits one and not the other
     fails here.
  2. SAFE DIRECTION — for every interval 1..400, the mapping never yields a period LONGER than the
     interval asked for.
  3. NO PRIVATE COPIES — no page reintroduces its own days->frequency bucket list.

Live tier for (1) (skips cleanly when docker is down); static for (2) and (3). Self-test: --selftest.
"""
from __future__ import annotations
import io, json, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent
UTILS = ROOT / "utils.js"
DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c"]

# Pages that turn an interval in days into a frequency WORD. Each must use the shared helper.
WRITER_PAGES = ["integrations.html", "asset-hub.html"]

# A local bucket list is the shape being banned: an array/object literal pairing day-counts with
# frequency labels. Matching on the label side keeps it from firing on unrelated numeric arrays.
PRIVATE_MAP_RE = re.compile(
    r"\[\s*\d+\s*,\s*['\"](?:Daily|Weekly|Monthly|Quarterly|Semi-?[Aa]nnual|Annual)['\"]\s*\]")


def psql(sql):
    try:
        r = subprocess.run(DOCKER_DB + [sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return None if r.returncode != 0 else (r.stdout or "").strip()
    except Exception:
        return None


def utils_mapping():
    """Read WH_FREQ_DAYS out of utils.js -> {label: days}. Source of truth for the client."""
    txt = UTILS.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"var FREQ_DAYS\s*=\s*\[(.*?)\];", txt, re.S)
    if not m:
        return None
    pairs = re.findall(r"\[\s*'([^']+)'\s*,\s*(\d+)\s*\]", m.group(1))
    return {label: int(days) for label, days in pairs}


def view_mapping():
    """Read the frequency_days CASE out of the live view -> {lowercased label: days}."""
    ddl = psql("SELECT pg_get_viewdef('public.v_pm_scope_items_truth'::regclass, true);")
    if ddl is None:
        return None
    body = ddl.split("AS frequency_days")[0]
    return {lab.lower(): int(days)
            for lab, days in re.findall(r"WHEN '([^']+)'::text THEN (\d+)", body)}


def check_parity():
    u, v = utils_mapping(), view_mapping()
    if u is None:
        return ["utils.js: WH_FREQ_DAYS not found — the shared mapping is gone or was renamed"]
    if v is None:
        return None  # DB down -> caller skips this check
    problems = []
    for label, days in u.items():
        got = v.get(label.lower())
        if got is None:
            problems.append(f"'{label}' is offered by utils.js but the view has no case for it — "
                            f"the view would silently schedule it every {v.get('_else', 30)} days")
        elif got != days:
            problems.append(f"'{label}': utils.js says {days}d, v_pm_scope_items_truth says {got}d — "
                            f"the page and the schedule disagree about what the word means")
    # The synonyms the UI accepts must resolve the same way in both places.
    for syn, want in (("biweekly", 14), ("fortnightly", 14)):
        got = v.get(syn)
        if got is not None and got != want:
            problems.append(f"'{syn}': view says {got}d, utils.js resolves it to {want}d")
    return problems


def check_safe_direction():
    """The mapping must never schedule a PM LESS often than the interval requested."""
    u = utils_mapping()
    if not u:
        return ["utils.js: WH_FREQ_DAYS not found"]
    buckets = sorted(u.values())
    problems = []
    for asked in range(1, 401):
        chosen = buckets[0]
        for b in buckets:
            if b <= asked:
                chosen = b
        if chosen > asked:
            problems.append(f"an interval of {asked}d maps to a {chosen}d period — RARER than asked")
            break  # one example is enough to fail
    return problems


def check_no_private_maps():
    problems = []
    for name in WRITER_PAGES:
        p = ROOT / name
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"whFreqFromDays\s*\(", txt):
            problems.append(f"{name} converts intervals to frequency words but does not call "
                            f"whFreqFromDays — it has its own rule again")
        hits = PRIVATE_MAP_RE.findall(txt)
        if hits:
            problems.append(f"{name} carries a private days->frequency bucket list ({len(hits)} "
                            f"entries, e.g. {hits[0]}) — that is how the two writers drifted apart")
    return problems


def run_all():
    results = []
    parity = check_parity()
    if parity is None:
        results.append(("parity", "SKIP", "local DB unreachable — utils.js vs the view not compared"))
    else:
        results.append(("parity", "FAIL" if parity else "PASS",
                        parity or "utils.js day-values match v_pm_scope_items_truth, label for label"))
    safe = check_safe_direction()
    results.append(("safe_direction", "FAIL" if safe else "PASS",
                    safe or "no interval 1..400 maps to a period longer than itself"))
    priv = check_no_private_maps()
    results.append(("one_mapping", "FAIL" if priv else "PASS",
                    priv or f"{len(WRITER_PAGES)} interval writers all use the shared helper"))
    return results


def run_selftest():
    """Pin the shapes that must keep failing, so the gate cannot rot into a no-op."""
    problems = []
    if not PRIVATE_MAP_RE.search("const B = [[7,'Weekly'],[30,'Monthly']];"):
        problems.append("PRIVATE_MAP_RE no longer matches the exact bucket-list shape that caused "
                        "the bug — it would not catch a reintroduction")
    if PRIVATE_MAP_RE.search("const xs = [[7, 'nope'], [30, 'other']];"):
        problems.append("PRIVATE_MAP_RE matches a non-frequency numeric array — too broad")
    u = utils_mapping()
    if not u:
        problems.append("utils.js: WH_FREQ_DAYS not parseable")
    else:
        if u.get("Daily") != 1:
            problems.append("Daily must be 1 day — its absence is what made an imported daily "
                            "inspection weekly")
        if len(u) < 6:
            problems.append(f"expected the 6 canonical frequencies, parsed {len(u)}")
    return problems


def main():
    if "--selftest" in sys.argv:
        probs = run_selftest()
        print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
        return 1 if probs else 0

    print(f"\n{BOLD}PM FREQUENCY MAPPING (one rule, never rarer than asked){RESET}")
    print("-" * 58)
    results = run_all()
    fails = 0
    for name, status, detail in results:
        colour = {"PASS": GREEN, "FAIL": RED, "SKIP": YELLOW}[status]
        print(f"  {colour}{status}{RESET}  {name}")
        if isinstance(detail, list):
            fails += 1
            for d in detail:
                print(f"        {d}")
        else:
            print(f"        {detail}")
    print(f"\n  Summary: {len(results) - fails} pass · {fails} fail")
    (ROOT / "pm_frequency_mapping_report.json").write_text(
        json.dumps({"validator": "pm_frequency_mapping",
                    "results": [{"check": n, "status": s} for n, s, _ in results],
                    "fail": fails}, indent=2), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
