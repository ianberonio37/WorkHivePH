"""
AI Companion Energy + Sustainability Validator (turns #195-#204)
"""
from __future__ import annotations
import os, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str: return read_file(VOICE_HANDLER_JS) or ""


SYMBOLS = {
    "enpi":     ["_energyUseIndex"],
    "carbon":   ["_carbonFromKwh", "_PH_GRID_CARBON_FACTOR", "0.717"],
    "peak":     ["_isPeakDemandBreach"],
    "anomaly":  ["_detectEnergyAnomaly"],
    "standby":  ["_standbyWaste"],
    "water":    ["_waterUseBreach"],
    "air_leak": ["_compressedAirLeakLoss"],
    "motor":    ["_motorEfficiencyDelta", "IE3"],
    "bundle":   ["_buildSustainabilityBundle"],
    "energy_q": ["_ENERGY_QUERY_RE", "_isEnergyQuery"],
    "wires":    ["ENERGY QUERY", "_isEnergyQuery(transcript)"],
}
LABELS = {
    "enpi":     "T195 _energyUseIndex (ISO 50001 EnPI)",
    "carbon":   "T196 _carbonFromKwh + PH grid factor 0.717",
    "peak":     "T197 _isPeakDemandBreach",
    "anomaly":  "T198 _detectEnergyAnomaly (5σ for electrical noise)",
    "standby":  "T199 _standbyWaste",
    "water":    "T200 _waterUseBreach",
    "air_leak": "T201 _compressedAirLeakLoss (dB → cfm → kWh/yr)",
    "motor":    "T202 _motorEfficiencyDelta against IE3 baseline",
    "bundle":   "T203 _buildSustainabilityBundle",
    "energy_q": "T204 _ENERGY_QUERY_RE + _isEnergyQuery",
    "wires":    "PHASE A wires — T204 ENERGY QUERY anchor live in perTurnAnchors",
}


def main() -> int:
    print("\033[1m\nAI Companion Energy + Sustainability Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    issues = []
    for k, syms in SYMBOLS.items():
        for s in syms:
            if s not in c:
                issues.append({"check": k, "reason": f"{s} missing."})
    n_pass, n_skip, n_fail = format_result(list(SYMBOLS.keys()), LABELS, issues)
    print()
    if n_fail == 0: print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
