"""
Wastewater Treatment (STP) — Phase 6j (Option B port from TypeScript)
Standards: DENR DAO 2016-08 (Effluent Standards: BOD≤30, TSS≤50 mg/L),
           Metcalf & Eddy "Wastewater Engineering" 5th Ed.,
           ADB Urban Environmental Guidelines, PNS/DOH standards
Libraries: math

Method: Activated Sludge Process — SRT method (Metcalf & Eddy Eq. 8-20)
  V = Q × Y × SRT × (S0-Se) / (X_v × (1 + kd × SRT))
  O2 demand: O2 = a × BOD_removed + b × MLVSS × V  (Metcalf & Eddy Eq. 8-47)
  Blower: kg O2/day → m³/min air at 8% standard transfer efficiency
"""

import math


def calculate(inputs: dict) -> dict:
    flow_source    = str(inputs.get("flow_source",    "population"))
    population     = int(inputs.get("population",     200))
    per_cap_lpd    = float(inputs.get("per_capita_lpd", 150))
    flow_direct    = float(inputs.get("flow_direct_m3d", 30))
    bod_in         = float(inputs.get("bod_influent",  220))   # mg/L
    bod_out        = float(inputs.get("bod_effluent",  30))    # mg/L DENR limit
    srt_days       = float(inputs.get("srt_days",     8))      # Sludge Retention Time
    mlss_mgl       = float(inputs.get("mlss_mg_l",    3000))   # Mixed Liquor Suspended Solids
    disinfection   = str(inputs.get("disinfection",   "Chlorination"))

    # Design flow
    flow_m3d       = (population * per_cap_lpd / 1000.0 if flow_source == "population"
                      else flow_direct)
    flow_m3hr      = flow_m3d / 24.0
    peak_factor    = 1.5
    peak_m3hr      = flow_m3hr * peak_factor
    peak_lps       = peak_m3hr * 1000.0 / 3600.0

    # BOD loading
    bod_load       = bod_in  * flow_m3d / 1000.0          # kg BOD/day
    bod_removed    = (bod_in - bod_out) * flow_m3d / 1000.0  # kg BOD/day removed
    bod_removal_pct = round((bod_in - bod_out) / bod_in * 100, 1) if bod_in > 0 else 0.0

    # Activated sludge kinetics (Metcalf & Eddy typical values)
    Y          = 0.60    # yield coefficient (kg VSS / kg BOD)
    kd         = 0.06    # endogenous decay (/day)
    mlvss_frac = 0.80    # VSS/TSS ratio
    mlvss_mgl  = mlss_mgl * mlvss_frac

    # Aeration tank volume (SRT method)
    aer_vol_m3  = math.ceil(
        (flow_m3d * Y * srt_days * (bod_in - bod_out)) /
        (mlvss_mgl * (1.0 + kd * srt_days)) * 10
    ) / 10
    aer_hrt_hr  = round(aer_vol_m3 / flow_m3hr, 1) if flow_m3hr > 0 else 0.0

    # Tank dimensions: L:W:D ≈ 2:1:4 (depth 4 m)
    depth       = 4.0
    plan_area   = aer_vol_m3 / depth
    width       = math.ceil(math.sqrt(plan_area / 2) * 10) / 10
    length      = math.ceil(width * 2 * 10) / 10
    aer_dims    = f"{length} m x {width} m x {depth} m"

    mlvss_kg    = round(mlvss_mgl * aer_vol_m3 / 1000.0, 1)
    fm_ratio    = round(bod_removed / mlvss_kg, 3) if mlvss_kg > 0 else 0.0

    # Oxygen demand (Metcalf & Eddy Eq. 8-47)
    a, b            = 0.50, 0.10
    o2_synthesis    = round(a * bod_removed, 1)
    o2_endogenous   = round(b * mlvss_mgl * aer_vol_m3 / 1000.0, 1)
    o2_total        = round(o2_synthesis + o2_endogenous, 1)

    # Blower sizing (STE = 8%, air density 1.2 kg/m³, O2 fraction 23.2%)
    blower_m3min     = round(o2_total / (0.232 * 1.2 * 0.08 * 1440), 2)
    blower_rec_m3min = round(blower_m3min * 1.2, 2)    # 20% safety factor
    blower_kw        = math.ceil(blower_rec_m3min * 0.55 * 10) / 10  # 0.55 kW/(m³/min)

    # Primary clarifier (SOR = 28 m³/m²/day)
    prim_sor     = 28.0
    prim_area    = round(flow_m3d / prim_sor, 2)
    prim_dia     = round(math.sqrt(prim_area * 4 / math.pi), 1)
    prim_depth   = 3.5
    prim_hdt_hr  = round(prim_area * prim_depth / flow_m3hr, 1) if flow_m3hr > 0 else 0.0

    # Secondary clarifier (SOR = 20 m³/m²/day)
    sec_sor      = 20.0
    sec_area     = round(flow_m3d / sec_sor, 2)
    sec_dia      = round(math.sqrt(sec_area * 4 / math.pi), 1)
    sec_depth    = 4.0

    # Sludge production: Px = Y_obs × BOD_removed
    y_obs        = Y / (1.0 + kd * srt_days)
    sludge_kg_d  = round(y_obs * bod_removed, 1)
    sludge_m3_d  = round(sludge_kg_d / 10.0, 2)   # at 1% DS = 10 kg/m³
    desludge_d   = round(20.0 / sludge_m3_d, 1) if sludge_m3_d > 0 else 0.0
    desludge_freq = f"Every {desludge_d} days ({sludge_m3_d} m3/day, 20 m3 holding)"

    # Disinfection (secondary effluent)
    cl2_dose_mgl = 5.0
    naocl_lpd    = round(cl2_dose_mgl * flow_m3d * 0.083, 1)  # 10% NaOCl
    contact_m3   = round(peak_m3hr / 60.0 * 30.0, 1)           # 30-min contact at peak

    # Effluent quality projection
    effluent_bod = bod_out
    effluent_tss = max(round(mlss_mgl * 0.005, 1), 10.0)       # ~0.5% carryover, min 10 mg/L

    denr_compliant = effluent_bod <= 30.0 and effluent_tss <= 50.0
    denr_status    = "COMPLIANT" if denr_compliant else "REVIEW"

    return {
        "flow_source":              flow_source,
        "flow_m3_day":              round(flow_m3d,  1),
        "flow_m3_hr":               round(flow_m3hr, 2),
        "peak_flow_m3_hr":          round(peak_m3hr, 2),
        "peak_flow_lps":            round(peak_lps,  1),
        "bod_load_kg_day":          round(bod_load,     1),
        "bod_removed_kg_day":       round(bod_removed,  1),
        "bod_removal_pct":          bod_removal_pct,
        "aeration_vol_m3":          aer_vol_m3,
        "aeration_hrt_hr":          aer_hrt_hr,
        "aeration_dims":            aer_dims,
        "mlvss_mg_l":               mlvss_mgl,
        "mlvss_kg":                 mlvss_kg,
        "fm_ratio":                 fm_ratio,
        "o2_synthesis_kg_day":      o2_synthesis,
        "o2_endogenous_kg_day":     o2_endogenous,
        "o2_total_kg_day":          o2_total,
        "blower_m3_min":            blower_m3min,
        "blower_recommended_m3_min": blower_rec_m3min,
        "blower_kw":                blower_kw,
        "prim_sor":                 prim_sor,
        "prim_area_m2":             prim_area,
        "prim_dia_m":               prim_dia,
        "prim_depth_m":             prim_depth,
        "prim_hdt_hr":              prim_hdt_hr,
        "sec_sor":                  sec_sor,
        "sec_area_m2":              sec_area,
        "sec_dia_m":                sec_dia,
        "sec_depth_m":              sec_depth,
        "sludge_kg_day":            sludge_kg_d,
        "sludge_m3_day":            sludge_m3_d,
        "was_m3_day":               sludge_m3_d,
        "desludge_freq":            desludge_freq,
        "cl2_dose_mg_l":            cl2_dose_mgl,
        "naocl_lpd":                naocl_lpd,
        "contact_tank_m3":          contact_m3,
        "effluent_bod":             effluent_bod,
        "effluent_tss":             effluent_tss,
        "denr_status":              denr_status,
    }
