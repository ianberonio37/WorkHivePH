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

────────────────────────────────────────────────────────────────────────────────
2026-08-04 - THE COUNTER IS NO LONGER A RELEASE VALVE. This is the hole that let
the 8th recurrence through, and it was in THIS FILE, not in Claude's prose.

The old code was:

    count = _read_count(session)
    if count >= MAX_BLOCKS:      # "safety valve: ... then trust the model"
        _write_count(session, 0)
        allow()

Two defects, one fatal:
  1. Hitting the cap ALLOWED the stop. So the guard taught exactly the lesson it
     exists to prevent: keep trying to stop and eventually the mechanism yields.
     Claude read block 10/10, reasoned "the cap is reached, so the next stop is
     permitted", and ended a turn with BJ 40 + BK 35 + ~145 F1 arch rows still
     open. No `.momentum_allow_stop` was ever created, because no genuine ender
     held - the stop happened because the ENFORCEMENT RAN OUT.
  2. It then reset the count to 0, so a stop became available every 10 blocks,
     forever, with the audit trail wiped each time.

"Then trust the model" is precisely the part that is known-broken - the doctrine
exists because Claude's judgment about when to stop keeps failing. A safety valve
against an infinite loop must not double as permission to stop.

THE FIX: the ONLY release is the sentinel, and the sentinel must SAY which ender
it is claiming. That claim is appended to `.momentum_stop_log.jsonl` so Ian can
audit every turn-end after the fact - if a claimed ender turns out to be false,
the receipt is on disk with the session id and the block count at the time.

There is no deadlock risk: writing the sentinel is one Bash call and is always
available, so a genuinely-finished turn can always end. What is no longer
available is ending a turn by simply outlasting the guard.
────────────────────────────────────────────────────────────────────────────────

Escape hatch (the only one):
  Sentinel `.momentum_allow_stop` in the project root, created when a GENUINE
  turn-ender holds - (a) a fork needing Ian's decision, (b) a hard external
  ceiling, (c) an irreversible/outward action that is the SOLE remaining item,
  (d) the local queue is genuinely empty, (e) Ian explicitly said wrap/stop THIS
  message. Write the ender into the file so the log records WHY:
      printf 'd: queue empty - every row banked' > .momentum_allow_stop
  The guard consumes (deletes) the sentinel, logs the claim, and allows the stop.

Hook contract: read the Stop event JSON on stdin; print {} to allow, or
{"decision":"block","reason":"..."} to block + feed the reason back to the model.
"""
import sys, os, json, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root = parent of tools/
DRIVE_FLAG = os.path.join(ROOT, ".momentum_drive")
SENTINEL = os.path.join(ROOT, ".momentum_allow_stop")
STATE = os.path.join(ROOT, ".momentum_stop_state.json")
LOG = os.path.join(ROOT, ".momentum_stop_log.jsonl")

# Escalation thresholds. NEITHER of these allows a stop - they only sharpen the
# message. The counter is a thermometer, never a door.
NAG_AT = 10   # past this, the block text calls out that outlasting the guard is the violation
LOUD_AT = 25  # past this, it also demands Claude state the ender in the sentinel


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


def _log_release(session, count, claim):
    """Append the claimed ender so a false one leaves a receipt Ian can audit."""
    try:
        rec = {
            "at": datetime.datetime.now().isoformat(timespec="seconds"),
            "session": session,
            "blocks_before_release": count,
            "claimed_ender": (claim or "(none stated)").strip()[:400],
        }
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
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

    count = _read_count(session)

    # THE ONLY RELEASE: a sentinel declaring which ender (a)-(e) holds.
    if os.path.exists(SENTINEL):
        claim = ""
        try:
            with open(SENTINEL, encoding="utf-8") as f:
                claim = f.read()
        except Exception:
            pass
        try:
            os.remove(SENTINEL)
        except OSError:
            pass
        _log_release(session, count, claim)
        _write_count(session, 0)
        allow()

    _write_count(session, count + 1)
    n = count + 1

    reason = (
        "MOMENTUM DOCTRINE - STOP INTERCEPTED (block %d). You are about to end the turn while the "
        "`.momentum_drive` session is ARMED. Run the TURN-END TEST now: does a concrete, LOCAL, KNOWN next "
        "unit exist? Re-read the active roadmap's `NEXT:` line and/or run "
        "`python C:\\Users\\ILBeronio\\.claude-memento\\tools\\memento_retrieve.py \"what is the NEXT unit\"`. "
        "A `NEXT:` line you authored = YES = ending is FORBIDDEN -> DELETE any closing/summary/scoreboard prose "
        "you just drafted and GO EXECUTE that unit's first concrete slice IN THIS TURN.\n\n"
        "A stop is allowed ONLY if a genuine ender holds: (a) a fork needing Ian's decision (use AskUserQuestion), "
        "(b) a hard EXTERNAL ceiling that truly cannot be done locally, (c) an irreversible/outward action that is "
        "the SOLE remaining item, (d) the local queue is genuinely EMPTY, (e) Ian explicitly said wrap/stop in his "
        "LAST message. If and ONLY if one of (a)-(e) holds, declare it and stop again:\n"
        "    printf '<letter>: <one line why>' > .momentum_allow_stop\n"
        "The guard consumes the sentinel, LOGS your claim to .momentum_stop_log.jsonl for Ian to audit, and "
        "allows the stop. Otherwise the only correct action is MORE TOOL CALLS that advance the NEXT unit."
    ) % n

    if n > NAG_AT:
        reason += (
            "\n\nTHERE IS NO BLOCK CAP. This guard used to allow the stop after 10 blocks - that hole is "
            "CLOSED (2026-08-04), because on 2026-08-04 you read 'block 10/10', concluded the cap meant "
            "permission, and ended a turn with hundreds of local rows still owed. The counter is a "
            "thermometer, not a door. Outlasting the guard is not an ender; it is the violation with a "
            "number attached. If work remains, do the work. If it genuinely does not, SAY WHICH ENDER "
            "HOLDS in the sentinel and it will be recorded."
        )
    if n > LOUD_AT:
        reason += (
            "\n\n%d blocks in one session means one of two things, and both need an explicit act from you: "
            "either you are refusing to execute a known unit (then execute it), or the guard is misfiring "
            "because the queue really is empty (then write the sentinel with ender (d) and the reason). "
            "Repeating a bare stop is not a third option." % n
        )

    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


if __name__ == "__main__":
    main()
