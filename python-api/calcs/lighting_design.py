"""
Lighting Design - Phase 7b
Standards: IESNA (Illuminating Engineering Society of North America) Handbook 10th Ed.,
           IES RP-1 (Offices), IES RP-7 (Industrial), IES RP-28 (Parking),
           PEC 2017 (Philippine Electrical Code - Part 1, Article 220),
           ASHRAE 90.1-2019 (Lighting Power Density limits),
           DOLE D.O. 13 (PH illumination requirements for workplaces)
Libraries: math (all formulas closed-form)

Method: Zonal Cavity Method (IES)
  RCR = 5 × h_rc × (L + W) / (L × W)       Room Cavity Ratio
  CU  = f(RCR, ρ_ceiling, ρ_wall, ρ_floor)  Coefficient of Utilization
  N   = (E × A) / (Φ_lamp × n_lamps × CU × LLF)  Number of luminaires
  Eav = N × Φ_lamp × n_lamps × CU × LLF / A      Achieved illuminance (lux)
"""

import math

# ─── IES / DOLE illuminance targets (lux) ────────────────────────────────────
ILLUMINANCE_TARGETS: dict[str, dict] = {
    "Office - general":           {"lux": 500,  "UGR_max": 19, "Ra_min": 80},
    "Office - computer task":     {"lux": 300,  "UGR_max": 19, "Ra_min": 80},
    "Conference room":            {"lux": 500,  "UGR_max": 19, "Ra_min": 80},
    "Corridor / Hallway":         {"lux": 100,  "UGR_max": 28, "Ra_min": 60},
    "Staircase":                  {"lux": 150,  "UGR_max": 28, "Ra_min": 60},
    "Restroom / Toilet":          {"lux": 200,  "UGR_max": 25, "Ra_min": 80},
    "Lobby / Reception":          {"lux": 300,  "UGR_max": 22, "Ra_min": 80},
    "Classroom":                  {"lux": 500,  "UGR_max": 19, "Ra_min": 80},
    "Library":                    {"lux": 500,  "UGR_max": 19, "Ra_min": 80},
    "Hospital - ward":            {"lux": 200,  "UGR_max": 19, "Ra_min": 90},
    "Hospital - examination":     {"lux": 1000, "UGR_max": 16, "Ra_min": 90},
    "Hospital - operating":       {"lux": 10000,"UGR_max": 10, "Ra_min": 90},
    "Retail - general":           {"lux": 500,  "UGR_max": 22, "Ra_min": 80},
    "Retail - display":           {"lux": 1000, "UGR_max": 19, "Ra_min": 90},
    "Warehouse - general":        {"lux": 100,  "UGR_max": 25, "Ra_min": 60},
    "Warehouse - picking":        {"lux": 300,  "UGR_max": 25, "Ra_min": 60},
    "Manufacturing - fine work":  {"lux": 1000, "UGR_max": 16, "Ra_min": 80},
    "Manufacturing - rough work": {"lux": 200,  "UGR_max": 25, "Ra_min": 60},
    "Parking - covered":          {"lux": 50,   "UGR_max": 28, "Ra_min": 60},
    "Parking - open":             {"lux": 30,   "UGR_max": 28, "Ra_min": 60},
    "Kitchen - commercial":       {"lux": 500,  "UGR_max": 25, "Ra_min": 80},
    "Dining area":                {"lux": 200,  "UGR_max": 22, "Ra_min": 80},
    "Emergency egress":           {"lux": 10,   "UGR_max": 35, "Ra_min": 40},
}

# ─── ASHRAE 90.1-2019 Lighting Power Density (W/m²) ──────────────────────────
# Table 9.6.1 Space-by-space method
ASHRAE_LPD: dict[str, float] = {
    "Office - general":           11.0,
    "Office - computer task":      8.5,
    "Conference room":            13.7,
    "Corridor / Hallway":          5.4,
    "Staircase":                   6.5,
    "Restroom / Toilet":          10.0,
    "Lobby / Reception":           9.7,
    "Classroom":                  13.9,
    "Library":                    14.1,
    "Hospital - ward":             9.4,
    "Hospital - examination":     18.4,
    "Hospital - operating":       23.7,
    "Retail - general":           14.5,
    "Retail - display":           18.0,
    "Warehouse - general":         6.6,
    "Warehouse - picking":         9.0,
    "Manufacturing - fine work":  20.4,
    "Manufacturing - rough work": 12.6,
    "Parking - covered":           2.7,
    "Parking - open":              1.5,
    "Kitchen - commercial":       12.5,
    "Dining area":                11.0,
    "Emergency egress":            1.0,
}

# ─── Common luminaire types ───────────────────────────────────────────────────
# initial_lumens = total output of the fixture
LUMINAIRE_TYPES: dict[str, dict] = {
    "LED Panel 600×600 (36W)":          {"watts": 36,   "lumens": 3600,  "n_lamps": 1},
    "LED Panel 600×600 (40W)":          {"watts": 40,   "lumens": 4000,  "n_lamps": 1},
    "LED Panel 1200×300 (36W)":         {"watts": 36,   "lumens": 3200,  "n_lamps": 1},
    "LED Downlight 9W":                 {"watts":  9,   "lumens":  800,  "n_lamps": 1},
    "LED Downlight 18W":                {"watts": 18,   "lumens": 1800,  "n_lamps": 1},
    "LED Troffer 2×4 ft (50W)":         {"watts": 50,   "lumens": 5500,  "n_lamps": 1},
    "LED High Bay 100W":                {"watts":100,   "lumens":14000,  "n_lamps": 1},
    "LED High Bay 150W":                {"watts":150,   "lumens":21000,  "n_lamps": 1},
    "LED High Bay 200W":                {"watts":200,   "lumens":28000,  "n_lamps": 1},
    "LED Streetlight 50W":              {"watts": 50,   "lumens": 6000,  "n_lamps": 1},
    "LED Streetlight 100W":             {"watts":100,   "lumens":12000,  "n_lamps": 1},
    "T8 LED 4ft 18W (2-lamp)":          {"watts": 36,   "lumens": 5400,  "n_lamps": 2},
    "T8 LED 4ft 18W (1-lamp)":          {"watts": 18,   "lumens": 2700,  "n_lamps": 1},
    "T5HO 54W (2-lamp)":                {"watts":116,   "lumens":10000,  "n_lamps": 2},
    "Metal Halide 250W":                {"watts":270,   "lumens":20000,  "n_lamps": 1},
    "Metal Halide 400W":                {"watts":430,   "lumens":32000,  "n_lamps": 1},
}

# ─── Coefficient of Utilization lookup (simplified IES table) ─────────────────
# CU = f(RCR) for a typical direct/indirect luminaire
# ρ_ceiling=70%, ρ_wall=50%, ρ_floor=20% (typical office)
# For other reflectance combinations, scale by reflectance factor
CU_TABLE: list[dict] = [
    {"RCR": 0,   "CU": 0.78},
    {"RCR": 1,   "CU": 0.70},
    {"RCR": 2,   "CU": 0.63},
    {"RCR": 3,   "CU": 0.57},
    {"RCR": 4,   "CU": 0.52},
    {"RCR": 5,   "CU": 0.47},
    {"RCR": 6,   "CU": 0.43},
    {"RCR": 7,   "CU": 0.39},
    {"RCR": 8,   "CU": 0.36},
    {"RCR": 9,   "CU": 0.33},
    {"RCR": 10,  "CU": 0.31},
]


def _interpolate_cu(rcr: float) -> float:
    """Linear interpolation of CU from table."""
    rcr = max(0, min(rcr, 10))
    for i in range(len(CU_TABLE) - 1):
        lo = CU_TABLE[i]
        hi = CU_TABLE[i + 1]
        if lo["RCR"] <= rcr <= hi["RCR"]:
            frac = (rcr - lo["RCR"]) / (hi["RCR"] - lo["RCR"])
            return lo["CU"] + frac * (hi["CU"] - lo["CU"])
    return CU_TABLE[-1]["CU"]


def _reflectance_factor(rho_c: float, rho_w: float, rho_f: float) -> float:
    """
    Scale CU for non-standard reflectances (IES §9.6).
    Reference: ρ_c=0.70, ρ_w=0.50, ρ_f=0.20
    Approximate linear scale on combined weighted reflectance.
    """
    rho_ref_weighted = 0.70 * 0.50 + 0.50 * 0.30 + 0.20 * 0.20
    rho_weighted     = rho_c * 0.50 + rho_w * 0.30 + rho_f * 0.20
    return rho_weighted / rho_ref_weighted if rho_ref_weighted > 0 else 1.0


def _llf(
    lamp_lumen_depreciation: float = 0.90,
    luminaire_dirt_depreciation: float = 0.90,
    maintenance_category: str = "Good",
) -> float:
    """
    Light Loss Factor (LLF) = LLD × LDD × other factors.
    IES: LLD = 0.85-0.95 for LED; LDD = 0.85-0.95 (Good maintenance)
    """
    maint_factors = {"Excellent": 0.95, "Good": 0.90, "Fair": 0.85, "Poor": 0.75}
    ldd = maint_factors.get(maintenance_category, 0.90)
    return lamp_lumen_depreciation * ldd


def calculate(inputs: dict) -> dict:
    """Main entry point - compatible with TypeScript calcLightingDesign() keys."""
    # ── Room parameters ───────────────────────────────────────────────────────
    room_length_m   = float(inputs.get("room_length_m",  10.0))
    room_width_m    = float(inputs.get("room_width_m",    8.0))
    room_height_m   = float(inputs.get("room_height_m",   3.0))
    work_plane_m    = float(inputs.get("work_plane_m",    0.75))   # desk height
    luminaire_height_m = float(inputs.get("luminaire_height_m",
                                           room_height_m))         # mounting height

    space_type      = str(inputs.get("space_type", "Office - general"))
    # Normalize: frontend may still send em dash versions — convert to hyphen for lookup
    space_type = space_type.replace('—', '-').replace('–', '-')
    target_lux      = float(inputs.get("target_lux",
                              ILLUMINANCE_TARGETS.get(space_type, {}).get("lux", 500)))

    # ── Reflectances ──────────────────────────────────────────────────────────
    rho_ceiling     = float(inputs.get("rho_ceiling", 0.70))
    rho_wall        = float(inputs.get("rho_wall",    0.50))
    rho_floor       = float(inputs.get("rho_floor",   0.20))

    # ── Luminaire ─────────────────────────────────────────────────────────────
    lum_key         = str  (inputs.get("luminaire_type", "LED Panel 600×600 (40W)"))
    lum_data        = LUMINAIRE_TYPES.get(lum_key, {"watts": 40, "lumens": 4000, "n_lamps": 1})
    lamp_lumens     = float(inputs.get("lamp_lumens",  lum_data["lumens"]))  # per fixture total
    watts_per_fix   = float(inputs.get("watts_per_fixture", lum_data["watts"]))

    maintenance     = str(inputs.get("maintenance_category", "Good"))
    lld             = float(inputs.get("lamp_lumen_depreciation", 0.90))

    # ── Room Cavity Ratio ─────────────────────────────────────────────────────
    h_rc = luminaire_height_m - work_plane_m          # room cavity height
    h_cc = room_height_m - luminaire_height_m          # ceiling cavity height
    A    = room_length_m * room_width_m
    perimeter = 2 * (room_length_m + room_width_m)

    RCR = 5 * h_rc * perimeter / A if A > 0 else 0.0

    # ── Coefficient of Utilization ────────────────────────────────────────────
    CU_base = _interpolate_cu(RCR)
    rf      = _reflectance_factor(rho_ceiling, rho_wall, rho_floor)
    CU      = min(CU_base * rf, 0.90)   # cap at physical limit

    # ── Light Loss Factor ─────────────────────────────────────────────────────
    LLF = _llf(lld, 0.90, maintenance)

    # ── Number of luminaires ──────────────────────────────────────────────────
    # N = (E × A) / (Φ × CU × LLF)
    if lamp_lumens > 0 and CU > 0 and LLF > 0:
        N_exact = (target_lux * A) / (lamp_lumens * CU * LLF)
    else:
        N_exact = 0
    N_required = math.ceil(N_exact)

    # ── Achieved illuminance ──────────────────────────────────────────────────
    E_achieved = (N_required * lamp_lumens * CU * LLF) / A if A > 0 else 0
    illuminance_ok = E_achieved >= target_lux

    # ── Layout recommendation ─────────────────────────────────────────────────
    # Distribute as evenly as possible in rows × columns
    cols = max(1, round(math.sqrt(N_required * room_length_m / room_width_m)))
    rows = max(1, math.ceil(N_required / cols))
    n_actual = rows * cols
    spacing_x = room_length_m / cols    # m between fixtures (centre to centre)
    spacing_y = room_width_m  / rows
    # IES spacing criterion: S ≤ max spacing-to-mounting-height ratio (S/MH ≤ 1.5 typical)
    smh_x = spacing_x / h_rc if h_rc > 0 else 0
    smh_y = spacing_y / h_rc if h_rc > 0 else 0
    spacing_ok = smh_x <= 1.5 and smh_y <= 1.5

    # ── Power calculations ────────────────────────────────────────────────────
    total_watts    = n_actual * watts_per_fix
    lpd_actual     = total_watts / A if A > 0 else 0      # W/m²
    lpd_limit      = ASHRAE_LPD.get(space_type, 15.0)     # W/m²
    lpd_ok         = lpd_actual <= lpd_limit

    # ── Annual energy estimate ────────────────────────────────────────────────
    operating_hrs   = float(inputs.get("operating_hours_per_year", 2500))
    kwh_per_year    = total_watts * operating_hrs / 1000

    # ── Standards compliance notes ────────────────────────────────────────────
    ies_data = ILLUMINANCE_TARGETS.get(space_type, {})
    code_notes = [
        f"Space type: {space_type} - target {target_lux} lux (IES RP / DOLE D.O. 13).",
        f"RCR = {round(RCR,2)} → CU = {round(CU,3)} (Ref factors: C={rho_ceiling}, "
        f"W={rho_wall}, F={rho_floor}).",
        f"LLF = {round(LLF,3)} (LLD={lld}, LDD=0.90, maintenance={maintenance}).",
        f"Illuminance achieved: {round(E_achieved,0)} lux ({'PASS' if illuminance_ok else 'FAIL'}).",
        f"Spacing-to-MH: x={round(smh_x,2)}, y={round(smh_y,2)} "
        f"({'PASS' if spacing_ok else 'WARN: exceeds 1.5 S/MH - add fixtures'}).",
        f"LPD: {round(lpd_actual,2)} W/m² vs ASHRAE 90.1-2019 limit {lpd_limit} W/m² "
        f"({'PASS' if lpd_ok else 'FAIL - exceeds energy code'}).",
        f"UGR limit for space: {ies_data.get('UGR_max','-')} (verify with manufacturer photometry).",
        f"Minimum CRI (Ra): {ies_data.get('Ra_min','-')} - specify on luminaire schedule.",
        "Emergency lighting: NSCP §E-1 / IES RP-2 - egress paths require ≥ 10 lux.",
    ]

    return {
        # Room
        "room_area_m2":        round(A, 2),
        "room_length_m":       room_length_m,
        "room_width_m":        room_width_m,
        "room_height_m":       room_height_m,

        # IES Zonal Cavity
        "RCR":                 round(RCR, 3),
        "CU":                  round(CU, 3),
        "LLF":                 round(LLF, 3),

        # Luminaire design
        "luminaire_type":      lum_key,
        "lamp_lumens":         lamp_lumens,
        "watts_per_fixture":   watts_per_fix,
        "N_exact":             round(N_exact, 2),
        "N_required":          N_required,
        "n_actual":            n_actual,
        "layout_rows":         rows,
        "layout_cols":         cols,
        "spacing_x_m":         round(spacing_x, 2),
        "spacing_y_m":         round(spacing_y, 2),
        "SMH_x":               round(smh_x, 3),
        "SMH_y":               round(smh_y, 3),
        "spacing_ok":          spacing_ok,

        # Illuminance
        "target_lux":          target_lux,
        "E_achieved_lux":      round(E_achieved, 1),
        "illuminance_ok":      illuminance_ok,
        "UGR_max":             ies_data.get("UGR_max"),
        "Ra_min":              ies_data.get("Ra_min"),

        # Power
        "total_watts":         total_watts,
        "lpd_actual_W_m2":     round(lpd_actual, 2),
        "lpd_limit_W_m2":      lpd_limit,
        "lpd_ok":              lpd_ok,

        # Energy
        "operating_hrs_yr":    operating_hrs,
        "kwh_per_year":        round(kwh_per_year, 1),

        # Compliance
        "code_notes":          code_notes,

        # Metadata
        "inputs_used": {
            "space_type":       space_type,
            "target_lux":       target_lux,
            "luminaire_type":   lum_key,
            "room_length_m":    room_length_m,
            "room_width_m":     room_width_m,
        },
        "calculation_source": "python/math",
        "standard": "IESNA 10th Ed. | IES RP-1/7/28 | ASHRAE 90.1-2019 | PEC 2017 | DOLE D.O. 13",
    }
