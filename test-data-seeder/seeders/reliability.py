"""Seed Reliability Engineering Workbench tables (Phase R.1+).

Without this seeder the FMEA / RCM / Weibull / P-F tabs and the Print Report
all render empty against a freshly-seeded local Supabase, which means the
Tester gates do not actually exercise Phase R.1-R.7. This seeder produces:

  - rcm_fmea_modes:   3-5 rows per asset, mix of approved + pending,
                      mix of source='manual' and source='ai_logbook'
  - rcm_strategies:   1-2 rows per asset (linked to top-RPN modes), mix of
                      decisions per JA1011 with realistic intervals
  - weibull_fits:     1 row per asset with realistic (beta, eta) per asset
                      criticality
  - pf_intervals:     1 row per asset on a vibration parameter, basis P-F/2

All FK relationships are resolved through queries (asset_nodes by hive,
existing FMEA mode IDs for strategies). The data is deterministic via the
orchestrator's RNG seed so visual baselines stay stable.

Skill input:
  - maintenance-expert (FMEA vocabulary, S/O/D ranges per consequence_class,
    JA1011 decision distribution by criticality)
  - data-engineer      (avoid duplicates via unique-per-function constraint;
    write batch_size=500)
  - architect          (write to underlying tables; canonical views surface
    only approved rows automatically)
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from .utils import batch_insert


# ── Vocabulary buckets ─────────────────────────────────────────────────────────
# Pulled by ISO class so the seeded data looks realistic on Asset Hub.
# Keys mirror asset_nodes.iso_class values seeded by seed_assets.

FMEA_TEMPLATES = {
    "Mechanical": [
        ("Maintain rated discharge pressure", "V-belt slipping under load",
         "Loss of pressure, reduced flow", "Worn V-belt + misaligned sheaves",
         "production", 6, 5, 4),
        ("Transmit torque without vibration", "Bearing inner race spalling",
         "Vibration > 7 mm/s, audible roar",
         "Inadequate lubrication / overload",
         "production", 7, 4, 6),
        ("Maintain shaft alignment", "Coupling misalignment beyond 0.05 mm",
         "Premature seal failure, vibration", "Foundation settlement / hot alignment skipped",
         "production", 6, 6, 5),
        ("Hold lubricant inside housing", "Lip seal leaking",
         "Oil drips, contamination of floor",
         "Worn seal lip + abrasive shaft surface",
         "environment", 4, 5, 3),
    ],
    "Electrical": [
        ("Deliver 380V three-phase to load", "Cable insulation breakdown",
         "Earth fault trip, line down",
         "UV embrittlement / rodent damage",
         "safety", 9, 3, 4),
        ("Maintain stable contactor operation", "Contactor coil burnout",
         "Motor will not start, alarm",
         "Coil insulation aged, sustained over-voltage",
         "production", 6, 4, 3),
        ("Detect over-current within 10 ms", "MCCB trip unit drift",
         "Nuisance trip or no trip on fault",
         "Calibration drift, missed PM",
         "safety", 8, 3, 7),
        ("Provide stable 24V control supply", "Switch-mode PSU output ripple",
         "PLC dropouts, intermittent shutdowns",
         "Output capacitor ESR rising with age",
         "production", 5, 5, 6),
    ],
    "Hydraulic": [
        ("Maintain 180 bar working pressure", "Pump cavitation",
         "Pressure drop, foaming oil",
         "Suction strainer clogged / low oil level",
         "production", 7, 5, 4),
        ("Hold cylinder position under load", "Internal piston seal leak",
         "Cylinder drift, slow operation",
         "Worn seal kit, contaminated oil",
         "production", 5, 6, 4),
        ("Filter oil to ISO 18/16/13", "Filter element bypass",
         "Particle ingress to servo valves",
         "Bypass spring fatigue, missed change-out",
         "production", 7, 4, 6),
    ],
    "Pneumatic": [
        ("Deliver clean dry compressed air at 6.5 bar", "Refrigerated dryer fail",
         "Wet air to pneumatic actuators",
         "Refrigerant low, condenser fouled",
         "quality", 5, 4, 3),
        ("Maintain regulator setpoint", "Regulator drift",
         "Variable cylinder force, reject parts",
         "Spring fatigue, dirty diaphragm",
         "quality", 4, 5, 5),
    ],
    "Instrumentation": [
        ("Report process pressure to PLC", "4-20 mA loop break",
         "PLC reads 0 mA — false low alarm",
         "Cable damage, loose terminal",
         "safety", 8, 3, 2),
        ("Maintain calibration within +/-1% FS", "Sensor drift",
         "Process value off-spec, reject batch",
         "Calibration cycle missed",
         "quality", 5, 6, 4),
    ],
    "Lubrication": [
        ("Deliver grease to bearing every 500h", "Auto-luber line block",
         "Bearing starves, dry-running",
         "Grease congealed at low temp / line bent",
         "production", 6, 4, 6),
    ],
}
# Fallback templates for any iso_class not in the map above
FMEA_FALLBACK = FMEA_TEMPLATES["Mechanical"]

# ── Equipment-type-specific FMEA templates ────────────────────────────────────
# Keyed by exact assets.type strings. Falls back to FMEA_TEMPLATES[iso_class]
# for any type not listed here. Adding a new equipment type's failure modes
# here is purely seeder fidelity — the platform schema does not change.
FMEA_TEMPLATES_BY_TYPE: dict[str, list[tuple]] = {
    "Bag Filter": [
        ("Maintain pressure drop within design (1-3 kPa)", "Bag puncture",
         "Dust emission to atmosphere, fail emission test",
         "Abrasive material, embrittlement, over-pulsing",
         "environment", 7, 5, 3),
        ("Capture particulates effectively", "Pulse-jet diaphragm valve rupture",
         "Loss of cleaning, increasing dP, blinded bags",
         "Diaphragm material fatigue, dirty air supply",
         "production", 5, 4, 4),
        ("Seal compartments under pressure", "Plenum gasket leak",
         "Bypass of dirty air to clean side",
         "Gasket aged or damaged at door / inspection hatch",
         "environment", 5, 4, 5),
        ("Maintain bag tension on cage", "Bag cage corrosion",
         "Bag wear at touching points, premature failure",
         "Moisture ingress, acid attack, missed cage replacement",
         "production", 4, 4, 4),
        ("Detect a broken bag event", "Broken-bag detector failure",
         "Dust release goes undetected for hours",
         "Sensor dust-coated, calibration missed",
         "safety", 8, 3, 8),
    ],
    "Dust Collector": None,   # alias — see _resolve_type_pool
    "Steam Boiler": [
        ("Generate steam at rated pressure", "Tube wall thinning / leak",
         "Pressure loss, shell water carryover",
         "Scale, corrosion, missed UT inspection",
         "safety", 9, 3, 5),
        ("Maintain water level within band", "Low-water cutoff failure to trip",
         "Dry-firing, shell damage, blow-down",
         "Probe fouling, contact failure",
         "safety", 10, 2, 4),
        ("Burn fuel completely", "Burner flame instability",
         "High CO, sooting, refractory damage",
         "Wrong air-fuel ratio, nozzle wear",
         "quality", 6, 4, 3),
        ("Withstand thermal cycling", "Refractory cracking",
         "Hot spot, tube damage, efficiency loss",
         "Thermal shock from cold start, age",
         "production", 5, 4, 6),
        ("Vent overpressure safely", "Safety valve seat leakage",
         "Continuous steam loss, energy waste",
         "Seat damage, scale, missed lift test",
         "safety", 7, 3, 4),
    ],
    "Air Compressor": [
        ("Deliver clean dry air at rated pressure", "Aftercooler approach temp high",
         "Wet air downstream, dryer overload",
         "Heat exchanger fouling, low water flow",
         "quality", 5, 5, 4),
        ("Maintain oil/air separation", "Air-oil separator clog",
         "High discharge temp, oil carryover into system",
         "Saturation, missed change interval",
         "production", 6, 5, 4),
        ("Lubricate compressor element", "Oil filter bypass open",
         "Contaminated oil to bearings",
         "Filter clogged, missed PM",
         "production", 5, 4, 4),
        ("Cool compressor head", "Cylinder head crack",
         "Oil leak, output drop, possible seizure",
         "Thermal shock from coolant interruption",
         "production", 7, 3, 6),
        ("Stop on overpressure", "Pressure switch drift",
         "Compressor cycles into relief valve",
         "Mechanical wear, calibration missed",
         "production", 4, 5, 5),
    ],
    "Reciprocating Compressor": None,   # alias
    "Genset": [
        ("Start within 10s on demand", "Battery failure to crank",
         "No start, lose backup power",
         "Sulfation, missed weekly exercise",
         "safety", 9, 3, 3),
        ("Generate stable 380V at 50 Hz", "AVR voltage drift",
         "Voltage swing, downstream equipment damage",
         "Component drift, capacitor age",
         "production", 6, 4, 4),
        ("Cool engine under sustained load", "Radiator fouling",
         "Engine overheat, derate or shutdown",
         "Dust, scale, missed cleaning",
         "production", 6, 4, 4),
        ("Sustain rated load for 8h+", "Alternator bearing failure",
         "Trip during outage, no power",
         "Lube failure, age",
         "safety", 8, 3, 5),
        ("Burn fuel cleanly", "Injector wear",
         "Black smoke, power drop, fuel waste",
         "Wear, contaminated fuel",
         "quality", 5, 5, 3),
    ],
    "UPS": [
        ("Maintain backup for 15+ min at full load", "Battery string capacity loss",
         "Reduced runtime, possible drop on outage",
         "Cell aging, ambient over 25°C",
         "safety", 8, 4, 4),
        ("Provide clean sine wave to load", "Inverter module failure",
         "Load drops on transfer to bypass",
         "Component aging, thermal stress",
         "production", 7, 3, 5),
        ("Switch to battery within 4 ms", "Static switch failure",
         "Load drop on outage event",
         "Thyristor failure, control board",
         "production", 7, 3, 6),
        ("Recharge battery within 8h", "Charger fault",
         "Battery deep-discharge over time",
         "Charger control board, fan failure",
         "production", 5, 4, 4),
    ],
    "Transformer": [
        ("Step down voltage with low loss", "Winding insulation degradation",
         "Partial discharge, eventual failure",
         "Thermal aging, moisture in oil",
         "safety", 9, 2, 7),
        ("Cool through oil + radiators", "Oil pump or fan failure",
         "Hot spot, gas formation, derate",
         "Bearing wear, control circuit",
         "production", 7, 3, 4),
        ("Maintain dielectric strength", "Oil moisture > 30 ppm",
         "Reduced BIL, breakdown risk",
         "Breather silica gel saturated",
         "safety", 7, 4, 4),
        ("Bushing seal integrity", "Bushing oil leak",
         "Insulator pollution, flashover risk",
         "Gasket failure, vibration",
         "safety", 8, 3, 4),
    ],
    "Switchgear": [
        ("Interrupt fault current safely", "Vacuum bottle insulation drop",
         "Failed interruption, persistent arc",
         "Mechanism wear, vacuum loss",
         "safety", 10, 2, 7),
        ("Operate close/open mechanism", "Spring charge motor failure",
         "Cannot reset breaker after trip",
         "Motor brushes, control circuit",
         "safety", 7, 3, 3),
        ("Sense fault current via CT", "CT secondary open circuit",
         "Wrong trip behaviour, dangerous voltages",
         "Wiring damage, test plug left open",
         "safety", 8, 3, 5),
        ("Hold rated current without heating", "Bus joint loose / hot",
         "Hot spot, eventual melt, flashover",
         "Vibration, missed thermography",
         "safety", 8, 3, 7),
    ],
    "AC Motor": [
        ("Drive load at rated speed", "DE/NDE bearing failure",
         "Vibration, growling, eventual seizure",
         "Lube failure, contamination, misalignment",
         "production", 7, 4, 4),
        ("Maintain insulation > 100 MΩ", "Stator winding insulation breakdown",
         "Earth fault trip, line down",
         "Moisture, thermal stress, age",
         "safety", 9, 3, 5),
        ("Operate within thermal limit", "Overheating",
         "Insulation degradation, premature failure",
         "Overload, blocked cooling fins",
         "production", 6, 4, 3),
        ("Run on balanced phases", "Single-phasing on supply",
         "Winding burn-out within seconds",
         "Open contactor pole, blown fuse",
         "production", 8, 2, 3),
    ],
    "VFD": [
        ("Convert AC to variable-freq AC", "IGBT module failure",
         "Drive trip, no output",
         "Thermal cycling, dv/dt to motor",
         "production", 7, 4, 5),
        ("Maintain DC bus capacitance", "DC link capacitor aging",
         "Output ripple, intermittent trip",
         "Capacitor electrolyte dry-out",
         "production", 5, 5, 5),
        ("Cool power stage", "Cooling fan failure",
         "Thermal trip under load",
         "Fan bearing wear, dust ingress",
         "production", 5, 5, 3),
        ("Filter motor cable harmonics", "Output reactor failure",
         "Motor insulation stress, premature winding fail",
         "Coil thermal runaway",
         "production", 6, 3, 5),
    ],
    "Centrifugal Pump": [
        ("Deliver rated flow at design head", "Impeller wear / erosion",
         "Reduced head, cavitation, low flow",
         "Abrasive solids, NPSHa low",
         "production", 6, 5, 4),
        ("Seal pumped fluid from atmosphere", "Mechanical seal leak",
         "Process fluid release on floor",
         "Misalignment, dry running, contamination",
         "environment", 6, 5, 3),
        ("Run without vibration > 4.5 mm/s", "Bearing failure",
         "Vibration alarm, shaft seizure risk",
         "Lube starvation, contamination",
         "production", 7, 4, 5),
        ("Hold prime under suction lift", "Suction strainer blockage",
         "Cavitation, no flow",
         "Process debris, fouling",
         "production", 5, 5, 3),
        ("Maintain coupling alignment", "Coupling element failure",
         "Vibration, seal damage, downtime",
         "Misalignment, age",
         "production", 6, 4, 4),
    ],
    "Process Pump": None,
    "Slurry Pump": None,
    "Submersible Pump": None,
    "Cooling Tower": [
        ("Reject heat at design rate", "Fill fouling",
         "Reduced cooling capacity, downstream temp rise",
         "Biofilm, suspended solids, sediment",
         "production", 5, 5, 3),
        ("Maintain water distribution", "Spray nozzle clogging",
         "Channelling, low ΔT",
         "Suspended solids, scale",
         "production", 4, 5, 3),
        ("Drive fan at rated speed", "Gearbox oil leak",
         "Fan wobble, eventual seizure",
         "Seal failure, vibration",
         "production", 6, 4, 4),
        ("Prevent legionella proliferation", "Biocide dosing failure",
         "Health hazard for workers",
         "Dosing pump fault, missed top-up",
         "safety", 9, 2, 5),
    ],
    "Heat Exchanger": [
        ("Transfer heat at design ΔT", "Tube fouling",
         "Reduced ΔT, performance loss",
         "Scale, biofouling, missed cleaning",
         "production", 5, 5, 3),
        ("Separate two fluids", "Tube leak / cross-contamination",
         "Quality contamination, possible reaction",
         "Erosion, corrosion, vibration",
         "quality", 8, 3, 4),
        ("Withstand pressure cycling", "Gasket leak",
         "External fluid loss, area contamination",
         "Bolt relaxation, gasket aged",
         "environment", 5, 4, 4),
    ],
    "Chiller": [
        ("Produce chilled water at setpoint", "Compressor surge",
         "Loss of capacity, possible damage",
         "Wrong head pressure, low evap temp",
         "production", 7, 4, 5),
        ("Reject heat through condenser", "Condenser fouling",
         "High discharge temp, derate",
         "Scale, dust on coils",
         "production", 5, 5, 3),
        ("Maintain refrigerant charge", "Refrigerant leak",
         "Low capacity, environmental release",
         "Fitting failure, vibration",
         "environment", 6, 4, 5),
        ("Lubricate compressor", "Oil pump failure",
         "Bearing damage, compressor seizure",
         "Pump wear, oil contamination",
         "production", 7, 3, 5),
    ],
    "Air Handling Unit": [
        ("Supply conditioned air at design CFM", "Filter pressure drop high",
         "Reduced flow, occupant complaints",
         "Filter loaded, missed change interval",
         "quality", 5, 5, 4),
        ("Drive supply fan at rated speed", "Fan belt slip",
         "Reduced air, vibration",
         "Belt wear, tension loss",
         "production", 4, 5, 4),
        ("Cool air through coil", "Coil fin damage",
         "Reduced heat transfer, freezing risk",
         "Physical damage, debris",
         "production", 5, 4, 3),
    ],
    "Hydraulic Power Unit": [
        ("Supply oil at rated pressure", "Pump cavitation",
         "Loss of pressure, foaming oil",
         "Suction strainer clog, low oil level",
         "production", 7, 5, 4),
        ("Filter to ISO 18/16/13", "Filter element bypass",
         "Particle ingress to servo valves",
         "Bypass spring fatigue, missed change-out",
         "production", 7, 4, 6),
        ("Cool oil below 60°C", "Cooler fan failure",
         "Oil overheating, viscosity drop",
         "Fan motor failure",
         "production", 6, 4, 3),
        ("Hold cylinder position under load", "Piston seal leak",
         "Cylinder drift, slow operation",
         "Worn seal kit, contaminated oil",
         "production", 5, 6, 4),
    ],
    "Pressure Vessel": [
        ("Contain pressure within design", "Shell corrosion thinning",
         "Burst risk, regulatory non-compliance",
         "Process chemistry, missed UT inspection",
         "safety", 10, 2, 5),
        ("Vent overpressure safely", "Relief valve simmer",
         "Continuous loss, eventual stuck-open",
         "Seat damage, scale",
         "production", 5, 4, 4),
        ("Maintain corrosion allowance", "Internal coating peel",
         "Substrate corrosion accelerated",
         "Heat cycling, mechanical impact",
         "production", 4, 4, 6),
        ("Detect inventory level", "Level transmitter drift",
         "Wrong inventory shown, overfill risk",
         "Probe coating, calibration missed",
         "safety", 6, 5, 5),
    ],
    "Belt Conveyor": [
        ("Transport material at rated TPH", "Belt tracking off-center",
         "Spillage, belt edge wear, fire risk",
         "Misalignment, frame settled, head pulley wear",
         "safety", 6, 5, 3),
        ("Drive belt without slip", "Drive pulley lagging worn",
         "Belt slip, motor overload",
         "Wear from carryback abrasion",
         "production", 4, 5, 4),
        ("Support belt across run", "Idler bearing seizure",
         "Hot spot, belt fire risk",
         "Lube failure, dust ingress",
         "safety", 8, 3, 3),
        ("Strip carryback at head", "Skirt seal worn",
         "Material fall-off, housekeeping issue",
         "Wear, missed adjustment",
         "environment", 4, 5, 3),
    ],
    "Bucket Elevator": [
        ("Lift material to head pulley", "Bucket loss / damage",
         "Reduced throughput, spillage in boot",
         "Feed-side impact, bolt loosening",
         "production", 5, 5, 3),
        ("Maintain belt/chain tension", "Take-up bearing seizure",
         "Tension loss, belt slap",
         "Lube failure, dust ingress",
         "production", 6, 4, 4),
        ("Discharge cleanly at head", "Hood liner wear-through",
         "Material spillage, equipment damage",
         "Abrasive product, wear",
         "production", 4, 5, 5),
    ],
    "Press Brake": [
        ("Apply force per program", "Hydraulic pressure drop",
         "Underforming, scrap parts",
         "Pump wear, internal leak",
         "quality", 5, 4, 4),
        ("Position ram within ±0.05 mm", "Linear scale drift",
         "Out-of-tolerance bend angle",
         "Cable damage, contamination",
         "quality", 6, 4, 5),
        ("Detect operator hands in work envelope", "Light curtain failure",
         "Operator injury risk",
         "Sensor misalignment, lens dust",
         "safety", 10, 2, 5),
    ],
    "CNC Lathe": [
        ("Position tool within ±0.02 mm", "Ball screw backlash",
         "Out-of-tolerance parts, scrap",
         "Wear, lost preload",
         "quality", 6, 4, 5),
        ("Hold workpiece stable", "Chuck jaw wear",
         "Workpiece spin, surface defect",
         "Wear, no calibration",
         "quality", 6, 4, 4),
        ("Cool tool tip", "Coolant pump failure",
         "Tool wear accelerated, scrap",
         "Pump impeller wear",
         "quality", 5, 4, 3),
    ],
    "CNC Mill": None,    # alias to CNC Lathe templates
    "Forklift": [
        ("Lift to rated capacity", "Mast chain stretch",
         "Tilt failure, drop hazard",
         "Wear, missed lubrication, overload",
         "safety", 9, 3, 4),
        ("Brake within stopping distance", "Brake pad wear",
         "Reduced stopping power",
         "Wear, missed PM",
         "safety", 8, 4, 3),
        ("Steer accurately", "Tie rod end wear",
         "Steering play, control loss",
         "Wear",
         "safety", 6, 4, 5),
        ("Maintain battery for full shift", "Battery cell failure",
         "Reduced runtime, mid-shift swap",
         "Sulfation, deep discharge",
         "production", 5, 4, 4),
    ],
    "Overhead Crane": [
        ("Lift load to rated capacity", "Wire rope wear / broken strands",
         "Load drop hazard, personnel risk",
         "Wear, fatigue, missed UT inspection",
         "safety", 10, 2, 4),
        ("Travel along rails smoothly", "Wheel flange wear",
         "Derailment risk",
         "Misalignment, wear",
         "safety", 8, 3, 5),
        ("Brake within design slip", "Brake disc glazing",
         "Increased slip, runaway risk",
         "Heat, contamination",
         "safety", 9, 3, 3),
    ],
    "Welder": [
        ("Maintain stable arc current", "Output transformer fault",
         "Erratic weld, weld defects",
         "Insulation breakdown",
         "quality", 6, 3, 5),
        ("Cool torch nozzle", "Coolant flow loss",
         "Torch overheat, consumable damage",
         "Pump failure, hose kink",
         "production", 5, 4, 3),
        ("Feed wire smoothly", "Drive roller wear",
         "Wire jam, weld interruption",
         "Wear, dust",
         "quality", 4, 5, 4),
    ],
    "Pressure Transmitter": [
        ("Report process pressure to PLC", "4-20 mA loop break",
         "PLC reads 0 mA, false low alarm",
         "Cable damage, terminal loose",
         "safety", 8, 3, 2),
        ("Maintain calibration ±1% FS", "Sensor drift",
         "Process value off-spec",
         "Calibration cycle missed",
         "quality", 5, 6, 4),
        ("Survive process exposure", "Diaphragm corrosion",
         "Plugged signal, false low",
         "Chemistry attack, missed inspection",
         "production", 5, 3, 6),
        ("Communicate via HART", "HART comms loss",
         "Diagnostic alarms cease",
         "Wiring damage, master failure",
         "quality", 4, 4, 6),
    ],
    "Temperature Transmitter": None,  # alias to Pressure Transmitter
    "PLC": [
        ("Run logic without lockup", "Watchdog timeout",
         "Process trip, downtime",
         "Firmware bug, supply ripple",
         "safety", 7, 3, 4),
        ("Communicate with field I/O", "Comms card failure",
         "Loss of I/O, blind operation",
         "Hardware failure, EMI",
         "production", 7, 3, 4),
        ("Retain program over power-fail", "Battery for retentive memory dead",
         "Loss of program on power fail",
         "Battery aged",
         "production", 6, 4, 5),
    ],
}

# Resolve None-valued entries to their alias targets so the seeder can index
# directly. This keeps the table above readable while avoiding repeating
# template lists for similar equipment.
_TYPE_ALIASES = {
    "Dust Collector":           "Bag Filter",
    "Reciprocating Compressor": "Air Compressor",
    "Process Pump":             "Centrifugal Pump",
    "Slurry Pump":              "Centrifugal Pump",
    "Submersible Pump":         "Centrifugal Pump",
    "CNC Mill":                 "CNC Lathe",
    "Temperature Transmitter":  "Pressure Transmitter",
}
for _alias, _target in _TYPE_ALIASES.items():
    FMEA_TEMPLATES_BY_TYPE[_alias] = FMEA_TEMPLATES_BY_TYPE[_target]


def _resolve_pool(asset_type: str | None, iso_class: str | None) -> list:
    """Pick the most-specific FMEA template list available."""
    t = (asset_type or "").strip()
    if t and t in FMEA_TEMPLATES_BY_TYPE:
        return FMEA_TEMPLATES_BY_TYPE[t]
    cat = (iso_class or "Mechanical").strip()
    return FMEA_TEMPLATES.get(cat) or FMEA_FALLBACK


RCM_DECISION_BY_CONSEQ = {
    # Drives a defensible JA1011 decision based on the FMEA consequence class.
    "safety":      ("scheduled_on_condition", "Continuous monitoring + walk-down per shift",      30),
    "environment": ("scheduled_on_condition", "Quarterly seal inspection + leak survey",          90),
    "production":  ("scheduled_restoration",  "Time-based overhaul; replace wear parts",          180),
    "quality":     ("scheduled_on_condition", "Calibration check + drift trending",               90),
    "cost":        ("run_to_failure",         None,                                                None),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _between_days(lo: int, hi: int) -> str:
    days = random.randint(lo, hi)
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def seed_reliability(client, log, ctx: dict) -> dict:
    """Seed FMEA + RCM + Weibull + P-F per seeded asset_node."""
    log("Seeding Reliability Workbench (FMEA + RCM + Weibull + P-F)...")

    hives = ctx.get("hives") or []
    if not hives:
        log("  no hives in ctx — reliability skipped")
        return {"fmea_modes": 0, "rcm_strategies": 0, "weibull_fits": 0, "pf_intervals": 0}

    # Pull the seeded asset_nodes back so we have their UUIDs (asset_brain.py
    # inserted them but does not return IDs in ctx).
    nodes = []
    for hive in hives:
        try:
            res = client.table("asset_nodes").select(
                "id, hive_id, name, tag, iso_class, criticality, worker_name, legacy_asset_id"
            ).eq("hive_id", hive["id"]).limit(500).execute()
            nodes.extend(res.data or [])
        except Exception as e:
            log(f"  WARN: asset_nodes fetch failed for hive {hive['id'][:8]}: {e}")

    if not nodes:
        log("  no asset_nodes found — reliability skipped")
        return {"fmea_modes": 0, "rcm_strategies": 0, "weibull_fits": 0, "pf_intervals": 0}

    # Pull legacy assets.type for every node that has a bridge. The reliability
    # seeder picks equipment-type-specific FMEA templates when available,
    # otherwise falls back to the iso_class generic pool. Without this lookup,
    # a Bag Filter would get pump-style failure modes (the "wrong vocabulary"
    # bug visible in the first BF-001 Reliability Report).
    legacy_ids = [n["legacy_asset_id"] for n in nodes if n.get("legacy_asset_id")]
    type_by_legacy: dict[str, str] = {}
    chunk = 500
    for i in range(0, len(legacy_ids), chunk):
        batch_ids = legacy_ids[i : i + chunk]
        try:
            res = client.table("assets").select("id, type").in_("id", batch_ids).execute()
            for a in (res.data or []):
                if a.get("type"):
                    type_by_legacy[a["id"]] = a["type"]
        except Exception as e:
            log(f"  WARN: assets.type lookup failed: {type(e).__name__}: {e}")

    log(f"  seeding reliability rows for {len(nodes)} asset_nodes ({len(type_by_legacy)} with type)")

    # ── 1. FMEA failure modes ────────────────────────────────────────────────
    fmea_rows = []
    for n in nodes:
        asset_type = type_by_legacy.get(n.get("legacy_asset_id"))
        pool       = _resolve_pool(asset_type, n.get("iso_class"))
        if not pool:
            continue
        # 3-5 modes per asset, but never more than the pool size — Pneumatic /
        # Instrumentation / Lubrication intentionally have small template lists
        # so randint(3, len(pool)) would crash on len(pool) < 3.
        hi = min(5, len(pool))
        lo = min(3, hi)
        n_modes = random.randint(lo, hi)
        sampled = random.sample(pool, k=n_modes)
        for i, t in enumerate(sampled):
            (fn_text, failure_mode, effect, cause, conseq, sev, occ, det) = t
            # Mix sources: 70% manual, 30% ai_logbook (mirrors fmea-populator output)
            is_ai = random.random() < 0.30
            # Mix approval state: 85% approved (fresh seed), 15% pending
            is_approved = random.random() < 0.85
            ai_conf = round(random.uniform(0.55, 0.92), 3) if is_ai else None
            fmea_rows.append({
                "hive_id":           n["hive_id"],
                "asset_id":          n["id"],
                "function_text":     fn_text,
                "failure_mode":      failure_mode,
                "effect_text":       effect,
                "cause_text":        cause,
                "consequence_class": conseq,
                "severity":          sev,
                "occurrence":        occ,
                "detection":         det,
                "source":            "ai_logbook" if is_ai else "manual",
                "ai_confidence":     ai_conf,
                "created_by":        n.get("worker_name") or "seed",
                "approved_by":       (n.get("worker_name") or "seed") if is_approved else None,
                "approved_at":       _between_days(1, 30) if is_approved else None,
            })

    fmea_inserted = 0
    if fmea_rows:
        try:
            fmea_inserted = batch_insert(client, "rcm_fmea_modes", fmea_rows, chunk=500)
            log(f"  inserted {fmea_inserted} rcm_fmea_modes")
        except Exception as e:
            log(f"  WARN: rcm_fmea_modes insert failed: {type(e).__name__}: {e}")

    # ── 2. RCM strategies (link to top-RPN modes per asset) ───────────────────
    # Re-fetch with IDs + asset_id so we can attach strategies.
    fmea_by_asset: dict[str, list[dict]] = {}
    try:
        for hive in hives:
            res = client.table("rcm_fmea_modes").select(
                "id, hive_id, asset_id, severity, occurrence, detection, rpn, consequence_class, approved_at"
            ).eq("hive_id", hive["id"]).limit(2000).execute()
            for r in (res.data or []):
                fmea_by_asset.setdefault(r["asset_id"], []).append(r)
    except Exception as e:
        log(f"  WARN: rcm_fmea_modes fetch failed: {e}")

    strategy_rows = []
    for asset_id, modes in fmea_by_asset.items():
        # Pick the top-RPN approved modes — strategies only make sense on
        # approved FMEA rows (canonical view filters those anyway).
        approved = [m for m in modes if m.get("approved_at")]
        approved.sort(key=lambda m: -(m.get("rpn") or 0))
        targets = approved[:2]   # 1-2 strategies per asset
        for m in targets:
            conseq = m.get("consequence_class") or "production"
            decision, task, interval = RCM_DECISION_BY_CONSEQ.get(
                conseq, RCM_DECISION_BY_CONSEQ["production"]
            )
            # Half of "scheduled_*" strategies get pushed to PM (we don't
            # actually create the pm_scope_item row here — the link target
            # is null so the UI shows "not linked"; that's the realistic
            # cold-start state).
            strategy_rows.append({
                "hive_id":      m["hive_id"],
                "fmea_mode_id": m["id"],
                "decision":     decision,
                "task_text":    task,
                "interval_days": interval,
                "rationale":    f"Seeded for tester. RPN={m.get('rpn')}, consequence={conseq}.",
                "source":       "manual",
                "approved_by":  "seed",
                "approved_at":  _between_days(0, 14),
            })

    rcm_inserted = 0
    if strategy_rows:
        try:
            rcm_inserted = batch_insert(client, "rcm_strategies", strategy_rows, chunk=500)
            log(f"  inserted {rcm_inserted} rcm_strategies")
        except Exception as e:
            log(f"  WARN: rcm_strategies insert failed: {type(e).__name__}: {e}")

    # ── 3. Weibull fits ──────────────────────────────────────────────────────
    weibull_rows = []
    for n in nodes:
        # Distribution biased toward wear-out for older / critical assets.
        crit = (n.get("criticality") or "medium").lower()
        if crit == "critical":
            beta = round(random.uniform(2.2, 3.6), 2)         # wear-out
            eta  = round(random.uniform(140, 320), 1)
            pattern = "wearout"
        elif crit == "high":
            beta = round(random.uniform(1.4, 2.4), 2)
            eta  = round(random.uniform(180, 380), 1)
            pattern = "wearout"
        elif crit == "low":
            beta = round(random.uniform(0.7, 1.1), 2)         # mixed
            eta  = round(random.uniform(220, 540), 1)
            pattern = "infant" if beta < 0.95 else "random"
        else:  # medium
            beta = round(random.uniform(0.95, 1.35), 2)
            eta  = round(random.uniform(200, 460), 1)
            pattern = "random" if beta < 1.05 else "wearout"
        n_failures = random.randint(4, 12)
        weibull_rows.append({
            "hive_id":            n["hive_id"],
            "asset_id":           n["id"],
            "fmea_mode_id":       None,
            "beta":               beta,
            "eta_days":           eta,
            "failure_pattern":    pattern,
            "n_failures":         n_failures,
            "n_censored":         random.randint(0, 2),
            "fit_method":         "mle_lifelines",
            "log_likelihood":     round(-1 * random.uniform(20, 80), 2),
            "source_window_days": 730,
        })

    weibull_inserted = 0
    if weibull_rows:
        try:
            weibull_inserted = batch_insert(client, "weibull_fits", weibull_rows, chunk=500)
            log(f"  inserted {weibull_inserted} weibull_fits")
        except Exception as e:
            log(f"  WARN: weibull_fits insert failed: {type(e).__name__}: {e}")

    # ── 4. P-F intervals ─────────────────────────────────────────────────────
    # One per asset on a category-appropriate parameter. Uses median pf_days
    # in a realistic operating range so the UI shows non-degenerate cadence.
    PF_BY_CAT = {
        "Mechanical":      ("vibration_mms", 4.5, 7.1, "above"),
        "Electrical":      ("temperature_c", 70, 95,  "above"),
        "Hydraulic":       ("pressure_bar",  155, 130, "below"),
        "Pneumatic":       ("pressure_bar",  5.5, 4.0, "below"),
        "Instrumentation": ("signal_ma",     14, 20.5, "above"),
        "Lubrication":     ("temperature_c", 65, 82,  "above"),
    }
    pf_rows = []
    for n in nodes:
        cat = n.get("iso_class") or "Mechanical"
        if cat not in PF_BY_CAT:
            continue
        param, p_thr, f_thr, _direction = PF_BY_CAT[cat]
        pf_days = random.randint(14, 56)
        # Half of critical assets get P-F/3 basis (more conservative)
        is_safety = (n.get("criticality") or "").lower() == "critical" and random.random() < 0.5
        basis = "P-F/3" if is_safety else "P-F/2"
        divisor = 3 if is_safety else 2
        rec_interval = max(1, round(pf_days / divisor))
        pf_rows.append({
            "hive_id":                   n["hive_id"],
            "asset_id":                  n["id"],
            "fmea_mode_id":              None,
            "parameter":                 param,
            "p_threshold":               p_thr,
            "f_threshold":               f_thr,
            "pf_days":                   pf_days,
            "recommended_interval_days": rec_interval,
            "basis":                     basis,
        })

    pf_inserted = 0
    if pf_rows:
        try:
            pf_inserted = batch_insert(client, "pf_intervals", pf_rows, chunk=500)
            log(f"  inserted {pf_inserted} pf_intervals")
        except Exception as e:
            log(f"  WARN: pf_intervals insert failed: {type(e).__name__}: {e}")

    return {
        "fmea_modes":     fmea_inserted,
        "rcm_strategies": rcm_inserted,
        "weibull_fits":   weibull_inserted,
        "pf_intervals":   pf_inserted,
    }
