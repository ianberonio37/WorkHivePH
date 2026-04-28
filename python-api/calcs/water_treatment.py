"""
Water Treatment System — Phase 6i (Option B port from TypeScript)
Standards: PNS 1998 / PNSDW (Philippine National Standards for Drinking Water),
           DOH AO 2017-0010, DENR DAO 2016-08, EPA Guidance Manual (UV/CT),
           NSF/ANSI 61 (treatment equipment)
Libraries: math

Method: Selects treatment train based on source quality flags
        Sizes filter, iron removal, coagulant, disinfection, storage
"""

import math

STD_FILTER_DIA_MM = [400, 500, 600, 700, 800, 900, 1000, 1200, 1400, 1600, 1800, 2000, 2400]


def calculate(inputs: dict) -> dict:
    demand_source = str(inputs.get("demand_source",   "direct"))
    n_people      = int(inputs.get("n_people",        0))
    per_capita    = float(inputs.get("per_capita_lpd", 200))

    if demand_source == "people":
        if n_people <= 0:
            return {"error": "Number of people must be greater than 0."}
        demand_lpd = n_people * per_capita
    else:
        demand_lpd = (float(inputs.get("demand_lpd",      0))
                   or float(inputs.get("daily_demand_L",  0))
                   or float(inputs.get("daily_demand_m3", 0)) * 1000)
        if demand_lpd <= 0:
            return {"error": "Daily water demand must be greater than 0."}

    raw_source       = str(inputs.get("raw_source",       "Deep Well / Bore"))
    turbidity_ntu    = max(0.0, float(inputs.get("turbidity_ntu",  10)))
    iron_mgl         = max(0.0, float(inputs.get("iron_mg",        0.3)))
    bacteria_concern = str(inputs.get("bacteria_concern", "yes")).lower() in ("yes", "true", "1")
    intended_use     = str(inputs.get("intended_use",     "Potable"))
    peak_factor      = max(1.1, min(3.0, float(inputs.get("peak_factor", 1.5))))

    # Flows
    demand_m3d    = demand_lpd / 1000.0
    peak_flow_m3hr = round((demand_m3d * peak_factor) / 24.0, 3)
    avg_flow_m3hr  = round(demand_m3d / 24.0, 3)
    avg_flow_lpm   = round(demand_lpd / (24 * 60), 2)

    # Treatment needs
    needs_coag     = turbidity_ntu > 25
    needs_sed      = turbidity_ntu > 50
    needs_iron     = iron_mgl > 0.3
    needs_disinfect = bacteria_concern or raw_source in ("Surface Water", "Rainwater")
    needs_softener = intended_use in ("Boiler Makeup", "Cooling Tower Makeup")
    needs_ro       = intended_use == "Boiler Makeup (High Pressure)"

    disinfect_method = ("UV + Chlorination" if bacteria_concern and demand_lpd <= 50000
                        else "Chlorination")

    train: list[str] = []
    if needs_coag:   train.append("Coagulation / Flocculation (Alum dosing)")
    if needs_sed:    train.append("Sedimentation / Clarifier")
    train.append("Iron Removal Filter (Greensand + Aeration)" if needs_iron
                 else "Multimedia Filter (Quartz sand + Anthracite)")
    if turbidity_ntu > 5:
        train.append("Activated Carbon Filter (Taste / Odor / Chlorine)")
    if needs_disinfect:
        train.append("UV Disinfection + Chlorination" if "UV" in disinfect_method
                     else "Chlorination (Sodium Hypochlorite dosing)")
    if needs_softener: train.append("Water Softener (refer to Water Softener Sizing calc)")
    if needs_ro:       train.append("Reverse Osmosis (RO)")
    train.append("Treated Water Storage Tank")

    # PNS 1998 checks
    turbidity_check = (
        "WITHIN PNS 1998 (≤5 NTU post-filtration achievable)" if turbidity_ntu <= 5 else
        "Filtration required for PNS 1998 ≤5 NTU"            if turbidity_ntu <= 25 else
        "Coagulation + Filtration required for PNS 1998"
    )
    iron_check = (
        "Within PNS 1998 (≤0.3 mg/L)"                           if iron_mgl <= 0.3 else
        "EXCEEDS PNS 1998: iron removal required"               if iron_mgl <= 1.0 else
        "Severely elevated: aeration + greensand filtration req"
    )
    turbid_class = ("Clear" if turbidity_ntu < 5 else "Slightly Turbid" if turbidity_ntu < 25
                    else "Moderately Turbid" if turbidity_ntu < 100 else "Highly Turbid")

    # 1. Filter sizing
    filt_rate       = 8.0 if needs_iron else 10.0   # m/hr
    filter_area_m2  = round(peak_flow_m3hr / filt_rate, 3)
    filter_dia_m    = round(math.sqrt(filter_area_m2 * 4 / math.pi), 3)
    req_dia_mm      = filter_dia_m * 1000
    sel_dia_mm      = next((d for d in STD_FILTER_DIA_MM if d >= req_dia_mm), STD_FILTER_DIA_MM[-1])
    sel_area_m2     = round(math.pi / 4 * (sel_dia_mm / 1000) ** 2, 4)
    actual_filt     = round(peak_flow_m3hr / sel_area_m2, 2) if sel_area_m2 > 0 else 0.0
    bw_flow_m3hr    = round(sel_area_m2 * 25, 2)
    bw_flow_lpm     = round(bw_flow_m3hr / 60 * 1000)
    bed_depth_mm    = 900 if needs_iron else 750
    tank_ht_mm      = bed_depth_mm + 400 + 300

    # 2. Iron removal
    aeration_m3hr   = round(peak_flow_m3hr * 4, 1)   if needs_iron else 0.0
    greensand_kg    = round(sel_area_m2 * 3.5 * (bed_depth_mm / 750), 1) if needs_iron else 0.0
    iron_removed_ghr = round(peak_flow_m3hr * 1000 / 60 * max(0, iron_mgl - 0.1), 1) if needs_iron else 0.0
    kmno4_daily_kg  = round(iron_removed_ghr * 0.25 * 24 / 1000, 2) if needs_iron else 0.0

    # 3. Coagulant
    alum_dose_mgl   = (10 if turbidity_ntu < 50 else 25 if turbidity_ntu < 100 else 40) if needs_coag else 0
    alum_daily_kg   = round(alum_dose_mgl * demand_m3d / 1000, 2) if needs_coag else 0.0

    # 4. Chlorination
    cl2_dose = {"Municipal Supply": 0.5, "Deep Well / Bore": 1.0,
                "Rainwater": 2.0}.get(raw_source,
                5.0 if (raw_source == "Surface Water" and turbidity_ntu > 50) else 3.0)
    cl2_daily_kg    = round(cl2_dose * demand_m3d / 1000, 3)
    naocl_daily_l   = round(cl2_daily_kg * 8.3, 2)
    ct_required     = 36.0                               # mg·min/L (EPA 3-log Giardia)
    contact_time_min = round(ct_required / cl2_dose, 1) if cl2_dose > 0 else 0.0
    contact_tank_m3 = round(peak_flow_m3hr / 60 * contact_time_min, 2)
    ct_achieved     = round(cl2_dose * contact_time_min, 1)
    ct_check        = (f"PASS: CT {ct_achieved} ≥ {ct_required} mg·min/L" if ct_achieved >= ct_required
                       else f"FAIL: CT {ct_achieved} < required {ct_required} mg·min/L")

    # 5. UV
    uv_dose    = 40 if "UV" in disinfect_method else 0
    uv_flow    = peak_flow_m3hr if uv_dose > 0 else 0.0

    # 6. Storage (1 day)
    storage_m3  = round(demand_m3d, 1)
    storage_l   = round(storage_m3 * 1000)

    # 7. AC filter
    ac_dia_mm   = sel_dia_mm if turbidity_ntu > 5 else 0
    ac_area_m2  = sel_area_m2 if ac_dia_mm > 0 else 0.0
    ac_bed_vol  = round(peak_flow_m3hr / 60 * 10, 3)    # EBCT = 10 min
    ac_depth_mm = round(ac_bed_vol / ac_area_m2 * 1000) if ac_area_m2 > 0 else 0

    # 8. Projected quality
    proj_turbidity = round(turbidity_ntu * (0.02 if needs_coag else 0.05 if needs_sed else 0.10), 2)
    proj_iron      = round(iron_mgl * 0.05, 3) if needs_iron else iron_mgl
    proj_cl_res    = round(cl2_dose * 0.3, 2) if needs_disinfect else 0.0
    meets_pns      = (proj_turbidity <= 5 and proj_iron <= 0.3
                      and (not bacteria_concern or proj_cl_res >= 0.2))
    pns_status     = "MEETS PNS 1998 / PNSDW" if meets_pns else "REVIEW required"

    return {
        "demand_lpd":               round(demand_lpd),
        "demand_m3d":               round(demand_m3d, 3),
        "peak_flow_m3hr":           peak_flow_m3hr,
        "avg_flow_m3hr":            avg_flow_m3hr,
        "avg_flow_lpm":             avg_flow_lpm,
        "raw_source":               raw_source,
        "turbidity_ntu":            turbidity_ntu,
        "turbidity_class":          turbid_class,
        "iron_mg":                  iron_mgl,
        "bacteria_concern":         bacteria_concern,
        "intended_use":             intended_use,
        "peak_factor":              peak_factor,
        "turbidity_check":          turbidity_check,
        "iron_check":               iron_check,
        "train_steps":              train,
        "needs_coag_floc":          needs_coag,
        "needs_sedimentation":      needs_sed,
        "needs_iron_removal":       needs_iron,
        "needs_disinfection":       needs_disinfect,
        "disinfection_method":      disinfect_method,
        "needs_softener_note":      needs_softener,
        "needs_ro_note":            needs_ro,
        "filtration_rate_mhr":      filt_rate,
        "filter_area_req_m2":       filter_area_m2,
        "filter_dia_req_mm":        round(req_dia_mm),
        "selected_filter_dia_mm":   sel_dia_mm,
        "selected_filter_area_m2":  sel_area_m2,
        "actual_filtration_rate":   actual_filt,
        "backwash_flow_m3hr":       bw_flow_m3hr,
        "backwash_flow_lpm":        bw_flow_lpm,
        "filter_bed_depth_mm":      bed_depth_mm,
        "filter_tank_height_mm":    tank_ht_mm,
        "iron_removal_air_m3hr":    aeration_m3hr,
        "greensand_media_kg":       greensand_kg,
        "kmno4_daily_kg":           kmno4_daily_kg,
        "alum_dose_mg_L":           alum_dose_mgl,
        "alum_daily_kg":            alum_daily_kg,
        "cl2_dose_mg_L":            cl2_dose,
        "cl2_daily_kg":             cl2_daily_kg,
        "naocl_daily_L":            naocl_daily_l,
        "contact_time_min":         contact_time_min,
        "contact_tank_m3":          contact_tank_m3,
        "ct_achieved":              ct_achieved,
        "ct_required":              ct_required,
        "ct_check":                 ct_check,
        "uv_dose_mj_cm2":           uv_dose,
        "uv_flow_m3hr":             uv_flow,
        "ac_filter_dia_mm":         ac_dia_mm,
        "ac_bed_volume_m3":         ac_bed_vol,
        "ac_bed_depth_mm":          ac_depth_mm,
        "ac_ebct_min":              10,
        "storage_tank_m3":          storage_m3,
        "storage_tank_L":           storage_l,
        "proj_turbidity_ntu":       proj_turbidity,
        "proj_iron_mg_L":           proj_iron,
        "proj_cl_residual_mg_L":    proj_cl_res,
        "pns1998_status":           pns_status,
    }
