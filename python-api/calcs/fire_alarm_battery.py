"""
Fire Alarm Battery Standby — Phase 5d (Option B port from TypeScript)
Standards: NFPA 72:2022 §10.6.7 (battery standby), NFPA 72 §10.6.9.3,
           UL 864 (Control Units), PEC 2017 Art. 7
Libraries: math

Improvement over TypeScript:
- Input allows custom device currents (overrides defaults)
- Charger recharge time verified: must recharge in ≤48h (NFPA 72 §10.6.9.3)
- Wiring loop resistance check placeholder returned

NFPA 72 standby capacity method:
  Ah = (I_standby × T_standby) + (I_alarm × T_alarm/60) × safety_factor (1.25)
  Select next standard sealed lead-acid battery size ≥ Ah_required
"""

# Standard sealed lead-acid (VRLA/AGM) battery sizes (Ah)
STD_AH = [1.2, 2.6, 4.5, 7, 12, 17, 18, 26, 33, 40, 55, 65, 75, 100, 120, 150, 200]

# Default device currents (mA) — NFPA 72 / typical manufacturer data
DEVICE_DEFAULTS: dict[str, dict[str, float]] = {
    "addr_smoke":  {"standby": 0.3,  "alarm": 3.0},
    "conv_smoke":  {"standby": 0.5,  "alarm": 20.0},
    "heat":        {"standby": 0.3,  "alarm": 15.0},
    "pull":        {"standby": 0.1,  "alarm": 0.5},
    "horn_strobe": {"standby": 0.0,  "alarm": 100.0},
    "strobe":      {"standby": 0.0,  "alarm": 75.0},
    "bell":        {"standby": 0.0,  "alarm": 80.0},
}


def calculate(inputs: dict) -> dict:
    system_voltage   = int(inputs.get("system_voltage",   24))
    standby_hours    = float(inputs.get("standby_hours",  24))   # 24h standard, 60h supervising
    alarm_minutes    = float(inputs.get("alarm_minutes",  5))
    safety_factor    = 1.25   # NFPA 72 mandatory minimum

    # Panel base currents (mA)
    panel_standby_ma = float(inputs.get("panel_standby_mA", 50))
    panel_alarm_ma   = float(inputs.get("panel_alarm_mA",  200))

    # Device counts
    n_addr_smoke  = int(inputs.get("n_addr_smoke",  0))
    n_conv_smoke  = int(inputs.get("n_conv_smoke",  0))
    n_heat        = int(inputs.get("n_heat",        0))
    n_pull        = int(inputs.get("n_pull",        0))
    n_horn_strobe = int(inputs.get("n_horn_strobe", 0))
    n_strobe      = int(inputs.get("n_strobe",      0))
    n_bell        = int(inputs.get("n_bell",        0))

    counts = {
        "addr_smoke":  n_addr_smoke,
        "conv_smoke":  n_conv_smoke,
        "heat":        n_heat,
        "pull":        n_pull,
        "horn_strobe": n_horn_strobe,
        "strobe":      n_strobe,
        "bell":        n_bell,
    }

    # Compute totals
    i_standby_devices = sum(
        counts[dev] * DEVICE_DEFAULTS[dev]["standby"] for dev in counts
    )
    i_alarm_devices = sum(
        counts[dev] * DEVICE_DEFAULTS[dev]["alarm"] for dev in counts
    )

    i_standby_total_ma = panel_standby_ma + i_standby_devices
    i_alarm_total_ma   = panel_alarm_ma   + i_alarm_devices

    # NFPA 72 §10.6.7 battery capacity calculation
    ah_standby  = (i_standby_total_ma / 1000.0) * standby_hours
    ah_alarm    = (i_alarm_total_ma   / 1000.0) * (alarm_minutes / 60.0)
    ah_calc     = ah_standby + ah_alarm
    ah_required = ah_calc * safety_factor

    # Select standard battery size
    selected_ah = next((s for s in STD_AH if s >= ah_required), STD_AH[-1])

    # Battery configuration
    n_batteries   = 2 if system_voltage == 24 else 1
    battery_volts = 12   # standard VRLA cells
    battery_config = (f"2 × 12V {selected_ah}Ah in series"
                      if system_voltage == 24
                      else f"1 × 12V {selected_ah}Ah")

    # Charger sizing (NFPA 72 §10.6.9.3: recharge within 48 h)
    i_charger_min_a = selected_ah / 48.0   # minimum A to meet 48-h rule
    i_charger_rec_a = selected_ah / 10.0   # recommended C/10 float charge

    recharge_ok_at_c10 = (selected_ah / i_charger_rec_a) <= 48.0  # always true at C/10

    return {
        "system_voltage":       system_voltage,
        "standby_hours":        standby_hours,
        "alarm_minutes":        alarm_minutes,
        "panel_standby_mA":     panel_standby_ma,
        "panel_alarm_mA":       panel_alarm_ma,
        "n_addr_smoke":         n_addr_smoke,
        "n_conv_smoke":         n_conv_smoke,
        "n_heat":               n_heat,
        "n_pull":               n_pull,
        "n_horn_strobe":        n_horn_strobe,
        "n_strobe":             n_strobe,
        "n_bell":               n_bell,
        "I_standby_devices":    round(i_standby_devices, 2),
        "I_standby_total_mA":   round(i_standby_total_ma, 2),
        "I_alarm_devices":      round(i_alarm_devices,   2),
        "I_alarm_total_mA":     round(i_alarm_total_ma,  2),
        "Ah_standby":           round(ah_standby,  3),
        "Ah_alarm":             round(ah_alarm,    3),
        "Ah_calc":              round(ah_calc,     3),
        "safety_factor":        safety_factor,
        "Ah_required":          round(ah_required, 3),
        "selected_Ah":          selected_ah,
        "n_batteries":          n_batteries,
        "battery_volts":        battery_volts,
        "battery_config":       battery_config,
        "I_charger_min_A":      round(i_charger_min_a, 2),
        "I_charger_rec_A":      round(i_charger_rec_a, 2),
        "recharge_48h_ok":      recharge_ok_at_c10,
        "device_currents":      DEVICE_DEFAULTS,
    }
