"""
Solar PV System - Phase 4f
Standards: IEC 62548:2016 (PV array design requirements),
           IEC 61215 (Module performance testing at STC),
           IEC 62109 (Inverter safety), PAGASA climatological normals,
           PEC 2017 Article 6.90 (Solar PV systems), IEEE 929
Libraries: math (all formulas closed-form)

SKILL RULE (IEC 62548): String sizing MUST use Voc at T_min (coldest ambient),
NOT STC (25°C). Cold temperatures increase cell voltage.
  Voc_max = Voc_STC × (1 + (tempCoeffVoc/100) × (T_min − 25))
  panels_per_string = floor(V_inverter_max / Voc_max)

Philippine T_min table (PAGASA):
  Baguio: 8°C, Metro Manila: 18°C, Batangas: 18°C, Cebu: 20°C, Davao: 20°C

Calculates:
- String sizing (panels/string) from cold Voc vs inverter max input voltage
- Strings in parallel from power/current requirement
- Array power and area
- Energy yield (kWh/day, kWh/yr) from Peak Sun Hours (PSH)
- Off-grid battery bank sizing
- Inverter sizing (kVA, input voltage range)
- System efficiency and performance ratio
- PEC 2017 / IEC 62548 safety checks (Voc, Isc, string fuse sizing)
"""

import math

# ─── Philippine T_min (°C) - PAGASA climatological normals ───────────────────
# IEC 62548: use coldest recorded ambient for Voc_max calculation
T_MIN_PHILIPPINES: dict[str, float] = {
    "Baguio":        8.0,
    "Metro Manila": 18.0,
    "Batangas":     18.0,
    "Legazpi":      17.0,
    "Tacloban":     19.0,
    "CDO":          19.0,
    "Cebu":         20.0,
    "Davao":        20.0,
    "Iloilo":       20.0,
    "Zamboanga":    21.0,
}
T_MIN_DEFAULT = 18.0   # Metro Manila conservative baseline

# ─── Philippine Peak Sun Hours (PSH) by location - PVGIS / PAGASA ────────────
# PSH = daily solar irradiance (kWh/m2/day) at optimal tilt angle
PSH_PHILIPPINES: dict[str, float] = {
    "Baguio":        3.8,   # cloud cover reduces PSH
    "Metro Manila":  4.5,
    "Batangas":      4.8,
    "Legazpi":       4.2,
    "Tacloban":      4.6,
    "CDO":           5.0,
    "Cebu":          5.1,
    "Davao":         5.2,
    "Iloilo":        5.0,
    "Zamboanga":     5.3,
}
PSH_DEFAULT = 4.5   # Metro Manila

# ─── Standard STC module parameters (typical 400Wp monocrystalline) ───────────
# IEC 61215 rating at STC: 1000 W/m2, 25°C cell temp, AM 1.5
DEFAULT_MODULE: dict = {
    "Pmax_w":        400,    # Wp rated power at STC
    "Voc_stc":       49.5,   # V open-circuit at STC
    "Vmp_stc":       41.5,   # V maximum power at STC
    "Isc_stc":       10.2,   # A short-circuit at STC
    "Imp_stc":        9.6,   # A maximum power at STC
    "tempCoeff_Voc": -0.29,  # %/°C (negative - Voc drops as T rises)
    "tempCoeff_Pmax": -0.35, # %/°C (negative - power drops as T rises)
    "area_m2":        1.92,  # m² module area (typical 400Wp)
    "efficiency_pct": 20.8,  # % module efficiency
}

# ─── System losses (IEC 62548 / PVsyst typical) ────────────────────────────────
SYSTEM_LOSSES: dict[str, float] = {
    "wiring":       0.02,   # DC cable losses
    "mismatch":     0.02,   # module mismatch losses
    "soiling":      0.03,   # dirt/dust on panels (Manila dusty urban)
    "inverter":     0.04,   # inverter conversion losses (~96% efficiency)
    "shading":      0.03,   # inter-row shading (well-designed)
    "temperature":  0.05,   # Pmax temperature derating at 45°C cell temp
}
PERFORMANCE_RATIO = 1 - sum(SYSTEM_LOSSES.values())   # ≈ 0.81

# ─── NOCT cell temperature correction (IEC 61215) ────────────────────────────
# T_cell = T_ambient + (NOCT - 20) / 800 × G_irradiance
# At NOCT (45°C cell temp, 800 W/m2, 20°C ambient, 1 m/s wind)
NOCT_C = 45.0   # °C - typical for standard modules

# ─── Off-grid battery sizing ──────────────────────────────────────────────────
BATT_DOD       = 0.80   # VRLA design DOD
BATT_EFF       = 0.85   # round-trip efficiency
BATT_CELL_V    = 12.0   # V per monobloc

# ─── Standard inverter kVA sizes ─────────────────────────────────────────────
STD_INVERTER_KVA = [1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12.5, 15, 17.5, 20,
                    25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 250]


def _voc_max(voc_stc: float, temp_coeff_pct: float, t_min_c: float) -> float:
    """
    IEC 62548: Maximum Voc at coldest ambient temperature.
    Voc_max = Voc_STC × (1 + (tempCoeffVoc/100) × (T_min − 25))
    tempCoeff is negative, so T_min < 25°C increases Voc.
    """
    return voc_stc * (1 + (temp_coeff_pct / 100) * (t_min_c - 25))


def _vmp_hot(vmp_stc: float, temp_coeff_pct: float, t_cell_hot: float) -> float:
    """Vmp at maximum operating cell temperature (for MPPT lower limit check)."""
    return vmp_stc * (1 + (temp_coeff_pct / 100) * (t_cell_hot - 25))


def _pmax_hot(pmax_w: float, temp_coeff_pct: float, t_cell_hot: float) -> float:
    """Pmax derating at elevated cell temperature."""
    return pmax_w * (1 + (temp_coeff_pct / 100) * (t_cell_hot - 25))


def calculate(inputs: dict) -> dict:
    """
    Main entry point - compatible with TypeScript calcSolarPV() input keys.
    """
    # ── System parameters ─────────────────────────────────────────────────────
    system_kw    = float(inputs.get("system_kw",     0)
                     or  inputs.get("load_kw",        0))
    location     = str  (inputs.get("location",       "Metro Manila"))
    system_type  = str  (inputs.get("system_type",    "Grid-Tied"))   # Grid-Tied / Off-Grid / Hybrid

    t_min_c      = float(inputs.get("t_min_c",
                         T_MIN_PHILIPPINES.get(location, T_MIN_DEFAULT)))
    psh          = float(inputs.get("peak_sun_hours")
                     or  inputs.get("psh_hr")
                     or  PSH_PHILIPPINES.get(location, PSH_DEFAULT))
    t_ambient_max = float(inputs.get("ambient_temp_max_c", 35.0))

    # User-specified derating and inverter efficiency → performance ratio
    derating_pct     = float(inputs.get("derating_pct",     80.0))
    inverter_eff_pct = float(inputs.get("inverter_eff_pct", 96.0))
    perf_ratio = (derating_pct / 100.0) * (inverter_eff_pct / 100.0)
    if perf_ratio <= 0:
        perf_ratio = PERFORMANCE_RATIO   # fallback to hardcoded

    # ── Module parameters — accept frontend field names ───────────────────────
    voc_stc      = float(inputs.get("voc_stc")     or inputs.get("panel_voc")        or DEFAULT_MODULE["Voc_stc"])
    vmp_stc      = float(inputs.get("vmp_stc",        DEFAULT_MODULE["Vmp_stc"]))
    isc_stc      = float(inputs.get("isc_stc",        DEFAULT_MODULE["Isc_stc"]))
    imp_stc      = float(inputs.get("imp_stc",        DEFAULT_MODULE["Imp_stc"]))
    pmax_w       = float(inputs.get("module_wp")   or inputs.get("panel_wp")         or DEFAULT_MODULE["Pmax_w"])
    tc_voc       = float(inputs.get("tempCoeff_voc")or inputs.get("temp_coeff_voc")  or DEFAULT_MODULE["tempCoeff_Voc"])
    tc_pmax      = float(inputs.get("tempCoeff_pmax",  DEFAULT_MODULE["tempCoeff_Pmax"]))
    module_area  = float(inputs.get("module_area_m2")or inputs.get("panel_area_m2")  or DEFAULT_MODULE["area_m2"])

    # ── Inverter parameters ───────────────────────────────────────────────────
    inv_vdc_max  = float(inputs.get("inverter_vdc_max",  1000))  # V max DC input
    inv_vdc_min  = float(inputs.get("inverter_vdc_min",   200))  # V min MPPT
    inv_idc_max  = float(inputs.get("inverter_idc_max",    30))  # A max DC input per MPPT

    # ── Default system kW from PSH if not given ───────────────────────────────
    daily_load_kwh = float(inputs.get("daily_load_kwh") or inputs.get("daily_energy_kwh") or 0)
    if system_kw <= 0 and daily_load_kwh > 0:
        system_kw = daily_load_kwh / (psh * perf_ratio)
    if system_kw <= 0:
        system_kw = 5.0

    # ── IEC 62548: String sizing at T_min (SKILL RULE) ───────────────────────
    voc_cold = _voc_max(voc_stc, tc_voc, t_min_c)
    panels_per_string = math.floor(inv_vdc_max / voc_cold)
    panels_per_string = max(panels_per_string, 1)

    # Check Vmp at maximum cell temperature (MPPT lower limit)
    # T_cell_hot = T_ambient_max + (NOCT - 20) / 800 × 1000 W/m2 ≈ T_amb + 25
    t_cell_hot   = t_ambient_max + (NOCT_C - 20) / 800 * 1000
    vmp_hot      = _vmp_hot(vmp_stc, tc_voc, t_cell_hot)
    vmp_string_hot = vmp_hot * panels_per_string
    mppt_ok      = vmp_string_hot >= inv_vdc_min

    # ── Array sizing from system kW ───────────────────────────────────────────
    # Pmax derating at hot cell temperature
    pmax_hot_w   = _pmax_hot(pmax_w, tc_pmax, t_cell_hot)
    # Total panels needed
    total_panels = math.ceil((system_kw * 1000) / pmax_hot_w)
    # Strings in parallel
    strings_parallel = math.ceil(total_panels / panels_per_string)
    # Actual total panels (rounded to full strings)
    total_panels = strings_parallel * panels_per_string
    # Actual array peak power at STC
    array_wp     = total_panels * pmax_w
    array_kw_stc = array_wp / 1000

    # ── Array area ────────────────────────────────────────────────────────────
    array_area_m2 = total_panels * module_area
    # Approximate roof area needed (1.3 spacing factor for inter-row shading)
    roof_area_m2  = array_area_m2 * 1.3

    # ── String voltages for safety check ─────────────────────────────────────
    voc_string_cold = voc_cold * panels_per_string   # Voc at T_min - highest voltage
    vmp_string_stc  = vmp_stc  * panels_per_string   # Vmp at STC

    # ── Array current ─────────────────────────────────────────────────────────
    isc_array    = isc_stc * strings_parallel    # Isc at STC
    imp_array    = imp_stc * strings_parallel    # Imp at STC

    # ── IEC 62548 string fuse sizing ─────────────────────────────────────────
    # String fuse: 1.5 × Isc_stc ≤ fuse ≤ 2.4 × Isc_stc
    fuse_min_a   = 1.5 * isc_stc
    fuse_max_a   = 2.4 * isc_stc
    std_fuses    = [10, 12, 15, 20, 25, 30, 32, 40]
    rec_fuse_a   = next((f for f in std_fuses if f >= fuse_min_a and f <= fuse_max_a),
                        std_fuses[-1])

    # ── DC cable sizing (simplified - detailed in Wire Sizing calc) ───────────
    # Max DC current = 1.25 × Isc (IEC 62548 safety factor)
    dc_cable_a   = isc_stc * 1.25 * strings_parallel

    # ── Energy yield ──────────────────────────────────────────────────────────
    energy_day_kwh  = array_kw_stc * psh * perf_ratio
    energy_yr_kwh   = energy_day_kwh * 365
    energy_yr_mwh   = energy_yr_kwh / 1000

    # Specific yield (kWh/kWp/yr) - performance benchmark
    specific_yield  = energy_yr_kwh / max(array_kw_stc, 1)

    # CO2 offset (kg/yr) - Philippine grid emission factor: 0.522 kg CO2/kWh (DOE 2022)
    co2_offset_kg_yr = energy_yr_kwh * 0.522

    # ── Inverter sizing ───────────────────────────────────────────────────────
    # Inverter DC input power = array kWp (1:1 for grid-tied, per IEC 62109)
    # Inverter AC output ≥ 90% of DC array kWp (standard sizing ratio)
    inv_kva_min  = array_kw_stc * 0.90   # kW → kVA (unity PF for inverter output)
    rec_inv_kva  = next((s for s in STD_INVERTER_KVA if s >= inv_kva_min),
                        STD_INVERTER_KVA[-1])

    # ── Off-grid battery bank ─────────────────────────────────────────────────
    batt_bank = None
    if system_type in ("Off-Grid", "Hybrid"):
        autonomy_days = float(inputs.get("autonomy_days", 1.0))
        batt_kwh_req  = daily_load_kwh * autonomy_days / (BATT_DOD * BATT_EFF)
        batt_v_bank   = 48 if system_kw < 10 else 96   # V DC bus
        batt_ah_req   = batt_kwh_req * 1000 / batt_v_bank
        std_batt_ah   = [100, 150, 200, 250]
        rec_batt_ah   = next((a for a in std_batt_ah if a >= batt_ah_req),
                              std_batt_ah[-1])
        n_parallel    = math.ceil(batt_ah_req / rec_batt_ah)
        n_series      = int(batt_v_bank / BATT_CELL_V)
        total_cells   = n_series * n_parallel

        batt_bank = {
            "daily_load_kwh":     daily_load_kwh,
            "autonomy_days":      autonomy_days,
            "required_kwh":       round(batt_kwh_req, 2),
            "bank_voltage_V":     batt_v_bank,
            "required_Ah":        round(batt_ah_req, 1),
            "recommended_Ah":     rec_batt_ah,
            "strings_parallel":   n_parallel,
            "cells_in_series":    n_series,
            "total_cells":        total_cells,
        }

    return {
        # Array sizing
        "panels_per_string":      panels_per_string,
        "strings_parallel":       strings_parallel,
        "total_panels":           total_panels,
        "array_kWp":              round(array_kw_stc, 2),
        "array_Wp":               array_wp,
        "array_area_m2":          round(array_area_m2, 1),
        "roof_area_required_m2":  round(roof_area_m2, 1),

        # IEC 62548 cold-temperature sizing (SKILL RULE)
        "iec62548": {
            "voc_stc":            voc_stc,
            "t_min_c":            t_min_c,
            "tempCoeff_Voc_pct":  tc_voc,
            "voc_cold":           round(voc_cold, 2),
            "formula":            f"Voc_max = {voc_stc} × (1 + ({tc_voc}/100) × ({t_min_c}−25)) = {round(voc_cold,2)} V",
            "inverter_vdc_max":   inv_vdc_max,
            "panels_per_string_calc": f"floor({inv_vdc_max} / {round(voc_cold,2)}) = {panels_per_string}",
        },

        # String voltages
        "voc_string_cold_V":      round(voc_string_cold, 1),
        "vmp_string_stc_V":       round(vmp_string_stc, 1),
        "vmp_string_hot_V":       round(vmp_string_hot, 1),
        "mppt_lower_limit_ok":    mppt_ok,

        # Array current
        "isc_array_A":            round(isc_array, 1),
        "imp_array_A":            round(imp_array, 1),
        "dc_design_current_A":    round(dc_cable_a, 1),

        # String fuse (IEC 62548)
        "fuse_min_A":             round(fuse_min_a, 1),
        "fuse_max_A":             round(fuse_max_a, 1),
        "recommended_fuse_A":     rec_fuse_a,

        # Inverter
        "inverter_kVA_min":       round(inv_kva_min, 2),
        "recommended_inverter_kVA": rec_inv_kva,

        # Energy yield
        "location":               location,
        "peak_sun_hours":         psh,
        "performance_ratio":      round(perf_ratio, 3),
        "energy_day_kWh":         round(energy_day_kwh, 2),
        "energy_yr_kWh":          round(energy_yr_kwh, 0),
        "energy_yr_MWh":          round(energy_yr_mwh, 2),
        "specific_yield_kWh_kWp": round(specific_yield, 0),
        "co2_offset_kg_yr":       round(co2_offset_kg_yr, 0),

        # Temperature derating
        "t_cell_hot_c":           round(t_cell_hot, 1),
        "pmax_hot_W":             round(pmax_hot_w, 1),
        "pmax_derate_pct":        round((1 - pmax_hot_w / pmax_w) * 100, 1),

        # Off-grid battery (only if applicable)
        "battery_bank":           batt_bank,

        # System losses breakdown
        "system_losses": {k: round(v * 100, 1) for k, v in SYSTEM_LOSSES.items()},

        # Metadata
        "inputs_used": {
            "system_type":        system_type,
            "location":           location,
            "t_min_c":            t_min_c,
            "peak_sun_hours":     psh,
            "module_wp":          pmax_w,
            "inverter_vdc_max":   inv_vdc_max,
        },
        "calculation_source": "python/math",
        "standard": "IEC 62548:2016 | IEC 61215 | IEC 62109 | PEC 2017 Art.6.90 | PAGASA",

        # ── Legacy renderer aliases (frontend renderSolarPVReport) ─────────────
        "panel_qty":           total_panels,
        "num_strings":         strings_parallel,
        "actual_array_kwp":    round(array_kw_stc, 2),
        "required_array_kwp":  round(system_kw, 2),
        "annual_yield_kwh":    round(energy_yr_kwh, 0),
        "inverter_kw":         round(rec_inv_kva * 0.90, 2),
        "psh_hr":              psh,
        "system_efficiency":   round(perf_ratio, 3),
        "t_min_c":             t_min_c,
        "temp_coeff_voc":      tc_voc,
        "total_roof_area_m2":  round(array_area_m2 * 1.15, 1),   # 15% extra for spacing
        "voc_max":             round(voc_string_cold, 2),
        "co2_reduction_kg":    round(co2_offset_kg_yr, 0),
        "battery_ah":          batt_bank.get("capacity_ah") if batt_bank else None,
        "battery_kwh":         batt_bank.get("energy_kwh") if batt_bank else None,
    }
