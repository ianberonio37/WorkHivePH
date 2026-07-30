#!/usr/bin/env python3
"""validate_service_triage_eval.py — S7-ai: the triage suggestion must be IN THE PRODUCT'S VOCABULARY.

The bank's S7 cell is the one layer that cannot use an exact-match oracle. A free-text problem goes to
the `service-triage` agent and comes back with a category, an urgency and a mode; asking a free-tier
LLM to return one specific string every time would test the model's mood, not the product. So the
oracle is a RUBRIC: never "did it say Plumbing", always "is what it said something this product can
actually use".

WHY THAT IS THE INVARIANT THAT MATTERS. marketplace.html applies the suggestion by looking the
category up among the real <option>s:

    const opt = Array.from(sel.options).find(o => o.textContent.startsWith(t.category));
    if (opt) { sel.value = opt.value; bits.push(t.category); }

An out-of-vocabulary answer - "Plumbing Services", "Aircon Repair", "urgent" - finds nothing, sets
nothing, and reports nothing. The person presses "Ask AI", watches the form not move, and has no idea
whether the AI failed or simply had no opinion. Nothing throws. No gate reds. Exactly the shape of the
`urgency = 'emergency'` branch this same session found dead in the push fan-out: a value written
against a vocabulary that does not exist ([[feedback_view_predicate_forbidden_by_check]]).

THE VOCABULARIES ARE READ FROM THE DATABASE, never hardcoded here — the catalog's live categories and
the CHECK constraints on service_requests. Add a category tomorrow and this gate grades against it
without being touched.

A RATE-LIMITED OR ABSENT CHAIN IS A SKIP, NEVER A PASS. The free-tier chain 429s under load, and a
gate that scores "no answer" as "in vocabulary" would be green precisely when the feature is down.

Usage:  python tools/validate_service_triage_eval.py [--selftest] [--verbose]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATEWAY = "http://127.0.0.1:54321/functions/v1/ai-gateway"
KEY = "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"
DB = "supabase_db_workhive"
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# Real Philippine maintenance complaints, in the register a client actually types. Not prompts chosen
# to be easy: two are ambiguous on purpose, because an honest "no clear match" is a legitimate answer
# and must not be graded as a failure.
PROMPTS = [
    "Our compressor at the plant is leaking oil and the line is down right now",
    "Aircon sa office hindi na lumalamig, tumutulo yung tubig",
    "Need someone to check the standby generator before the rainy season",
    "May kailangan ayusin dito sa shop, medyo marami",
]


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-Atc", sql], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30)
    except Exception:
        return None
    return (r.stdout or "").strip()


def vocabularies():
    """(categories, urgencies, modes) — all three read live. None if the DB is unreachable."""
    cats = psql("select string_agg(distinct category, '|') from public.service_catalog where active;")
    if cats is None:
        return None
    checks = psql("select string_agg(pg_get_constraintdef(oid), ' ;; ') from pg_constraint "
                  "where conrelid='public.service_requests'::regclass and contype='c';") or ""
    def vocab(col):
        m = re.search(rf"{col}\s*=\s*ANY\s*\(ARRAY\[(.*?)\]", checks, re.S)
        return set(re.findall(r"'([^']+)'", m.group(1))) if m else set()
    return (set(filter(None, (cats or "").split("|"))), vocab("urgency"), vocab("mode"))


def capture(prompts, timeout=240):
    """-> list of {prompt, triage, error} via the PAGE's own client path.

    A raw urllib POST returned 401 "Sign-in required" against a token that the auth endpoint accepted
    on the same headers: the gateway resolves its caller through `authedClient.auth.getUser()`, and
    only voice-journal is anon-allowed. Driving supabase-js means this gate exercises what the person
    actually triggers ([[feedback_verify_the_instrument_before_the_page]]).
    """
    script = os.path.join(ROOT, "tools", "service_triage_capture.mjs")
    if not os.path.exists(script):
        return None, "capture script missing"
    try:
        r = subprocess.run(["node", script, json.dumps(prompts)], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except Exception as e:
        return None, str(e)
    rows = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    fatal = next((x["fatal"] for x in rows if x.get("fatal")), None)
    if fatal:
        return None, fatal
    if not rows:
        return None, (r.stderr or "no output")[:120]
    return rows, ""


def grade(t, cats, urgencies, modes):
    """-> list of problems. An ABSENT field is fine (no opinion); a field with a value the product
    cannot use is not, because the UI will silently discard it."""
    bad = []
    if t.get("category") and t["category"] not in cats:
        bad.append(f"category {t['category']!r} is not in the catalog — the select never moves")
    if t.get("urgency") and t["urgency"] not in urgencies:
        bad.append(f"urgency {t['urgency']!r} is outside the CHECK vocabulary {sorted(urgencies)}")
    if t.get("mode") and t["mode"] not in modes:
        bad.append(f"mode {t['mode']!r} is outside the CHECK vocabulary {sorted(modes)}")
    return bad


def main():
    if "--selftest" in sys.argv:
        return selftest()
    verbose = "--verbose" in sys.argv
    vocab = vocabularies()
    if vocab is None:
        print("  SKIP: docker/psql unavailable — cannot read the live vocabularies")
        return 0
    cats, urgencies, modes = vocab
    if not cats or not urgencies:
        print(f"  {RED}FAIL{RST} the vocabularies came back empty — grading against nothing would "
              f"pass everything")
        return 1

    print("=" * 84)
    print(f"  {BOLD}Service triage eval — is the AI's suggestion something the product can use?{RST}")
    print("=" * 84)
    print(f"  {DIM}catalog {len(cats)} categories · urgency {sorted(urgencies)} · mode {sorted(modes)}{RST}")

    rows, why = capture(PROMPTS)
    if rows is None:
        print(f"  {YEL}SKIP{RST} could not reach the live chain ({why}). NOT a pass.")
        return 0

    answered, problems, notes = 0, [], []
    for row in rows:
        p, t = row.get("prompt", ""), row.get("triage")
        if not isinstance(t, dict):
            notes.append(f"{p[:44]}... [{row.get('error') or 'no answer'}]")
            continue
        answered += 1
        bad = grade(t, cats, urgencies, modes)
        if verbose or bad:
            got = " · ".join(f"{k}={t[k]}" for k in ("category", "urgency", "mode") if t.get(k)) or "no opinion"
            print(f"  {GREEN + 'PASS' + RST if not bad else RED + 'FAIL' + RST}  {p[:52]}…  {DIM}{got}{RST}")
        for b in bad:
            print(f"        {RED}{b}{RST}")
            problems.append(b)

    print()
    if answered == 0:
        print(f"  {YEL}SKIP{RST} the chain answered none of {len(PROMPTS)} prompts "
              f"(rate-limited or down). NOT a pass — a green here would mean the feature is broken.")
        for n in notes:
            print(f"    {DIM}{n}{RST}")
        return 0
    if problems:
        print(f"{RED}FAIL{RST} — {len(problems)} suggestion(s) the UI would silently discard, "
              f"leaving the person watching a form that does not move")
        return 1
    print(f"{GREEN}PASS{RST} — every one of {answered} answered prompt(s) returned values this "
          f"product can actually apply (rubric oracle: in-vocabulary, never exact-match)")
    if notes:
        print(f"  {DIM}{len(notes)} prompt(s) unanswered: " + " · ".join(notes) + f"{RST}")
    return 0


def selftest():
    """Teeth on the GRADER, which is the deterministic half — the model is not the thing under test."""
    ok = True
    cats, urg, modes = {"Plumbing", "Aircon"}, {"low", "normal", "high", "critical"}, {"instant", "quote"}
    cases = [
        ({"category": "Plumbing", "urgency": "critical", "mode": "instant"}, 0, "a fully in-vocabulary answer passes"),
        ({}, 0, "no opinion at all is legitimate, not a failure"),
        ({"category": "Plumbing Services"}, 1, "a near-miss category is caught (the select never moves)"),
        ({"urgency": "emergency"}, 1, "an urgency the CHECK forbids is caught — the exact dead-branch class"),
        ({"mode": "urgent"}, 1, "a mode outside the CHECK is caught"),
    ]
    for t, want, label in cases:
        got = len(grade(t, cats, urg, modes))
        if got != want:
            print(f"  {RED}FAIL{RST} {label} (found {got}, expected {want})"); ok = False
        else:
            print(f"  {GREEN}PASS{RST} {label}")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
