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
    # ── Per-turn-anchor wiring (turns #175-#184 plumbed into prompt) ──
    "wire_incident": ["INCIDENT GATE", "_isIncidentReport(transcript)"],
    "wire_loto":     ["LOTO GATE", "_detectLotoIntent(transcript)", "energy isolation checklist", "zero-energy"],
    "wire_hot":      ["HOT WORK GATE", "_detectHotWorkIntent(transcript)", "hot-work permit", "fire watch"],
    "wire_confined": ["CONFINED SPACE GATE", "_detectConfinedSpaceIntent(transcript)", "PH OSHS limits", "19.5-23.5%", "LEL ≤10%"],
    "wire_ppe":      ["PPE MATRIX", "_isPpeQuery(transcript)", "authoritative matrix"],
    "wire_nearmiss": ["NEAR-MISS CAPTURE", "_isNearMissReport(transcript)", "safety_near_miss"],
    "wire_jsa":      ["JSA OFFER", "_shouldOfferJsa(transcript)", "4-step JSA"],
}
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
    "wire_incident": "WIRE T182 INCIDENT GATE anchor + dispatch on _isIncidentReport(transcript)",
    "wire_loto":     "WIRE T175 LOTO GATE anchor referencing isolation checklist + zero-energy verification",
    "wire_hot":      "WIRE T176 HOT WORK GATE anchor referencing hot-work permit + fire watch",
    "wire_confined": "WIRE T177 CONFINED SPACE GATE anchor referencing PH OSHS gas limits (O2/LEL)",
    "wire_ppe":      "WIRE T178 PPE MATRIX anchor flagged as authoritative (no LLM improvisation)",
    "wire_nearmiss": "WIRE T179 NEAR-MISS CAPTURE anchor routing to safety_near_miss",
    "wire_jsa":      "WIRE T180 JSA OFFER anchor with explicit 4-step structure",
}


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
    n_pass, n_skip, n_fail = format_result(list(SYMBOLS.keys()), LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
