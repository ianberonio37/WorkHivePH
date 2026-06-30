#!/usr/bin/env python3
"""
Momentum Stop Guard - Ian's "tick before a handoff" forcing function (2026-06-26).

Runs as a synchronous Stop hook: it fires every time Claude tries to END a turn.
While ARMED, it BLOCKS the stop and re-injects the Momentum Doctrine + "run the
turn-end test and go execute the NEXT unit" - so a premature stop becomes a forced
continuation instead of a report-and-wait hand-back. This removes the failure mode
where Claude's *judgment* about when to stop is wrong: the harness (not Claude)
re-engages on every stop.

OPT-IN per work-session (so casual Q&A turns are never blocked):
  - ARMED only when the flag file `.momentum_drive` exists in the project root.
    Arm it when Ian says "drive to 100% / no more stopping": `touch .momentum_drive`
    (Claude does this at the start of a drive session; Ian can too). Disarm by
    deleting it when Ian says "wrap".
  - When the flag is ABSENT the guard is a no-op (allows every stop).

Escape hatches (so an armed guard never traps a legitimate end):
  1. Sentinel `.momentum_allow_stop` in the project root: create it when a GENUINE
     turn-ender holds - (a) a fork needing Ian's decision, (b) a hard external
     ceiling, (c) an irreversible/outward action that is the SOLE remaining item,
     (d) the local queue is genuinely empty, (e) Ian explicitly said wrap/stop THIS
     message. The guard consumes (deletes) the sentinel and allows the stop.
  2. Per-session safety cap (MAX_BLOCKS): after that many blocks in one session it
     allows the stop, so a misfire can never become a true infinite loop.

Hook contract: read the Stop event JSON on stdin; print {} to allow, or
{"decision":"block","reason":"..."} to block + feed the reason back to the model.
"""
import sys, os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root = parent of tools/
DRIVE_FLAG = os.path.join(ROOT, ".momentum_drive")
SENTINEL = os.path.join(ROOT, ".momentum_allow_stop")
STATE = os.path.join(ROOT, ".momentum_stop_state.json")
MAX_BLOCKS = 10  # safety valve: force at most this many continuations per session, then trust the model


def allow():
    print("{}")
    sys.exit(0)


def _read_count(session):
    try:
        with open(STATE, encoding="utf-8") as f:
            return int(json.load(f).get(session, 0))
    except Exception:
        return 0


def _write_count(session, n):
    try:
        d = {}
        if os.path.exists(STATE):
            with open(STATE, encoding="utf-8") as f:
                d = json.load(f)
        d[session] = n
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    session = str(payload.get("session_id", "default"))

    # Disarmed -> no-op (normal conversational turns are never blocked).
    if not os.path.exists(DRIVE_FLAG):
        allow()

    # Escape 1: a genuine ender (a)-(e) was declared this turn.
    if os.path.exists(SENTINEL):
        try:
            os.remove(SENTINEL)
        except OSError:
            pass
        _write_count(session, 0)
        allow()

    # Escape 2: per-session safety valve.
    count = _read_count(session)
    if count >= MAX_BLOCKS:
        _write_count(session, 0)
        allow()
    _write_count(session, count + 1)

    reason = (
        "MOMENTUM DOCTRINE - STOP INTERCEPTED (block %d/%d). You are about to end the turn while the "
        "`.momentum_drive` session is ARMED. Run the TURN-END TEST now: does a concrete, LOCAL, KNOWN next "
        "unit exist? Re-read the active roadmap's `NEXT:` line and/or run "
        "`python C:\\Users\\ILBeronio\\.claude-memento\\tools\\memento_retrieve.py \"what is the NEXT unit\"`. "
        "A `NEXT:` line you authored = YES = ending is FORBIDDEN -> DELETE any closing/summary/scoreboard prose "
        "you just drafted and GO EXECUTE that unit's first concrete slice IN THIS TURN.\n\n"
        "A stop is allowed ONLY if a genuine ender holds: (a) a fork needing Ian's decision (use AskUserQuestion), "
        "(b) a hard EXTERNAL ceiling that truly cannot be done locally, (c) an irreversible/outward action that is "
        "the SOLE remaining item, (d) the local queue is genuinely EMPTY, (e) Ian explicitly said wrap/stop in his "
        "LAST message. If and ONLY if one of (a)-(e) holds, create the file `.momentum_allow_stop` in the project "
        "root (Bash: `touch .momentum_allow_stop`) and stop again - the next Stop will be allowed. Otherwise, "
        "the only correct action is MORE TOOL CALLS that advance the NEXT unit."
    ) % (count + 1, MAX_BLOCKS)

    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


if __name__ == "__main__":
    main()
