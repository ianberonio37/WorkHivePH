"""
Hoist Capacity — Vertical Transport (Option B port from TypeScript)
Standards: ASME B30.2 (Overhead and Gantry Cranes),
           ASME HST-4 (Hand Chain Lever Hoists),
           FEM 1.001 (Rules for Design of Hoisting Appliances),
           DOLE OSH Standards (Philippines)
Libraries: math

Method:
  Gross load = rated load + hook + sling
  Rope pull  = gross load / (n_parts × rope_efficiency_factor)
  Power      = rope_pull × rope speed, and rope speed = lift_speed × n_parts
  Motor HP   = power / (mech_eff × 746)  × 1.15 SF
"""

import math
from ._catalog import discloses, pick_at_least

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


# formula: hoist_capacity
@discloses
def calculate(inputs: dict) -> dict:
    rated_load_kg   = float(inputs.get("rated_load_kg",   2000))
    hook_weight_kg  = float(inputs.get("hook_weight_kg",  30))
    sling_weight_kg = float(inputs.get("sling_weight_kg", 15))
    lift_height_m   = float(inputs.get("lift_height_m",   6))
    lift_speed_mpm  = float(inputs.get("lift_speed_mpm",  8))
    n_parts         = int(inputs.get("n_parts",           1))
    safety_factor   = float(inputs.get("safety_factor",   5))
    mech_eff_pct    = float(inputs.get("mech_eff_pct",    82))
    # ★THE FORM'S HOIST TYPE CHANGED NOTHING (2026-11-02, ED-I1 Hoist Capacity, census_calc_input_reach.py). The page sends
    # hoist_type (Wire Rope Electric / Electric Chain / Manual Chain); this recommended a 6x19 wire rope and sized a motor for
    # all three - a chain hoist carries its load on load chain, and a manual chain hoist has no motor (its own guide says
    # "no motor sizing needed"). The type now decides the lifting medium and whether a motor is sized.
    hoist_type = str(inputs.get("hoist_type") or "Wire Rope Electric")
    is_chain   = "Chain" in hoist_type
    is_manual  = "Manual" in hoist_type

    gross_load_kg = rated_load_kg + hook_weight_kg + sling_weight_kg
    gross_load_kN = round(gross_load_kg * 9.81 / 1000.0, 2)

    # Minimum breaking force required - per PART of rope (ASME B30.2: the rated load plus the block, divided by the parts
    # of rope, shall not exceed 1/5 of the rope's minimum breaking force).
    # ★THE PARTS OF LINE NEVER REACHED THE ROPE (2026-11-02, ED-G1 Hoist, read against the guide). This was gross load x SF
    # whatever the reeving, so a 4-part hoist for 2045 kg was told to fit a 14 mm rope (MBF >= 100 kN) when each part
    # carries 511 kg and an 8 mm rope (MBF >= 25 kN) meets the 5:1 design factor - the rope, the drum and the sheaves all
    # specified oversize. One part is unchanged (100.31 kN).
    MBF_kg = gross_load_kg / max(n_parts, 1) * safety_factor
    MBF_kN = round(MBF_kg * 9.81 / 1000.0, 2)

    # Rope efficiency (0.98 per sheave/part — standard for lubricated wire rope)
    rope_eff = round(0.98 ** n_parts, 2)
    rope_pull_kg = round(gross_load_kg / (n_parts * rope_eff), 1)
    rope_pull_N  = round(rope_pull_kg * 9.81)

    # Lift speed - this is the LOAD's speed, which is how a hoist is specified
    # unrounded - rounding 8 m/min to 0.13 m/s before the power cut it 2.5% (2835 W for 2907 at 4 parts); shown rounded
    speed_ms = lift_speed_mpm / 60.0

    # ★THE ROPE MOVES n_parts TIMES FASTER THAN THE LOAD (2026-09-16). Reeving divides the rope TENSION
    # by n and multiplies the rope TRAVEL by n; power is their product and is therefore invariant - a
    # block and tackle trades force for distance and buys no power. This paired the divided tension with
    # the undivided speed, so the reported power fell as 1/n_parts: 2661 W at 1 part, 1358 at 2, 709 at 4,
    # against a true 2675 W at the load. The recommended motor followed it down - 7.5 HP, 3 HP, 1.5 HP for
    # one and the same lift - so the calculator was least right exactly where a rigger adds parts, which is
    # when the load is heaviest. Written as a multiplication rather than cancelled into the algebra so the
    # names keep saying what the machine does.
    rope_speed_ms = round(speed_ms * n_parts, 4)

    # Power at rope = rope tension x rope speed
    power_W = round(rope_pull_N * rope_speed_ms)

    # Motor sizing
    mech_eff = mech_eff_pct / 100.0
    motor_hp_calc = round(power_W / (mech_eff * 746), 2)
    motor_hp_sf   = motor_hp_calc * 1.15   # 15% service factor
    motor_hp_std  = pick_at_least(STD_HP, motor_hp_sf, "hoist motor (hp)")
    motor_kW      = round(motor_hp_std * 0.746, 2)
    motor_note    = ""
    if is_manual:
        motor_hp_calc = motor_hp_sf = motor_hp_std = motor_kW = 0
        motor_note    = "Manual chain hoist: hand-operated, no motor to size."

    # Wire rope selection
    selected = pick_at_least(ROPE_SIZES, MBF_kN, "wire rope minimum breaking force (kN)", key="MBF")
    rope_rec  = f"{selected['dia']}, 6x19 IWRC EIPS wire rope (MBF = {selected['MBF']} kN)"
    if is_chain:
        rope_rec = (f"load chain rated for a working load of at least {gross_load_kg} kg (ASME B30.16 / the hoist maker's "
                    f"rating) - a chain hoist carries its load on chain, so a wire rope does not apply")

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
        "speed_ms":               round(speed_ms, 4),
        "power_W":                power_W,
        "rope_speed_ms":          rope_speed_ms,   # n_parts x the hook speed - what the report's power line multiplies
        "n_parts":                n_parts,
        "motor_hp_calc":          motor_hp_calc,
        "motor_hp_std":           motor_hp_std,
        "motor_kW":               motor_kW,
        "rope_recommendation":    rope_rec,
        # the selected rope's MBF over the load on EACH part (ASME B30.2) - the drawing divided by the whole gross load,
        # which understates the factor n-fold on a multi-part hoist
        "rope_sf_achieved":       (round(float(selected["MBF"]) / (gross_load_kN / max(n_parts, 1)), 2)
                                   if isinstance(selected, dict) and selected.get("MBF") and gross_load_kN > 0 and not is_chain else None),
        "rope_length_m":          rope_length_m,
        "safety_factor_check":    sf_check,
        "hoist_type":             hoist_type,
        "lifting_medium":         "load chain" if is_chain else "wire rope",
        "motor_note":             motor_note,
    }
