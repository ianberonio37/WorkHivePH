"""
FCU Selection - Phase 3b
Standards: ASHRAE 62.1, ASHRAE 90.1, ASHRAE 2021 Fundamentals Ch.1,
           PSME Code, ARI 440 (Fan Coil Units)
Libraries: psychrolib (entering wet-bulb state point), math

Calculates:
- Room sensible and latent load from inputs (or accepts pre-calculated values)
- Required airflow from sensible load + supply-room temperature difference
- Chilled water flow at standard 6°C delta-T (ARI 440 rating condition)
- Coil entering wet-bulb (EWB) and leaving conditions via psychrolib
- Standard FCU size selection from ARI 440 nominal capacity table
- ASHRAE 62.1 OA rate per zone (2.5 L/s/person + 0.3 L/s/m2)
- Fan power check (ASHRAE 90.1 fan power density ≤ 0.3 W/(L/s) for FCU)
"""

import psychrolib
import math

psychrolib.SetUnitSystem(psychrolib.SI)

# ─── Standard FCU nominal capacities (ARI 440 rating conditions) ─────────────
# Rating: EWT 7°C CW, 27°C/50% RH room, 6°C delta-T
# Format: {nominal_size: {"total_kW": x, "sensible_kW": y, "airflow_m3hr": z}}
FCU_CATALOGUE: list[dict] = [
    {"size": "FCU-200",  "total_kW":  1.5, "sensible_kW":  1.1, "airflow_m3hr":  200},
    {"size": "FCU-300",  "total_kW":  2.2, "sensible_kW":  1.6, "airflow_m3hr":  300},
    {"size": "FCU-400",  "total_kW":  2.8, "sensible_kW":  2.0, "airflow_m3hr":  400},
    {"size": "FCU-500",  "total_kW":  3.5, "sensible_kW":  2.5, "airflow_m3hr":  500},
    {"size": "FCU-600",  "total_kW":  4.2, "sensible_kW":  3.0, "airflow_m3hr":  600},
    {"size": "FCU-800",  "total_kW":  5.6, "sensible_kW":  4.0, "airflow_m3hr":  800},
    {"size": "FCU-1000", "total_kW":  7.0, "sensible_kW":  5.0, "airflow_m3hr": 1000},
    {"size": "FCU-1200", "total_kW":  8.4, "sensible_kW":  6.0, "airflow_m3hr": 1200},
    {"size": "FCU-1500", "total_kW": 10.5, "sensible_kW":  7.5, "airflow_m3hr": 1500},
    {"size": "FCU-2000", "total_kW": 14.0, "sensible_kW": 10.0, "airflow_m3hr": 2000},
    {"size": "FCU-2500", "total_kW": 17.5, "sensible_kW": 12.5, "airflow_m3hr": 2500},
    {"size": "FCU-3000", "total_kW": 21.0, "sensible_kW": 15.0, "airflow_m3hr": 3000},
    {"size": "FCU-4000", "total_kW": 28.0, "sensible_kW": 20.0, "airflow_m3hr": 4000},
]

# Chilled water design delta-T - ARI 440 standard
CW_DELTA_T = 6.0   # °C  (EWT 7°C → LWT 13°C)
CW_EWT_C   = 7.0   # °C  entering water temperature (chiller supply)
CW_LWT_C   = CW_EWT_C + CW_DELTA_T   # 13°C

# Water density and Cp at ~10°C
RHO_WATER = 999.7   # kg/m³
CP_WATER  = 4186.0  # J/(kg·K)

# ASHRAE 90.1 FCU fan power density limit
FAN_POWER_LIMIT_W_LPS = 0.30   # W/(L/s) - FCU integral fan, ASHRAE 90.1 Table 10.8

# ARI 440 coil face velocity range (m/s)
FACE_VEL_MIN = 1.5
FACE_VEL_MAX = 2.8
FACE_VEL_STD = 2.0   # standard ARI rating face velocity

# ─── Fan efficiency for FCU (small centrifugal / cross-flow) ─────────────────
FCU_FAN_EFF  = 0.45   # lower than AHU - compact scroll/cross-flow fan
FCU_MOTOR_EFF = 0.85


def _coil_ewb(room_db: float, room_rh: float) -> tuple[float, float, float]:
    """
    Entering wet-bulb (EWB) and enthalpy at room conditions.
    Returns (ewb_c, w_kgkg, h_Jkg).
    """
    try:
        w  = psychrolib.GetHumRatioFromRelHum(room_db, room_rh / 100, 101325)
        h  = psychrolib.GetMoistAirEnthalpy(room_db, w)
        wb = psychrolib.GetTWetBulbFromHumRatio(room_db, w, 101325)
        return wb, w, h
    except Exception:
        return 17.0, 0.0105, 51500.0


def _leaving_air_state(supply_db: float) -> tuple[float, float, float]:
    """
    Leaving air state - assume near-saturation off coil (RH ~95%).
    Returns (wb_c, w_kgkg, h_Jkg).
    """
    try:
        w  = psychrolib.GetHumRatioFromRelHum(supply_db, 0.95, 101325)
        h  = psychrolib.GetMoistAirEnthalpy(supply_db, w)
        wb = psychrolib.GetTWetBulbFromHumRatio(supply_db, w, 101325)
        return wb, w, h
    except Exception:
        return 12.5, 0.0088, 35000.0


def _pipe_nps_from_flow(lps: float) -> tuple[int, float]:
    """Select NPS (mm) for CHW pipe at ≤2.5 m/s and return (nps_mm, vel_ms)."""
    q_m3s = lps / 1000.0   # L/s → m³/s
    for nps in [15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150]:
        area = math.pi * (nps / 1000.0 / 2.0) ** 2
        v = q_m3s / area if area > 0 else 999.0
        if v <= 2.5:
            return nps, round(v, 2)
    return 150, round(q_m3s / (math.pi * 0.075 ** 2), 2)


def _calc_single_zone(inputs: dict) -> dict:
    """Internal single-zone calculation (existing logic)."""
    return calculate(dict(inputs, _skip_multi=True))


def calculate(inputs: dict) -> dict:
    """
    Main entry point. Supports both single-zone and multi-room (rooms[]) inputs.
    - Single zone: reads q_sensible_w / q_total_kW / floor_area etc. directly.
    - Multi-room:  iterates inputs.rooms[], selects FCU per zone, aggregates totals.
    Compatible with TypeScript calcFCUSelection() input keys.
    """
    # ── Multi-room dispatch ───────────────────────────────────────────────────
    rooms_input = inputs.get("rooms", [])
    if rooms_input and len(rooms_input) > 0 and not inputs.get("_skip_multi"):
        diversity   = float(inputs.get("diversity_factor", 0.85))
        chw_supply  = float(inputs.get("chw_supply_c", CW_EWT_C))
        chw_return  = float(inputs.get("chw_return_c", CW_LWT_C))
        dT_custom   = chw_return - chw_supply

        room_results: list[dict] = []
        total_units    = 0
        total_conn_kw  = 0.0
        total_chw_lps  = 0.0

        for rm in rooms_input:
            qty  = max(1, int(rm.get("qty", 1)))
            load = float(rm.get("cooling_load_kw", 0) or rm.get("load_kw", 0))
            area = float(rm.get("area_m2", 50))
            name = str(rm.get("room_name", "Zone"))

            # Build single-zone sub-call
            zone_inp = dict(inputs)
            zone_inp.update({
                "q_total_kW":    load,
                "floor_area":    area,
                "room_name":     name,
                "rooms":         [],       # prevent recursion
                "_skip_multi":   True,
            })
            z = calculate(zone_inp)

            # chw_flow_lps_total is stored as kg/s ≈ L/s (ρ_water ≈ 1 kg/L)
            fcu_flow_lps = float(z.get("chw_flow_lps_total", 0) or
                                  z.get("cw_flow_lps_total", 0))

            rr = {
                "room_name":          name,
                "area_m2":            area,
                "load_kw":            round(load, 2),
                "cooling_load_kw":    round(load, 2),   # alias for renderer
                "qty":                qty,
                "selected_model":     z.get("selected_fcu", "—"),
                "selected_kw":        z.get("fcu_capacity_kW", 0),
                "selected_tr":        round(z.get("fcu_capacity_kW", 0) / 3.517, 2),
                "airflow_cmh":        z.get("fcu_airflow_m3hr", 0),
                "chw_flow_lps_total": round(fcu_flow_lps * qty, 3),
            }
            room_results.append(rr)
            total_units   += qty
            total_conn_kw += z.get("fcu_capacity_kW", 0) * qty
            total_chw_lps += fcu_flow_lps * qty

        total_req_kw  = sum(float(rm.get("cooling_load_kw", 0)) for rm in rooms_input)
        total_des_kw  = total_req_kw * diversity
        nps_mm, vel_ms = _pipe_nps_from_flow(total_chw_lps)

        return {
            # Aggregate totals (renderer uses these)
            "total_units":         total_units,
            "total_connected_kw":  round(total_conn_kw, 2),
            "total_connected_tr":  round(total_conn_kw / 3.517, 2),
            "total_required_kw":   round(total_req_kw, 2),
            "total_design_kw":     round(total_des_kw, 2),
            "total_design_tr":     round(total_des_kw / 3.517, 2),
            "total_chw_lps":       round(total_chw_lps, 3),
            "main_pipe_nps_mm":    nps_mm,
            "main_pipe_vel_ms":    vel_ms,
            "diversity_factor":    diversity,
            # Room-level results
            "rooms":               room_results,
            # Single-zone aliases (for diagram / narrative)
            "fcu_capacity_kW":     round(total_conn_kw / max(total_units, 1), 2),
            "fcu_airflow_m3hr":    room_results[0]["airflow_cmh"] if room_results else 0,
            "chw_flow_lps_total":  round(total_chw_lps, 3),
            "selected_fcu":        room_results[0]["selected_model"] if room_results else "—",
            "selected_kw":         room_results[0]["selected_kw"] if room_results else 0,
            "qty":                 total_units,
            "room_name":           f"{len(rooms_input)} zones",
            "cw_ewt_c":            chw_supply,
            "cw_lwt_c":            chw_return,
            "calculation_source":  "python/psychrolib",
            "standard":            "ARI 440 | ASHRAE 62.1 | ASHRAE 90.1 | PSME",
        }
    # ── Single-zone path (existing logic) ────────────────────────────────────
    # ── Room load inputs ──────────────────────────────────────────────────────
    q_sensible_w = float(inputs.get("q_sensible_w",      0)
                     or  inputs.get("q_sensible_total",   0)
                     or  inputs.get("q_sensible",         0))
    q_latent_w   = float(inputs.get("q_latent_w",        0)
                     or  inputs.get("q_latent",           0))
    q_total_w    = float(inputs.get("q_total_w",         0)
                     or  inputs.get("q_total",            0))

    # Accept kW input form as well
    if q_sensible_w <= 0:
        q_sensible_w = float(inputs.get("q_sensible_kW", 0)) * 1000
    if q_total_w <= 0:
        q_total_w = float(inputs.get("q_total_kW", 0)) * 1000

    if q_total_w <= 0 and q_sensible_w > 0:
        q_total_w = q_sensible_w + q_latent_w

    if q_total_w <= 0:
        q_total_w    = 5000.0   # default 5 kW
        q_sensible_w = 3500.0
        q_latent_w   = 1500.0

    if q_sensible_w <= 0:
        q_sensible_w = q_total_w * 0.70
        q_latent_w   = q_total_w * 0.30

    # ── Room conditions ───────────────────────────────────────────────────────
    room_db      = float(inputs.get("indoor_temp",      24.0))
    room_rh_pct  = float(inputs.get("indoor_rh_pct",    55.0))
    supply_db    = float(inputs.get("supply_air_temp_c", 13.0))
    floor_area   = float(inputs.get("floor_area",        50.0))
    persons      = float(inputs.get("persons",            5.0))
    ceiling_h    = float(inputs.get("ceiling_height",     3.0))
    design_margin = float(inputs.get("design_margin_pct", 10.0))

    # ── Psychrometrics at room (EWB) and leaving (LAT) ────────────────────────
    ewb_c, room_w, room_h = _coil_ewb(room_db, room_rh_pct)
    lat_wb, sa_w, sa_h    = _leaving_air_state(supply_db)

    # ── Required airflow from sensible load ───────────────────────────────────
    rho_air  = 1.15   # kg/m³ tropical
    cp_air   = 1006   # J/(kg·K)
    dT       = max(room_db - supply_db, 4.0)
    mass_kgs = q_sensible_w / (cp_air * dT)
    flow_m3s = mass_kgs / rho_air
    flow_m3hr = flow_m3s * 3600
    flow_cfm  = flow_m3s * 2118.88

    # Design flow with margin
    flow_design_m3hr = flow_m3hr * (1 + design_margin / 100)

    # SHR
    shr = q_sensible_w / max(q_total_w, 1)

    # ── Room air changes per hour ─────────────────────────────────────────────
    room_vol = floor_area * ceiling_h
    ach      = flow_m3hr / max(room_vol, 1)

    # ── FCU selection - smallest unit that covers total load with margin ───────
    q_design_kw = q_total_w * (1 + design_margin / 100) / 1000
    selected    = None
    for unit in FCU_CATALOGUE:
        if unit["total_kW"] >= q_design_kw:
            selected = unit
            break
    if selected is None:
        # Multiple units required
        n_units   = math.ceil(q_design_kw / FCU_CATALOGUE[-1]["total_kW"])
        selected  = {
            "size":         f"{n_units}× {FCU_CATALOGUE[-1]['size']}",
            "total_kW":     FCU_CATALOGUE[-1]["total_kW"] * n_units,
            "sensible_kW":  FCU_CATALOGUE[-1]["sensible_kW"] * n_units,
            "airflow_m3hr": FCU_CATALOGUE[-1]["airflow_m3hr"] * n_units,
            "n_units":      n_units,
        }

    # Capacity surplus
    cap_surplus_pct = round(
        (selected["total_kW"] - q_design_kw) / q_design_kw * 100, 1
    )

    # ── Chilled water flow ────────────────────────────────────────────────────
    # Q_water = Q_total / (rho * Cp * delta_T)
    cw_flow_kgs  = (selected["total_kW"] * 1000) / (CP_WATER * CW_DELTA_T)
    cw_flow_lps  = cw_flow_kgs / RHO_WATER
    cw_flow_lmin = cw_flow_lps * 60

    # ── Coil face area ────────────────────────────────────────────────────────
    unit_flow_m3s = selected["airflow_m3hr"] / 3600
    coil_area_m2  = unit_flow_m3s / FACE_VEL_STD
    coil_h        = round(math.sqrt(coil_area_m2 / 1.5), 2)
    coil_w        = round(coil_h * 1.5, 2)

    # Actual face velocity at selected unit's rated airflow
    face_vel_actual = unit_flow_m3s / max(coil_area_m2, 0.01)

    # ── Fan power ─────────────────────────────────────────────────────────────
    # FCU fans - low static, ~50-80 Pa external
    fcu_static_pa  = 60.0   # Pa typical FCU fan ESP
    fan_kw         = (unit_flow_m3s * fcu_static_pa) / (FCU_FAN_EFF * FCU_MOTOR_EFF * 1000)
    flow_lps       = unit_flow_m3s * 1000
    fan_w_lps      = (fan_kw * 1000) / max(flow_lps, 1)
    fan_power_ok   = fan_w_lps <= FAN_POWER_LIMIT_W_LPS

    # ── ASHRAE 62.1 OA check ──────────────────────────────────────────────────
    oa_req_lps    = persons * 2.5 + floor_area * 0.3
    oa_req_m3hr   = oa_req_lps * 3.6
    oa_adequate   = selected["airflow_m3hr"] >= oa_req_m3hr

    # ── Coil load breakdown ───────────────────────────────────────────────────
    # Coil total from enthalpy difference × mass flow
    coil_total_check = mass_kgs * (room_h - sa_h) / 1000   # kW check

    return {
        # Room load
        "q_total_kW":          round(q_total_w / 1000, 2),
        "q_sensible_kW":       round(q_sensible_w / 1000, 2),
        "q_latent_kW":         round(q_latent_w / 1000, 2),
        "q_design_kW":         round(q_design_kw, 2),
        "shr":                 round(shr, 3),

        # Required airflow
        "required_flow_m3hr":  round(flow_m3hr, 1),
        "required_flow_cfm":   round(flow_cfm, 1),
        "design_flow_m3hr":    round(flow_design_m3hr, 1),
        "supply_temp_c":       supply_db,
        "air_changes_per_hr":  round(ach, 1),

        # Selected FCU
        "selected_fcu":        selected["size"],
        "fcu_capacity_kW":     selected["total_kW"],
        "fcu_sensible_kW":     selected["sensible_kW"],
        "fcu_airflow_m3hr":    selected["airflow_m3hr"],
        "capacity_surplus_pct": cap_surplus_pct,

        # Chilled water
        "cw_flow_lps":         round(cw_flow_lps, 3),
        "cw_flow_lmin":        round(cw_flow_lmin, 2),
        "cw_ewt_c":            CW_EWT_C,
        "cw_lwt_c":            CW_LWT_C,
        "cw_delta_T_c":        CW_DELTA_T,

        # Coil geometry
        "coil_face_area_m2":   round(coil_area_m2, 3),
        "coil_face_vel_ms":    round(face_vel_actual, 2),
        "coil_height_m":       coil_h,
        "coil_width_m":        coil_w,

        # Fan
        "fan_power_kW":        round(fan_kw, 3),
        "fan_power_w_lps":     round(fan_w_lps, 3),
        "fan_power_ok":        fan_power_ok,

        # Psychrometrics
        "psychrometrics": {
            "room_db_c":       room_db,
            "room_rh_pct":     room_rh_pct,
            "room_ewb_c":      round(ewb_c, 1),
            "room_w_gkg":      round(room_w * 1000, 2),
            "room_h_kJkg":     round(room_h / 1000, 2),
            "supply_db_c":     supply_db,
            "supply_wb_c":     round(lat_wb, 1),
            "supply_w_gkg":    round(sa_w * 1000, 2),
            "supply_h_kJkg":   round(sa_h / 1000, 2),
            "coil_total_kW_check": round(coil_total_check, 2),
        },

        # Ventilation
        "oa_required_lps":     round(oa_req_lps, 1),
        "oa_required_m3hr":    round(oa_req_m3hr, 1),
        "oa_adequate":         oa_adequate,

        # Metadata
        "inputs_used": {
            "room_function":     inputs.get("room_function", "Office"),
            "design_margin_pct": design_margin,
            "cw_delta_T_c":      CW_DELTA_T,
            "supply_air_temp_c": supply_db,
        },
        "calculation_source": "python/psychrolib",
        "standard": "ARI 440 | ASHRAE 62.1 | ASHRAE 90.1 | PSME",

        # ── Legacy renderer aliases (frontend renderFCUSelectionReport) ────────
        "cooling_load_kw":    round(q_design_kw, 2),
        "selected_kw":        selected["total_kW"],
        "airflow_cmh":        selected["airflow_m3hr"],
        "chw_flow_lps_total": round(cw_flow_kgs, 3),
        "room_name":          str(inputs.get("room_name", inputs.get("project_name", "Zone 1"))),
        "qty":                1,   # single-zone calc always = 1
        # Wrap single result as rooms array for multi-room renderer
        "rooms": [{
            "room_name":          str(inputs.get("room_name", "Zone 1")),
            "area_m2":            floor_area,
            "load_kw":            round(q_design_kw, 2),
            "cooling_load_kw":    round(q_design_kw, 2),   # alias — renderer reads this key
            "qty":                1,
            "selected_model":     selected["size"],
            "selected_kw":        selected["total_kW"],
            "selected_tr":        round(selected["total_kW"] / 3.517, 2),
            "airflow_cmh":        selected["airflow_m3hr"],
            "chw_flow_lps_total": round(cw_flow_lps, 3),
        }],

        # ── Aggregate fields (renderer uses these for totals row) ──────────────
        "total_units":         1,
        "total_connected_kw":  round(selected["total_kW"], 2),
        "total_connected_tr":  round(selected["total_kW"] / 3.517, 2),
        "total_required_kw":   round(q_total_w / 1000, 2),
        "total_design_kw":     round(q_design_kw, 2),
        "total_design_tr":     round(q_design_kw / 3.517, 2),
        "total_chw_lps":       round(cw_flow_lps, 3),
        "main_pipe_nps_mm":    _pipe_nps_from_flow(cw_flow_lps)[0],
        "main_pipe_vel_ms":    _pipe_nps_from_flow(cw_flow_lps)[1],
    }
