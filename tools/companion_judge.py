"""
Companion JUDGMENT-probe LLM judge (cross-model, free-tier).
============================================================
For probes whose correctness is an open-ended JUDGMENT ("is this number plausible?", "is this PM
answer complete?") that the companion voices in free-form Taglish persona metaphor ("that's not a
number, that's a fire drill"), a deterministic substring grader systematically under-credits correct
answers (see reference_companion_grader_fit + ai-engineer SKILL). CLINICAL-FACT probes stay on the
substring grader; only JUDGMENT probes route here.

Trust / independence + reliability: the companion answers via Groq `llama-4-scout` (top of the chain);
this judge reuses the SAME generous 19-model free-tier fallback (`tools/ai_chain.call_ai_chain`) but
PREFERS a different provider — Google `gemini-2.5-flash` — so the typical judge call is CROSS-MODEL
(grader ≠ answer-producer, the property `ai-eval-runner` relies on) while the rest of the chain still
serves as fallback, so one provider's rate-limit can never fail-close the judge into a false FAIL. The
judge only ever sees {question, answer, criterion}; it knows nothing about how the companion is built.

This module is SELF-CONTAINED: no companion imports. `grade_judgment_unit` (in companion_rigorous_grader)
calls `judge_pass` as a pluggable `judge_fn`, and injects a MOCK in its offline self-test, so the grader
WIRING is proven with no LLM. `--self-test` here is the separate LIVE judge calibration (spends a few
Gemini calls) that proves the JUDGE PROMPT itself discriminates a correct answer from a wrong one.

Usage:
  python tools/companion_judge.py --self-test     # LIVE: prove the judge prompt discriminates (~6 calls)
  python tools/companion_judge.py --ask "<question>" --answer "<answer>" --rubric "<criterion>"
"""
from __future__ import annotations
import argparse
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ai_chain import call_ai_chain  # the generous 19-model free-tier fallback (mirror of ai-chain.ts)

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"

# Prefer a non-Groq model (the companion answers on Groq llama-4-scout) so the judge is CROSS-MODEL;
# the rest of the 19-model chain is still the fallback. Bump JUDGE_VERSION on any judge prompt change.
JUDGE_PREFER = "gemini-2.5-flash"
JUDGE_VERSION = 1

# Strict, criterion-only grader. Style/tone/language are explicitly OUT of scope so a correct answer in
# Taglish persona voice ("that's not a number, that's a fire drill") is judged on substance, not words.
JUDGE_PROMPT = """You are a strict industrial-maintenance examiner grading a maintenance assistant.

You are given a QUESTION, the assistant's ANSWER, and a CRITERION describing what a correct answer must
do. Judge ONLY whether the ANSWER satisfies the CRITERION on substance. IGNORE style, tone, brevity, and
language — Taglish / Filipino / colorful metaphor are all fine; an answer that conveys the right
judgment in informal words ("that's not a number, that's a fire drill", "way below your watch line")
SATISFIES a criterion about recognizing an implausible value.

Return ONLY a JSON object, no prose:
{"verdict": "PASS" | "FAIL", "score": <0-100>, "reason": "<one short clause>"}

PASS iff the answer clearly satisfies the criterion. FAIL if it is off-topic, evasive, affirms the
wrong thing, or omits what the criterion requires."""


def judge_pass(question: str, answer: str, rubric: str, *, timeout: int = 40) -> dict:
    """Cross-model LLM judge over the free-tier fallback chain. Returns {verdict: PASS|FAIL, score,
    reason, error}. On ANY error / all-providers-down returns a FAIL with the error noted — a judge
    outage must never silently PASS (fail closed)."""
    if not str(answer or "").strip():
        return {"verdict": "FAIL", "score": 0, "reason": "empty answer", "error": None}
    user = f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nCRITERION:\n{rubric}"
    try:
        raw = call_ai_chain(user, system_prompt=JUDGE_PROMPT, temperature=0.0, max_tokens=256,
                            json_mode=True, timeout=timeout, prefer_model=JUDGE_PREFER)
        if not raw or raw.strip() in ("{}", ""):
            return {"verdict": "FAIL", "score": 0, "reason": "judge chain returned nothing", "error": "chain_empty"}
        # Lenient parse: free-tier models often ignore json_mode and return prose or ```json fences.
        # Prefer a JSON object; fall back to extracting the verdict token so a correct answer is not
        # false-failed by a formatting wobble (the verdict word is what matters, not the wrapper).
        body_txt = raw.strip().strip("`")
        parsed = None
        m = re.search(r"\{.*\}", body_txt, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None
        if parsed is None:
            vm = (re.search(r'verdict["\s:]*?(PASS|FAIL)', body_txt, re.IGNORECASE)
                  or re.search(r'\b(PASS|FAIL)\b', body_txt, re.IGNORECASE))
            if not vm:
                return {"verdict": "FAIL", "score": 0, "reason": f"unparseable judge reply: {body_txt[:80]}",
                        "error": "unparseable"}
            parsed = {"verdict": vm.group(1).upper(), "score": 0, "reason": "parsed from non-JSON reply"}
        verdict = "PASS" if str(parsed.get("verdict", "")).upper() == "PASS" else "FAIL"
        return {"verdict": verdict, "score": int(parsed.get("score", 0) or 0),
                "reason": str(parsed.get("reason", ""))[:160], "error": None}
    except Exception as e:  # noqa: BLE001 — fail closed
        return {"verdict": "FAIL", "score": 0, "reason": f"judge error: {e}", "error": str(e)}


def self_test() -> int:
    """LIVE judge calibration: prove the JUDGE PROMPT separates a correct answer from a wrong one on a
    tiny fixture (3 criteria x {correct, wrong}). Spends ~6 Gemini calls. NOT part of offline mega — the
    grader's offline self-test uses a MOCK judge instead."""
    fixtures = [
        {"q": "My logs say a pump's MTBF is 5 minutes. Is that right?",
         "rubric": "Recognizes the value is implausibly low / a likely data error for MTBF and does NOT affirm 5 minutes as a normal MTBF.",
         "correct": "Hala, 5 minutes MTBF? That's not a number, that's a fire drill — way below any real pump. Check your logs for duplicate entries.",
         "wrong": "Yes, 5 minutes is a perfectly normal MTBF for a healthy pump."},
        {"q": "My dashboard shows an OEE of 130%. Is that possible?",
         "rubric": "States OEE cannot exceed 100% and flags 130% as a calculation/data error.",
         "correct": "OEE can't go past 100% — 130% means something's off in the formula or the inputs.",
         "wrong": "130% is a great OEE, your line is running very efficiently."},
        {"q": "What PM would you schedule for a standby diesel generator?",
         "rubric": "Gives genset PM SCOPE (e.g. oil/fuel/coolant/battery) AND a cadence (any of weekly/monthly/hours/routine due-dates).",
         "correct": "Check oil and coolant, exercise the battery, and run a monthly load test; track it on a routine schedule.",
         "wrong": "Generators are basically maintenance-free, just start it if there's a blackout."},
    ]
    print(f"\n{BOLD}Judge calibration (LIVE · chain prefer={JUDGE_PREFER}){RESET}  ·  {len(fixtures)} criteria x correct/wrong")
    print("=" * 70)
    problems = []
    for f in fixtures:
        good = judge_pass(f["q"], f["correct"], f["rubric"])
        bad = judge_pass(f["q"], f["wrong"], f["rubric"])
        gok = good["verdict"] == "PASS"
        bok = bad["verdict"] == "FAIL"
        print(f"  {'OK ' if gok else 'XX '}correct->{good['verdict']:<4}  {'OK ' if bok else 'XX '}wrong->{bad['verdict']:<4}  | {f['q'][:46]}")
        if not gok:
            problems.append(f"judged a CORRECT answer as FAIL: {f['q'][:40]} ({good['reason']})")
        if not bok:
            problems.append(f"judged a WRONG answer as PASS: {f['q'][:40]} ({bad['reason']})")
    if not problems:
        print(f"\n{GREEN}OK{RESET}  the judge prompt discriminates correct vs wrong on every fixture.")
        print("=" * 70)
        return 0
    print(f"\n{RED}FAIL{RESET}  judge calibration problems:")
    for p in problems:
        print(f"  - {p}")
    print("=" * 70)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Companion judgment-probe LLM judge (cross-model, free-tier)")
    ap.add_argument("--self-test", action="store_true", help="LIVE judge calibration (spends Gemini calls)")
    ap.add_argument("--ask", default=None)
    ap.add_argument("--answer", default=None)
    ap.add_argument("--rubric", default=None)
    args = ap.parse_args()
    if args.ask and args.answer and args.rubric:
        print(json.dumps(judge_pass(args.ask, args.answer, args.rubric), indent=2))
        return 0
    return self_test()


if __name__ == "__main__":
    sys.exit(main())
