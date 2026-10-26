"""
AI Companion Safety + Permit-to-Work Validator (turns #175-#184)
==================================================================
Forward-only L0 ratchet for the eighteenth 10-turn flywheel batch (2026-05-21).

  T175  LOTO intent detector
  T176  Hot-work intent
  T177  Confined-space intent
  T178  PPE query + matrix
  T179  Near-miss report
  T180  JSA prompt
  T181  Gas-test reading validator
  T182  Incident report trigger
  T183  Energy isolation checklist
  T184  Permit expiry check
"""

from __future__ import annotations
import os, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str:
    return read_file(VOICE_HANDLER_JS) or ""


SYMBOLS = {
    "loto":          ["_LOTO_RE", "_detectLotoIntent"],
    "hot_work":      ["_HOT_WORK_RE", "_detectHotWorkIntent"],
    "confined":      ["_CONFINED_RE", "_detectConfinedSpaceIntent"],
    "ppe":           ["_PPE_QUERY_RE", "_isPpeQuery", "_PPE_MATRIX", "_ppeFor", "hot_work:", "confined_space:", "chemical:", "electrical:", "height:"],
    "near_miss":     ["_NEAR_MISS_RE", "_isNearMissReport"],
    "jsa":           ["_JSA_NEED_RE", "_shouldOfferJsa", "_buildJsaTemplate"],
    "gas_test":      ["_validateGasReading", "O2_min", "LEL_max", "CO_max", "H2S_max"],
    "incident":      ["_INCIDENT_RE", "_isIncidentReport"],
    "isolation":     ["_energyIsolationChecklist", "electrical:", "mechanical:", "hydraulic:", "pneumatic:"],
    "permit_expiry": ["_permitTimeRemaining"],
}
# ── Wiring: where the rule reaches a MODEL (BRH-AP, 2026-10-27) ──────────────────────────────────────────────────────────
# These used to grep voice-handler.js for the anchor text - which sat in perTurnAnchors, a string no request carried, so
# every WIRE check certified a rule no model ever received (and two of them certified false text: "PH OSHS limits" for
# CO/H2S figures, and a "safety_near_miss" write that has no table and no writer). The rules are stated now by
# _shared/turn-steering.ts inside the prompt voice-journal-agent builds; the checks read that, and the agent's use of it.
STEERING_TS = "supabase/functions/_shared/turn-steering.ts"
AGENT_TS = "supabase/functions/voice-journal-agent/index.ts"
GATEWAY_TS = "supabase/functions/ai-gateway/index.ts"
WIRE = {
    "wire_agent":    [(AGENT_TS, 'from "../_shared/turn-steering.ts"'), (AGENT_TS, "turnSteering(rawMessage)"), (AGENT_TS, "steer.text + conv.text;"),
                      (AGENT_TS, "enforceSteering(clean, steer.kinds)"), (AGENT_TS, "steering: [...steer.kinds, ...conv.kinds]"),
                      (AGENT_TS, "steering_enforced: enf.enforced"), (GATEWAY_TS, "parsedEnvelope?.steering")],
    "wire_incident": [(STEERING_TS, "INCIDENT_RE.test(s)"), (STEERING_TS, "911"), (STEERING_TS, "Do NOT say you have flagged")],
    "wire_loto":     [(STEERING_TS, "LOTO GATE"), (STEERING_TS, "LOTO_RE.test(s)"), (STEERING_TS, "energy isolation checklist"),
                      (STEERING_TS, "zero-energy verified")],
    "wire_hot":      [(STEERING_TS, "HOT WORK GATE"), (STEERING_TS, "hot-work"), (STEERING_TS, "fire watch")],
    "wire_confined": [(STEERING_TS, "CONFINED SPACE GATE"), (STEERING_TS, "O2 19.5-23.5%"), (STEERING_TS, "10% of LEL"),
                      (STEERING_TS, "entry permit")],
    "wire_ppe":      [(STEERING_TS, "Answer ONLY from this matrix"), (STEERING_TS, "PPE_QUERY_RE.test(s)")],
    "wire_nearmiss": [(STEERING_TS, "NEAR_MISS_RE.test(s)"), (STEERING_TS, "Logbook"), (STEERING_TS, "Do NOT say you have filed")],
    "wire_jsa":      [(STEERING_TS, "4-step JSA"), (STEERING_TS, "JSA_NEED_RE.test(s)")],
}
# promises the model must never be told to make - each names a feature that does not exist
FORBIDDEN_PROMISES = ["SOS button", "file this as a near-miss", "PH OSHS limits"]
# while the browser keeps its exported copies (tests/journey-voice-companion-gates.spec.ts calls them), the triggers must
# be the same expression in both places - two copies drift
DRIFT = [("_LOTO_RE", "LOTO_RE"), ("_HOT_WORK_RE", "HOT_WORK_RE"), ("_CONFINED_RE", "CONFINED_RE"),
         ("_PPE_QUERY_RE", "PPE_QUERY_RE"), ("_NEAR_MISS_RE", "NEAR_MISS_RE"), ("_INCIDENT_RE", "INCIDENT_RE")]
LABELS = {
    "loto":          "T175 _LOTO_RE + _detectLotoIntent",
    "hot_work":      "T176 _HOT_WORK_RE + _detectHotWorkIntent",
    "confined":      "T177 _CONFINED_RE + _detectConfinedSpaceIntent",
    "ppe":           "T178 _PPE_QUERY_RE + _isPpeQuery + _PPE_MATRIX (hot_work/confined_space/chemical/electrical/height)",
    "near_miss":     "T179 _NEAR_MISS_RE + _isNearMissReport",
    "jsa":           "T180 _JSA_NEED_RE + _shouldOfferJsa + _buildJsaTemplate",
    "gas_test":      "T181 _validateGasReading with O2/LEL/CO/H2S limits",
    "incident":      "T182 _INCIDENT_RE + _isIncidentReport",
    "isolation":     "T183 _energyIsolationChecklist with electrical/mechanical/hydraulic/pneumatic",
    "permit_expiry": "T184 _permitTimeRemaining",
    "wire_agent":    "WIRE voice-journal-agent states turnSteering in its prompt, enforces the life-safety six after the model, reports both; the gateway passes them",
    "wire_incident": "WIRE server INCIDENT rule: care, the Safety Officer and 911, and no claim of having flagged anyone",
    "wire_loto":     "WIRE server LOTO GATE with the isolation checklist + zero-energy verification",
    "wire_hot":      "WIRE server HOT WORK GATE: hot-work permit + fire watch",
    "wire_confined": "WIRE server CONFINED SPACE GATE: O2 19.5-23.5%, under 10% of LEL, CO/H2S per the entry permit",
    "wire_ppe":      "WIRE server PPE rule answers only from the matrix",
    "wire_nearmiss": "WIRE server NEAR-MISS rule points to the Logbook and never claims a filing",
    "wire_jsa":      "WIRE server JSA rule with the explicit 4-step structure",
    "no_false_promise": "No safety rule tells the model to promise a feature that does not exist (SOS button, near-miss filing)",
    "no_drift":      "While the browser keeps exported copies, each trigger is the same expression on both sides",
}


def _regex_src(text: str, name: str) -> str | None:
    import re as _re
    m = _re.search(r"(?:const|export const)\s+" + _re.escape(name) + r"\s*=\s*(/.+?/[a-z]*);", text)
    return m.group(1) if m else None


def server_issues(client: str) -> list:
    """the WIRE / promise / drift checks over the server files (and the client copies, for drift)"""
    issues = []
    texts = {f: (read_file(f) or "") for f in (STEERING_TS, AGENT_TS, GATEWAY_TS)}
    for k, needles in WIRE.items():
        for f, n in needles:
            if n not in texts[f]:
                issues.append({"check": k, "reason": f"{n!r} missing from {f}"})
    for bad in FORBIDDEN_PROMISES:
        code = "\n".join(ln for ln in texts[STEERING_TS].splitlines() if not ln.lstrip().startswith("//"))
        if bad in code:
            issues.append({"check": "no_false_promise", "reason": f"turn-steering.ts tells the model {bad!r} - that does not exist"})
    for cn, sn in DRIFT:
        a, b = _regex_src(client, cn), _regex_src(texts[STEERING_TS], sn)
        if a is not None and a != b:
            issues.append({"check": "no_drift", "reason": f"voice-handler.js {cn} differs from turn-steering.ts {sn}"})
    return issues


def main() -> int:
    print("\033[1m\nAI Companion Safety + Permit-to-Work Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")
    issues = []
    for k, syms in SYMBOLS.items():
        for s in syms:
            if s not in c:
                issues.append({"check": k, "reason": f"{s} missing."})
    issues += server_issues(c)
    n_pass, n_skip, n_fail = format_result(list(SYMBOLS.keys()) + list(WIRE.keys()) + ["no_false_promise", "no_drift"],
                                           LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
