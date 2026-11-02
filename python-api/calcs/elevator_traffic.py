"""
Elevator Traffic Analysis — Vertical Transport (Option B port from TypeScript)
Standards: CIBSE Guide D:2015 (Transportation Systems in Buildings),
           ASME A17.1:2019 (Safety Code for Elevators),
           ISO 4190-6:2004 (Measurement of passenger service)
Libraries: math

Method: CIBSE Guide D Round Trip Time (RTT) method
  RTT = 2·H·tv + (S+1)·ts + 2·P·tp
  Interval = RTT / n_elevators
  HC% = (n_elevators × 300 × P / RTT) / population × 100
  Average stops S = N × [1 − (1 − 1/N)^P]; highest reversal H = N − Σ(j/N)^P
"""

import math


OCCUPANCY_TARGETS: dict[str, dict] = {
    "Office":      {"interval": 30, "HC": 12},
    "Residential": {"interval": 60, "HC": 7},
    "Hotel":       {"interval": 40, "HC": 10},
    "Mixed-Use":   {"interval": 40, "HC": 11},
}

# CIBSE Guide D typical single-floor flight time for a 3.3 m floor (rated speed m/s, s); 3.5 and 5.0 m/s take the
# upper end of the 3.7-4.0 s band: a car at those speeds never reaches rated speed in one floor.
TF1_TABLE = [(1.0, 7.0), (1.5, 6.0), (2.5, 4.8), (3.5, 4.0), (5.0, 4.0)]
TP_S = 1.2   # passenger transfer time, each way (CIBSE Guide D typical for a 1.1 m door)


# formula: elevator_traffic_iso_4190_6
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

    # ★THE ROUND TRIP LEFT OUT WHAT EACH STOP COSTS THE CAR (2026-11-02, ED-G1 Elevator, read against CIBSE Guide D /
    # Peters 2000 Eq. 9: RTT = 2·H·tv + (S+1)·ts + 2·P·tp). The engine ran the whole rise at rated speed, charged each stop
    # only its door times, skipped the stop at the main floor, and moved every passenger in 0.8 s one way. A car that stops
    # loses the time to slow down and speed up again (ts = tf1 + tc + to − tv: the single-floor flight time less the time
    # to cross that floor at speed), and a passenger takes about 1.2 s each to get in and again to get out. The default
    # 12-floor, three-car office read RTT 110 s and a 37 s interval; by CIBSE it is 147 s and 49 s - the handling capacity
    # was overstated by about a third, enough to buy one car too few.
    # P is the average load, CF·CC, not a whole number of people.
    P = capacity * 0.80
    effective_pax = round(P, 1)

    H_m = round((n_floors - 1) * floor_height, 1)
    N = max(n_floors - 1, 1)                               # floors above the main terminal

    # Probable stops and highest reversal floor, equal floor populations (CIBSE Guide D / Peters Eq. 3-4)
    S_raw = N * (1.0 - (1.0 - 1.0 / N) ** P)
    H_rev = N - sum((j / N) ** P for j in range(1, N))
    avg_stops = round(S_raw, 1)

    t_v = floor_height / speed if speed > 0 else 0.0       # one floor at rated speed

    # Single-floor flight time, CIBSE Guide D Table (3.3 m floors); the extra height is crossed at rated speed.
    if speed <= TF1_TABLE[0][0]:
        tf1 = TF1_TABLE[0][1] + 3.3 / speed - 3.3 / TF1_TABLE[0][0]
    elif speed >= TF1_TABLE[-1][0]:
        tf1 = TF1_TABLE[-1][1]
    else:
        for (v0, t0), (v1, t1) in zip(TF1_TABLE, TF1_TABLE[1:]):
            if v0 <= speed <= v1:
                tf1 = t0 + (t1 - t0) * (speed - v0) / (v1 - v0)
                break
    tf1 += (floor_height - 3.3) / speed

    t_s = tf1 + t_door_close + t_door_open - t_v           # time a stop costs the car

    # Passenger transfer, 2·P·tp. The dwell is the least time the doors stay open at a stop: it governs only when
    # the passengers per stop clear faster than that.
    t_transfer = 2.0 * P * TP_S
    t_load_raw = max(t_transfer, (S_raw + 1.0) * t_dwell)

    t_flight_s = round(2.0 * H_rev * t_v, 1)
    t_stops_s  = round((S_raw + 1.0) * t_s, 1)
    t_load_s   = round(t_load_raw, 1)
    RTT_raw    = 2.0 * H_rev * t_v + (S_raw + 1.0) * t_s + t_load_raw
    RTT_s      = round(RTT_raw, 1)

    # Traffic performance
    interval_s    = round(RTT_raw / n_elevators, 1) if n_elevators > 0 else 0.0
    hc5_raw       = 300.0 * P * n_elevators / RTT_raw if RTT_raw > 0 else 0.0
    capacity_5min = round(hc5_raw)
    HC_pct        = round(hc5_raw / population * 100, 1) if population > 0 else 0.0

    tgt = OCCUPANCY_TARGETS.get(occupancy, OCCUPANCY_TARGETS["Office"])
    interval_ok = interval_s <= tgt["interval"]
    HC_ok       = HC_pct >= tgt["HC"]
    overall     = "PASS" if interval_ok and HC_ok else "FAIL"

    return {
        "H_m":               H_m,
        "t_flight_s":        t_flight_s,
        "avg_stops":         avg_stops,
        "H_reversal":        round(H_rev, 2),
        "t_v_s":             round(t_v, 2),
        "t_flight_1floor_s": round(tf1, 2),
        "t_stop_s":          round(t_s, 2),
        "t_transfer_s":      round(t_transfer, 1),
        "tp_s":              TP_S,
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
