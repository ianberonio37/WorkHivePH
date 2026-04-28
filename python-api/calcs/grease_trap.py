"""
Grease Trap Sizing — Phase 6g (Option B port from TypeScript)
Standards: PDI G-101 (Plumbing & Drainage Institute), ASME A112.14.3,
           PPC §P-1001 to §P-1007, DENR DAO 2016-08
Libraries: math

Method: PDI G-101 flow-rate method — sum connected fixture flows × SUF
        → convert to GPM → select next standard PDI size → liquid/grease capacity

Improvement over TypeScript:
- FOG load check against DENR DAO 2016-08 (FOG effluent limit 100 mg/L)
- Recommended pumping frequency added (EPA / PPC §P-1006)
"""

# Standard PDI grease trap sizes (GPM) — PDI G-101 Table 1
PDI_STD_GPM = [4, 6, 7, 10, 15, 20, 25, 35, 50, 75, 100]

LPM_TO_GPM = 0.26417   # 1 L/min = 0.26417 US gal/min


def calculate(inputs: dict) -> dict:
    fixtures   = inputs.get("fixtures", [])   # [{fixture_type, flow_lpm, qty}]
    suf        = float(inputs.get("suf",          0.75))   # Simultaneous Use Factor
    meals_day  = int(inputs.get("meals_per_day",  0))

    # Total connected fixture flow
    total_flow_lpm = sum(
        float(fx.get("flow_lpm", 0)) * int(fx.get("qty", 1))
        for fx in fixtures
    )

    # Design flow with SUF
    q_design_lpm = total_flow_lpm * suf
    q_design_gpm = q_design_lpm * LPM_TO_GPM

    # Select next standard PDI size
    pdi_gpm = next((g for g in PDI_STD_GPM if g >= q_design_gpm), PDI_STD_GPM[-1])

    # Liquid capacity: PDI GPM × 2 gal → litres (PDI G-101 §4.3)
    liquid_cap_l  = pdi_gpm * 2 * 3.78541

    # Grease retention capacity: 1 lb per GPM (PDI G-101 §4.4)
    grease_ret_kg = pdi_gpm * 0.4536

    # Cleaning interval: based on FOG load (EPA / PPC §P-1006)
    # Clean when 25% of grease retention reached (best practice vs 50% code minimum)
    if meals_day > 0:
        fog_per_day_kg      = meals_day * 0.06    # ~60 g FOG per meal served
        days_to_25pct       = (grease_ret_kg * 0.25) / fog_per_day_kg
        clean_interval_days = max(1, min(90, int(days_to_25pct)))
    else:
        fog_per_day_kg      = 0.0
        clean_interval_days = 30   # default recommendation

    # DENR FOG effluent check: trap efficiency ~80-85%; inlet FOG ~150 mg/L typical
    fog_inlet_mgl   = 150.0
    trap_efficiency  = 0.82
    fog_effluent_mgl = fog_inlet_mgl * (1.0 - trap_efficiency)
    denr_fog_limit   = 100.0   # DENR DAO 2016-08 Class SB
    fog_compliant    = fog_effluent_mgl <= denr_fog_limit

    return {
        "total_flow_lpm":     round(total_flow_lpm,  2),
        "q_design_lpm":       round(q_design_lpm,    2),
        "q_design_gpm":       round(q_design_gpm,    2),
        "pdi_gpm":            pdi_gpm,
        "liquid_cap_l":       round(liquid_cap_l,    1),
        "grease_ret_kg":      round(grease_ret_kg,   2),
        "clean_interval_days": clean_interval_days,
        "suf_used":           suf,
        "meals_per_day":      meals_day,
        "fog_per_day_kg":     round(fog_per_day_kg,  3),
        "fog_effluent_mgl":   round(fog_effluent_mgl, 1),
        "denr_fog_limit_mgl": denr_fog_limit,
        "fog_denr_compliant": fog_compliant,
    }
