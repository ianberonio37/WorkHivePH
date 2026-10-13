"""chain_pacer.py - pace any eval or batch harness that bursts the free-tier AI chain, and cap live calls.

WHY (measured 2026-10-07/08). A grounding-eval re-run drove the edge runtime's chain at up to 68 chain events a
minute. Within minutes every general model answered 429 - Gemini 2.5 Flash and Flash-Lite, Mistral medium, all six
OpenRouter :free models (the last within 35 ms of each other: OpenRouter's free allowance is ONE daily pool per
account, not per model) - and 411 of the next answers came from mistral codestral-latest, the code model kept as a
last resort. A harness that bursts is not measuring the platform; it is spending the platform's daily free quota and
then grading the last resort. Three rules, in one place so every harness gets the same ones:

  1. a minimum gap between calls (min_gap_s),
  2. a per-run cap on calls (max_calls) - a harness that grows a new case cannot quietly double its spend,
  3. stop EARLY - with a "QUOTA EXHAUSTED" line, never a failure - once every provider has answered 429 on
     `exhausted_after` consecutive calls: past that point every further call only re-confirms the 429.

THE NUMBERS. One ai-gateway invoke runs the chain up to three times (the answer, the memory distiller, the history
summariser), and the tightest per-model limit on the chain's head is Groq's ~30 requests/minute. An 8 s gap keeps one
harness at <= 7.5 invokes/min ~= 22 chain calls/min, under that limit even if one model took every call. A direct
chain caller (one request per call) needs only 3 s: OpenRouter's free models allow 20 requests/minute.
THE CAPS. In the 48 h before 2026-10-08 the chain's GENERAL (non-code) models served 362 answers in all before every one
of them answered 429 - about 180 a day of real free capacity, shared with the live platform (the tools use the same
keys). One run may spend at most half a day of it: 90 chain calls for a direct caller (PROCESS_MAX_CALLS), or 30 edge
invokes for a harness that goes through ai-gateway, each up to 3 chain calls (RUN_CAP_EDGE_INVOKES). Both are flags or
env overrides, never silent.

LiveCallBudget is the hard ceiling for a session's live generation calls - a JSON counter that is incremented BEFORE
each request is sent and refuses once it reaches its cap, counting refusals (a 429 is a call).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

EDGE_RUNTIME = "supabase_edge_runtime_workhive"
GAP_EDGE_INVOKE_S = 8.0     # one edge-fn invoke = up to 3 chain calls; Groq ~30 RPM per model
GAP_DIRECT_CALL_S = 3.0     # one chain request; OpenRouter :free 20 RPM
RUN_CAP_EDGE_INVOKES = 30   # ~90 chain calls: half a measured day of general-model free capacity (see THE CAPS)


class LiveCallBudget:
    """A file-backed counter of live provider requests. take() BEFORE sending; False means do not send."""

    def __init__(self, path: str | os.PathLike, cap: int | None = None):
        self.path = Path(path)
        state = self._read()
        if cap is not None and "cap" not in state:
            state["cap"] = int(cap)
            self._write(state)

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"used": 0, "log": []}

    def _write(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp-write")
        tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)          # atomic: a crash mid-write never truncates the ledger

    def remaining(self) -> int:
        s = self._read()
        return max(0, int(s.get("cap", 0)) - int(s.get("used", 0)))

    def take(self, label: str) -> bool:
        s = self._read()
        cap, used = int(s.get("cap", 0)), int(s.get("used", 0))
        if used >= cap:
            print(f"  BUDGET: refused '{label}' - {used}/{cap} live calls already spent; nothing sent")
            return False
        s["used"] = used + 1
        s.setdefault("log", []).append({"n": used + 1, "label": label, "at": time.strftime("%H:%M:%S")})
        self._write(s)
        return True


class ChainPacer:
    """Gap + cap + stop-on-exhaustion for one harness run."""

    def __init__(self, label: str, min_gap_s: float, max_calls: int, exhausted_after: int = 2,
                 raise_hint: str = "--max-calls"):
        self.label, self.min_gap_s, self.max_calls, self.exhausted_after = label, float(min_gap_s), int(max_calls), int(exhausted_after)
        self.raise_hint = raise_hint
        self.calls = 0
        self._last = 0.0
        self._streak = 0
        self.stop_reason = ""
        self._lock = threading.Lock()   # a concurrent harness shares ONE gap: workers queue behind it

    def wait(self) -> bool:
        """Call before each chain-bound call. Sleeps for the gap; False = stop (cap or exhaustion)."""
        with self._lock:
            return self._wait_locked()

    def _wait_locked(self) -> bool:
        if self.stop_reason:
            return False
        if self.calls >= self.max_calls:
            self.stop_reason = f"CAP REACHED: {self.calls}/{self.max_calls} calls this run - stopping (raise with {self.raise_hint})"
            print(f"  [{self.label}] {self.stop_reason}")
            return False
        dt = time.time() - self._last
        if self._last and dt < self.min_gap_s:
            time.sleep(self.min_gap_s - dt)
        self._last = time.time()
        self.calls += 1
        return True

    def record(self, outcome: str) -> None:
        """outcome: 'served' | 'all_429' | 'other'. Two consecutive all_429 (default) stop the run."""
        with self._lock:
            self._record_locked(outcome)

    def _record_locked(self, outcome: str) -> None:
        self._streak = self._streak + 1 if outcome == "all_429" else 0
        if self._streak >= self.exhausted_after and not self.stop_reason:
            self.stop_reason = (f"QUOTA EXHAUSTED: every provider answered 429 on {self._streak} consecutive calls - "
                                f"stopping early; the remaining cases are SKIPPED, not failed")
            print(f"  [{self.label}] {self.stop_reason}")

    @property
    def exhausted(self) -> bool:
        return self.stop_reason.startswith("QUOTA EXHAUSTED")


_PROCESS_PACER: ChainPacer | None = None
PROCESS_MAX_CALLS = 90      # half a measured day of general-model free capacity (see THE CAPS); WH_AI_MAX_CALLS


def process_pacer() -> ChainPacer:
    """The ONE pacer every direct chain call in this Python process shares (tools/ai_chain.py and tools/lib/ai_chain.py
    both use it), so a batch tool is paced whether or not its author thought about quota. The Python tools spend the
    SAME provider keys as the live platform, so an unpaced batch starves the platform's own users. Defaults:
    WH_AI_MIN_GAP_S=3 (OpenRouter :free 20 RPM), WH_AI_MAX_CALLS=90 per process (0 = no cap). A single interactive call
    never waits - the gap only applies between calls."""
    global _PROCESS_PACER
    if _PROCESS_PACER is None:
        gap = float(os.environ.get("WH_AI_MIN_GAP_S", GAP_DIRECT_CALL_S))
        cap = int(os.environ.get("WH_AI_MAX_CALLS", PROCESS_MAX_CALLS))
        _PROCESS_PACER = ChainPacer("ai-chain", gap, cap if cap > 0 else 10 ** 9, raise_hint="WH_AI_MAX_CALLS=<n>, 0 = no cap")
    return _PROCESS_PACER


def outcome_from_statuses(statuses, served: bool) -> str:
    """A direct chain call's outcome from the HTTP status of every entry it asked."""
    if served:
        return "served"
    asked = [s for s in statuses if s is not None]
    return "all_429" if asked and all(s == 429 for s in asked) else "other"


_SERVED = re.compile(r"\[ai-chain(?::vision)?\] served by ")
_R429 = re.compile(r"\[ai-chain(?::vision)?\] \S+ skipped \(HTTP 429")
_OTHER = re.compile(r"\[ai-chain(?::vision)?\] \S+ (?:error \d{3}|threw|returned empty|returned only reasoning|ran out of budget)")


def outcome_from_lines(lines) -> str:
    """Classify one call window of [ai-chain] log lines. 'all_429' only when something answered 429, nothing
    served, and nothing failed for any OTHER reason - 'every provider answered 429', not 'the chain was down'."""
    served = r429 = other = 0
    for ln in lines:
        if _SERVED.search(ln):
            served += 1
        elif _R429.search(ln):
            r429 += 1
        elif _OTHER.search(ln):
            other += 1
    if served:
        return "served"
    if r429 and not other:
        return "all_429"
    return "other"


def edge_window_outcome(t0: float, t1: float) -> str:
    """The edge runtime's [ai-chain] lines for one invoke's window. The runtime log interleaves every caller, so a
    concurrent caller's 'served' line can mask an exhausted window - which only ever delays the stop, never fakes it."""
    try:
        r = subprocess.run(["docker", "logs", "--since", f"{int(t0) - 1}", "--until", f"{int(t1) + 2}", EDGE_RUNTIME],
                           capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
    except Exception:
        return "other"
    return outcome_from_lines((r.stdout + "\n" + r.stderr).splitlines())


def selftest() -> bool:
    cases = [
        (["[ai-chain] groq/qwen skipped (HTTP 429)", "[ai-chain] served by mistral / codestral-latest (tokens 9)"], "served"),
        (["[ai-chain] google/gemini-2.5-flash skipped (HTTP 429)", "[ai-chain] openrouter/x:free skipped (HTTP 429, retry-after 30s)"], "all_429"),
        (["[ai-chain] groq/openai/gpt-oss-20b error 400 (transient: x): {}", "[ai-chain] google/g skipped (HTTP 429)"], "other"),
        ([], "other"),
    ]
    ok = all(outcome_from_lines(lines) == want for lines, want in cases)
    p = ChainPacer("selftest", 0, 10)
    for o in ("all_429", "served", "all_429"):
        p.wait(); p.record(o)
    ok &= not p.exhausted                     # a served call in between resets the streak
    p.wait(); p.record("all_429")
    ok &= p.exhausted and not p.wait()        # two in a row stop the run
    q = ChainPacer("selftest", 0, 2)
    ok &= q.wait() and q.wait() and not q.wait() and q.stop_reason.startswith("CAP REACHED")
    g = ChainPacer("selftest", 0.3, 5)
    t = time.time(); g.wait(); g.wait()
    ok &= time.time() - t >= 0.29             # the gap is honoured
    return bool(ok)


if __name__ == "__main__":
    import sys
    passed = selftest()
    print("chain_pacer selftest:", "PASS" if passed else "FAIL")
    sys.exit(0 if passed else 1)
