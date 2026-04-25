"""
Lightning Protection System (LPS) Design - Phase 7c
Standards: IEC 62305-1:2010 (General principles),
           IEC 62305-2:2010 (Risk management),
           IEC 62305-3:2010 (Physical damage - air-termination, down conductors, earth),
           IEC 62305-4:2010 (Electrical / electronic systems - LPZ, SPD),
           NSCP 2015 Vol.3 (Electrical - lightning protection),
           PEC 2017 Part 1 Article 280 (Lightning protection)
Libraries: math (all formulas closed-form)

Method:
  1. Lightning Protection Level (LPL) from IEC 62305-2 risk assessment
  2. Rolling sphere radius R (IEC 62305-3 Table 2): LPL I=20m, II=30m, III=45m, IV=60m
  3. Air-termination: rolling sphere + mesh method
  4. Down conductor count and spacing per LPL
  5. Earth termination: ring electrode + driven rods
  6. Lightning Protection Zones (LPZ 0A/0B/1/2) for SPD coordination
  7. Separation distance s between LPS and internal installations
"""

import math

# ─── IEC 62305-3 Lightning Protection Levels (LPL) ───────────────────────────
LPL_PARAMS: dict[str, dict] = {
    "LPL I":   {"R_sphere_m": 20,  "mesh_m": 5,   "down_spacing_m": 10, "Iimp_kA": 200, "protection_pct": 98},
    "LPL II":  {"R_sphere_m": 30,  "mesh_m": 10,  "down_spacing_m": 10, "Iimp_kA": 150, "protection_pct": 95},
    "LPL III": {"R_sphere_m": 45,  "mesh_m": 15,  "down_spacing_m": 15, "Iimp_kA": 100, "protection_pct": 90},
    "LPL IV":  {"R_sphere_m": 60,  "mesh_m": 20,  "down_spacing_m": 20, "Iimp_kA": 100, "protection_pct": 80},
}

# ─── IEC 62305-2 Risk thresholds ─────────────────────────────────────────────
RISK_THRESHOLD_RT = 1e-5    # tolerable risk for loss of human life (per year)

# ─── IEC 62305-3 Table NA.1 - Ground Flash Density (Ng) for Philippines ──────
# Ng (flashes/km²/yr) - use PAGASA data; typical Philippine values:
NG_PHILIPPINES: dict[str, float] = {
    "Metro Manila":    10,
    "Cebu":            8,
    "Davao":           12,
    "Visayas":         10,
    "Mindanao":        15,
    "Luzon (highland)": 12,
    "General":         10,   # conservative default
}

# ─── IEC 62305-3 Air-termination material specs ───────────────────────────────
CONDUCTOR_SPECS: dict[str, dict] = {
    "Copper":               {"min_mm2_air": 50, "min_mm2_down": 16, "min_mm2_earth": 50},
    "Aluminium":            {"min_mm2_air": 70, "min_mm2_down": 25, "min_mm2_earth": 0},   # Al not for buried
    "Hot-dip Galvanized Steel": {"min_mm2_air": 50, "min_mm2_down": 50, "min_mm2_earth": 80},
    "Stainless Steel":      {"min_mm2_air": 50, "min_mm2_down": 50, "min_mm2_earth": 80},
}

# ─── IEC 62305-3 Earth termination: resistance targets ───────────────────────
EARTH_R_TARGET = 10.0   # Ω - IEC 62305-3 §5.4.2 (less than 10 Ω recommended)

# ─── SPD (Surge Protection Device) class per LPZ boundary ────────────────────
SPD_CLASS: dict[str, dict] = {
    "LPZ 0A → LPZ 1": {"class": "Type 1 (Class I)",    "Iimp_kA": 12.5,  "Up_kV": 2.5},
    "LPZ 1  → LPZ 2": {"class": "Type 2 (Class II)",   "Imax_kA": 20,    "Up_kV": 1.5},
    "LPZ 2  → LPZ 3": {"class": "Type 3 (Class III)",  "Imax_kA":  5,    "Up_kV": 1.5},
}


def _collection_area(L_m: float, W_m: float, H_m: float, R_m: float) -> float:
    """
    IEC 62305-2 §A.1 - Equivalent collection area Ad (m²) of an isolated structure.
    Ad = L×W + 2×(L+W)×H + π×H²   (simplified for rectangular building, H ≤ R)
    For H > R: uses rolling sphere geometry.
    """
    if H_m <= R_m:
        return L_m * W_m + 2 * (L_m + W_m) * H_m + math.pi * H_m ** 2
    else:
        # IEC simplified for tall structure (H > R): rolling sphere
        r_top = math.sqrt(R_m ** 2 - (R_m - H_m + R_m) ** 2) if R_m > 0 else 0
        return L_m * W_m + 2 * (L_m + W_m) * R_m + math.pi * R_m ** 2


def _flash_frequency(Ad_m2: float, Ng: float, Cd: float = 1.0) -> float:
    """
    IEC 62305-2 §A.1 - Annual number of dangerous events to the structure.
    Nd = Ng × Ad × Cd × 10^-6
    Cd = location factor (1.0 isolated, 0.5 surrounded, 2.0 on hilltop)
    """
    return Ng * Ad_m2 * Cd * 1e-6


def _rolling_sphere_height(R_m: float, x_m: float) -> float:
    """
    Height of the rolling sphere arc above a horizontal surface at horizontal
    distance x from the attachment point.
    z = R − √(R² − x²) - depth of sphere below attachment point at distance x.
    Protection zone: points below the arc are protected.
    """
    if x_m > R_m:
        return 0.0
    return R_m - math.sqrt(R_m ** 2 - x_m ** 2)


def _down_conductor_count(L_m: float, W_m: float, spacing_m: float) -> int:
    """
    Minimum number of down conductors along the perimeter.
    IEC 62305-3 §5.3.3: N = perimeter / spacing (rounded up, min 2).
    """
    perimeter = 2 * (L_m + W_m)
    n = math.ceil(perimeter / spacing_m)
    return max(n, 2)


def _separation_distance(lpl: str, l_m: float, ki: float = 0.04) -> float:
    """
    IEC 62305-3 §6.3 - minimum separation distance s (m) to avoid dangerous sparking.
    s = ki × (kc / km) × l
    ki = 0.08 (LPL I), 0.06 (II), 0.04 (III/IV)
    kc = current share factor (1 for single down conductor path)
    km = material factor (1 for air)
    l  = length of down conductor from strike point to bonding point (m)
    Default: ki=0.04 (LPL III/IV), kc=1, km=1 (air) - conservative.
    """
    ki_lpl = {"LPL I": 0.08, "LPL II": 0.06, "LPL III": 0.04, "LPL IV": 0.04}
    k = ki_lpl.get(lpl, ki)
    kc = 1.0   # single path (conservative)
    km = 1.0   # air
    return k * (kc / km) * l_m


def _earth_rod_count(rho_soil: float, rod_len_m: float, R_target: float) -> int:
    """
    Resistance of a single vertical rod: R1 = (rho/(2π×L)) × ln(4L/d)
    where d = 0.014m (14mm rod diameter).
    n rods in parallel (>5 rod spacings): Rn ≈ R1 / n
    → n = ceil(R1 / R_target)
    """
    d_rod = 0.014   # 14mm rod diameter (IEC 62305-3)
    if rod_len_m <= 0:
        return 4
    R1 = (rho_soil / (2 * math.pi * rod_len_m)) * math.log(4 * rod_len_m / d_rod)
    n = math.ceil(R1 / R_target)
    return max(n, 1)


def calculate(inputs: dict) -> dict:
    """Main entry point - compatible with TypeScript calcLightningProtection() keys."""
    # ── Structure parameters ──────────────────────────────────────────────────
    building_length_m  = float(inputs.get("building_length_m",  30.0))
    building_width_m   = float(inputs.get("building_width_m",   20.0))
    building_height_m  = float(inputs.get("building_height_m",  15.0))
    lpl                = str  (inputs.get("lpl",                 "LPL II"))
    location           = str  (inputs.get("location",            "General"))
    Ng                 = float(inputs.get("ground_flash_density",
                                          NG_PHILIPPINES.get(location, 10.0)))
    Cd                 = float(inputs.get("location_factor",     1.0))
    conductor_material = str  (inputs.get("conductor_material",  "Copper"))
    rho_soil           = float(inputs.get("soil_resistivity_ohm_m", 100.0))
    rod_length_m       = float(inputs.get("earth_rod_length_m",   3.0))

    # ── LPL parameters ────────────────────────────────────────────────────────
    lpl_data = LPL_PARAMS.get(lpl, LPL_PARAMS["LPL II"])
    R_sphere  = lpl_data["R_sphere_m"]
    mesh_size = lpl_data["mesh_m"]
    down_spacing = lpl_data["down_spacing_m"]
    Iimp_kA   = lpl_data["Iimp_kA"]
    protection_pct = lpl_data["protection_pct"]

    # ── Collection area and strike frequency ─────────────────────────────────
    Ad_m2 = _collection_area(building_length_m, building_width_m, building_height_m, R_sphere)
    Nd    = _flash_frequency(Ad_m2, Ng, Cd)

    # Simple risk check: risk acceptable if LPS protection efficiency is sufficient
    # P = 1 − Nd×(1−E) < RT → E = 1 − RT/Nd  (simplified IEC 62305-2)
    E_required = max(0, 1 - RISK_THRESHOLD_RT / Nd) if Nd > 0 else 0
    E_provided = protection_pct / 100
    risk_ok    = E_provided >= E_required or Nd <= RISK_THRESHOLD_RT

    # ── Air-termination ───────────────────────────────────────────────────────
    # Mesh method: cells on roof (m² roof / mesh cell area)
    roof_area_m2 = building_length_m * building_width_m
    mesh_cells_L = math.ceil(building_length_m / mesh_size)
    mesh_cells_W = math.ceil(building_width_m  / mesh_size)
    n_mesh_cells = mesh_cells_L * mesh_cells_W
    # Total air-termination conductor length (ring + grid)
    ring_conductor_m = 2 * (building_length_m + building_width_m)
    grid_conductor_m = (mesh_cells_L + 1) * building_width_m + (mesh_cells_W + 1) * building_length_m
    air_conductor_total_m = ring_conductor_m + grid_conductor_m

    # Rolling sphere: check if any point on the building roof needs a finial
    # At edges/corners the sphere can only roll to R from the edge - typically
    # the ridge and corners need finials at LPL I/II
    finials_needed = 4   # minimum 4 corners + any roof ridges or projections
    if building_height_m > R_sphere:
        finials_needed += 2   # additional finials at top edges of tall structures

    # ── Down conductors ───────────────────────────────────────────────────────
    n_down = _down_conductor_count(building_length_m, building_width_m, down_spacing)
    down_conductor_length_m = building_height_m + 1.0    # +1m for earth connection
    total_down_m = n_down * down_conductor_length_m

    # ── Separation distance ───────────────────────────────────────────────────
    s_sep_m = _separation_distance(lpl, building_height_m)

    # ── Earth termination ─────────────────────────────────────────────────────
    n_rods   = _earth_rod_count(rho_soil, rod_length_m, EARTH_R_TARGET)
    # Ring earth electrode: required for buildings ≥ 20m or LPL I/II
    ring_earth_required = (lpl in ["LPL I", "LPL II"]) or (building_length_m >= 20)
    ring_earth_m = ring_conductor_m   # same perimeter

    # ── LPZ zoning ───────────────────────────────────────────────────────────
    lpz_zones = [
        {"zone": "LPZ 0A", "description": "Exposed to direct strike - outside, unprotected"},
        {"zone": "LPZ 0B", "description": "Protected by air-termination - shielded from direct strike"},
        {"zone": "LPZ 1",  "description": "Inside structure - surge current limited at boundary"},
        {"zone": "LPZ 2",  "description": "Protected room - further reduction of surge energy"},
    ]
    spd_schedule = [
        {"boundary": "LPZ 0A → LPZ 1",
         "location": "Main distribution board (MDB) entry",
         **SPD_CLASS["LPZ 0A → LPZ 1"]},
        {"boundary": "LPZ 1 → LPZ 2",
         "location": "Sub-distribution boards (SDB)",
         **SPD_CLASS["LPZ 1  → LPZ 2"]},
        {"boundary": "LPZ 2 → LPZ 3",
         "location": "Equipment panels, sensitive electronics",
         **SPD_CLASS["LPZ 2  → LPZ 3"]},
    ]

    # ── Conductor cross-section ───────────────────────────────────────────────
    mat_spec = CONDUCTOR_SPECS.get(conductor_material, CONDUCTOR_SPECS["Copper"])

    # ── Material takeoff (approximate) ───────────────────────────────────────
    bom = [
        {"item": f"Air-termination conductor ({conductor_material})",
         "qty": round(air_conductor_total_m, 1), "unit": "m",
         "spec": f"≥{mat_spec['min_mm2_air']} mm²"},
        {"item": f"Down conductors ({conductor_material})",
         "qty": round(total_down_m, 1), "unit": "m",
         "spec": f"≥{mat_spec['min_mm2_down']} mm²"},
        {"item": "Test clamps (at grade level)", "qty": n_down, "unit": "no.",
         "spec": "Removable per IEC 62305-3 §5.3.4"},
        {"item": f"Earth rods ({rod_length_m}m × 14mm dia.)", "qty": n_rods, "unit": "no.",
         "spec": f"Copper-bonded or {conductor_material}"},
        {"item": f"Ring earth electrode ({conductor_material})",
         "qty": round(ring_earth_m, 1) if ring_earth_required else 0, "unit": "m",
         "spec": f"≥{mat_spec['min_mm2_earth']} mm², buried ≥0.5m"},
        {"item": "Air-termination finials / rods",
         "qty": finials_needed, "unit": "no.",
         "spec": f"H ≥ 300mm, {conductor_material}"},
        {"item": "Bonding clamps / connectors", "qty": n_down * 3, "unit": "no.",
         "spec": "Listed for LPS use"},
    ]

    # ── Compliance notes ──────────────────────────────────────────────────────
    code_notes = [
        f"LPL selected: {lpl} - rolling sphere R={R_sphere}m, mesh {mesh_size}×{mesh_size}m, "
        f"down conductor spacing ≤{down_spacing}m.",
        f"Ground flash density Ng={Ng} fl/km²/yr ({location}) - annual strikes Nd={round(Nd,4)}/yr.",
        f"Risk assessment (IEC 62305-2): risk {'acceptable' if risk_ok else 'EXCEEDS threshold - upgrade LPL'}.",
        f"Separation distance to internal wiring/equipment: s ≥ {round(s_sep_m,2)} m (IEC 62305-3 §6.3).",
        f"Earth resistance target: ≤ {EARTH_R_TARGET} Ω - soil ρ={rho_soil} Ω·m → {n_rods} rod(s) required.",
        f"{'Ring earth electrode required.' if ring_earth_required else 'Ring earth electrode optional for this LPL/size.'}",
        "All LPS conductors must be bonded to structural steel, reinforcement, and metallic services (IEC 62305-3 §6.2).",
        f"SPD coordination: Type 1 at MDB, Type 2 at SDB, Type 3 at equipment (IEC 62305-4).",
        "PEC 2017 Art. 280: LPS installation requires licensed Electrical Engineer design and PEE inspection.",
    ]

    return {
        # Structure
        "building_length_m":       building_length_m,
        "building_width_m":        building_width_m,
        "building_height_m":       building_height_m,
        "roof_area_m2":            round(roof_area_m2, 1),

        # LPL
        "lpl":                     lpl,
        "rolling_sphere_radius_m": R_sphere,
        "mesh_size_m":             mesh_size,
        "Iimp_kA":                 Iimp_kA,
        "protection_efficiency_pct": protection_pct,

        # Risk
        "Ng_fl_km2_yr":            Ng,
        "Ad_m2":                   round(Ad_m2, 1),
        "Nd_per_year":             round(Nd, 5),
        "E_required":              round(E_required, 4),
        "E_provided":              E_provided,
        "risk_ok":                 risk_ok,

        # Air-termination
        "n_mesh_cells":            n_mesh_cells,
        "air_conductor_total_m":   round(air_conductor_total_m, 1),
        "finials_needed":          finials_needed,

        # Down conductors
        "n_down_conductors":       n_down,
        "down_conductor_length_m": round(down_conductor_length_m, 1),
        "total_down_conductor_m":  round(total_down_m, 1),

        # Separation distance
        "separation_distance_m":   round(s_sep_m, 2),

        # Earth
        "rho_soil_ohm_m":          rho_soil,
        "n_earth_rods":            n_rods,
        "ring_earth_required":     ring_earth_required,
        "ring_earth_m":            round(ring_earth_m, 1) if ring_earth_required else 0,

        # LPZ and SPD
        "lpz_zones":               lpz_zones,
        "spd_schedule":            spd_schedule,

        # Conductor spec
        "conductor_material":      conductor_material,
        "air_termination_mm2":     mat_spec["min_mm2_air"],
        "down_conductor_mm2":      mat_spec["min_mm2_down"],
        "earth_conductor_mm2":     mat_spec["min_mm2_earth"],

        # BOM
        "bom":                     bom,

        # Notes
        "code_notes":              code_notes,

        # Metadata
        "inputs_used": {
            "lpl":                 lpl,
            "building_height_m":   building_height_m,
            "location":            location,
            "conductor_material":  conductor_material,
            "soil_resistivity":    rho_soil,
        },
        "calculation_source": "python/math",
        "standard": "IEC 62305-1/2/3/4:2010 | NSCP 2015 Vol.3 | PEC 2017 Art.280",
    }
