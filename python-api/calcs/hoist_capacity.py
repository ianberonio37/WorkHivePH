"""
Hoist Capacity — Vertical Transport (Option B port from TypeScript)
Standards: ASME B30.2 (Overhead and Gantry Cranes),
           ASME HST-4 (Hand Chain Lever Hoists),
           FEM 1.001 (Rules for Design of Hoisting Appliances),
           DOLE OSHS Rule 1230 (Philippines)
Libraries: math

Method:
  Gross load = rated load + hook + sling
  Rope pull  = gross load / (n_parts × rope_efficiency_factor)
  Power      = rope_pull × lift_speed
  Motor HP   = power / (mech_eff × 746)  × 1.15 SF
"""

import math

# Wire rope 6×19 IWRC EIPS minimum breaking force (kN) by diameter
ROPE_SIZES: list[dict] = [
    {"dia": "8 mm",  "MBF": 38.7},  {"dia": "10 mm", "MBF": 60.4},
    {"dia": "12 mm", "MBF": 87.1},  {"dia": "14 mm", "MBF": 118},
    {"dia": "16 mm", "MBF": 154},   {"dia": "18 mm", "MBF": 195},
    {"dia": "20 mm", "MBF": 241},   {"dia": "22 mm", "MBF": 291},
    {"dia": "24 mm", "MBF": 347},   {"dia": "26 mm", "MBF": 406},
    {"dia": "28 mm", "MBF": 471},   {"dia": "32 mm", "MBF": 615},
    {"dia": "36 mm", "MBF": 779},
]

# Standard motor HP (IEC/NEMA common sizes — Philippine market)
STD_HP = [0.5, 1, 1.5, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200]


def calculate(inputs: dict) -> dict:
    rated_load_kg   = float(inputs.get("rated_load_kg",   2000))
    hook_weight_kg  = float(inputs.get("hook_weight_kg",  30))
    sling_weight_kg = float(inputs.get("sling_weight_kg", 15))
    lift_height_m   = float(inputs.get("lift_height_m",   6))
    lift_speed_mpm  = float(inputs.get("lift_speed_mpm",  8))
    n_parts         = int(inputs.get("n_parts",           1))
    safety_factor   = float(inputs.get("safety_factor",   5))
    mech_eff_pct    = float(inputs.get("mech_eff_pct",    82))

    gross_load_kg = rated_load_kg + hook_weight_kg + sling_weight_kg
    gross_load_kN = round(gross_load_kg * 9.81 / 1000.0, 2)

    # Minimum breaking force required
    MBF_kg = gross_load_kg * safety_factor
    MBF_kN = round(MBF_kg * 9.81 / 1000.0, 2)

    # Rope efficiency (0.98 per sheave/part — standard for lubricated wire rope)
    rope_eff = round(0.98 ** n_parts, 2)
    rope_pull_kg = round(gross_load_kg / (n_parts * rope_eff), 1)
    rope_pull_N  = round(rope_pull_kg * 9.81)

    # Lift speed
    speed_ms = round(lift_speed_mpm / 60.0, 2)

    # Power at rope
    power_W = round(rope_pull_N * speed_ms)

    # Motor sizing
    mech_eff = mech_eff_pct / 100.0
    motor_hp_calc = round(power_W / (mech_eff * 746), 2)
    motor_hp_sf   = motor_hp_calc * 1.15   # 15% service factor
    motor_hp_std  = next((hp for hp in STD_HP if hp >= motor_hp_sf), STD_HP[-1])
    motor_kW      = round(motor_hp_std * 0.746, 2)

    # Wire rope selection
    selected = next((r for r in ROPE_SIZES if r["MBF"] >= MBF_kN), ROPE_SIZES[-1])
    rope_rec  = f"{selected['dia']}, 6x19 IWRC EIPS wire rope (MBF = {selected['MBF']} kN)"

    # Rope length on drum (n_parts × lift height + dead wraps)
    dead_wrap = 3 * math.pi * 0.15   # 3 wraps on ~150mm core
    rope_length_m = math.ceil(lift_height_m * n_parts + dead_wrap)

    sf_check = "PASS" if safety_factor >= 5 else "FAIL"

    return {
        "gross_load_kg":          gross_load_kg,
        "gross_load_kN":          gross_load_kN,
        "MBF_kg":                 MBF_kg,
        "MBF_kN":                 MBF_kN,
        "rope_efficiency_factor": rope_eff,
        "rope_pull_kg":           rope_pull_kg,
        "rope_pull_N":            rope_pull_N,
        "speed_ms":               speed_ms,
        "power_W":                power_W,
        "motor_hp_calc":          motor_hp_calc,
        "motor_hp_std":           motor_hp_std,
        "motor_kW":               motor_kW,
        "rope_recommendation":    rope_rec,
        "rope_length_m":          rope_length_m,
        "safety_factor_check":    sf_check,
    }
