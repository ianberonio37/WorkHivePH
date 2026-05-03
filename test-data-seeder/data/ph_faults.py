"""Fault description templates per equipment category.

Each entry:
  problem        - what was observed
  root_cause     - what was diagnosed
  action         - corrective action taken
  parts_used     - common parts (used by inventory seeder)
  severity       - low | medium | high
"""

FAULTS_BY_CATEGORY = {
    "Genset": [
        {"problem": "Engine failed to start on auto", "root_cause": "Battery voltage low (10.8V); failed CCA test", "action": "Replaced 12V 100Ah battery; verified alternator output 13.8V", "parts_used": ["Battery 12V 100Ah"], "severity": "high"},
        {"problem": "High exhaust temperature alarm at 75% load", "root_cause": "Turbocharger fouling, post-filter restriction", "action": "Cleaned air filter housing, replaced primary element", "parts_used": ["Air filter element"], "severity": "medium"},
        {"problem": "Coolant temperature exceeded 95°C alarm", "root_cause": "Radiator core 40% blocked with debris", "action": "Pressure-washed radiator core, refilled coolant 50/50 glycol", "parts_used": ["Coolant 20L"], "severity": "medium"},
        {"problem": "Loss of synchronization with grid", "root_cause": "AVR voltage sensing relay sticking", "action": "Replaced AVR relay K3, rechecked sync timing", "parts_used": ["AVR relay K3"], "severity": "high"},
        {"problem": "Fuel pressure low alarm during load test", "root_cause": "Primary fuel filter clogged at 8 weeks service", "action": "Replaced primary + secondary fuel filters", "parts_used": ["Primary fuel filter", "Secondary fuel filter"], "severity": "medium"},
        {"problem": "Lube oil pressure dropping over 30 min run", "root_cause": "Oil filter bypass valve worn, internal leakage", "action": "Replaced oil filter and bypass valve assembly", "parts_used": ["Oil filter", "Lube oil 20L SAE 15W-40"], "severity": "high"},
    ],
    "Centrifugal Pump": [
        {"problem": "Mechanical seal leak detected at gland", "root_cause": "Seal faces worn after 11,000 hrs service", "action": "Replaced cartridge mechanical seal John Crane Type 2100", "parts_used": ["Mech seal Type 2100"], "severity": "medium"},
        {"problem": "Vibration alarm 8.5 mm/s at DE bearing", "root_cause": "Coupling misalignment 0.4 mm parallel offset", "action": "Re-aligned with laser tool to 0.05 mm; rechecked vibration 2.1 mm/s", "parts_used": [], "severity": "medium"},
        {"problem": "Cavitation noise during morning startup", "root_cause": "Suction strainer 60% clogged with sediment", "action": "Cleaned suction strainer, restored NPSHa", "parts_used": [], "severity": "low"},
        {"problem": "DE bearing temperature 92°C trip", "root_cause": "Bearing grease degraded, contamination present", "action": "Replaced 6310 C3 bearing, repacked with high-temp grease", "parts_used": ["Bearing 6310 C3", "Grease NLGI 2"], "severity": "high"},
        {"problem": "Discharge pressure dropped 0.8 bar over shift", "root_cause": "Impeller wear ring gap 1.2 mm vs spec 0.4 mm", "action": "Replaced wear rings, re-tested pump curve", "parts_used": ["Wear ring set"], "severity": "medium"},
    ],
    "Process Pump": [
        {"problem": "Casing gasket weeping product", "root_cause": "Gasket compression set after temperature cycling", "action": "Replaced spiral-wound gasket SS316/Graphite", "parts_used": ["Spiral wound gasket"], "severity": "medium"},
        {"problem": "Pump tripping on motor overload", "root_cause": "Specific gravity of product higher than design", "action": "Trimmed impeller 5mm, retested current draw within FLA", "parts_used": [], "severity": "low"},
    ],
    "Slurry Pump": [
        {"problem": "Throat bush worn through to liner", "root_cause": "High-density slurry at 1.6 SG accelerated wear", "action": "Replaced throat bush and frame plate liner", "parts_used": ["Throat bush", "Frame plate liner"], "severity": "high"},
    ],
    "Submersible Pump": [
        {"problem": "Insulation resistance dropped to 2.5 MΩ", "root_cause": "Cable seal entry compromised, water ingress", "action": "Replaced cable gland, dried motor 2 hrs at 80°C", "parts_used": ["Cable gland 25mm"], "severity": "high"},
    ],
    "AC Motor": [
        {"problem": "Vibration ISO 10816 zone D (10.5 mm/s)", "root_cause": "DE bearing inner race spalling, age 22,000 hrs", "action": "Replaced DE bearing 6313 C3 with shaft polish", "parts_used": ["Bearing 6313 C3"], "severity": "high"},
        {"problem": "Stator overheating, winding 145°C", "root_cause": "Cooling fan damaged from object strike", "action": "Replaced external cooling fan and cowl", "parts_used": ["Motor cooling fan"], "severity": "medium"},
        {"problem": "Insulation resistance 1.8 MΩ at 500V Megger", "root_cause": "Moisture absorption during 2-week shutdown", "action": "Dry-out at 60°C for 8 hrs, IR restored to 50 MΩ", "parts_used": [], "severity": "medium"},
        {"problem": "Terminal box water ingress after rain", "root_cause": "Conduit gland NPT thread sealing failed", "action": "Replaced gland with IP68 type, applied dielectric grease", "parts_used": ["IP68 cable gland"], "severity": "medium"},
        {"problem": "Bearing NDE running at 78°C", "root_cause": "Grease re-lubrication interval exceeded by 4 weeks", "action": "Purged old grease, refilled 30g per IEC schedule", "parts_used": ["Grease NLGI 2"], "severity": "low"},
    ],
    "VFD": [
        {"problem": "Drive tripped F005 OVERCURRENT during accel", "root_cause": "Acceleration ramp too aggressive for inertia", "action": "Extended accel time 5s → 12s, retested under load", "parts_used": [], "severity": "low"},
        {"problem": "Heatsink overtemperature warning at 78°C", "root_cause": "Cooling fan bearings dry, RPM 30% below spec", "action": "Replaced internal cooling fan EBM-Papst 4314", "parts_used": ["VFD cooling fan"], "severity": "medium"},
        {"problem": "Output phase loss fault, motor not running", "root_cause": "U-phase output cable lug loose at motor terminal", "action": "Re-terminated lug to 12 Nm spec, megger-tested", "parts_used": [], "severity": "high"},
        {"problem": "DC bus overvoltage trip on deceleration", "root_cause": "No braking resistor; regen energy unhandled", "action": "Installed 22 kW braking resistor with thermal protection", "parts_used": ["Braking resistor 22 kW"], "severity": "medium"},
        {"problem": "Communication fault to PLC", "root_cause": "Profinet cable shield not bonded at panel entry", "action": "Bonded shield to PE, reseated RJ45", "parts_used": [], "severity": "low"},
    ],
    "Air Compressor": [
        {"problem": "Discharge pressure cycling between 6.0-8.5 barg", "root_cause": "Pressure switch differential too narrow", "action": "Adjusted differential 1.0 → 1.5 bar, stable cycling", "parts_used": [], "severity": "low"},
        {"problem": "Condensate not draining from receiver", "root_cause": "Auto drain valve solenoid stuck closed", "action": "Replaced auto drain valve, added Y-strainer", "parts_used": ["Auto drain valve", "Y-strainer 1/2 inch"], "severity": "low"},
        {"problem": "Oil filter bypass indicator showing red", "root_cause": "Filter loaded after 2200 hrs (rated 2000 hrs)", "action": "Replaced oil filter and oil 60L", "parts_used": ["Oil filter", "Compressor oil 60L"], "severity": "medium"},
        {"problem": "Air leak audible at piping joint", "root_cause": "Threaded joint thread sealant failed", "action": "Disassembled, applied PTFE tape + Loctite 567", "parts_used": ["PTFE tape", "Loctite 567"], "severity": "low"},
        {"problem": "Aftercooler approach temp high (15°C delta)", "root_cause": "Cooling water side fouling", "action": "Cleaned aftercooler tubes, treated cooling water", "parts_used": [], "severity": "medium"},
    ],
    "Reciprocating Compressor": [
        {"problem": "Suction valve plate cracked, capacity 70%", "root_cause": "Liquid carryover damaged valve plate", "action": "Replaced suction valve assembly, added KO drum drain", "parts_used": ["Suction valve assembly"], "severity": "high"},
    ],
    "Chiller": [
        {"problem": "Approach temperature 6°C above design", "root_cause": "Condenser tubes fouled with biofilm", "action": "Mechanical clean tubes with brushes, treated CW system", "parts_used": [], "severity": "medium"},
        {"problem": "Compressor surge during low-load operation", "root_cause": "Hot gas bypass valve not modulating", "action": "Replaced hot gas bypass valve cartridge", "parts_used": ["HGB valve cartridge"], "severity": "high"},
        {"problem": "Refrigerant low alarm R-134a", "root_cause": "Leak at compressor discharge flange", "action": "Replaced flange gasket, charged 8 kg R-134a", "parts_used": ["Flange gasket", "R-134a refrigerant 8 kg"], "severity": "high"},
    ],
    "Cooling Tower": [
        {"problem": "Fan vibration trending upward over 3 weeks", "root_cause": "Fan blade pitch 2° off spec, imbalance", "action": "Re-pitched blades to spec, dynamically balanced", "parts_used": [], "severity": "medium"},
        {"problem": "Drift loss visible from stack", "root_cause": "Drift eliminator panels dislodged after typhoon", "action": "Reinstalled and clipped 12 drift eliminator panels", "parts_used": ["Drift eliminator panels"], "severity": "low"},
    ],
    "Air Handling Unit": [
        {"problem": "Filter pressure drop 250 Pa above clean", "root_cause": "Pre-filter loaded 4 weeks past schedule", "action": "Replaced pre-filter G4 and final filter F7", "parts_used": ["Pre-filter G4", "Final filter F7"], "severity": "low"},
        {"problem": "AHU belt slipping on high static", "root_cause": "Belt stretched, tension below spec", "action": "Replaced V-belt set, re-tensioned to 80 Hz strand", "parts_used": ["V-belt SPB 1700 ×3"], "severity": "low"},
    ],
    "Steam Boiler": [
        {"problem": "Burner not igniting, lockout fault", "root_cause": "Ignition transformer secondary open circuit", "action": "Replaced ignition transformer 6kV", "parts_used": ["Ignition transformer 6kV"], "severity": "high"},
        {"problem": "Water level low alarm during peak demand", "root_cause": "Feedwater pump cavitating, NPSH issue", "action": "Cleaned feed tank breather, increased deaerator level", "parts_used": [], "severity": "high"},
        {"problem": "Stack temperature 280°C (design 220°C)", "root_cause": "Fire-side fouling, scale on fire tubes", "action": "Mechanical fire-side clean, refractory inspection", "parts_used": [], "severity": "medium"},
    ],
    "Heat Exchanger": [
        {"problem": "Plate exchanger pressure drop doubled", "root_cause": "Fouling on hot side from CIP residue", "action": "Disassembled, chemical clean with CIP-100", "parts_used": ["CIP-100 cleaner 25L"], "severity": "medium"},
    ],
    "Belt Conveyor": [
        {"problem": "Belt tracking right 80mm at head pulley", "root_cause": "Self-aligning idler stuck, tail pulley crowned", "action": "Freed idler, lubricated bearings, retracked to centerline", "parts_used": [], "severity": "medium"},
        {"problem": "Spillage at transfer chute T-1", "root_cause": "Skirt rubber worn, gap 25 mm vs 5 mm spec", "action": "Replaced 4m of skirt rubber, adjusted clamps", "parts_used": ["Skirt rubber 4m"], "severity": "low"},
        {"problem": "Drive bearing temperature 85°C", "root_cause": "Pillow block grease NDE side starving", "action": "Re-lubricated, established 4-week regrease schedule", "parts_used": ["Grease NLGI 2"], "severity": "medium"},
    ],
    "Bucket Elevator": [
        {"problem": "Bucket struck inspection door, debris", "root_cause": "Bucket bolt sheared, bucket loose", "action": "Replaced bucket and 4 grade-8 bolts; rotation inspected", "parts_used": ["Bucket BE-250", "Hex bolt M16 grade 8 ×4"], "severity": "high"},
    ],
    "Overhead Crane": [
        {"problem": "Hoist limit switch failed to stop at top", "root_cause": "Limit switch contact bridged, IP rating compromised", "action": "Replaced limit switch with IP67 type", "parts_used": ["Limit switch IP67"], "severity": "high"},
        {"problem": "Wire rope strands broken, 3 wires per lay", "root_cause": "Rope at 8 yrs service, exceeds discard criteria", "action": "Replaced wire rope assembly per ISO 4309", "parts_used": ["Wire rope 12mm 30m"], "severity": "high"},
    ],
    "Forklift": [
        {"problem": "Hydraulic mast lifting slow under load", "root_cause": "Hydraulic filter loaded; oil level low", "action": "Replaced filter, topped up hydraulic oil", "parts_used": ["Hydraulic filter", "ISO VG46 hyd oil 20L"], "severity": "low"},
    ],
    "UPS": [
        {"problem": "Battery cell voltage 1.8V (spec 2.15V)", "root_cause": "Cell sulfated, capacity 60% of nameplate", "action": "Replaced 4 cells in string A, equalized charge", "parts_used": ["Battery cell 2V 200Ah ×4"], "severity": "high"},
        {"problem": "Static bypass active, inverter offline", "root_cause": "Inverter IGBT gate driver fault", "action": "Replaced inverter module per OEM service", "parts_used": ["Inverter module"], "severity": "high"},
    ],
    "Transformer": [
        {"problem": "Buchholz relay alarm activated", "root_cause": "Gas accumulation from minor internal flashover", "action": "Sampled gas (DGA), monitor closely; oil filter", "parts_used": [], "severity": "high"},
    ],
    "Switchgear": [
        {"problem": "Hot spot detected on busbar joint via thermography", "root_cause": "Bolt torque relaxed below 65 Nm spec", "action": "Re-torqued joint to 70 Nm, applied conductive paste", "parts_used": ["NoOx-ID conductive paste"], "severity": "high"},
    ],
    "Dust Collector": [
        {"problem": "Differential pressure 220 mm WC (high alarm)", "root_cause": "Pulse-jet timer set too long; cake bridging", "action": "Reduced pulse interval 30s → 15s, manual clean", "parts_used": [], "severity": "medium"},
        {"problem": "Filter cartridge leaking dust to clean side", "root_cause": "Cartridge media torn at pleats", "action": "Replaced 8 cartridges, inspected gaskets", "parts_used": ["Cartridge filter ×8"], "severity": "medium"},
    ],
    "Bag Filter": [
        {"problem": "Bag broken on row 3, dust emission", "root_cause": "Bag end-of-life at 18 months service", "action": "Replaced 24 bags + cages on row 3", "parts_used": ["Filter bag ×24", "Filter cage ×24"], "severity": "medium"},
    ],
    "Roots Blower": [
        {"problem": "Discharge silencer rattling at full load", "root_cause": "Internal silencer baffle weld cracked", "action": "Welded baffle, balanced rotor assembly", "parts_used": [], "severity": "low"},
    ],
    "Hydraulic Power Unit": [
        {"problem": "Hydraulic oil temp 75°C alarm", "root_cause": "Oil cooler tube fouling, water side scale", "action": "Descaled cooler with citric acid; flow restored", "parts_used": ["Citric acid 10kg"], "severity": "medium"},
    ],
    "Pressure Vessel": [
        {"problem": "PSV lifted at 11.5 barg (set 12.0 barg)", "root_cause": "PSV spring relaxation, due for recertification", "action": "Sent PSV for shop test/cert; installed spare", "parts_used": ["PSV spare assembly"], "severity": "medium"},
    ],
    "CNC Lathe": [
        {"problem": "Spindle vibration trend up over 1 month", "root_cause": "Spindle bearing preload loss", "action": "Adjusted preload per OEM, vibration restored", "parts_used": [], "severity": "medium"},
    ],
    "CNC Mill": [
        {"problem": "Coolant pump tripping thermal overload", "root_cause": "Impeller jammed by chip ingestion", "action": "Cleared chip, replaced suction strainer", "parts_used": ["Suction strainer 50mm"], "severity": "low"},
    ],
    "Press Brake": [
        {"problem": "Hydraulic ram drift 0.3 mm over hold time", "root_cause": "Counterbalance valve seal worn", "action": "Replaced seal kit, tested no drift over 5 min hold", "parts_used": ["Counterbalance valve seal kit"], "severity": "medium"},
    ],
    "Welder": [
        {"problem": "Output current unstable, weld quality poor", "root_cause": "Carbon brushes 80% worn", "action": "Replaced 4 carbon brushes, cleaned commutator", "parts_used": ["Carbon brush ×4"], "severity": "low"},
    ],
    "Flow Meter": [
        {"problem": "Reading drifted +8% over month", "root_cause": "Coating buildup on electrodes", "action": "Cleaned electrodes, in-situ verification with master", "parts_used": [], "severity": "low"},
    ],
    "Pressure Transmitter": [
        {"problem": "Reading frozen at last value", "root_cause": "HART comm failure, terminals corroded", "action": "Cleaned terminals, retorque, tested HART comm", "parts_used": [], "severity": "low"},
    ],
    "Temperature Transmitter": [
        {"problem": "Reading -40°C (sensor open)", "root_cause": "Pt100 lead wire broken at thermowell", "action": "Replaced Pt100 sensor", "parts_used": ["Pt100 sensor"], "severity": "low"},
    ],
    "PLC": [
        {"problem": "CPU stop mode, fault LED on", "root_cause": "Backup battery depleted, RAM lost", "action": "Replaced battery, reloaded program from project file", "parts_used": ["PLC backup battery"], "severity": "high"},
    ],
}


def get_faults_for_category(category: str):
    """Returns the fault list for a category, or generic list if unknown."""
    return FAULTS_BY_CATEGORY.get(category, FAULTS_BY_CATEGORY.get("AC Motor", []))
