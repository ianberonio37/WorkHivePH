#!/usr/bin/env python3
"""companion_persona_battery.py — LIVE persona/bridge eval harness (CL9 D7, first slice, 2026-07-08).

The map's build (2a/2b/2e): a reusable probe + deterministic grader over a persona golden set. Keys the
HARD identity assertion on the structural persona-echo (data.persona — the field built this session) and
grades the VOICE DIFFERENTIAL + REACTIVE BRIDGE with deterministic markers. Covers:
  A voice-differential — same prompt under hezekiah vs zaniah answers in each one's lane.
  B reactive bridge (both directions) — Zaniah asked a TECHNICAL Q bridges to Hezekiah; Hezekiah asked a
    STRATEGIC Q bridges to Zaniah.
  E (separately) persona-scope RAG isolation — see validate_persona_echo_live.py + the roadmap.

Grading (deterministic, no LLM judge — the ai-engineer "grade against a process observable" discipline):
  HARD (fail): data.persona must equal the requested persona (the echo contract).
  SOFT (scored, reported): the expected voice/bridge markers for the probe shape.
Markers: Hezekiah = torque/temp/RPM/Nm value or "Naks"/PH code-switch; Zaniah = OEE/MTBF/KPI/ratio or "Hala"/
English; Bridge = the OTHER persona name + ("lane" | "switch him in" | "switch her in").

Live-tier: GoTrue-auths a seeded worker; skips cleanly (exit 0) if the local stack is down. The soft voice
markers are probabilistic, so by default only the HARD echo contract fails the run; pass --strict-voice to
also fail on a voice/bridge miss (for a curated golden run, not the gate).

Usage:  python tools/companion_persona_battery.py [--json] [--strict-voice]
Exit 0 = echo contract holds on every probe (+ voice markers reported) · 1 = an echo contract broke.
"""
import re
import sys
import json
import time
import pathlib
import urllib.request
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDGE = "http://127.0.0.1:54321"
WORKER_EMAIL = "leandromarquez@auth.workhiveph.com"
# HIVE is RESOLVED at runtime from the user's live hive_members row (test_identity pattern) —
# a pinned UUID here rotted TWICE across reseeds (9b4eaeac → 636cf7e8 → deleted). The literal
# below is only the last-resort fallback if the resolver itself fails.
_HIVE_FALLBACK = "636cf7e8-431a-4907-8a9f-43dd4cc216d6"
def _resolve_hive() -> str:
    try:
        import sys as _s
        _s.path.insert(0, str(ROOT / "tools" / "lib"))
        from test_identity import resolve_test_identity
        return resolve_test_identity(WORKER_EMAIL).hive_id
    except Exception:
        return _HIVE_FALLBACK
HIVE = _resolve_hive()

HEZEKIAH_MARK = re.compile(r"\b\d+\s*(?:nm|n·m|newton|rpm|°c|deg|bar|psi)\b|\btorque\b|\bnaks\b", re.I)
ZANIAH_MARK = re.compile(r"\b(?:oee|mtbf|mttr|kpi|ratio|planned[- ]vs[- ]reactive|criticality|availability)\b|\bhala\b", re.I)


def _bridge_to(name: str) -> re.Pattern:
    # A hand-off to the other persona: their name + a defer/hand-off cue. Broadened after a live run showed
    # the model bridges with varied phrasing ("Hezekiah CARRIES the exact torque tables", not only the
    # canonical "…lane… switch him in?"). Calibrate the instrument to the real replies, not vice-versa.
    return re.compile(
        rf"\b{name}\b[^.?!]*(?:\blane\b|switch (?:him|her) in|carries|handles|has the|knows the|"
        rf"is (?:the|your) (?:one|expert|go[- ]to|specialist)|better (?:for|at)|"
        rf"specialt|that['’]?s (?:more )?{name})", re.I)


# The golden set: (label, persona, prompt, shape, marker/bridge check)
GOLDEN = [
    ("hezekiah-technical-answers-lane", "hezekiah",
     "What exact torque should I use on the M20 anchor bolts on the compressor base?",
     "voice", lambda a: bool(HEZEKIAH_MARK.search(a))),
    ("zaniah-technical-bridges-to-hezekiah", "zaniah",
     "What exact torque should I use on the M20 anchor bolts on the compressor base?",
     "bridge", lambda a: bool(_bridge_to("hezekiah").search(a))),
    ("zaniah-strategic-answers-lane", "zaniah",
     "How should I prioritise reliability strategy across my most critical assets this quarter?",
     "voice", lambda a: bool(ZANIAH_MARK.search(a))),
    ("hezekiah-strategic-bridges-to-zaniah", "hezekiah",
     "How should I prioritise reliability strategy across my most critical assets this quarter?",
     "bridge", lambda a: bool(_bridge_to("zaniah").search(a))),
]


def _anon_key():
    f = ROOT / "tests" / "_db-cleanup.ts"
    if not f.exists():
        return None
    m = re.search(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}", f.read_text(encoding="utf-8", errors="ignore"))
    return m.group(0) if m else None


def _post(url, body, headers, timeout=60.0):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    as_json = "--json" in sys.argv
    strict_voice = "--strict-voice" in sys.argv
    anon = _anon_key()
    if not anon:
        print("persona-battery: SKIP (no anon key / not a local checkout)")
        return 0
    try:
        tok = _post(f"{EDGE}/auth/v1/token?grant_type=password", {"email": WORKER_EMAIL, "password": "test1234"},
                    {"apikey": anon}, timeout=10).get("access_token")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        print("persona-battery: SKIP (local Supabase unreachable — stack down)")
        return 0
    if not tok:
        print("persona-battery: SKIP (could not auth seeded worker)")
        return 0
    hdr = {"apikey": anon, "Authorization": f"Bearer {tok}"}

    # D7 (build 2d): a fixed-persona MULTI-TURN session — persona + lane must hold across turns, and an
    # off-topic aside must not derail the lane. Consecutive gateway calls share agent_memory (worker+agent),
    # so this exercises the real multi-turn path. HARD = every turn echoes zaniah; SOFT = lane held + no drift.
    d7_turns = [
        "How's my reliability posture on the critical assets this quarter?",
        "Anyway, traffic was terrible on EDSA this morning, grabe.",   # off-topic aside — must be ignored
        "Back to it — which asset should I prioritise for a strategy review?",
    ]
    d7_rows, d7_hard = [], 0
    for i, msg in enumerate(d7_turns):
        try:
            resp = _post(f"{EDGE}/functions/v1/ai-gateway",
                         {"agent": "voice-journal", "message": msg, "hive_id": HIVE,
                          "context": {"persona": "zaniah"}}, hdr, timeout=70)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            break
        dd = resp.get("data") or {}
        echo = dd.get("persona"); ans = dd.get("answer") or ""
        echo_ok = (echo == "zaniah")
        # anti-marker: a Hezekiah signature (torque/RPM/Nm) leaking into a Zaniah lane = drift
        drift = bool(re.search(r"\b\d+\s*(?:nm|rpm|°c)\b|\btorque\b", ans, re.I))
        if not echo_ok:
            d7_hard += 1
        d7_rows.append({"turn": i + 1, "echo": echo, "echo_ok": echo_ok, "hezekiah_drift": drift, "answer": ans[:90]})

    rows, hard_fail, soft_miss = [], 0, 0
    for label, persona, prompt, shape, check in GOLDEN:
        try:
            resp = _post(f"{EDGE}/functions/v1/ai-gateway",
                         {"agent": "voice-journal", "message": prompt, "hive_id": HIVE,
                          "context": {"persona": persona}}, hdr, timeout=70)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            print(f"persona-battery: SKIP (gateway unreachable: {e})")
            return 0
        dd = resp.get("data") or {}
        echo = dd.get("persona")
        ans = dd.get("answer") or ""
        echo_ok = (echo == persona)
        voice_ok = bool(check(ans))
        if not echo_ok:
            hard_fail += 1
        if not voice_ok:
            soft_miss += 1
        rows.append({"probe": label, "persona": persona, "shape": shape, "echo": echo,
                     "echo_ok": echo_ok, "voice_ok": voice_ok, "answer": ans[:110]})

    d7_drift = sum(1 for r in d7_rows if r["hezekiah_drift"])
    ok = (hard_fail == 0) and (d7_hard == 0) and (not strict_voice or soft_miss == 0)
    if as_json:
        print(json.dumps({"rows": rows, "d7": d7_rows, "hard_fail": hard_fail, "d7_hard": d7_hard,
                          "soft_miss": soft_miss, "d7_drift": d7_drift, "pass": ok}, indent=2))
    else:
        print("CL9 persona/bridge battery (HARD=echo contract · SOFT=voice/bridge markers)")
        for r in rows:
            tag = "OK " if (r["echo_ok"] and r["voice_ok"]) else ("ECHO-FAIL" if not r["echo_ok"] else "voice-miss")
            print(f"  [{tag:9}] {r['probe']:38} echo={r['echo']} {r['shape']}_ok={r['voice_ok']}")
            print(f"              answer: {r['answer']}")
        print("  D7 multi-turn consistency (fixed persona=zaniah across 3 turns incl. an off-topic aside):")
        for r in d7_rows:
            tag = "OK " if (r["echo_ok"] and not r["hezekiah_drift"]) else ("ECHO-FAIL" if not r["echo_ok"] else "DRIFT")
            print(f"    [{tag:9}] turn {r['turn']} echo={r['echo']} hezekiah_drift={r['hezekiah_drift']}  {r['answer']}")
        print(f"  --> HARD echo fails: {hard_fail}+{d7_hard}(d7) | SOFT voice misses: {soft_miss}/{len(rows)} | d7-drift: {d7_drift} | pass={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
