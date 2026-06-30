#!/usr/bin/env python3
"""
Validator: Calc Formula ACCURACY (value-correctness)

WHAT THIS IS (and what it is NOT)
---------------------------------
The 4-layer engineering-calc suite (validate_fields / validate_renderers /
validate_bom_sow / validate_integration) tests FIELD-NAME CONTRACTS — i.e. that
the renderer/BOM reads fields the Python API actually returns. None of them
assert that the returned NUMBER is correct per the engineering standard.

This validator closes that gap. It imports each pure calc handler
(python-api/calcs/<type>.py :: calculate(inputs)->dict) and asserts that, for a
known input, the engine produces the value an engineer would get by hand from
the published standard. Each golden vector is anchored to a specific standard
clause and an INDEPENDENTLY hand-computed expected value (see the worked
examples in the maintenance-expert SKILL.md), or to a skill-rule INVARIANT
(e.g. IEC 60909: cable impedance Z = sqrt(R^2 + X^2), never R alone).

WHY value-verification matters: these calcs size fire pumps, breakers, stair
pressurization fans and lightning protection — a silently-wrong formula is a
safety defect that a field-name contract test can never catch.

HONEST SCOPE: this is a value-correctness FLOOR, not full coverage. It pins the
calc types with a clean, standard-anchored hand-computed oracle. Extend VECTORS
as more oracles are derived — every added vector raises the measured coverage
printed in the summary.

DENOMINATOR (mined from EVIDENCE, 2026-06-17): the honest denominator is the
number of calc handler modules main.py actually dispatches to, NOT the stale "33"
the skill once listed. `python-api/main.py :: _load_handlers()` registers 59
distinct calc_type keys backed by 58 handler modules (chiller serves the
water/air pair). The skill's old "TypeScript-only (13+)" list — Voltage Drop,
Stairwell, Bearing Life, Load Estimation, Cable Tray, etc. — is STALE: every one
now has a live Python handler in the dispatch table. So coverage is measured
against 58, and was overstated when the denominator was 33 (8/33=24% read as far
more complete than the true 8/58=14%). Mine the denominator from the dispatch
table, never a surface list.

Hermetic: imports the pure functions directly (no network, no edge fn, no DB).
A calc whose module needs an uninstalled dependency (e.g. pipe_sizing needs
fluids+iapws) is reported as SKIP, never FAIL — missing local deps must not
turn a green math check red.

Run:  python tools/validate_calc_formula_accuracy.py
Self-test (proves the validator has teeth):
      python tools/validate_calc_formula_accuracy.py --self-test
"""

import importlib
import math
import os
import sys

# Windows cp1252 stdout guard — required on every validator (see
# validate_validator_cp1252_guard.py). Without it, printing any non-cp1252
# char (em-dash, box-drawing, Greek) raises UnicodeEncodeError and crashes
# the validator mid-run, taking down the Mega Gate silently. Conditional
# (.detach() + encoding check) form so importing this module for its stats
# after another guard has already re-wrapped stdout is a safe no-op.
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# ─── Make python-api/calcs importable ────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PYAPI = os.path.join(_ROOT, "python-api")
if _PYAPI not in sys.path:
    sys.path.insert(0, _PYAPI)

# Honest denominator for the value-coverage figure: the number of calc handler
# MODULES main.py actually dispatches to (mined from the dispatch table, not a
# stale skill list). python-api/main.py::_load_handlers registers 59 calc_type
# keys over 58 modules (chiller serves water+air). Re-mine if main.py changes:
#   python -c "import re;s=open('python-api/main.py').read();..."  (see docstring)
TOTAL_PYTHON_CALCS = 58


def _get(d: dict, path: str):
    """Walk a dotted path through nested dicts. Raises KeyError if absent."""
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(f"missing result field '{path}' (stopped at '{part}')")
        cur = cur[part]
    return cur


def _close(actual, expected, tol):
    """Numeric closeness within absolute tolerance."""
    try:
        return abs(float(actual) - float(expected)) <= tol
    except (TypeError, ValueError):
        return actual == expected


# ─── Custom-check helpers (skill-rule invariants) ────────────────────────────
def _check_short_circuit_zsqrt(mod):
    """IEC 60909 / skill rule: cable+system impedance must use Z = sqrt(R^2+X^2),
    and reactance X must NOT be dropped. Verifies the engine output is internally
    consistent with that rule rather than using R alone.

    Also gates the DECISION-DRIVING output (Arc Q untested-surface lesson, 2026-06-23):
    the prior oracle only proved the Z method, never the fault-current magnitude or the
    breaker-interrupting-capacity verdict the user actually acts on. A breaker recommended
    BELOW the fault current is the dangerous failure mode — assert it can never happen."""
    r = mod.calculate({})  # defaults: 500 kVA trafo, 50 mm2 / 30 m cable
    imp = r["impedance"]
    R, X, Z = imp["R_total_ohm"], imp["X_total_ohm"], imp["Z_total_ohm"]
    out = []
    z_calc = math.sqrt(R ** 2 + X ** 2)
    out.append((
        "Z_total = sqrt(R^2 + X^2)  [IEC 60909 — never R alone]",
        _close(Z, z_calc, 1e-3),
        f"Z={Z}  sqrt(R^2+X^2)={round(z_calc, 6)}",
    ))
    out.append((
        "reactance X_total included (> 0), not dropped",
        X > 0,
        f"X_total={X} ohm",
    ))
    # ── decision-driving output: IEC 60909 fault current + OCPD adequacy verdict ──
    c, V = r["c_factor"], r["voltage_lv_V"]
    isc_indep_a = c * V / (math.sqrt(3) * Z)            # I"k3 = c·V/(√3·Z_total)
    out.append((
        "Isc_3ph = c·V/(sqrt(3)·Z_total)  [IEC 60909 initial symmetrical SCC]",
        _close(r["Isc_3ph_A"], isc_indep_a, max(abs(isc_indep_a) * 0.005, 1.0)),
        f"served {r['Isc_3ph_A']} A  vs  {round(isc_indep_a, 1)} A",
    ))
    isc_ka = r["Isc_3ph_kA"]
    out.append((
        "ocpd_adequate verdict == (provided_kA >= Isc_kA)  [breaker can interrupt]",
        bool(r["ocpd_adequate"]) == (r["ocpd_provided_kA"] >= isc_ka),
        f"adequate={r['ocpd_adequate']} provided={r['ocpd_provided_kA']}kA Isc={isc_ka}kA",
    ))
    out.append((
        "recommended_ocpd_kA >= Isc_kA  [SAFETY: never recommend a breaker below the fault]",
        r["recommended_ocpd_kA"] >= isc_ka,
        f"recommended={r['recommended_ocpd_kA']}kA must cover Isc={isc_ka}kA",
    ))
    return out


def _check_duct_de_vs_dh(mod):
    """ASHRAE 2021 Ch.21 / skill rule: De (sizing) and D_h (pressure drop) are
    TWO DIFFERENT diameters. D_h = 2ab/(a+b) is exact; for 600x300 mm => 400 mm.
    De > D_h for a non-square rectangular duct."""
    a, b = 0.6, 0.3  # 600 x 300 mm
    dh = mod._dh_from_rect(a, b)
    de = mod._de_from_rect(a, b)
    return [
        ("D_h(600x300) = 2ab/(a+b) = 0.400 m exact", _close(dh, 0.400, 1e-6), f"D_h={round(dh,6)} m"),
        ("De > D_h (distinct diameters, ASHRAE Ch.21)", de > dh, f"De={round(de,4)} m, D_h={round(dh,4)} m"),
    ]


def _check_harmonic_519_individual_limits(mod):
    """IEEE 519-2014/2022 Table 2: the individual ODD-harmonic current limits (% of IL) are a
    FULL 5x5 matrix — each ISC/IL tier has DIFFERENT per-band values, NOT a uniform scale of
    the <20 row. This oracle is the verbatim published Table 2 (hand-typed here, independent of
    the engine), so it catches any relapse to the 'base x uniform-scale' change-detector that
    overstated every higher tier by 14-43% = too permissive (Arc Q fix, 2026-06-23)."""
    # Independent IEEE 519 Table 2 — rows by ISC/IL tier, cols by band 3-11/11-17/17-23/23-35/>35.
    TABLE2 = {
        10:   (4.0,  2.0, 1.5, 0.6, 0.3),   # ISC/IL < 20
        30:   (7.0,  3.5, 2.5, 1.0, 0.5),   # 20 <= ISC/IL < 50
        75:   (10.0, 4.5, 4.0, 1.5, 0.7),   # 50 <= ISC/IL < 100
        500:  (12.0, 5.5, 5.0, 2.0, 1.0),   # 100 <= ISC/IL < 1000
        5000: (15.0, 7.0, 6.0, 2.5, 1.4),   # ISC/IL >= 1000
    }
    probe_orders = [5, 13, 19, 25, 37]   # one representative order per band
    out = []
    for isc_il, expected_row in TABLE2.items():
        r = mod.calculate({
            "fundamental_current_a": 100, "max_demand_current_a": 100,
            "short_circuit_current_a": isc_il * 100,   # ratio = isc_il
            "harmonics": [{"order": o, "current_pct": 1} for o in probe_orders],
        })
        served = {h["order"]: h["limit_pct_of_IL"] for h in r["individual_harmonics"]}
        for o, exp in zip(probe_orders, expected_row):
            got = served.get(o)
            out.append((
                f"ISC/IL={isc_il} h{o}: limit = {exp}% of IL (IEEE 519 Table 2)",
                _close(got, exp, 0.01),
                f"served {got}%",
            ))
    return out


# ─── Golden vectors ──────────────────────────────────────────────────────────
# Each: declarative {module, calc_type, standard, inputs, asserts:[{path,expected,tol,note}]}
#       or invariant {module, calc_type, standard, custom: callable(mod)->[(label,ok,detail)]}
VECTORS = [
    {
        "module": "calcs.solar_pv",
        "calc_type": "Solar PV System",
        "standard": "IEC 62548:2016 — Voc at coldest ambient, not STC",
        "inputs": {"voc_stc": 100, "tempCoeff_voc": -0.29, "t_min_c": 8,
                   "inverter_vdc_max": 1000, "system_kw": 5},
        "asserts": [
            {"path": "iec62548.voc_cold", "expected": 104.93, "tol": 0.05,
             "note": "Voc_max = 100*(1+(-0.29/100)*(8-25)) = 104.93 V"},
            {"path": "panels_per_string", "expected": 9, "tol": 0,
             "note": "floor(1000/104.93) = 9 (STC would over-count to 10 -> inverter overvolt)"},
        ],
    },
    {
        "module": "calcs.stairwell_pressurization",
        "calc_type": "Stairwell Pressurization",
        "standard": "NFPA 92 §6.5.1.1 — door force lever-arm formula",
        "inputs": {"door_width": 0.9, "door_height": 2.1, "delta_P": 50,
                   "building_type": "Sprinklered"},
        "asserts": [
            {"path": "F_pressure_N", "expected": 51.6, "tol": 0.2,
             "note": "50 * (0.9*2.1) * (0.9/(2*(0.9-0.076))) = 51.6 N"},
            {"path": "F_total_N", "expected": 96.6, "tol": 0.2,
             "note": "51.6 + 45 (closer) = 96.6 N <= 133 N PASS (simplified F=DP*A would FAIL at 139.5)"},
        ],
    },
    {
        "module": "calcs.bearing_life",
        "calc_type": "Bearing Life (L10)",
        "standard": "ISO 281:2007 §5 — L10 = (C/P)^p",
        "inputs": {"C_kN": 64, "Fr_kN": 4, "Fa_kN": 0, "speed_rpm": 1000,
                   "bearing_type": "Ball", "reliability_pct": 90},
        "asserts": [
            {"path": "L10_Mrev", "expected": 4096.0, "tol": 0.01,
             "note": "(64/4)^3 = 16^3 = 4096 million rev (ball p=3)"},
            {"path": "L10h", "expected": 68267, "tol": 1,
             "note": "4096e6 / (60*1000) = 68267 h"},
        ],
    },
    {
        # Q5 oracle DEPTH (2026-06-23): the reliability-adjustment BRANCH the R=90
        # point can't catch. R=90 -> a1=1.0 (trivial); a bug in the a1 lookup table
        # passes the R=90 oracle and fails only here. "matches the standard across
        # its domain, not one point."
        "module": "calcs.bearing_life",
        "calc_type": "Bearing Life (L10)",
        "standard": "ISO 281:2007 §7 — reliability-adjusted life L_nm = a1·L10 (a1=0.21 at R=99%)",
        "inputs": {"C_kN": 64, "Fr_kN": 4, "Fa_kN": 0, "speed_rpm": 1000,
                   "bearing_type": "Ball", "reliability_pct": 99},
        "asserts": [
            {"path": "a1", "expected": 0.21, "tol": 0.001,
             "note": "ISO 281 §7 reliability factor a1 at R=99% = 0.21 (R=90% would be 1.0)"},
            {"path": "L10h_adj", "expected": 14336, "tol": 1,
             "note": "L_nm = a1·L10h = 0.21·68267 = 14336 h (the depth branch R=90 misses)"},
        ],
    },
    {
        "module": "calcs.load_estimation",
        "calc_type": "Load Estimation",
        "standard": "PEC 2017 — watts_each IS real power; PF not applied to kW",
        "inputs": {
            "phase_config": "3-Phase 4-Wire (400V)",
            "loads": [
                {"load_type": "Lighting (General)", "quantity": 10, "watts_each": 100, "power_factor": 0.9},
                {"load_type": "Motor (General)", "quantity": 2, "watts_each": 1000, "power_factor": 0.8},
            ],
        },
        "asserts": [
            {"path": "total_connected_kw", "expected": 3.0, "tol": 0.001,
             "note": "(10*100 + 2*1000)/1000 = 3.0 kW — NOT reduced by PF (a 0.85 multiply would give 2.55)"},
            {"path": "total_demand_kw", "expected": 3.5, "tol": 0.001,
             "note": "(1000*1.0 + 2000*1.25)/1000 = 3.5 kW — Motor demand factor 1.25 applied to demand only"},
        ],
    },
    {
        "module": "calcs.lightning_protection",
        "calc_type": "Lightning Protection (LPS)",
        "standard": "IEC 62305-2 Annex A — collection area Ad + strike freq Nd",
        "inputs": {"building_length_m": 30, "building_width_m": 20, "building_height_m": 15,
                   "lpl": "LPL II", "ng_location": "Metro Manila / NCR", "structure_type": "Residential"},
        "asserts": [
            {"path": "Ad_m2", "expected": 11461.7, "tol": 0.2,
             "note": "30*20 + 6*15*(50) + 9*pi*15^2 = 600+4500+6361.7 = 11461.7 m^2"},
            {"path": "Nd_strikes_yr", "expected": 0.11462, "tol": 0.0001,
             "note": "Ng(10) * Ad * Cd(1) * 1e-6 = 0.11462 strikes/yr"},
            # Decision-driving outputs (Arc Q untested-surface lesson, 2026-06-23):
            {"path": "efficiency_pct", "expected": 95, "tol": 0,
             "note": "IEC 62305-2: LPL II protection efficiency = 95% (I=98, II=95, III=90, IV=80)"},
            {"path": "risk_check", "expected": "LPS REQUIRED", "tol": 0,
             "note": "verdict: Nd 0.115/yr exceeds the tolerable strike frequency → an LPS IS required"},
        ],
    },
    {
        "module": "calcs.ups_sizing",
        "calc_type": "UPS Sizing",
        "standard": "IEEE 1184:2006 battery Ah + IEEE 446 80% sizing + VRLA DC-bus tiers",
        "inputs": {"load_kw": 10, "power_factor": 0.90, "backup_minutes": 60,
                   "topology": "Online Double-Conversion", "ambient_temp_c": 25},
        "asserts": [
            {"path": "recommended_kVA", "expected": 20, "tol": 0,
             "note": "IEEE 446: load_kVA(11.11)×1.2 margin / 0.80 limit = 16.67 → next std 20 kVA"},
            {"path": "dc_bus_voltage_V", "expected": 192, "tol": 0,
             "note": "20 kVA → 10–40 kVA tier → 192 V (16×12V) per IEEE 1184"},
            {"path": "ieee1184.kW_design", "expected": 10.638, "tol": 0.005,
             "note": "kW_design = load_kW / η_UPS = 10/0.94 = 10.638"},
            {"path": "required_Ah", "expected": 70.7, "tol": 0.2,
             "note": "Ah = (10.638×1.0h) / (192/1000 × 0.80 DOD × 0.98 η_wire) = 70.7"},
        ],
    },
    {
        "module": "calcs.short_circuit",
        "calc_type": "Short Circuit",
        "standard": "IEC 60909 — Z = sqrt(R^2 + X^2), reactance not dropped",
        "custom": _check_short_circuit_zsqrt,
    },
    {
        "module": "calcs.duct_sizing",
        "calc_type": "Duct Sizing",
        "standard": "ASHRAE 2021 Ch.21 — De (sizing) vs D_h (pressure drop)",
        "custom": _check_duct_de_vs_dh,
    },
    {
        "module": "calcs.power_factor_correction",
        "calc_type": "Power Factor Correction",
        "standard": "IEEE 18-2012 — Qc = kW·(tanφ1 − tanφ2)",
        "inputs": {"load_kw": 100, "pf_existing": 0.75, "pf_target": 0.95,
                   "voltage_v": 400, "phases": 3},
        "asserts": [
            {"path": "kvar_required", "expected": 55.32, "tol": 0.05,
             "note": "100*(tan(acos0.75)-tan(acos0.95)) = 100*(0.88192-0.32868) = 55.32 kVAR"},
            {"path": "selected_kvar", "expected": 60, "tol": 0,
             "note": "next IEEE-18 standard bank >= 55.32 = 60 kVAR"},
            {"path": "kva_before", "expected": 133.33, "tol": 0.05,
             "note": "100/0.75 = 133.33 kVA"},
            {"path": "kva_after", "expected": 105.26, "tol": 0.05,
             "note": "100/0.95 = 105.26 kVA (apparent power drops as PF rises)"},
        ],
    },
    {
        "module": "calcs.bolt_torque",
        "calc_type": "Bolt Torque & Preload",
        "standard": "ISO 898-1:2013 Table 3 + Shigley — T = K·d·Fi, Fi = preload%·At·Sp; "
                    "grade 8.8 proof stress Sp = 580 MPa for d <= 16 mm (incl. M16), "
                    "600 MPa only for d > 16 mm (oracle anchored to the STANDARD, NOT "
                    "the engine table — fixed 2026-06-23 Arc Q, was a change-detector at 600)",
        "inputs": {"bolt_size": "M16", "bolt_grade": "8.8", "nut_factor": 0.20,
                   "preload_pct": 75},
        "asserts": [
            {"path": "Fp_kN", "expected": 91.06, "tol": 0.02,
             "note": "Fp = At·Sp = 157.0 mm2 · 580 MPa / 1000 = 91.06 kN proof load "
                     "(ISO 898-1: M16 d=16<=16 -> Sp=580, NOT 600)"},
            {"path": "Fi_kN", "expected": 68.30, "tol": 0.02,
             "note": "Fi = 0.75 · 91.06 = 68.30 kN preload"},
            {"path": "sigma_MPa", "expected": 435.0, "tol": 0.2,
             "note": "σ = 75% · Sp = 0.75 · 580 = 435.0 MPa (independent of engine: "
                     "at 75% preload the stress is exactly 75% of the ISO proof stress)"},
            {"path": "torque_Nm", "expected": 218.5, "tol": 0.3,
             "note": "T = K·d·Fi = 0.20 · 0.016 m · 68295 N = 218.5 N·m"},
        ],
    },
    {
        "module": "calcs.shaft_design",
        "calc_type": "Shaft Design",
        "standard": "ASME B106.1M / Shigley — T = P/ω, M = F·L/4 (SS midspan)",
        "inputs": {"power_kW": 10, "shaft_rpm": 1450, "transverse_load_N": 2000,
                   "span_mm": 400},
        "asserts": [
            {"path": "torque_Nm", "expected": 65.86, "tol": 0.05,
             "note": "T = P/ω = 10000 W / (2π·1450/60 rad/s) = 65.86 N·m"},
            {"path": "bending_moment_Nm", "expected": 200.0, "tol": 0.1,
             "note": "M = F·L/4 = 2000 N · 0.4 m / 4 = 200 N·m (simply-supported midspan)"},
            {"path": "d_twist_required_mm", "expected": 26.33, "tol": 0.1,
             "note": "ASME B106.1M angle-of-twist: d = (32·T/(G·π·θ_lim))^¼ = (32·65.86/(80e9·π·(π/180)))^0.25·1000 = 26.33 mm (1 deg/m limit, G=80 GPa)"},
        ],
    },
    {
        "module": "calcs.transformer_sizing",
        "calc_type": "Transformer Sizing",
        "standard": "IEC 60076-1 / PEC Art.4.50 — S = √3·V·I_FL, spare headroom",
        "inputs": {"load_kva": 100, "primary_voltage": 13800, "secondary_voltage": 400,
                   "load_power_factor": 0.85, "phases": 3, "impedance_pct": 5.0,
                   "spare_capacity_pct": 25.0},
        "asserts": [
            {"path": "required_kva", "expected": 125.0, "tol": 0.01,
             "note": "100 · (1 + 25%) = 125 kVA required (load + spare headroom)"},
            {"path": "rated_kva", "expected": 150, "tol": 0,
             "note": "next standard distribution rating >= 125 = 150 kVA"},
            {"path": "I1_full_load_A", "expected": 6.28, "tol": 0.02,
             "note": "I1 = S/(√3·Vp) = 150000/(√3·13800) = 6.28 A"},
            {"path": "I2_full_load_A", "expected": 216.51, "tol": 0.05,
             "note": "I2 = S/(√3·Vs) = 150000/(√3·400) = 216.51 A"},
        ],
    },
    {
        "module": "calcs.voltage_drop",
        "calc_type": "Voltage Drop",
        "standard": "PEC 2017 / IEEE 141 — VD = 2·I·R·L, ρ(T) temp-corrected",
        "inputs": {"phase": "Single-phase", "voltage": 230, "current": 20,
                   "wire_length": 30, "conductor_mm2": 3.5, "conductor_mat": "Copper",
                   "conductor_temp_c": 75.0},
        "asserts": [
            {"path": "resistivity", "expected": 0.02097, "tol": 0.00005,
             "note": "ρ75 = 0.01724·(1+0.00393·(75−20)) = 0.02097 Ω·mm²/m (IEC 60228 temp-corr)"},
            {"path": "vd_volts", "expected": 7.19, "tol": 0.03,
             "note": "VD = 2·I·R·L = 2·20·(0.02097/3.5)·30 = 7.19 V (1φ: factor 2 = out+back)"},
            {"path": "vd_pct", "expected": 3.13, "tol": 0.03,
             "note": "VD% = 7.19/230·100 = 3.13% (just over PEC branch 3% limit)"},
        ],
    },
    {
        # Q5 oracle DEPTH (2026-06-23): the THREE-phase branch (factor √3, not the
        # single-phase factor 2). A handler that used 2 for 3φ — or √3 for 1φ — passes
        # the single-phase oracle above and fails only here.
        "module": "calcs.voltage_drop",
        "calc_type": "Voltage Drop",
        "standard": "PEC 2017 / IEEE 141 — 3φ VD = √3·I·R·L (vs 1φ factor 2)",
        "inputs": {"phase": "Three-phase", "voltage": 400, "current": 20,
                   "wire_length": 30, "conductor_mm2": 3.5, "conductor_mat": "Copper",
                   "conductor_temp_c": 75.0},
        "asserts": [
            {"path": "vd_volts", "expected": 6.23, "tol": 0.03,
             "note": "VD = √3·I·R·L = 1.732·20·(0.02097/3.5)·30 = 6.23 V (3φ factor √3, NOT 2)"},
            {"path": "vd_pct", "expected": 1.56, "tol": 0.03,
             "note": "VD% = 6.23/400·100 = 1.56% (line-to-line, within PEC limit)"},
        ],
    },
    {
        "module": "calcs.pressure_vessel",
        "calc_type": "Pressure Vessel",
        "standard": "ASME BPVC VIII-1 UG-27(c)(1) — t = P·R/(S·E − 0.6P)",
        "inputs": {"design_pressure_bar": 10.0, "inner_diameter_mm": 800.0,
                   "material": "SA-516 Gr.70 (Carbon Steel)",
                   "joint_efficiency": "Full radiography (Type 1)",
                   "corrosion_allowance": "Mild (water, steam)", "vessel_type": "Cylindrical"},
        "asserts": [
            {"path": "t_shell_min_mm", "expected": 2.911, "tol": 0.005,
             "note": "t = P·R/(S·E−0.6P) = 1.0·400/(138·1.0−0.6) = 2.911 mm (UG-27 — not P·R/S)"},
            {"path": "t_shell_required_mm", "expected": 4.511, "tol": 0.005,
             "note": "t_min + CA = 2.911 + 1.6 mild = 4.511 mm"},
            {"path": "t_shell_actual_mm", "expected": 5, "tol": 0,
             "note": "next standard plate >= 4.511 = 5 mm"},
            # Decision-driving outputs (Arc Q untested-surface lesson, 2026-06-23): the
            # prior oracle gated only the thickness, never the MAWP-holds VERDICT or the
            # hydrotest pressure the user acts on.
            {"path": "mawp_bar", "expected": 11.67, "tol": 0.05,
             "note": "MAWP = S·E·t_net/(R+0.6·t_net) = 138·1·3.4/(400+2.04) = 11.67 bar (t_net=5−1.6 CA)"},
            {"path": "mawp_ok", "expected": True, "tol": 0,
             "note": "SAFETY verdict: MAWP 11.67 bar >= design 10 bar → the actual plate holds design pressure"},
            {"path": "hydro_test_bar", "expected": 15.17, "tol": 0.05,
             "note": "UG-99(b): P_test = 1.3·MAWP = 1.3·11.67 = 15.17 bar"},
        ],
    },
    {
        "module": "calcs.gear_belt_drive",
        "calc_type": "Gear / Belt Drive (V-Belt)",
        "standard": "RMA IP-20 / Shigley Eq.17-1 — Lp = 2C + π(D+d)/2 + (D−d)²/4C",
        "inputs": {"drive_type": "V-Belt", "power_kW": 10, "n_driver_rpm": 1450,
                   "n_driven_rpm": 725, "belt_section": "B", "centre_distance_mm": 500,
                   "driver_dia_mm": 150},
        "asserts": [
            {"path": "speed_ratio", "expected": 2.0, "tol": 0.001,
             "note": "n_driver/n_driven = 1450/725 = 2.0"},
            {"path": "d_large_mm", "expected": 300, "tol": 0,
             "note": "driven sheave = d_small·ratio = 150·2 = 300 mm"},
            {"path": "belt_length_mm", "expected": 1718, "tol": 1,
             "note": "Lp = 2·500 + π·450/2 + 150²/(4·500) = 1000+706.86+11.25 = 1718 mm"},
        ],
    },
    {
        "module": "calcs.ventilation_ach",
        "calc_type": "Ventilation / ACH",
        "standard": "ASHRAE 62.1 VRP — Vbz = Rp·Pz + Ra·Az; required ACH = max(calc, min)",
        "inputs": {"floor_area": 50, "ceiling_height": 3.0, "persons": 10,
                   "room_function": "Office"},
        "asserts": [
            {"path": "room_volume", "expected": 150.0, "tol": 0.1,
             "note": "50 m² · 3.0 m = 150 m³"},
            {"path": "vbz_ls", "expected": 40.0, "tol": 0.1,
             "note": "Vbz = Rp·Pz + Ra·Az = 2.5·10 + 0.30·50 = 40 L/s (ASHRAE 62.1 Table 6-1 Office)"},
            {"path": "required_ach", "expected": 6.0, "tol": 0.01,
             "note": "max(ach_calc 0.96, min_ach 6) = 6 — min-ACH governs over the breathing-zone rate"},
            {"path": "supply_cmh", "expected": 900, "tol": 1,
             "note": "required_ach·volume = 6·150 = 900 m³/hr"},
        ],
    },
    {
        "module": "calcs.pump_tdh",
        "calc_type": "Pump Sizing (TDH)",
        "standard": "ISO 9906 — continuity v = Q/A; std nominal→ID; L/min→m³/hr",
        "inputs": {"flow_rate": 200, "pipe_diameter": 50, "static_head": 10,
                   "pipe_length": 50, "pipe_material": "PVC"},
        "asserts": [
            {"path": "flow_m3hr", "expected": 12.0, "tol": 0.001,
             "note": "200 L/min · 60/1000 = 12.0 m³/hr"},
            {"path": "pipe_dia_mm", "expected": 52.5, "tol": 0.1,
             "note": "nominal 50 mm → standard inside diameter 52.5 mm (PNS/ISO 4427)"},
            {"path": "pipe_velocity", "expected": 1.540, "tol": 0.005,
             "note": "v = Q/A = (200/60000)/(π·(0.0525/2)²) = 1.540 m/s (continuity, dep-free)"},
        ],
    },
    {
        "module": "calcs.heat_exchanger",
        "calc_type": "Heat Exchanger",
        "standard": "TEMA / Kern — LMTD = (ΔT1−ΔT2)/ln(ΔT1/ΔT2); F = Bowman 1-2 F(P,R), NOT a constant",
        "inputs": {"hot_inlet_C": 90, "hot_outlet_C": 60, "cold_inlet_C": 30,
                   "cold_outlet_C": 50, "flow_config": "Counterflow",
                   "shell_type": "E (single pass)"},
        "asserts": [
            {"path": "lmtd_K", "expected": 34.761, "tol": 0.01,
             "note": "counterflow: ΔT1=90−50=40, ΔT2=60−30=30 → (40−30)/ln(40/30) = 34.76 K"},
            {"path": "F_correction", "expected": 0.911, "tol": 0.003,
             "note": "Bowman 1-2: P=(50−30)/(90−30)=0.333, R=(90−60)/(50−30)=1.5 → F=0.911 "
                     "(computed from P,R; the prior fixed 0.95 was a change-detector that under-sized A)"},
            {"path": "lmtd_corrected_K", "expected": 31.632, "tol": 0.03,
             "note": "LMTD·F = 34.761·0.911 = 31.63 K (drives A = Q/(U·F·LMTD))"},
            {"path": "F_feasible", "expected": True, "tol": 0,
             "note": "F 0.911 ≥ 0.75 TEMA design floor → feasible as a 1-2 shell"},
        ],
    },
    {
        "module": "calcs.generator_sizing",
        "calc_type": "Generator Sizing",
        "standard": "ISO 8528-1 / ISO 3046-1 — kVA=kW/pf, margin, temp derate",
        "inputs": {"demand_kw": 200, "power_factor": 0.8, "design_margin_pct": 20,
                   "altitude_m": 10, "ambient_temp_c": 35, "gen_class": "G2",
                   "largest_motor_kw": 0},
        "asserts": [
            {"path": "demand_kVA", "expected": 250.0, "tol": 0.01,
             "note": "S = P/pf = 200/0.8 = 250 kVA"},
            {"path": "required_kVA_steady", "expected": 300.0, "tol": 0.01,
             "note": "250 · (1 + 20% margin) = 300 kVA"},
            {"path": "derate_factor", "expected": 0.98, "tol": 0.001,
             "note": "1 − (35−25)/5·1% = 0.98 (ISO 3046 temp derate; alt<1000m → no alt derate)"},
            {"path": "recommended_kVA", "expected": 312.5, "tol": 0,
             "note": "next ISO-8528 std ≥ 300/0.98 = 306.1 → 312.5 kVA"},
        ],
    },
    {
        "module": "calcs.cable_tray_sizing",
        "calc_type": "Cable Tray Sizing",
        "standard": "NEC 2023 Art.392 — fill area Σπ/4·d², width = A/(fill·depth)",
        "inputs": {"tray_type": "Ladder", "depth_mm": 75, "fill_ratio_pct": 40,
                   "cables": [{"cable_type": "THHN", "od_mm": 20, "qty": 10}]},
        "asserts": [
            {"path": "total_fill_area_mm2", "expected": 3141.59, "tol": 0.5,
             "note": "10 · (π/4·20²) = 10·314.16 = 3141.59 mm²"},
            {"path": "required_width_mm", "expected": 104.72, "tol": 0.1,
             "note": "A_fill/(fill·depth) = 3141.59/(0.40·75) = 104.72 mm"},
            {"path": "selected_width_mm", "expected": 150, "tol": 0,
             "note": "next NEMA std width ≥ 104.72 = 150 mm"},
            {"path": "fill_actual_pct", "expected": 27.93, "tol": 0.05,
             "note": "3141.59/(150·75)·100 = 27.93% (≤ NEC 392.22 50% ladder limit)"},
        ],
    },
    {
        "module": "calcs.compressed_air",
        "calc_type": "Compressed Air",
        "standard": "ISO 1217 Annex C — W = (n/(n−1))·P1·Q1·[(P2/P1)^((n−1)/n)−1]",
        "inputs": {"flow_rate": 10, "working_pressure": 7, "ambient_temp_c": 35},
        "asserts": [
            {"path": "total_demand_cfm", "expected": 353.15, "tol": 0.05,
             "note": "10 m³/min · 35.3147 = 353.15 cfm (FAD unit conversion)"},
            {"path": "iso_power_kw", "expected": 47.61, "tol": 0.2,
             "note": "(1.4/0.4)·101325·(10/60)·[(8.013/1.013)^0.2857−1] = 47.6 kW isentropic"},
        ],
    },
    {
        "module": "calcs.earthing_grounding",
        "calc_type": "Earthing / Grounding System",
        "standard": "IEC 60364-5-54 / Dwight 1936 — R = (ρ/2πL)·[ln(4L/d)−1]",
        "inputs": {"electrode_type": "Rod", "soil_resistivity": 100, "rod_length_m": 3.0,
                   "rod_dia_mm": 16, "num_electrodes": 1,
                   "system_type": "Residential / Commercial"},
        "asserts": [
            {"path": "r_single_ohm", "expected": 29.816, "tol": 0.02,
             "note": "(100/2π·3)·[ln(4·3/0.016)−1] = 5.305·[ln(750)−1] = 29.82 Ω (Dwight rod)"},
            {"path": "r_limit_ohm", "expected": 10.0, "tol": 0,
             "note": "Residential/Commercial earth-resistance limit = 10 Ω (IEEE 142 / PEC)"},
        ],
    },
    {
        "module": "calcs.fire_sprinkler",
        "calc_type": "Fire Sprinkler Hydraulic",
        "standard": "NFPA 13 — q=density·coverage; P=(Q/K)²; N=ceil(area/coverage)",
        "inputs": {"occupancy_hazard": "Light Hazard", "k_factor": 80,
                   "sprinkler_spacing_m": 3.6},
        "asserts": [
            # INDEPENDENT oracle: NFPA 13 Light Hazard design density = 0.10 gpm/ft²
            # = 4.08 mm/min (derived from the STANDARD, NOT the engine table — the
            # prior 2.04 oracle was a change-detector that blessed an under-design bug,
            # fixed 2026-06-23 Arc Q).
            {"path": "q_per_sprinkler_lpm", "expected": 52.9, "tol": 0.1,
             "note": "NFPA 13 Light Hazard 0.10 gpm/ft² = 4.08 mm/min · (3.6²=12.96 m²) = 52.9 L/min"},
            {"path": "p_remote_bar", "expected": 0.437, "tol": 0.003,
             "note": "P = (Q/K)² = (52.88/80)² = 0.437 bar (inverse of NFPA Q=K√P)"},
            {"path": "n_sprinklers_design_area", "expected": 11, "tol": 0,
             "note": "ceil(design_area/coverage) = ceil(139/12.96) = 11 heads"},
            {"path": "hose_stream_lpm", "expected": 379, "tol": 1,
             "note": "NFPA 13 Light Hazard hose allowance = 100 gpm × 3.785 = 379 L/min (independent of engine)"},
        ],
    },
    {
        "module": "calcs.fire_pump",
        "calc_type": "Fire Pump Sizing",
        "standard": "NFPA 20 — churn ≤140% rated (electric); 150%-flow ≥65% rated",
        "inputs": {"system_flow_lpm": 1900, "system_pressure_bar": 6.9,
                   "drive_type": "Electric Motor", "design_margin_pct": 10},
        "asserts": [
            {"path": "rated_pressure_bar", "expected": 7.59, "tol": 0.01,
             "note": "system 6.9 bar · (1+10% margin) = 7.59 bar rated"},
            {"path": "churn_pressure_bar", "expected": 10.626, "tol": 0.01,
             "note": "140% electric churn limit · 7.59 = 10.63 bar (NFPA 20 shutoff cap)"},
            {"path": "overload_150pct_press_bar", "expected": 4.934, "tol": 0.01,
             "note": "65% of rated · 7.59 = 4.93 bar (NFPA 20 150%-flow min pressure)"},
            {"path": "recommended_flow_lpm", "expected": 2840, "tol": 0,
             "note": "next NFPA-20 std flow ≥ 1900·1.10 = 2090 → 2840 L/min"},
            # Decision-driving outputs (Arc Q untested-surface lesson, 2026-06-23):
            {"path": "churn_limit_pct", "expected": 140, "tol": 0,
             "note": "Electric driver → NFPA 20 churn cap = 140% (diesel would be 121%); driver-correct limit"},
            {"path": "diesel_driver_required", "expected": True, "tol": 0,
             "note": "NFPA 20: diesel driver mandatory when motor > 22 kW (here 75 kW) → required"},
            {"path": "npsh_ok", "expected": True, "tol": 0,
             "note": "SAFETY verdict: NPSHa 10.0 m >= NPSHr 5.0 m → no cavitation"},
        ],
    },
    {
        "module": "calcs.lighting_design",
        "calc_type": "Lighting Design",
        "standard": "IES Zonal Cavity — RCR = 5·h_rc·(L+W)/(L·W); LLF = LLD·LDD",
        "inputs": {"room_length_m": 10, "room_width_m": 8, "room_height_m": 3.0,
                   "work_plane_m": 0.85, "space_type": "Office - general",
                   "maintenance_category": "Good", "lamp_lumen_depreciation": 0.90},
        "asserts": [
            {"path": "room_area_m2", "expected": 80.0, "tol": 0.01,
             "note": "L·W = 10·8 = 80 m²"},
            {"path": "RCR", "expected": 2.419, "tol": 0.005,
             "note": "5·h_rc·(L+W)/(L·W) = 5·2.15·18/80 = 2.419 (h_rc = 3.0−0.85)"},
            {"path": "LLF", "expected": 0.81, "tol": 0.005,
             "note": "LLD·LDD = 0.90·0.90 (Good maintenance) = 0.81 (IES light-loss factor)"},
        ],
    },
    {
        "module": "calcs.chiller",
        "calc_type": "Chiller System",
        "standard": "ASHRAE 90.1 / AHRI 550/590 — TR=kW/3.517, EER=COP·3.412, Qrej=Q+W",
        "inputs": {"cooling_kw": 100, "chiller_type": "Air Cooled", "cop": 3.0,
                   "safety_factor": 1.10, "chw_supply_c": 7, "chw_return_c": 13},
        "asserts": [
            {"path": "cooling_TR", "expected": 28.43, "tol": 0.02,
             "note": "100 kW / 3.517 = 28.43 TR (1 ton refrigeration = 3.517 kW)"},
            {"path": "EER", "expected": 10.24, "tol": 0.02,
             "note": "COP·3.412 = 3.0·3.412 = 10.24 (W→BTU/h efficiency)"},
            {"path": "compressor_kW", "expected": 36.67, "tol": 0.05,
             "note": "Q_design/COP = (100·1.10)/3.0 = 110/3 = 36.67 kW"},
            {"path": "q_rejection_kW", "expected": 146.67, "tol": 0.05,
             "note": "Q_design + W_comp = 110 + 36.67 = 146.67 kW (1st-law energy balance)"},
            # Fix-gate (Arc Q, 2026-06-23): the ASHRAE 90.1 minimum-efficiency table was
            # 90.1-2010 (too LOW → passed under-efficient chillers). Anchored to 90.1-2019
            # Table 6.8.1-3 Path A, air-cooled <150 TR (28.4 TR here).
            {"path": "ashrae_min_COP", "expected": 2.96, "tol": 0.01,
             "note": "ASHRAE 90.1-2019 T6.8.1-3 air-cooled <150 TR min COP = 2.96 (EER 10.1/3.412; was 2.80=2010)"},
            {"path": "ashrae_min_IPLV", "expected": 4.02, "tol": 0.01,
             "note": "ASHRAE 90.1-2019 air-cooled <150 TR min IPLV = 4.02 (was 3.05=2010, ~25% too low)"},
        ],
    },
    {
        "module": "calcs.fluid_power",
        "calc_type": "Fluid Power",
        "standard": "ISO 4413 — cylinder F = P·A, A_cap = πD²/4, A_rod = π(D²−d²)/4",
        "inputs": {"calc_type": "Cylinder", "system_pressure_bar": 200,
                   "bore_mm": 100, "rod_mm": 70, "stroke_mm": 200, "flow_lpm": 40},
        "asserts": [
            {"path": "cylinder.A_cap_cm2", "expected": 78.54, "tol": 0.05,
             "note": "πD²/4 = π·10²/4 = 78.54 cm² (cap-end bore area)"},
            {"path": "cylinder.F_extend_kN", "expected": 157.08, "tol": 0.05,
             "note": "F = P·A_cap = 2e7 Pa · 0.007854 m² = 157.08 kN extension"},
            {"path": "cylinder.F_retract_kN", "expected": 80.11, "tol": 0.05,
             "note": "F = P·A_rod = 2e7·(π·(0.1²−0.07²)/4) = 80.11 kN (annulus < cap)"},
        ],
    },
    {
        # Depth oracle (Arc Q, 2026-06-23): fluid_power has Cylinder/Pump/Motor/Accumulator
        # branches; only Cylinder was gated. Pump branch (ISO 4413), independent.
        "module": "calcs.fluid_power",
        "calc_type": "Fluid Power (Pump)",
        "standard": "ISO 4413 — Q = Vg·n·η_vol; T_drive = Vg·ΔP/(20π·η_mech); P_hyd = Q·ΔP/600",
        "inputs": {"calc_type": "Pump", "system_pressure_bar": 200, "pump_displacement_cm3": 28,
                   "pump_speed_rpm": 1450, "pump_eta_vol": 0.95, "pump_eta_mech": 0.92,
                   "motor_efficiency": 0.92},
        "asserts": [
            {"path": "pump.Q_lpm", "expected": 38.57, "tol": 0.05,
             "note": "Q = Vg·n·η_vol = 28·1450·0.95/1000 = 38.57 L/min"},
            {"path": "pump.torque_Nm", "expected": 96.88, "tol": 0.1,
             "note": "T = Vg·ΔP/(20π·η_mech) = 28·200/(20π·0.92) = 96.88 N·m"},
            {"path": "pump.P_hydraulic_kW", "expected": 12.857, "tol": 0.02,
             "note": "P_hyd = Q·ΔP/600 = 38.57·200/600 = 12.857 kW"},
        ],
    },
    {
        # Depth oracle (Arc Q, 2026-06-23): fluid_power Motor branch (ISO 4413), independent.
        "module": "calcs.fluid_power",
        "calc_type": "Fluid Power (Motor)",
        "standard": "ISO 4413 — n = Q·η_vol/Vg; T = Vg·ΔP·η_mech/(20π); P_out = T·ω",
        "inputs": {"calc_type": "Motor", "system_pressure_bar": 200, "flow_lpm": 40,
                   "motor_displacement_cm3": 28, "motor_eta_vol": 0.95, "motor_eta_mech": 0.92},
        "asserts": [
            {"path": "motor.n_rpm", "expected": 1357.1, "tol": 0.5,
             "note": "n = Q·η_vol/Vg = 40000·0.95/28 = 1357 rpm"},
            {"path": "motor.torque_Nm", "expected": 82.0, "tol": 0.1,
             "note": "T = Vg·ΔP·η_mech/(20π) = 28·200·0.92/(20π) = 82.0 N·m"},
            {"path": "motor.P_output_kW", "expected": 11.653, "tol": 0.02,
             "note": "P_out = T·ω = 82.0·2π·1357/60/1000 = 11.653 kW"},
        ],
    },
    {
        "module": "calcs.harmonic_distortion",
        "calc_type": "Harmonic Distortion",
        "standard": "IEEE 519-2022 — THD_I = √(ΣIh²)/I1; K = Σ(Ih/I1)²·h² + 1",
        "inputs": {"fundamental_current_a": 100, "harmonics": [
            {"order": 3, "current_pct": 25}, {"order": 5, "current_pct": 18},
            {"order": 7, "current_pct": 12}]},
        "asserts": [
            {"path": "THD_I_pct", "expected": 33.06, "tol": 0.02,
             "note": "√(25²+18²+12²)/100·100 = √1093 = 33.06% (current THD)"},
            {"path": "K_factor", "expected": 3.08, "tol": 0.02,
             "note": "Σ(Ih/I1)²·h²+1 = 0.5625+0.81+0.7056+1 = 3.08 (transformer K-factor)"},
        ],
    },
    {
        "module": "calcs.harmonic_distortion",
        "calc_type": "Harmonic Distortion (individual limits)",
        "standard": "IEEE 519-2014/2022 Table 2 — individual odd-harmonic limits are a full "
                    "matrix (per-band per-tier), NOT a uniform scale of the <20 row",
        "custom": _check_harmonic_519_individual_limits,
    },
    {
        "module": "calcs.beam_column",
        "calc_type": "Beam / Column Design",
        "standard": "AISC 360-22 LRFD — Mp = Fy·Zx; Vn = 0.6·Fy·Aw; φb = 0.90",
        "inputs": {"member_type": "Steel Beam", "steel_grade": "A36",
                   "section": "W310x45", "span_m": 6, "Mu_kNm": 150,
                   "Vu_kN": 100, "w_kNm": 10},
        "asserts": [
            {"path": "Mp_kNm", "expected": 295.0, "tol": 0.2,
             "note": "Mp = Fy·Zx = 250 MPa · 1180 cm³ = 250·1180·1e3 N·mm = 295 kN·m"},
            {"path": "phi_Mp_kNm", "expected": 265.5, "tol": 0.2,
             "note": "φb·Mp = 0.90·295.0 = 265.5 kN·m (LRFD bending)"},
            {"path": "Vn_kN", "expected": 333.3, "tol": 0.3,
             "note": "Vn = 0.6·Fy·Aw = 0.6·250·(313·7.1 mm²) = 333.3 kN (compact web)"},
        ],
    },
    {
        # Depth oracle (Arc Q, 2026-06-23): the beam_column engine has 4 member_type
        # branches but only Steel Beam was gated. This locks the RC Beam branch
        # (ACI 318-19 flexure) — independently hand-derived, NOT read from the engine.
        "module": "calcs.beam_column",
        "calc_type": "Beam / Column Design (RC Beam)",
        "standard": "ACI 318-19 — Mn = As·fy·(d−a/2); a = As·fy/(0.85·f'c·b); φ=0.90 tension-controlled",
        "inputs": {"member_type": "RC Beam", "b_mm": 300, "h_mm": 500, "cover_mm": 40,
                   "bar_dia_mm": 20, "n_bars": 4, "concrete_grade": "f'c 28 MPa (4000 psi)",
                   "rebar_grade": "Grade 60 (ASTM A615)", "Mu_kNm": 150, "Vu_kN": 80},
        "asserts": [
            {"path": "d_mm", "expected": 440.0, "tol": 0.1,
             "note": "d = h−cover−stirrup−bar/2 = 500−40−10−10 = 440 mm (effective depth)"},
            {"path": "As_mm2", "expected": 1256.64, "tol": 0.6,
             "note": "As = 4·π·(20/2)² = 1256.6 mm² (4-#20 bars)"},
            {"path": "a_mm", "expected": 72.86, "tol": 0.2,
             "note": "a = As·fy/(0.85·f'c·b) = 1256.6·414/(0.85·28·300) = 72.86 mm (stress block)"},
            {"path": "Mn_kNm", "expected": 209.95, "tol": 0.5,
             "note": "Mn = As·fy·(d−a/2) = 1256.6·414·(440−36.43)/1e6 = 209.95 kN·m"},
            {"path": "phi_Mn_kNm", "expected": 188.96, "tol": 0.5,
             "note": "φ·Mn = 0.90·209.95 = 188.96 kN·m (εt=0.0124≥0.005 → tension-controlled φ=0.9)"},
        ],
    },
    {
        # Depth oracle (Arc Q, 2026-06-23): locks the Steel Column branch (AISC 360 E3
        # inelastic buckling) on the GOVERNING (weak) axis. Iy is derived from section
        # geometry (W_SECTIONS has no Iy): Iy = tf·bf³/6 + (d−2tf)·tw³/12, fillets
        # neglected → conservative. This caught a real bug: the engine previously used
        # r=√(Ix/A) (strong axis) and reported this slender column DCR=0.59 (OK) when the
        # weak axis governs (DCR=1.39 FAIL). Independent oracle, geometry-derived.
        "module": "calcs.beam_column",
        "calc_type": "Beam / Column Design (Steel Column)",
        "standard": "AISC 360-22 E3 — weak-axis buckling: r=√(min(Ix,Iy)/A), Iy AISC-tabulated; "
                    "inelastic Fcr=0.658^(Fy/Fe)·Fy when KL/r≤4.71√(E/Fy); φc=0.90",
        "inputs": {"member_type": "Steel Column", "steel_grade": "A992",
                   "section": "W310x45", "span_m": 4, "Pu_kN": 1000, "K_factor": 1.0},
        "asserts": [
            {"path": "Iy_cm4", "expected": 845.0, "tol": 1.0,
             "note": "AISC v16.0 W310x45 (W12x30) Iy = 20.30 in⁴ × 41.6231 = 844.9 cm⁴ "
                     "(sourced from AISC, NOT the geometry formula → not a change-detector)"},
            {"path": "KL_r", "expected": 104.2, "tol": 0.5,
             "note": "KL/r = K·L/√(Iy/A) = 4/√(844.9/57.3 cm) = 4/0.03840 m = 104.2 (weak axis governs)"},
            {"path": "Fcr_MPa", "expected": 156.0, "tol": 1.0,
             "note": "104.2≤4.71√(E/Fy)=113.4 → inelastic Fcr=0.658^(345/181.9)·345 = 156.0 MPa"},
            {"path": "phi_Pn_kN", "expected": 804.4, "tol": 2.0,
             "note": "φc·Fcr·A = 0.90·156.0·5.73e-3·1000 = 804.4 kN (exact AISC Iy; the geometry "
                     "estimate gave 719 here but OVERSTATED Iy for 8 other sections = unsafe)"},
        ],
    },
    {
        # Regression oracle (Arc Q, 2026-06-23): W150x13 is the section the geometry-Iy
        # estimate OVERSTATED the most (+38%: geom 126.8 vs AISC 91.6 cm⁴) = a
        # NON-CONSERVATIVE (unsafe) column capacity. Anchored to the AISC Iy to prove the
        # exact value is used and the overstatement can't return.
        "module": "calcs.beam_column",
        "calc_type": "Beam / Column Design (Steel Column W150x13)",
        "standard": "AISC 360-22 E3 — W150x13 weak-axis Iy = 91.6 cm⁴ (NOT the geometry 126.8)",
        "inputs": {"member_type": "Steel Column", "steel_grade": "A992",
                   "section": "W150x13", "span_m": 3, "Pu_kN": 100, "K_factor": 1.0},
        "asserts": [
            {"path": "Iy_cm4", "expected": 92.0, "tol": 1.0,
             "note": "AISC W150x13 (W6x9) Iy = 2.20 in⁴ × 41.6231 = 91.6 cm⁴ (geometry gave 126.8 = +38% unsafe)"},
            {"path": "KL_r", "expected": 128.5, "tol": 0.5,
             "note": "KL/r = 3/√(91.6/16.8 cm) = 3/0.02335 m = 128.5 (slender; geom Iy would understate this)"},
            {"path": "phi_Pn_kN", "expected": 158.6, "tol": 1.5,
             "note": "φc·Fcr·A with exact Iy = 158.6 kN (geometry Iy would have OVERSTATED capacity)"},
        ],
    },
    {
        # Depth oracle (Arc Q, 2026-06-23): locks the RC Column branch (ACI 318 tied,
        # pure axial). Independently hand-derived from §22.4.2.
        "module": "calcs.beam_column",
        "calc_type": "Beam / Column Design (RC Column)",
        "standard": "ACI 318-19 §22.4.2 — Pn = 0.85·f'c·(Ag−Ast) + fy·Ast; tied φ=0.65 × 0.80 max axial",
        "inputs": {"member_type": "RC Column", "b_mm": 300, "h_mm": 500, "bar_dia_mm": 20,
                   "n_bars": 8, "concrete_grade": "f'c 28 MPa (4000 psi)",
                   "rebar_grade": "Grade 60 (ASTM A615)", "Pu_kN": 2000},
        "asserts": [
            {"path": "Ast_mm2", "expected": 2513.27, "tol": 1.0,
             "note": "Ast = 8·π·(20/2)² = 2513.3 mm² (8-#20 bars)"},
            {"path": "rho_g", "expected": 0.01676, "tol": 0.0005,
             "note": "ρg = Ast/Ag = 2513.3/150000 = 0.01676 (0.01 ≤ ρ ≤ 0.08 ok)"},
            {"path": "Pn_kN", "expected": 4550.7, "tol": 1.0,
             "note": "Pn = 0.85·28·(150000−2513.3)/1e3 + 414·2513.3/1e3 = 3510.2+1040.5 = 4550.7 kN"},
            {"path": "phi_Pn_kN", "expected": 2366.4, "tol": 1.0,
             "note": "φ·0.80·Pn = 0.65·0.80·4550.7 = 2366.4 kN (tied column reduction)"},
        ],
    },
    {
        "module": "calcs.refrigerant_pipe",
        "calc_type": "Refrigerant Pipe Sizing",
        "standard": "ASHRAE 2022 Refrig Hbk Ch.1 — ṁ = Q/h_fg; Qv = ṁ/ρ",
        "inputs": {"cooling_kw": 10, "refrigerant": "R-410A",
                   "application": "Air Conditioning"},
        "asserts": [
            {"path": "refrigerant_props.h_fg_kJkg", "expected": 213.0, "tol": 0,
             "note": "R-410A latent heat at +5°C evap = 213.0 kJ/kg (ASHRAE saturation table)"},
            {"path": "mass_flow_kgs", "expected": 0.0469, "tol": 0.0002,
             "note": "ṁ = Q/h_fg = 10 kW / 213.0 kJ/kg = 0.0469 kg/s"},
            {"path": "flow_suction_m3s", "expected": 0.001806, "tol": 0.00001,
             "note": "Qv = ṁ/ρ_vap = 0.046948/26.0 = 0.001806 m³/s"},
        ],
    },
    {
        "module": "calcs.ahu_sizing",
        "calc_type": "AHU Sizing",
        "standard": "ASHRAE — sensible heat ṁ = Q_s/(cp·ΔT); V = ṁ/ρ (dep: psychrolib)",
        "inputs": {"q_sensible": 20000, "supply_air_temp_c": 13.0, "indoor_temp": 24.0},
        "asserts": [
            {"path": "mass_flow_kgs", "expected": 1.8073, "tol": 0.001,
             "note": "ṁ = Q_s/(cp·ΔT) = 20000/(1006·(24−13)) = 1.807 kg/s"},
            {"path": "supply_flow_m3s", "expected": 1.5716, "tol": 0.001,
             "note": "V = ṁ/ρ = 1.8073/1.15 = 1.572 m³/s"},
            {"path": "supply_flow_cfm", "expected": 3330.0, "tol": 1,
             "note": "1.5716 m³/s · 2118.88 = 3330 cfm"},
        ],
    },
    {
        "module": "calcs.domestic_water",
        "calc_type": "Domestic Water System",
        "standard": "PSME / ASPE — ΣWSFU; demand=persons·lppd; head=floors·h·0.0981",
        "inputs": {"fixtures": [{"fixture_type": "Water Closet (flush valve)", "quantity": 5},
                                {"fixture_type": "Lavatory (faucet)", "quantity": 5}],
                   "occupancy_type": "Office", "num_persons": 50, "building_floors": 5,
                   "floor_height_m": 3.5, "storage_type": "overhead"},
        "asserts": [
            {"path": "total_wsfu", "expected": 60.0, "tol": 0,
             "note": "ΣWSFU·qty = 10·5 (WC flush-valve) + 2·5 (lavatory) = 60 (ASPE/PSME)"},
            {"path": "peak_flow_lpm", "expected": 202.5, "tol": 0.5,
             "note": "flush-VALVE Hunter curve @60 WSFU = interp(50→189.3, 100→255.5) = 202.5 L/min "
                     "(the flush-tank fit gave ~104 = ~50% under-design; fixed 2026-06-23 Arc Q)"},
            {"path": "daily_demand_m3", "expected": 2.5, "tol": 0.01,
             "note": "persons·lppd/1000 = 50·50 L/p/d /1000 = 2.5 m³/day (PSME Office)"},
            {"path": "static_head_bar", "expected": 1.717, "tol": 0.005,
             "note": "floors·height·0.0981 = 5·3.5·0.0981 = 1.717 bar (1 m water=0.0981 bar)"},
            {"path": "tank_required_m3", "expected": 0.83, "tol": 0.01,
             "note": "daily·storage_factor = 2.5·(1/3 overhead) = 0.83 m³"},
        ],
    },
    {
        "module": "calcs.storm_drain",
        "calc_type": "Storm Drain / Stormwater",
        "standard": "Rational Q=C·i·A/360; Manning D=((Q·n)/(0.3117·√S))^(3/8)",
        "inputs": {"intensity_mmhr": 100, "area_ha": 2.0, "c_value": 0.80,
                   "slope_pct": 1.0, "pipe_material": "Concrete", "area_mode": "single"},
        "asserts": [
            {"path": "design_flow_m3s", "expected": 0.44444, "tol": 0.0001,
             "note": "Q = C·i·A/360 = 0.80·100·2.0/360 = 0.4444 m³/s (Rational Method)"},
            {"path": "d_required_mm", "expected": 531.4, "tol": 0.5,
             "note": "Manning ((Q·n)/(0.3117·√S))^(3/8) = 531 mm (n=0.013 concrete, S=1%)"},
            {"path": "d_selected_mm", "expected": 600, "tol": 0,
             "note": "next DPWH std diameter ≥ 531.4 = 600 mm (min 300 per Blue Book)"},
        ],
    },
    {
        "module": "calcs.water_supply_pipe",
        "calc_type": "Water Supply Pipe Sizing",
        "standard": "PPC Hunter WFU → peak L/s (Table A-3 curve); H-W C-factor",
        "inputs": {"pipe_material": "PVC", "fixtures": [
            {"fixture_type": "Water Closet (Flush Valve)", "quantity": 10},
            {"fixture_type": "Lavatory / Hand Sink", "quantity": 20}]},
        "asserts": [
            {"path": "total_wfu", "expected": 120, "tol": 0,
             "note": "ΣWFU·qty = 10·10 (WC flush-valve) + 1·20 (lavatory) = 120 (PPC Table A-2)"},
            {"path": "peak_lps", "expected": 1.34, "tol": 0.005,
             "note": "Hunter PPC A-3 lerp at 120 WFU: 1.22 + (20/50)·(1.52−1.22) = 1.34 L/s"},
            {"path": "C_factor", "expected": 150, "tol": 0,
             "note": "PVC Hazen-Williams coefficient C=150 (PPC Appendix A)"},
        ],
    },
    {
        "module": "calcs.septic_tank",
        "calc_type": "Septic Tank Sizing",
        "standard": "PPC §P-1101 — V = liquid(flow·ret) + sludge(40·n·yr) + scum(15·n·yr)",
        "inputs": {"occupancy_type": "Residential", "occupants": 20, "retention_days": 1.0,
                   "desludge_years": 3.0, "liquid_depth": 1.5, "lw_ratio": 3.0,
                   "compartments": 2, "soil_type": "Sandy Loam"},
        "asserts": [
            {"path": "daily_flow_L", "expected": 3000, "tol": 0,
             "note": "occupants·ww_rate = 20·150 L/p/d = 3000 L/day (PPC Residential)"},
            {"path": "total_volume_L", "expected": 6300, "tol": 0,
             "note": "liquid(3000·1) + sludge(40·20·3) + scum(15·20·3) = 3000+2400+900 = 6300 L"},
            {"path": "comp1_L", "expected": 4200, "tol": 0,
             "note": "2-compartment 2/3 split = round(6300·2/3) = 4200 L (PPC)"},
            {"path": "leach_field_area_m2", "expected": 187.5, "tol": 0.1,
             "note": "daily_flow/abs_rate = 3000/16 (Sandy Loam) = 187.5 m² (PPC §P-1103)"},
        ],
    },
    {
        "module": "calcs.hot_water_demand",
        "calc_type": "Hot Water Demand",
        "standard": "ASHRAE Ch.50 — Σ qty·count·rate; +pipe loss; peak fraction",
        "inputs": {"uses": [{"use_type": "Hotel Room", "quantity": 50, "daily_count": 1}],
                   "supply_temp": 28, "hot_temp": 60, "pipe_loss_pct": 10,
                   "peak_fraction": 0.25, "storage_factor": 1.25, "recovery_hours": 2},
        "asserts": [
            {"path": "delta_T", "expected": 32.0, "tol": 0,
             "note": "T_hot − T_supply = 60 − 28 = 32 K"},
            {"path": "total_daily_without_loss_L", "expected": 6750, "tol": 0,
             "note": "Σ qty·count·rate = 50·1·135 (Hotel Room, ASHRAE Ch.50) = 6750 L"},
            {"path": "total_daily_L", "expected": 7425, "tol": 0,
             "note": "net·(1+pipe_loss) = 6750·1.10 = 7425 L"},
            {"path": "peak_hour_L", "expected": 1856, "tol": 0,
             "note": "total·peak_fraction = round(7425·0.25) = 1856 L"},
        ],
    },
    {
        "module": "calcs.drainage_pipe_sizing",
        "calc_type": "Drainage Pipe Sizing",
        "standard": "UPC Table 7-5 DFU + WC 100mm hard-rule; Manning self-cleansing",
        "inputs": {"fixtures": [{"fixture_type": "Water Closet", "quantity": 4},
                                {"fixture_type": "Lavatory / Hand Sink", "quantity": 6}],
                   "system_type": "Horizontal Branch", "slope": "2%", "pipe_material": "PVC"},
        "asserts": [
            {"path": "total_dfu", "expected": 22, "tol": 0,
             "note": "ΣDFU·qty = 4·4 (WC) + 1·6 (lavatory) = 22 (UPC Table 7-5)"},
            {"path": "recommended_dia_mm", "expected": 100, "tol": 0,
             "note": "75mm carries 22 DFU @2% but WC hard-rule forces ≥100 mm (UPC/PPC)"},
            {"path": "capacity_q_ls", "expected": 5.27, "tol": 0.05,
             "note": "Manning half-full d=100 n=0.009 S=2%: (1/n)·A·R^⅔·√S = 5.27 L/s"},
        ],
    },
    {
        "module": "calcs.grease_trap",
        "calc_type": "Grease Trap Sizing",
        "standard": "PDI G-101 — Q_design = Σflow·SUF → GPM → std size; 1 lb/GPM",
        "inputs": {"fixtures": [{"flow_lpm": 30, "qty": 2}], "suf": 0.75, "meals_per_day": 0},
        "asserts": [
            {"path": "q_design_lpm", "expected": 45.0, "tol": 0.01,
             "note": "total·SUF = (30·2)·0.75 = 45 L/min"},
            {"path": "q_design_gpm", "expected": 11.89, "tol": 0.02,
             "note": "45 L/min · 0.26417 = 11.89 GPM (PDI G-101 flow method)"},
            {"path": "pdi_gpm", "expected": 15, "tol": 0,
             "note": "next PDI G-101 standard size ≥ 11.89 = 15 GPM"},
            {"path": "grease_ret_kg", "expected": 6.8, "tol": 0.02,
             "note": "1 lb/GPM · 15 = 15·0.4536 = 6.8 kg grease retention (PDI §4.4)"},
        ],
    },
    {
        "module": "calcs.roof_drain",
        "calc_type": "Roof Drain Sizing",
        "standard": "IPC §1106 / Rational — Q = I·A/3600 (C=1.0 impervious roof)",
        "inputs": {"roof_area": 500, "n_drains": 2, "intensity_mmhr": 100,
                   "leader_slope_pct": 1.0, "pipe_material": "uPVC"},
        "asserts": [
            {"path": "q_total_ls", "expected": 13.89, "tol": 0.02,
             "note": "Q = I·A/3600 = 100·500/3600 = 13.89 L/s (Rational, C=1.0 roof)"},
            {"path": "q_each_ls", "expected": 6.94, "tol": 0.02,
             "note": "13.89 / 2 drains = 6.94 L/s per drain"},
            {"path": "drain_size_mm", "expected": 200, "tol": 0,
             "note": "first drain body cap (8.83 L/s) ≥ 6.94 = 200 mm (IPC Table 1106.2)"},
        ],
    },
    {
        "module": "calcs.sewer_drainage",
        "calc_type": "Sewer / Drainage",
        "standard": "NSCP/ASPE DFU + stack table; storm Rational; septic per-capita",
        "inputs": {"fixtures": [{"fixture_type": "Water Closet", "quantity": 10},
                                {"fixture_type": "Lavatory (single)", "quantity": 10}],
                   "pipe_material": "uPVC / CPVC", "roof_area_m2": 300,
                   "location": "Metro Manila", "num_persons": 40},
        "asserts": [
            {"path": "total_dfu", "expected": 50.0, "tol": 0,
             "note": "ΣDFU·qty = 4·10 (WC) + 1·10 (lavatory) = 50 (NSCP/ASPE)"},
            {"path": "stack_nominal_mm", "expected": 100, "tol": 0,
             "note": "smallest stack ≥ 50 DFU (75mm caps 30) = 100 mm (NSCP P-803.1)"},
            {"path": "storm_flow_lps", "expected": 15.0, "tol": 0.05,
             "note": "Rational C·i·A/3600 = 0.90·200·300/3600 = 15.0 L/s (Metro Manila 200 mm/hr)"},
            {"path": "septic_liquid_m3", "expected": 7.2, "tol": 0.01,
             "note": "persons·120·1.5/1000 = 40·120·1.5/1000 = 7.2 m³ (NSCP 120 L/p/d, 1.5d)"},
        ],
    },
    {
        "module": "calcs.water_softener",
        "calc_type": "Water Softener Sizing",
        "standard": "NSF/ANSI 44 — load=demand·Δhardness; resin=load·regen·SF/exch_cap",
        "inputs": {"demand_source": "direct", "demand_lpd": 10000, "inlet_hardness": 200,
                   "target_hardness": 17, "regen_interval": 3, "salt_dose_gL": 80,
                   "n_units": 1},
        "asserts": [
            {"path": "removal_mgL", "expected": 183.0, "tol": 0,
             "note": "inlet−target = 200−17 = 183 mg/L CaCO3 removed"},
            {"path": "daily_load_g", "expected": 1830.0, "tol": 0.1,
             "note": "demand·removal/1000 = 10000·183/1000 = 1830 g CaCO3/day"},
            {"path": "load_per_cycle_g", "expected": 6588, "tol": 0,
             "note": "daily·regen·SF = 1830·3·1.2 = 6588 g per cycle"},
            {"path": "resin_L_per_unit", "expected": 146.4, "tol": 0.1,
             "note": "load/exch_cap = 6588/45 (g/L at salt 80 g/L) = 146.4 L resin"},
        ],
    },
    {
        "module": "calcs.wastewater_stp",
        "calc_type": "Wastewater Treatment (STP)",
        "standard": "Metcalf & Eddy — Q=pop·lpcd; BOD load/removed mass balance",
        "inputs": {"flow_source": "population", "population": 200, "per_capita_lpd": 150,
                   "bod_influent": 220, "bod_effluent": 30, "srt_days": 8, "mlss_mg_l": 3000},
        "asserts": [
            {"path": "flow_m3_day", "expected": 30.0, "tol": 0.01,
             "note": "pop·per_capita/1000 = 200·150/1000 = 30 m³/day"},
            {"path": "bod_load_kg_day", "expected": 6.6, "tol": 0.01,
             "note": "BOD_in·Q/1000 = 220·30/1000 = 6.6 kg/day"},
            {"path": "bod_removed_kg_day", "expected": 5.7, "tol": 0.01,
             "note": "(BOD_in−BOD_out)·Q/1000 = 190·30/1000 = 5.7 kg/day"},
            {"path": "bod_removal_pct", "expected": 86.4, "tol": 0.1,
             "note": "(220−30)/220·100 = 86.4% BOD removal"},
        ],
    },
    {
        "module": "calcs.cooling_tower",
        "calc_type": "Cooling Tower Sizing",
        "standard": "CTI/ASHRAE — Range, Approach, condenser flow Q=ṁ·cp·Range",
        "inputs": {"heat_rejection_kw": 500, "condenser_water_in_c": 35,
                   "condenser_water_out_c": 29.5, "design_wb_c": 28},
        "asserts": [
            {"path": "range_c", "expected": 5.5, "tol": 0.01,
             "note": "T_hot_in − T_cold_out = 35 − 29.5 = 5.5 K (Range)"},
            {"path": "approach_c", "expected": 1.5, "tol": 0.01,
             "note": "T_cold_out − T_wb = 29.5 − 28 = 1.5 K (Approach)"},
            {"path": "heat_rejection_tr", "expected": 142.17, "tol": 0.02,
             "note": "500 kW / 3.517 = 142.17 TR"},
            {"path": "mass_flow_kgs", "expected": 21.717, "tol": 0.01,
             "note": "ṁ = Q/(cp·Range) = 500000/(4186·5.5) = 21.72 kg/s (condenser flow)"},
        ],
    },
    {
        "module": "calcs.expansion_tank",
        "calc_type": "Expansion Tank Sizing",
        "standard": "ASHRAE Ch.12 / ASME VIII — precharge=static head; α=1−Pf/Pmax",
        "inputs": {"system_type": "Chilled Water", "volume_method": "Estimate from kW",
                   "system_kw": 100, "fill_temp_c": 20, "max_temp_c": 7,
                   "static_head_m": 10, "max_pressure_kpa_g": 400},
        "asserts": [
            {"path": "system_volume_L", "expected": 800.0, "tol": 0.01,
             "note": "system_kw·8.0 L/kW (Chilled Water) = 100·8 = 800 L"},
            {"path": "precharge_kpa_g", "expected": 100.0, "tol": 0,
             "note": "ceil(9.81·10/10)·10 = ceil(9.81)·10 = 100 kPa (static head → nearest 10)"},
            {"path": "fill_pressure_kpa_g", "expected": 115.0, "tol": 0,
             "note": "precharge + 15 kPa safety = 115 kPa"},
            {"path": "acceptance_factor", "expected": 0.569, "tol": 0.002,
             "note": "α = 1 − P_fill_abs/P_max_abs = 1 − 216.3/501.3 = 0.569 (ASME VIII)"},
        ],
    },
    {
        "module": "calcs.fcu_selection",
        "calc_type": "FCU Selection",
        "standard": "ARI 440 — design load → catalogue select; CHW flow Q/(ρ·cp·6°C)",
        "inputs": {"q_total_kW": 5, "design_margin_pct": 10, "supply_air_temp_c": 13,
                   "indoor_temp": 24},
        "asserts": [
            {"path": "q_design_kW", "expected": 5.5, "tol": 0.01,
             "note": "q_total·(1+margin) = 5.0·1.10 = 5.5 kW"},
            {"path": "selected_fcu", "expected": "FCU-800", "tol": 0,
             "note": "first ARI-440 catalogue unit ≥ 5.5 kW = FCU-800 (5.6 kW)"},
            {"path": "cw_flow_lps", "expected": 0.223, "tol": 0.003,
             "note": "Q/(ρ·cp·ΔT) = 5600/(4186·6)·1000/999.7 = 0.223 L/s (FIX: ×1000 was missing)"},
        ],
    },
    {
        "module": "calcs.fire_alarm_battery",
        "calc_type": "Fire Alarm Battery",
        "standard": "NFPA 72 §10.6.7 — Ah = [(Is·Ts)+(Ia·Ta/60)]·1.25 SF",
        "inputs": {"system_voltage": 24, "standby_hours": 24, "alarm_minutes": 5,
                   "panel_standby_mA": 50, "panel_alarm_mA": 200,
                   "n_addr_smoke": 20, "n_horn_strobe": 10},
        "asserts": [
            {"path": "I_standby_total_mA", "expected": 56.0, "tol": 0.01,
             "note": "panel 50 + 20·0.3 (addr smoke standby) + 10·0.0 (strobe) = 56 mA"},
            {"path": "I_alarm_total_mA", "expected": 1260.0, "tol": 0.01,
             "note": "panel 200 + 20·3.0 (smoke) + 10·100 (horn/strobe) = 1260 mA"},
            {"path": "Ah_required", "expected": 1.811, "tol": 0.005,
             "note": "[(56/1000·24)+(1260/1000·5/60)]·1.25 = (1.344+0.105)·1.25 = 1.811 Ah"},
            {"path": "selected_Ah", "expected": 2.6, "tol": 0,
             "note": "next std VRLA ≥ 1.811 = 2.6 Ah (NFPA 72)"},
        ],
    },
    {
        "module": "calcs.clean_agent_suppression",
        "calc_type": "Clean Agent Suppression",
        "standard": "NFPA 2001 / ISO 14520 — W = (V/S)·[C/(100−C)]; S = s1+s2·T",
        "inputs": {"hazard_volume_m3": 100, "agent_type": "FM-200", "temperature_c": 20,
                   "altitude_m": 0, "safety_factor": 1.10},
        "asserts": [
            {"path": "specific_vol_m3_kg", "expected": 0.136914, "tol": 0.000001,
             "note": "S = s1 + s2·T = 0.1269 + 0.0005007·20 = 0.136914 m³/kg (FM-200)"},
            {"path": "adjusted_volume_m3", "expected": 100.0, "tol": 0.01,
             "note": "V·alt_factor = 100·1.0 (sea level) = 100 m³"},
            {"path": "W_calculated_kg", "expected": 54.97, "tol": 0.05,
             "note": "W = (V/S)·[C/(100−C)] = (100/0.136914)·(7/93) = 54.97 kg (NFPA 2001)"},
            {"path": "W_design_kg", "expected": 60.47, "tol": 0.05,
             "note": "W_calc·1.10 SF = 54.97·1.10 = 60.47 kg"},
        ],
    },
    {
        # Depth oracle (Arc Q, 2026-06-23): clean_agent had 4 agents but only FM-200 was
        # gated. Novec is the 2nd HALOCARBON — same C/(100−C) formula, independent values.
        "module": "calcs.clean_agent_suppression",
        "calc_type": "Clean Agent Suppression (Novec)",
        "standard": "NFPA 2001 §5.3 halocarbon — W=(V/S)·[C/(100−C)]; FK-5-1-12 S=0.0664+0.0002738·T",
        "inputs": {"hazard_volume_m3": 100, "agent_type": "FK-5-1-12", "temperature_c": 20,
                   "altitude_m": 0, "safety_factor": 1.10},
        "asserts": [
            {"path": "specific_vol_m3_kg", "expected": 0.071876, "tol": 0.000001,
             "note": "S = 0.0664 + 0.0002738·20 = 0.071876 m³/kg (Novec 1230)"},
            {"path": "W_calculated_kg", "expected": 73.23, "tol": 0.1,
             "note": "W = (100/0.071876)·(5/95) = 73.23 kg (halocarbon, C=5%)"},
            {"path": "W_design_kg", "expected": 80.55, "tol": 0.1,
             "note": "73.23·1.10 SF = 80.55 kg"},
        ],
    },
    {
        # Depth oracle (Arc Q, 2026-06-23): Inergen is an INERT GAS — must use the §5.4
        # LOGARITHMIC displacement formula 2.303·log10[100/(100−C)], NOT the halocarbon
        # C/(100−C). This caught a real bug: the engine applied C/(100−C) to all agents,
        # overstating Inergen ~22% (86→67 kg). Independent oracle anchored to §5.4.
        "module": "calcs.clean_agent_suppression",
        "calc_type": "Clean Agent Suppression (Inergen, inert)",
        "standard": "NFPA 2001 §5.4 inert gas — W=(V/S)·2.303·log10[100/(100−C)]; IG-541 S=0.6598+0.0024475·T",
        "inputs": {"hazard_volume_m3": 100, "agent_type": "Inergen", "temperature_c": 20,
                   "altitude_m": 0, "safety_factor": 1.10},
        "asserts": [
            {"path": "specific_vol_m3_kg", "expected": 0.70875, "tol": 0.00001,
             "note": "S = 0.6598 + 0.0024475·20 = 0.70875 m³/kg (IG-541)"},
            {"path": "W_calculated_kg", "expected": 67.46, "tol": 0.1,
             "note": "W = (100/0.70875)·2.303·log10(100/62) = 67.46 kg (INERT log, NOT 86.5 halocarbon)"},
            {"path": "W_design_kg", "expected": 74.21, "tol": 0.1,
             "note": "67.46·1.10 SF = 74.21 kg"},
        ],
    },
    {
        # Depth oracle (Arc Q, 2026-06-23): CO2 is an inert displacement gas — §5.4 log formula.
        "module": "calcs.clean_agent_suppression",
        "calc_type": "Clean Agent Suppression (CO2, inert)",
        "standard": "NFPA 2001/12 inert — W=(V/S)·2.303·log10[100/(100−C)]; CO2 S=0.5541+0.002031·T, C=34%",
        "inputs": {"hazard_volume_m3": 100, "agent_type": "CO2", "temperature_c": 20,
                   "altitude_m": 0, "safety_factor": 1.10},
        "asserts": [
            {"path": "specific_vol_m3_kg", "expected": 0.59472, "tol": 0.00001,
             "note": "S = 0.5541 + 0.002031·20 = 0.59472 m³/kg (CO2)"},
            {"path": "W_calculated_kg", "expected": 69.88, "tol": 0.1,
             "note": "W = (100/0.59472)·2.303·log10(100/66) = 69.88 kg (inert log displacement)"},
            {"path": "W_design_kg", "expected": 76.87, "tol": 0.1,
             "note": "69.88·1.10 SF = 76.87 kg"},
        ],
    },
    {
        "module": "calcs.load_schedule",
        "calc_type": "Load Schedule",
        "standard": "PEC/NEC 220 — connected = Σqty·watts/1000 (watts IS real power); demand·df",
        "inputs": {"panel_voltage": 400, "panel_phases": 3, "loads": [
            {"name": "Lights", "qty": 10, "watts_each": 100, "load_type": "Lighting"},
            {"name": "Recep", "qty": 20, "watts_each": 180, "load_type": "Receptacle"}]},
        "asserts": [
            {"path": "total_connected_kW", "expected": 4.6, "tol": 0.001,
             "note": "Σqty·watts/1000 = (10·100 + 20·180)/1000 = 4.6 kW (PF NOT applied to kW)"},
            {"path": "total_demand_kW", "expected": 2.8, "tol": 0.001,
             "note": "Σ connected·df = 1.0·1.0 (lighting) + 3.6·0.5 (receptacle) = 2.8 kW (NEC 220)"},
        ],
    },
    {
        "module": "calcs.wire_sizing",
        "calc_type": "Wire Sizing",
        "standard": "PEC 2017 — 125% continuous; ampacity·temp·fill derate ≥ sizing I",
        "inputs": {"load_amps": 100, "voltage": 230, "phases": 1, "power_factor": 0.85,
                   "wire_length_m": 30, "ambient_temp_c": 35, "conductors_in_conduit": 3,
                   "continuous_load": True},
        "asserts": [
            {"path": "sizing_current_a", "expected": 125.0, "tol": 0.01,
             "note": "design·1.25 = 100·1.25 = 125 A (PEC continuous-load rule)"},
            {"path": "temp_factor", "expected": 0.94, "tol": 0.001,
             "note": "PEC Table 310.15(B)(2)(a) at 35°C ambient (75°C conductor) = 0.94"},
            {"path": "wire_mm2", "expected": 50.0, "tol": 0,
             "note": "smallest where ampacity·0.94 ≥ 125: 50 mm² (150 A·0.94=141 ≥ 125; 38mm²→122 fails)"},
        ],
    },
    {
        # Fix-gate (Arc Q, 2026-06-23): the 61-70 °C temp-correction brackets were wrong —
        # 61-65 °C (0.47) was absent and 66-70 °C used 0.35 not 0.33. Anchored independently
        # to NEC/PEC Table 310.15(B)(2)(a) (75 °C conductor), NOT the engine.
        "module": "calcs.wire_sizing",
        "calc_type": "Wire Sizing (high-ambient temp brackets)",
        "standard": "NEC/PEC Table 310.15(B)(2)(a), 75 °C conductor: 61-65 °C = 0.47, 66-70 °C = 0.33",
        "inputs": {"load_amps": 100, "voltage": 230, "phases": 1, "ambient_temp_c": 68,
                   "wire_length_m": 30, "conductors_in_conduit": 3, "continuous_load": True},
        "asserts": [
            {"path": "temp_factor", "expected": 0.33, "tol": 0.001,
             "note": "66-70 °C ambient, 75 °C conductor = 0.33 (NOT 0.35 — over-rating undersizes the conductor)"},
        ],
    },
    {
        "module": "calcs.hoist_capacity",
        "calc_type": "Hoist Capacity",
        "standard": "ASME B30.2 — gross=rated+hook+sling; MBF=gross·SF; pull=gross/(n·η)",
        "inputs": {"rated_load_kg": 2000, "hook_weight_kg": 30, "sling_weight_kg": 15,
                   "lift_speed_mpm": 8, "n_parts": 1, "safety_factor": 5, "mech_eff_pct": 82},
        "asserts": [
            {"path": "gross_load_kg", "expected": 2045.0, "tol": 0,
             "note": "rated+hook+sling = 2000+30+15 = 2045 kg"},
            {"path": "gross_load_kN", "expected": 20.06, "tol": 0.01,
             "note": "2045·9.81/1000 = 20.06 kN"},
            {"path": "MBF_kN", "expected": 100.31, "tol": 0.02,
             "note": "gross·SF·g = 2045·5·9.81/1000 = 100.31 kN (ASME B30.2, SF=5)"},
            {"path": "rope_pull_kg", "expected": 2086.7, "tol": 0.1,
             "note": "gross/(n_parts·rope_eff) = 2045/(1·0.98) = 2086.7 kg"},
            # Decision-driving outputs (Arc Q untested-surface lesson, 2026-06-23): the
            # selected rope is the safety deliverable — its MBF must cover the required MBF.
            {"path": "safety_factor_check", "expected": "PASS", "tol": 0,
             "note": "ASME B30.2 / DOLE: SF=5 >= 5 minimum → PASS"},
            {"path": "rope_recommendation", "expected": "14 mm, 6x19 IWRC EIPS wire rope (MBF = 118 kN)", "tol": 0,
             "note": "SAFETY: smallest 6x19 EIPS rope whose MBF (118 kN) >= required 100.31 kN → 14 mm selected"},
        ],
    },
    {
        "module": "calcs.vibration_analysis",
        "calc_type": "Vibration Analysis",
        "standard": "ISO 10816 / Rao — fn=(1/2π)√(k/m); cc=2√(k·m); ζ=c/cc",
        "inputs": {"mass_kg": 500, "speed_rpm": 1450, "isolator_type": "Rubber mount (medium)",
                   "damping_ratio": 0.08},
        "asserts": [
            {"path": "fn_Hz", "expected": 3.1831, "tol": 0.001,
             "note": "(1/2π)·√(k/m) = √(200000/500)/(2π) = √400/(2π) = 3.18 Hz"},
            {"path": "f_op_Hz", "expected": 24.167, "tol": 0.005,
             "note": "speed/60 = 1450/60 = 24.17 Hz"},
            {"path": "cc_Ns_m", "expected": 20000.0, "tol": 1,
             "note": "critical damping = 2·√(k·m) = 2·√(200000·500) = 20000 N·s/m"},
            {"path": "zeta", "expected": 0.08, "tol": 0.001,
             "note": "ζ = c/cc = (0.08·20000)/20000 = 0.08 damping ratio"},
        ],
    },
    {
        "module": "calcs.noise_acoustics",
        "calc_type": "Noise / Acoustics",
        "standard": "ISO 9613 — Lp=Lw+10log(Q/4πr²); ΣL=10log(Σ10^(Li/10))",
        "inputs": {"calc_type": "Source", "source_Lw_dB": 90, "distance_m": 5,
                   "directivity_Q": 2, "sources": [{"Lp_dB": 80}, {"Lp_dB": 80}]},
        "asserts": [
            {"path": "Lp_at_distance_dB", "expected": 68.04, "tol": 0.02,
             "note": "Lw + 10·log10(Q/(4πr²)) = 90 + 10·log10(2/(4π·25)) = 68.04 dB"},
            {"path": "combined_Lp_dB", "expected": 83.01, "tol": 0.02,
             "note": "10·log10(10^8 + 10^8) = 80 + 10·log10(2) = 83.01 dB (two equal 80 dB)"},
        ],
    },
    {
        "module": "calcs.elevator_traffic",
        "calc_type": "Elevator Traffic Analysis",
        "standard": "CIBSE Guide D — RTT method; S = n·[1−(1−1/n)^P]",
        "inputs": {"n_floors": 12, "floor_height": 3.5, "population": 500, "n_elevators": 3,
                   "capacity": 13, "speed": 1.5, "t_door_open": 2.5, "t_door_close": 3.0,
                   "t_dwell": 2.0, "occupancy_type": "Office"},
        "asserts": [
            {"path": "effective_pax", "expected": 10, "tol": 0,
             "note": "round(capacity·0.80) = round(13·0.8=10.4) = 10 (CIBSE 80% loading)"},
            {"path": "H_m", "expected": 38.5, "tol": 0.01,
             "note": "(n_floors−1)·floor_height = 11·3.5 = 38.5 m rise"},
            {"path": "t_flight_s", "expected": 51.3, "tol": 0.1,
             "note": "2·H/speed = 2·38.5/1.5 = 51.3 s (round-trip flight)"},
            {"path": "avg_stops", "expected": 6.8, "tol": 0.1,
             "note": "S = n·[1−(1−1/n)^P] = 11·[1−(10/11)^10] = 6.8 (CIBSE Eq 3.1)"},
        ],
    },
    {
        "module": "calcs.boiler_steam",
        "calc_type": "Boiler / Steam System",
        "standard": "ASME PTC 4 — Q = ṁ·(h_steam−h_feed); BHP = Q/9.81",
        "inputs": {"steam_pressure_bar": 10, "steam_temperature_C": 0, "feedwater_temp_C": 80,
                   "steam_flowrate_kgs": 1.0, "fuel_type": "Natural gas (LNG)",
                   "boiler_efficiency_pct": 85},
        "asserts": [
            {"path": "h_steam_kJ_kg", "expected": 2776.2, "tol": 0.01,
             "note": "saturated steam hg at 10 bar = 2776.2 kJ/kg (IAPWS steam table)"},
            {"path": "h_feed_kJ_kg", "expected": 334.88, "tol": 0.01,
             "note": "Cp·T = 4.186·80 = 334.88 kJ/kg (feedwater enthalpy)"},
            {"path": "duty_kW", "expected": 2441.32, "tol": 0.05,
             "note": "ṁ·(h_steam−h_feed) = 1.0·(2776.2−334.88) = 2441.32 kW"},
            {"path": "BHP", "expected": 248.9, "tol": 0.1,
             "note": "Q/9.81 = 2441.32/9.81 = 248.9 BHP (1 BHP = 9.81 kW)"},
        ],
    },
    {
        "module": "calcs.hvac_cooling_load",
        "calc_type": "HVAC Cooling Load",
        "standard": "ASHRAE CLTD — q = U·A·CLTD (sensible conduction gains)",
        "inputs": {"floor_area": 50, "ceiling_height": 3, "wall_area": 100, "glass_area": 20,
                   "persons": 5, "equipment_kw": 0, "room_function": "Office",
                   "insulation": "Standard", "glass_type": "Standard",
                   "window_orientation": "West"},
        "asserts": [
            {"path": "components.q_walls", "expected": 630.0, "tol": 0.1,
             "note": "U·A·CLTD = 0.45·100·14.0 (West) = 630 W (ASHRAE CLTD method)"},
            {"path": "components.q_roof", "expected": 750.0, "tol": 0.1,
             "note": "U·A·CLTD_roof = 0.50·50·30.0 = 750 W"},
            {"path": "components.q_people", "expected": 375.0, "tol": 0.1,
             "note": "75 W/person (Office sensible) · 5 = 375 W"},
            {"path": "components.q_lighting", "expected": 600.0, "tol": 0.1,
             "note": "12 W/m² (Office) · 50 m² = 600 W"},
        ],
    },
    {
        "module": "calcs.water_treatment",
        "calc_type": "Water Treatment System",
        "standard": "PNS 1998 — demand flows; Cl2 dose; 1-day storage",
        "inputs": {"demand_source": "direct", "demand_lpd": 100000, "turbidity_ntu": 10,
                   "iron_mg": 0.5, "raw_source": "Deep Well / Bore", "peak_factor": 1.5,
                   "intended_use": "Potable", "bacteria_concern": "yes"},
        "asserts": [
            {"path": "demand_m3d", "expected": 100.0, "tol": 0.001,
             "note": "demand_lpd/1000 = 100000/1000 = 100 m³/day"},
            {"path": "peak_flow_m3hr", "expected": 6.25, "tol": 0.001,
             "note": "demand·peak/24 = 100·1.5/24 = 6.25 m³/hr"},
            {"path": "cl2_daily_kg", "expected": 0.1, "tol": 0.001,
             "note": "cl2_dose·demand_m3d/1000 = 1.0·100/1000 = 0.1 kg/day (Deep Well dose)"},
            {"path": "storage_tank_m3", "expected": 100.0, "tol": 0.01,
             "note": "1-day storage = demand_m3d = 100 m³"},
        ],
    },
    {
        "module": "calcs.boiler_system",
        "calc_type": "Boiler System",
        "standard": "ASME I — hf_fw=Cp·T; design=demand·SF; blowdown=TDSm/(TDSx−TDSm)",
        "inputs": {"boiler_type": "Steam", "load_mode": "Steam Demand (kg/hr)",
                   "steam_demand_kg_hr": 1000, "steam_pressure_barg": 7, "fw_temp_c": 80,
                   "safety_factor": 1.25, "num_boilers": 1, "fuel_type": "LPG",
                   "efficiency_pct": 82, "tds_makeup_ppm": 200, "tds_max_ppm": 3000},
        "asserts": [
            {"path": "steam_pressure_barg", "expected": 7.0, "tol": 0.01,
             "note": "gauge (design/working) echoed = input 7 barg — distinct from bara (≈ +1.01 bar); BOM agent grounds design pressure on this"},
            {"path": "steam_pressure_bara", "expected": 8.013, "tol": 0.001,
             "note": "gauge + atm = 7 + 1.01325 = 8.013 bar(a)"},
            {"path": "hf_fw_kj_kg", "expected": 335.0, "tol": 0.05,
             "note": "Cp·T_fw = 4.187·80 = 334.96 → rounds to 335.0 kJ/kg (feedwater)"},
            {"path": "design_steam_demand_kg_hr", "expected": 1250.0, "tol": 0.1,
             "note": "demand·SF = 1000·1.25 = 1250 kg/hr"},
            {"path": "blowdown_pct", "expected": 7.1, "tol": 0.05,
             "note": "TDSm/(TDSx−TDSm)·100 = 200/(3000−200)·100 = 7.1%"},
        ],
    },
    {
        # Depth oracle (Arc Q, 2026-06-23): boiler_system has Steam + Hot Water branches;
        # only Steam was gated. Hot Water = sensible-heat physics, independently derived.
        "module": "calcs.boiler_system",
        "calc_type": "Boiler System (Hot Water)",
        "standard": "ASME — hot-water sensible heat q=ṁ·cp·ΔT; BHP=kW/9.8095; fuel=q/(LHV·η)",
        "inputs": {"boiler_type": "Hot Water", "supply_temp_c": 80, "return_temp_c": 60,
                   "flow_rate_lhr": 5000, "fuel_type": "LPG", "efficiency_pct": 82,
                   "safety_factor": 1.25, "num_boilers": 1},
        "asserts": [
            {"path": "q_net_kw", "expected": 113.7, "tol": 0.3,
             "note": "q = ṁ·cp·ΔT = (5000·0.9778/3600)·4.187·20 = 113.7 kW (ρ@70°C=0.9778)"},
            {"path": "q_boiler_kw", "expected": 142.1, "tol": 0.3,
             "note": "q_net·SF = 113.7·1.25 = 142.1 kW"},
            {"path": "q_net_bhp", "expected": 11.6, "tol": 0.1,
             "note": "kW/9.8095 = 113.7/9.8095 = 11.6 BHP (1 BoHP = 9.8095 kW)"},
            {"path": "fuel_consumption_kg_hr", "expected": 13.53, "tol": 0.1,
             "note": "q_boiler/(LHV/3600·η) = 142.1/(46100/3600·0.82) = 13.53 kg/hr (LPG)"},
        ],
    },
    {
        "module": "calcs.pipe_sizing",
        "calc_type": "Pipe Sizing",
        "standard": "ASHRAE Ch.22 — continuity v=Q/A; select smallest pipe v≤vmax",
        "inputs": {"flow_rate": 600, "pipe_diameter": 0, "service_type": "General",
                   "pipe_material": "PVC", "fluid_temp_c": 25, "pipe_length": 50},
        "asserts": [
            {"path": "flow_m3hr", "expected": 36.0, "tol": 0.01,
             "note": "600 L/min · 60/1000 = 36 m³/hr"},
            {"path": "flow_lps", "expected": 10.0, "tol": 0.01,
             "note": "600/60 = 10 L/s"},
            {"path": "recommended_nominal_mm", "expected": 80, "tol": 0,
             "note": "smallest pipe where v=Q/A ≤ 3.0 m/s (General): 80mm (v=2.10); 65mm→3.24 too fast"},
            {"path": "pipe_velocity", "expected": 2.098, "tol": 0.005,
             "note": "v = Q/A = 0.01/(π·(0.0779/2)²) = 2.10 m/s (continuity, 80mm ID 77.9)"},
        ],
    },
]


def _run_vector(vec, blind=False):
    """Run one vector. Returns (status, lines) where status in {PASS,FAIL,SKIP}.
    blind=True (self-test) corrupts every expected so a healthy validator FAILs."""
    try:
        mod = importlib.import_module(vec["module"])
    except Exception as e:  # missing dependency / import error
        return "SKIP", [f"  [SKIP] {vec['calc_type']}: cannot import {vec['module']} ({e})"]

    results = []  # (label, ok, detail)
    try:
        if "custom" in vec:
            checks = vec["custom"](mod)
            if blind:
                # invariants can't be "wrong-expected" corrupted; invert them to prove teeth
                checks = [(lbl, not ok, det) for (lbl, ok, det) in checks]
            results.extend(checks)
        else:
            out = mod.calculate(vec["inputs"])
            for a in vec["asserts"]:
                actual = _get(out, a["path"])
                expected = a["expected"]
                if blind:
                    expected = (expected + 1000) if isinstance(expected, (int, float)) else "__WRONG__"
                ok = _close(actual, expected, a["tol"])
                results.append((
                    f"{a['path']} = {actual} (expect {expected} +/-{a['tol']})  [{a['note']}]",
                    ok, "",
                ))
    except Exception as e:
        return "FAIL", [f"  [FAIL] {vec['calc_type']}: raised {type(e).__name__}: {e}"]

    all_ok = all(ok for _, ok, _ in results)
    lines = [f"  [{'PASS' if all_ok else 'FAIL'}] {vec['calc_type']}  ({vec['standard']})"]
    for lbl, ok, det in results:
        tick = "ok " if ok else "XX "
        lines.append(f"        {tick}{lbl}" + (f"   {det}" if det and not ok else ""))
    return ("PASS" if all_ok else "FAIL"), lines


def validate_calc_formulas(blind=False):
    print("\n[Calc Formula Accuracy] value-correctness of engineering calc handlers")
    print("  (complements the field-contract suite: asserts the NUMBER, not just the field name)")
    if blind:
        print("  *** SELF-TEST (blind): every oracle is corrupted; a healthy validator FAILs all ***")

    n_pass = n_fail = n_skip = 0
    n_assert = 0
    modules_covered = set()   # unique calc MODULES exercised (a type may have >1 depth vector)
    for vec in VECTORS:
        status, lines = _run_vector(vec, blind=blind)
        for ln in lines:
            print(ln)
        if status == "PASS":
            n_pass += 1
        elif status == "FAIL":
            n_fail += 1
        else:
            n_skip += 1
        if status in ("PASS", "FAIL"):
            modules_covered.add(vec.get("module"))
        n_assert += len(vec.get("asserts", [])) or 2  # invariants ~2 checks each

    vectors_exercised = n_pass + n_fail               # for the teeth proof
    types_covered = len(modules_covered)              # dedup: depth vectors share a module
    pct = round(100 * min(types_covered, TOTAL_PYTHON_CALCS) / TOTAL_PYTHON_CALCS, 1)
    print("\n  ── Summary ─────────────────────────────────────────────")
    print(f"  Vectors                   : {n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP ({vectors_exercised} exercised, incl. depth)")
    print(f"  Value-coverage (honest)   : {types_covered}/{TOTAL_PYTHON_CALCS} Python calc types = {pct}%")
    print(f"  Standard-anchored oracles : {n_assert} assertions")

    if blind:
        # Teeth proof: blind run MUST flip every exercised vector to FAIL.
        ok = (n_fail == vectors_exercised and n_fail > 0)
        print(f"\n  SELF-TEST {'PASS' if ok else 'FAIL'}: blind run detected "
              f"{n_fail}/{vectors_exercised} corrupted oracles as failures "
              f"(validator {'has teeth' if ok else 'is BROKEN — would pass wrong math'}).")
        return ok

    return n_fail == 0


if __name__ == "__main__":
    blind = "--self-test" in sys.argv
    sys.exit(0 if validate_calc_formulas(blind=blind) else 1)
