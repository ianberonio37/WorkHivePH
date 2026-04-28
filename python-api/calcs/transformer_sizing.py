"""
Transformer Sizing — Electrical: Supply & Distribution (Phase 4h)
Standards: PEC 2017 Art. 4.50, IEC 60076-1:2011 (Power Transformers),
           IEEE C57.12.00 (General Requirements for Transformers),
           NEMA ST-20 (Dry-Type Transformers)
Libraries: math

Method:
  1. Apparent power → rated kVA (with demand factor and spare capacity)
  2. Primary/secondary full-load current (3-phase or 1-phase)
  3. Short-circuit current at secondary from transformer impedance
  4. Full-load losses: core (no-load) + copper (load)
  5. Efficiency at full load and 75% load (IEC 60076-1 typical test points)
  6. Voltage regulation at full load (PF-corrected)
"""

import math

# Standard transformer kVA ratings (distribution transformers — Philippine market)
STD_KVA = [5, 10, 15, 25, 37.5, 50, 75, 100, 112.5, 150, 167, 200,
           225, 250, 300, 333, 400, 500, 750, 1000, 1500, 2000, 2500, 3000]

# Typical no-load (core) loss and load (copper) loss fractions (IEC 60076-1)
# [kVA range, no_load_loss_pct, load_loss_pct]
LOSS_TABLE: list[tuple] = [
    (50,   0.25, 1.50),
    (100,  0.22, 1.40),
    (167,  0.20, 1.30),
    (250,  0.18, 1.25),
    (500,  0.16, 1.20),
    (1000, 0.14, 1.10),
    (2000, 0.12, 1.00),
    (9999, 0.10, 0.90),
]


def _loss_fracs(kva: float) -> tuple[float, float]:
    for limit, nl, ll in LOSS_TABLE:
        if kva <= limit:
            return nl / 100.0, ll / 100.0
    return 0.10 / 100.0, 0.90 / 100.0


def calculate(inputs: dict) -> dict:
    load_kva         = float(inputs.get("load_kva",           100))
    primary_v        = float(inputs.get("primary_voltage",    13800))
    secondary_v      = float(inputs.get("secondary_voltage",  400))
    load_pf          = float(inputs.get("load_power_factor",  0.85))
    phases           = int(inputs.get("phases",               3))
    impedance_pct    = float(inputs.get("impedance_pct",      5.0))   # Uz%
    spare_pct        = float(inputs.get("spare_capacity_pct", 25.0))  # headroom
    winding          = str(inputs.get("winding_connection",   "Delta-Star (Dyn11)"))
    cooling          = str(inputs.get("cooling_type",         "ONAN"))  # Oil Natural Air Natural
    num_units        = max(1, int(inputs.get("num_units",     1)))

    # Required kVA with spare capacity
    required_kva    = load_kva * (1.0 + spare_pct / 100.0)
    rated_kva       = next((s for s in STD_KVA if s >= required_kva),
                           math.ceil(required_kva / 100) * 100)
    total_kva       = rated_kva * num_units

    # Full-load currents
    sqrt3 = math.sqrt(3)
    div   = sqrt3 * primary_v   if phases == 3 else primary_v
    div2  = sqrt3 * secondary_v if phases == 3 else secondary_v
    I1_fl = (rated_kva * 1000.0) / div   if div  > 0 else 0.0
    I2_fl = (rated_kva * 1000.0) / div2  if div2 > 0 else 0.0

    # Short-circuit current at secondary (from transformer impedance)
    Isc_sec = I2_fl * 100.0 / impedance_pct if impedance_pct > 0 else 0.0

    # Losses
    nl_frac, ll_frac = _loss_fracs(rated_kva)
    P_core_kw  = rated_kva * nl_frac            # no-load (core) loss kW
    P_cu_kw    = rated_kva * ll_frac             # full-load copper loss kW
    P_loss_fl  = P_core_kw + P_cu_kw            # total loss at 100% load
    P_loss_75  = P_core_kw + P_cu_kw * 0.5625  # total loss at 75% load (0.75² × copper)

    # Output power at full load
    P_out_fl_kw  = rated_kva * load_pf
    P_out_75_kw  = P_out_fl_kw * 0.75
    eta_fl       = P_out_fl_kw / (P_out_fl_kw + P_loss_fl) * 100.0 if (P_out_fl_kw + P_loss_fl) > 0 else 0.0
    eta_75       = P_out_75_kw / (P_out_75_kw + P_loss_75) * 100.0 if (P_out_75_kw + P_loss_75) > 0 else 0.0

    # Voltage regulation (approximate: IEC 60076-1 §5)
    # VR% = εr × cosφ + εx × sinφ  where εr = Pcu/(S×10) %, εx ≈ √(Uz² - εr²)
    er   = (P_cu_kw / rated_kva) * 100.0 if rated_kva > 0 else 0.0  # resistance component %
    ex   = math.sqrt(max(0, impedance_pct**2 - er**2))               # reactance component %
    sinf = math.sqrt(max(0, 1.0 - load_pf**2))
    VR_pct = er * load_pf + ex * sinf                                 # approximate VR%

    # Loading %
    loading_pct = (load_kva / rated_kva * 100.0) if rated_kva > 0 else 0.0

    return {
        "load_kva":               round(load_kva,      2),
        "spare_capacity_pct":     spare_pct,
        "required_kva":           round(required_kva,  2),
        "rated_kva":              rated_kva,
        "num_units":              num_units,
        "total_installed_kva":    total_kva,
        "loading_pct":            round(loading_pct,   1),
        "primary_voltage":        primary_v,
        "secondary_voltage":      secondary_v,
        "phases":                 phases,
        "winding_connection":     winding,
        "cooling_type":           cooling,
        "I1_full_load_A":         round(I1_fl,    2),
        "I2_full_load_A":         round(I2_fl,    2),
        "impedance_pct":          impedance_pct,
        "Isc_secondary_A":        round(Isc_sec,  1),
        "Isc_secondary_kA":       round(Isc_sec / 1000.0, 3),
        "core_loss_kW":           round(P_core_kw, 3),
        "copper_loss_kW":         round(P_cu_kw,   3),
        "total_loss_fl_kW":       round(P_loss_fl, 3),
        "total_loss_75pct_kW":    round(P_loss_75, 3),
        "efficiency_fl_pct":      round(eta_fl,    2),
        "efficiency_75pct":       round(eta_75,    2),
        "voltage_regulation_pct": round(VR_pct,    2),
        "load_power_factor":      load_pf,
    }
