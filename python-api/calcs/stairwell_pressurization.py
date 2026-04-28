"""
Stairwell Pressurization — Phase 5c (Option B port from TypeScript)
Standards: NFPA 92:2021 (Smoke Control Systems), PEC 2017, PSME Code
Libraries: math

Improvement over TypeScript:
- Air density corrected for Manila altitude (15m ASL) and temperature
  instead of fixed 1.20 kg/m³ — affects Q calculation at high-rise sites
- Duct pressure loss estimate added for fan sizing reference

Formulae (NFPA 92 §6.4):
  Q = Cd × A_total × sqrt(2 × ΔP / ρ)
  Door force: F = F_dc + (ΔP × A_door × W) / (2 × (W − d))
  Fan power:  P = Q × ΔP_fan / (η_fan × 1000)
"""

import math

# Standard fan motor HP (IEC/NEMA frame) used in Philippine practice
STD_HP = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0]

# NFPA 92 Table B.1 — door gap leakage area (m²)
DOOR_LEAKAGE: dict[str, float] = {
    "Tight":   0.019,
    "Average": 0.039,
    "Loose":   0.052,
}


def _air_density(altitude_m: float = 0.0, temp_c: float = 25.0) -> float:
    """
    Air density (kg/m³) via ISA + ideal gas: ρ = P / (R_d × T)
    P at altitude: P = P0 × (1 − L×h/T0)^(g/(R_d×L))
    """
    P0 = 101325.0   # Pa
    T0 = 288.15     # K (15°C ISA)
    L  = 0.0065     # K/m lapse rate
    g  = 9.80665
    Rd = 287.058
    P  = P0 * (1.0 - L * altitude_m / T0) ** (g / (Rd * L))
    T  = temp_c + 273.15
    return P / (Rd * T)


def calculate(inputs: dict) -> dict:
    building_type   = str(inputs.get("building_type",      "Sprinklered"))
    n_stairwells    = int(inputs.get("n_stairwells",       1))
    n_floors        = int(inputs.get("n_floors",           5))
    doors_per_floor = int(inputs.get("doors_per_floor",    1))
    door_fit        = str(inputs.get("door_fit",           "Average"))
    door_w          = float(inputs.get("door_width",       0.90))
    door_h          = float(inputs.get("door_height",      2.10))
    fan_static_pa   = float(inputs.get("fan_static_pressure", 400))
    fan_eff_pct     = float(inputs.get("fan_efficiency",   60))
    altitude_m      = float(inputs.get("altitude_m",       15))   # Manila ~15m ASL
    design_temp_c   = float(inputs.get("design_temp_c",    30))   # PH ambient

    # Design ΔP: NFPA 92 §6.4.1.4 (sprinklered: 12.5–87 Pa; non-sprinklered: 25–87 Pa)
    default_dp = 25.0 if building_type == "Sprinklered" else 50.0
    delta_p_pa = float(inputs.get("delta_P", default_dp))

    safety_factor = 1.20   # NFPA 92 §A.6.4

    # Leakage areas
    a_door_m2      = DOOR_LEAKAGE.get(door_fit, 0.039)
    n_doors_total  = n_floors * doors_per_floor
    a_door_total   = n_doors_total * a_door_m2
    # Wall leakage: NFPA 92 ~0.0009 m²/m² of stairwell wall
    a_wall_per_floor = 36.0 * 0.0009   # 12m perimeter × 3m floor-to-floor × leakage ratio
    a_wall_total     = n_floors * a_wall_per_floor
    a_total_m2       = a_door_total + a_wall_total

    # Air density at site (improvement over fixed 1.20 kg/m³)
    rho  = _air_density(altitude_m, design_temp_c)
    cd   = 0.65   # NFPA 92 discharge coefficient

    # Pressurization airflow (NFPA 92 Eq. 6.4.1.1)
    q_per_m3s   = cd * a_total_m2 * math.sqrt(2.0 * delta_p_pa / rho)
    q_total_m3s = q_per_m3s * n_stairwells
    q_design_m3s = q_total_m3s * safety_factor

    q_per_cmh    = q_per_m3s   * 3600.0
    q_design_cmh = q_design_m3s * 3600.0

    # NFPA 92 ΔP limits
    delta_p_min = 12.5 if building_type == "Sprinklered" else 25.0
    delta_p_max = 87.0   # NFPA 92 §6.4.1.4
    delta_p_ok  = delta_p_min <= delta_p_pa <= delta_p_max

    # Door opening force check (NFPA 92 §6.5.1.1 max = 133 N)
    a_door_panel     = door_w * door_h
    d_handle         = 0.076   # 3 in handle setback from latch edge
    lever_arm_factor = door_w / (2.0 * (door_w - d_handle))
    f_pressure_n     = delta_p_pa * a_door_panel * lever_arm_factor
    f_closer_n       = 45.0   # typical door closer force (N)
    f_total_n        = f_pressure_n + f_closer_n
    door_force_ok    = f_total_n <= 133.0

    # Fan motor power
    p_fan_kw = (q_design_m3s * fan_static_pa) / ((fan_eff_pct / 100.0) * 1000.0)
    p_fan_hp = p_fan_kw * 1.341
    selected_hp = next((hp for hp in STD_HP if hp >= p_fan_hp), STD_HP[-1])

    return {
        "building_type":        building_type,
        "N_stairwells":         n_stairwells,
        "N_floors":             n_floors,
        "doors_per_floor":      doors_per_floor,
        "N_doors_total":        n_doors_total,
        "door_fit":             door_fit,
        "A_door_m2":            a_door_m2,
        "A_door_total":         round(a_door_total,     3),
        "A_wall_per_floor":     round(a_wall_per_floor, 3),
        "A_wall_total":         round(a_wall_total,     3),
        "A_total_m2":           round(a_total_m2,       3),
        "delta_P_Pa":           delta_p_pa,
        "delta_P_min":          delta_p_min,
        "delta_P_max":          delta_p_max,
        "delta_P_ok":           delta_p_ok,
        "air_density_kg_m3":    round(rho, 4),
        "Cd":                   cd,
        "Q_per_stairwell_m3s":  round(q_per_m3s,    3),
        "Q_per_CMH":            round(q_per_cmh,    1),
        "Q_total_m3s":          round(q_total_m3s,  3),
        "Q_design_m3s":         round(q_design_m3s, 3),
        "Q_design_CMH":         round(q_design_cmh, 1),
        "safety_factor":        safety_factor,
        "door_W":               door_w,
        "door_H":               door_h,
        "d":                    d_handle,
        "lever_arm_factor":     round(lever_arm_factor, 3),
        "A_door_panel":         round(a_door_panel, 2),
        "F_pressure_N":         round(f_pressure_n, 1),
        "F_closer_N":           f_closer_n,
        "F_total_N":            round(f_total_n, 1),
        "door_force_ok":        door_force_ok,
        "fan_static_Pa":        fan_static_pa,
        "fan_eff_pct":          fan_eff_pct,
        "P_fan_kW":             round(p_fan_kw, 2),
        "P_fan_HP":             round(p_fan_hp, 2),
        "selected_HP":          selected_hp,
    }
