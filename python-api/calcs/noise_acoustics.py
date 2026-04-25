"""
Noise / Acoustics - Phase 9c
Standards: ISO 9613-2:1996 (Attenuation of sound - outdoor propagation),
           OSHA 29 CFR 1910.95 (Occupational noise exposure),
           DOLE D.O. 13 Series of 1998 (Philippines occupational noise limits),
           IEC 61672-1 (Sound level meters),
           ASHRAE 2019 Fundamentals Ch.8 (Noise and vibration),
           NC (Noise Criteria) curves - ASHRAE RP-1126
Libraries: math (all formulas closed-form)

Methods:
  SPL addition:     L_total = 10 × log10(Σ 10^(Li/10))
  Distance attenuation: ΔL = 20 × log10(r2/r1) (point source)
                          ΔL = 10 × log10(r2/r1) (line source)
  Insertion loss (barrier): IL = 10 × log10(3 + 20N)  N = Fresnel number
  Room acoustics: L_room = Lw + 10 log10(Q/(4πr²) + 4/R)
                  R = α S / (1 − α)  (room constant)
  NC curve: from octave band SPL → NC rating (ASHRAE)
  Dose / TWA: OSHA / DOLE - action level 85 dBA, limit 90 dBA (8 hr TWA)
"""

import math

# ─── OSHA / DOLE permissible exposure levels ──────────────────────────────────
# Hours permitted at each dBA level (DOLE D.O. 13 Table 1 / OSHA Table G-16)
PERMISSIBLE_EXPOSURE: dict[float, float] = {
    80:  32.0,
    85:  16.0,
    90:   8.0,
    95:   4.0,
    100:  2.0,
    105:  1.0,
    110:  0.5,
    115:  0.25,
    120:  0.125,
    125:  0.063,
    130:  0.031,
}

# ─── NC curve SPL limits (dB) at octave band centre frequencies ───────────────
# From ASHRAE 2019 Fundamentals Ch.8 Table 4
NC_CURVES: dict[int, list] = {
    # NC : [63, 125, 250, 500, 1000, 2000, 4000, 8000] Hz
    15:  [47, 36, 29, 22, 17, 14, 12, 11],
    20:  [51, 40, 33, 26, 22, 19, 17, 16],
    25:  [54, 44, 37, 31, 27, 24, 22, 21],
    30:  [57, 48, 41, 35, 31, 29, 28, 27],
    35:  [60, 52, 45, 40, 36, 34, 33, 32],
    40:  [64, 56, 50, 45, 41, 39, 38, 37],
    45:  [67, 60, 54, 49, 46, 44, 43, 42],
    50:  [71, 64, 58, 54, 51, 49, 48, 47],
    55:  [74, 67, 62, 58, 56, 54, 53, 52],
    60:  [77, 71, 67, 63, 61, 59, 58, 57],
    65:  [80, 75, 71, 68, 66, 64, 63, 62],
    70:  [83, 79, 75, 72, 71, 70, 69, 68],
}
NC_FREQ = [63, 125, 250, 500, 1000, 2000, 4000, 8000]   # Hz

# ─── Recommended NC levels by occupancy ───────────────────────────────────────
NC_RECOMMENDED: dict[str, dict] = {
    "Bedroom / sleeping":      {"NC_max": 25, "dBA_approx": 35},
    "Private office":          {"NC_max": 35, "dBA_approx": 45},
    "Open-plan office":        {"NC_max": 40, "dBA_approx": 50},
    "Conference room":         {"NC_max": 30, "dBA_approx": 40},
    "Restaurant / cafeteria":  {"NC_max": 45, "dBA_approx": 55},
    "Classroom":               {"NC_max": 30, "dBA_approx": 40},
    "Hospital ward":           {"NC_max": 30, "dBA_approx": 40},
    "Library":                 {"NC_max": 35, "dBA_approx": 45},
    "Mechanical plant room":   {"NC_max": 65, "dBA_approx": 75},
    "Warehouse / light industry": {"NC_max": 55, "dBA_approx": 65},
    "Manufacturing (general)": {"NC_max": 65, "dBA_approx": 75},
}

# ─── A-weighting corrections at octave band centres (dB) ─────────────────────
A_WEIGHT: dict[int, float] = {
    63:   -26.2,
    125:  -16.1,
    250:   -8.6,
    500:   -3.2,
    1000:   0.0,
    2000:   1.2,
    4000:   1.0,
    8000:  -1.1,
}


def _add_spl(*levels_dB) -> float:
    """Logarithmic addition of multiple SPL levels (dB)."""
    return 10 * math.log10(sum(10**(L/10) for L in levels_dB if L is not None))


def _octave_to_dba(octave_spl: list) -> float:
    """Convert octave band SPL to A-weighted overall level (dBA)."""
    freqs = NC_FREQ
    total = sum(10**((octave_spl[i] + A_WEIGHT[freqs[i]]) / 10)
                for i in range(len(octave_spl)))
    return 10 * math.log10(total) if total > 0 else 0


def _nc_rating(octave_spl: list) -> int:
    """
    Determine NC rating: highest NC curve NOT exceeded in any octave band.
    Returns NC value (15–70) or 70+ if exceeds NC70.
    """
    for nc in sorted(NC_CURVES.keys()):
        limits = NC_CURVES[nc]
        if all(octave_spl[i] <= limits[i] for i in range(len(octave_spl))):
            return nc
    return 75   # exceeds NC70


def _point_source_attenuation(Lw_dB: float, r_m: float,
                               Q: float = 2.0) -> float:
    """
    Far-field SPL from a point source.
    Lp = Lw + 10 log10(Q/(4πr²))
    Q = 1 (free field), 2 (on ground), 4 (floor-wall junction)
    """
    if r_m <= 0:
        return Lw_dB
    return Lw_dB + 10 * math.log10(Q / (4 * math.pi * r_m**2))


def _room_spl(Lw_dB: float, r_m: float, Q: float,
              alpha: float, S_m2: float) -> dict:
    """
    Room equation: Lp = Lw + 10 log10(Q/(4πr²) + 4/R)
    R = α S / (1−α)  room constant (m²)
    Critical distance rc = (1/4) √(Q R / π)
    """
    R = alpha * S_m2 / (1 - alpha) if alpha < 1 else S_m2 * 1000
    direct  = Q / (4 * math.pi * r_m**2) if r_m > 0 else 0
    reverb  = 4 / R if R > 0 else 0
    Lp      = Lw_dB + 10 * math.log10(direct + reverb) if (direct + reverb) > 0 else 0
    rc      = 0.25 * math.sqrt(Q * R / math.pi) if R > 0 else 0
    return {"Lp_dB": round(Lp, 2), "R_m2": round(R, 2), "rc_m": round(rc, 2)}


def _barrier_il(d_s: float, d_r: float, d_sr: float,
                h_b: float, freq_Hz: float = 1000) -> float:
    """
    Barrier insertion loss - Maekawa formula.
    IL = 10 log10(3 + 20 N)   N = 2δ/λ   δ = path diff
    δ = d_s + d_r - d_sr  (path length difference)
    λ = 340 / freq
    """
    delta = d_s + d_r - d_sr
    lam   = 340 / freq_Hz
    N     = 2 * delta / lam if lam > 0 else 0
    IL    = 10 * math.log10(3 + 20 * N) if N > -0.15 else 0
    return max(IL, 0)


def _twa(exposures: list) -> dict:
    """
    OSHA / DOLE noise dose and Time-Weighted Average.
    exposures: list of {level_dBA, duration_hr}
    D = Σ (ti / Ti)   Ti from permissible table (interpolated)
    TWA = 16.61 × log10(D/100) + 90   (8-hr basis)
    """
    # Ti by interpolation
    levels = sorted(PERMISSIBLE_EXPOSURE.keys())

    def T_permitted(L: float) -> float:
        if L <= levels[0]:
            return PERMISSIBLE_EXPOSURE[levels[0]]
        if L >= levels[-1]:
            return PERMISSIBLE_EXPOSURE[levels[-1]]
        for i in range(len(levels) - 1):
            if levels[i] <= L <= levels[i+1]:
                # Linear interpolation in log domain
                f = (L - levels[i]) / (levels[i+1] - levels[i])
                T0 = math.log10(PERMISSIBLE_EXPOSURE[levels[i]])
                T1 = math.log10(PERMISSIBLE_EXPOSURE[levels[i+1]])
                return 10**(T0 + f * (T1 - T0))
        return 8.0

    D = sum(e["duration_hr"] / T_permitted(e["level_dBA"]) for e in exposures)
    D_pct = D * 100
    TWA   = 16.61 * math.log10(D_pct / 100) + 90 if D_pct > 0 else 0
    action_level_exceeded = TWA >= 85
    limit_exceeded        = TWA >= 90

    return {
        "dose_pct":     round(D_pct, 2),
        "TWA_dBA":      round(TWA, 2),
        "action_level_exceeded": action_level_exceeded,
        "limit_exceeded": limit_exceeded,
        "status": ("EXCEEDS LIMIT - engineering controls required"
                   if limit_exceeded else
                   "EXCEEDS ACTION LEVEL - hearing conservation program required"
                   if action_level_exceeded else
                   "Within limits"),
    }


def calculate(inputs: dict) -> dict:
    """Main entry point - compatible with TypeScript calcNoiseAcoustics() keys."""
    calc_type    = str(inputs.get("calc_type", "Room"))   # Room / Barrier / Dose / NC / Source

    results: dict = {"calc_type": calc_type}

    # ── Source level ──────────────────────────────────────────────────────────
    Lw_dB        = float(inputs.get("source_Lw_dB",      90.0))    # Sound power level
    Lp_at_1m     = float(inputs.get("Lp_at_1m_dB",        0.0))    # Alternative: SPL at 1m
    if Lp_at_1m > 0:
        # Back-calculate Lw: Lw = Lp + 20log10(r) + 11  (free field, Q=2)
        Lw_dB = Lp_at_1m + 20 * math.log10(1.0) + 8   # hemisphere

    # ── Octave band spectrum (if provided) ───────────────────────────────────
    octave_spl = inputs.get("octave_spl", None)   # 8 values at NC_FREQ

    # ── Distance SPL ──────────────────────────────────────────────────────────
    r_m          = float(inputs.get("distance_m",          5.0))
    Q_dir        = float(inputs.get("directivity_Q",        2.0))
    Lp_dist      = _point_source_attenuation(Lw_dB, r_m, Q_dir)
    results["Lp_at_distance_dB"] = round(Lp_dist, 2)
    results["distance_m"]         = r_m

    # ── Room acoustics ───────────────────────────────────────────────────────
    if calc_type in ("Room", "NC"):
        alpha        = float(inputs.get("avg_absorption_coeff", 0.15))
        S_m2         = float(inputs.get("room_surface_m2",      200.0))
        space_type   = str  (inputs.get("space_type",           "Open-plan office"))
        room_data    = _room_spl(Lw_dB, r_m, Q_dir, alpha, S_m2)
        results["room"] = room_data
        results["alpha"] = alpha

        # NC rating
        if octave_spl and len(octave_spl) == 8:
            nc_measured = _nc_rating(octave_spl)
            dba_measured = _octave_to_dba(octave_spl)
            nc_rec  = NC_RECOMMENDED.get(space_type, {}).get("NC_max", 40)
            results["NC_measured"] = nc_measured
            results["dBA_from_octave"] = round(dba_measured, 1)
            results["NC_limit"]    = nc_rec
            results["NC_ok"]       = nc_measured <= nc_rec
        else:
            nc_rec = NC_RECOMMENDED.get(space_type, {}).get("NC_max", 40)
            results["NC_limit"] = nc_rec

        results["space_type"]  = space_type
        results["NC_recommended"] = NC_RECOMMENDED.get(space_type, {})

    # ── Barrier ────────────────────────────────────────────────────────────────
    if calc_type == "Barrier":
        d_s    = float(inputs.get("source_to_barrier_m",   10.0))
        d_r    = float(inputs.get("barrier_to_receiver_m", 10.0))
        d_sr   = float(inputs.get("source_to_receiver_m",  20.0))
        h_b    = float(inputs.get("barrier_height_m",       3.0))
        freq   = float(inputs.get("frequency_Hz",        1000.0))

        il     = _barrier_il(d_s, d_r, d_sr, h_b, freq)
        Lp_no_barrier  = round(Lp_dist, 2)
        Lp_with_barrier = round(Lp_dist - il, 2)
        results["barrier_IL_dB"]          = round(il, 2)
        results["Lp_no_barrier_dB"]       = Lp_no_barrier
        results["Lp_with_barrier_dB"]     = Lp_with_barrier

    # ── Noise dose / TWA ──────────────────────────────────────────────────────
    if calc_type == "Dose":
        exposures = inputs.get("exposures", [{"level_dBA": 90.0, "duration_hr": 8.0}])
        dose_data = _twa(exposures)
        results["dose"] = dose_data

    # ── Multiple sources ───────────────────────────────────────────────────────
    sources = inputs.get("sources", [])
    if sources:
        levels = [s.get("Lp_dB", 70) for s in sources]
        results["combined_Lp_dB"] = round(_add_spl(*levels), 2)

    # ── Compliance notes ──────────────────────────────────────────────────────
    code_notes = [
        f"Sound power level Lw = {round(Lw_dB,1)} dB → Lp = {round(Lp_dist,1)} dB at {r_m}m.",
        "DOLE D.O. 13: 90 dBA TWA (8 hr) maximum; action level 85 dBA.",
        "OSHA 29 CFR 1910.95: exchange rate 5 dBA - dose doubles every 5 dBA increase.",
        "Engineering controls preferred over PPE (ISO 11690 hierarchy).",
        "A-weighted dBA used for hearing risk; octave bands used for NC rating.",
        "NC rating: conversational speech intelligibility requires NC ≤ 35 (ASHRAE).",
        "Barrier effectiveness limited to ~20–25 dB (diffraction dominant at low freq).",
    ]
    results["code_notes"] = code_notes

    results.update({
        "source_Lw_dB": Lw_dB,
        "inputs_used": {
            "calc_type":   calc_type,
            "source_Lw_dB": Lw_dB,
            "distance_m":  r_m,
        },
        "calculation_source": "python/math",
        "standard": "ISO 9613-2 | OSHA 29 CFR 1910.95 | DOLE D.O. 13 | ASHRAE 2019 Ch.8 | IEC 61672-1",
    })
    return results
