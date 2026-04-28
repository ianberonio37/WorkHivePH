"""
Elevator Traffic Analysis — Vertical Transport (Option B port from TypeScript)
Standards: CIBSE Guide D:2015 (Transportation Systems in Buildings),
           ASME A17.1:2019 (Safety Code for Elevators),
           ISO 4190-6:2004 (Measurement of passenger service)
Libraries: math

Method: CIBSE Guide D Round Trip Time (RTT) method
  RTT = t_flight + t_stops + t_load
  Interval = RTT / n_elevators
  HC% = (n_elevators × 300 / RTT) × effective_pax / population × 100
  Average stops S = n × [1 − (1 − 1/n)^P]   (CIBSE Guide D Eq. 3.1)
"""

import math


OCCUPANCY_TARGETS: dict[str, dict] = {
    "Office":      {"interval": 30, "HC": 12},
    "Residential": {"interval": 60, "HC": 7},
    "Hotel":       {"interval": 40, "HC": 10},
    "Mixed-Use":   {"interval": 40, "HC": 11},
}


def calculate(inputs: dict) -> dict:
    n_floors       = int(inputs.get("n_floors",     12))
    floor_height   = float(inputs.get("floor_height", 3.5))
    population     = int(inputs.get("population",   500))
    n_elevators    = int(inputs.get("n_elevators",  3))
    capacity       = int(inputs.get("capacity",     13))
    speed          = float(inputs.get("speed",      1.5))   # m/s
    t_door_open    = float(inputs.get("t_door_open",  2.5))
    t_door_close   = float(inputs.get("t_door_close", 3.0))
    t_dwell        = float(inputs.get("t_dwell",      2.0))
    occupancy      = str(inputs.get("occupancy_type", "Office"))

    # CIBSE Guide D: 80% car loading efficiency
    loading_eff  = 0.80
    effective_pax = round(capacity * loading_eff)

    # Total rise
    H_m = round((n_floors - 1) * floor_height, 1)

    # Round-trip flight time (both directions)
    t_flight_s = round(2.0 * H_m / speed, 1) if speed > 0 else 0.0

    # Average number of stops (CIBSE Guide D Eq. 3.1)
    n = n_floors - 1
    S_raw    = n * (1.0 - (1.0 - 1.0 / n) ** effective_pax) if n > 0 else 1.0
    avg_stops = round(S_raw, 1)

    t_per_stop = t_dwell + t_door_open + t_door_close
    t_stops_s  = round(t_per_stop * avg_stops, 1)

    # Passenger loading/unloading: 0.8 s per passenger (CIBSE typical)
    t_load_s = round(effective_pax * 0.8, 1)

    # Round Trip Time
    RTT_s = round(t_flight_s + t_stops_s + t_load_s, 1)

    # Traffic performance
    interval_s    = round(RTT_s / n_elevators, 1) if n_elevators > 0 else 0.0
    capacity_5min = round((n_elevators * 300 / RTT_s) * effective_pax) if RTT_s > 0 else 0
    HC_pct        = round(capacity_5min / population * 100, 1) if population > 0 else 0.0

    tgt = OCCUPANCY_TARGETS.get(occupancy, OCCUPANCY_TARGETS["Office"])
    interval_ok = interval_s <= tgt["interval"]
    HC_ok       = HC_pct >= tgt["HC"]
    overall     = "PASS" if interval_ok and HC_ok else "FAIL"

    return {
        "H_m":               H_m,
        "t_flight_s":        t_flight_s,
        "avg_stops":         avg_stops,
        "t_stops_s":         t_stops_s,
        "t_load_s":          t_load_s,
        "RTT_s":             RTT_s,
        "interval_s":        interval_s,
        "effective_pax":     effective_pax,
        "capacity_5min":     capacity_5min,
        "HC_pct":            HC_pct,
        "target_interval_s": tgt["interval"],
        "target_HC_pct":     tgt["HC"],
        "interval_check":    "PASS" if interval_ok else "FAIL",
        "HC_check":          "PASS" if HC_ok else "FAIL",
        "overall_check":     overall,
    }
