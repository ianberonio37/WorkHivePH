"""Realistic Philippine industrial equipment catalog with nameplate data.

Each entry is one ARCHETYPE. The seeder will instantiate multiple copies
across hives with different tag IDs (e.g., GEN-01, GEN-02, P-301).
"""

EQUIPMENT_CATALOG = [
    # Power generation
    {"category": "Genset", "discipline": "Mechanical", "make": "Caterpillar", "model": "3516B", "spec": "1825 kVA / 1460 kW", "tag_prefix": "GEN"},
    {"category": "Genset", "discipline": "Mechanical", "make": "Cummins", "model": "QSK60-G4", "spec": "2000 kVA / 1600 kW", "tag_prefix": "GEN"},
    {"category": "Genset", "discipline": "Mechanical", "make": "Perkins", "model": "4012-46TWG2A", "spec": "1500 kVA / 1200 kW", "tag_prefix": "GEN"},
    {"category": "Genset", "discipline": "Mechanical", "make": "MTU", "model": "16V4000 G83L", "spec": "2500 kVA", "tag_prefix": "GEN"},

    # Pumps
    {"category": "Centrifugal Pump", "discipline": "Mechanical", "make": "Grundfos", "model": "CR 95-3-2", "spec": "75 m³/h @ 60 m TDH", "tag_prefix": "P"},
    {"category": "Centrifugal Pump", "discipline": "Mechanical", "make": "KSB", "model": "Etanorm 100-250", "spec": "120 m³/h @ 50 m TDH", "tag_prefix": "P"},
    {"category": "Process Pump", "discipline": "Mechanical", "make": "Goulds", "model": "3196 i-FRAME", "spec": "180 m³/h @ 75 m TDH", "tag_prefix": "P"},
    {"category": "Slurry Pump", "discipline": "Mechanical", "make": "Warman", "model": "AH 6/4", "spec": "150 m³/h slurry", "tag_prefix": "SP"},
    {"category": "Submersible Pump", "discipline": "Mechanical", "make": "Flygt", "model": "NP 3171", "spec": "60 m³/h sewage", "tag_prefix": "SUB"},

    # Motors
    {"category": "AC Motor", "discipline": "Electrical", "make": "ABB", "model": "M3BP 250 SMA 4", "spec": "75 kW / 4 pole / 380V", "tag_prefix": "M"},
    {"category": "AC Motor", "discipline": "Electrical", "make": "Siemens", "model": "Simotics SD 200L", "spec": "30 kW / 4 pole / 380V", "tag_prefix": "M"},
    {"category": "AC Motor", "discipline": "Electrical", "make": "WEG", "model": "W22 IE3", "spec": "45 kW / 4 pole / 380V", "tag_prefix": "M"},
    {"category": "AC Motor", "discipline": "Electrical", "make": "Toshiba", "model": "TIK-FK", "spec": "110 kW / 4 pole / 460V", "tag_prefix": "M"},

    # VFDs
    {"category": "VFD", "discipline": "Electrical", "make": "ABB", "model": "ACS580-01", "spec": "75 kW / 380V", "tag_prefix": "VFD"},
    {"category": "VFD", "discipline": "Electrical", "make": "Siemens", "model": "Sinamics G120P", "spec": "45 kW / 380V", "tag_prefix": "VFD"},
    {"category": "VFD", "discipline": "Electrical", "make": "Allen-Bradley", "model": "PowerFlex 753", "spec": "110 kW / 460V", "tag_prefix": "VFD"},
    {"category": "VFD", "discipline": "Electrical", "make": "Yaskawa", "model": "A1000", "spec": "55 kW / 380V", "tag_prefix": "VFD"},

    # Compressors
    {"category": "Air Compressor", "discipline": "Mechanical", "make": "Atlas Copco", "model": "GA75+ VSD", "spec": "75 kW / 13 m³/min @ 7.5 barg", "tag_prefix": "AC"},
    {"category": "Air Compressor", "discipline": "Mechanical", "make": "Kaeser", "model": "CSD 105", "spec": "55 kW / 9.5 m³/min", "tag_prefix": "AC"},
    {"category": "Air Compressor", "discipline": "Mechanical", "make": "Ingersoll Rand", "model": "R-Series RS90n", "spec": "90 kW / 16 m³/min", "tag_prefix": "AC"},
    {"category": "Reciprocating Compressor", "discipline": "Mechanical", "make": "Burckhardt", "model": "Laby", "spec": "200 kW / 1500 Nm³/h", "tag_prefix": "RC"},

    # HVAC
    {"category": "Chiller", "discipline": "Mechanical", "make": "Carrier", "model": "30XW 1212", "spec": "1200 TR / R-134a", "tag_prefix": "CH"},
    {"category": "Chiller", "discipline": "Mechanical", "make": "Trane", "model": "CVHE CenTraVac", "spec": "1500 TR / R-1233zd", "tag_prefix": "CH"},
    {"category": "Chiller", "discipline": "Mechanical", "make": "Daikin", "model": "VRV IV Q-Series", "spec": "60 HP / R-410A", "tag_prefix": "VRV"},
    {"category": "Cooling Tower", "discipline": "Mechanical", "make": "Marley", "model": "NC8410", "spec": "2400 m³/h water", "tag_prefix": "CT"},
    {"category": "Air Handling Unit", "discipline": "Mechanical", "make": "Carrier", "model": "39M", "spec": "20000 CFM", "tag_prefix": "AHU"},

    # Boilers / steam
    {"category": "Steam Boiler", "discipline": "Mechanical", "make": "Cleaver-Brooks", "model": "CB-700-200", "spec": "200 BHP / 7 barg", "tag_prefix": "BLR"},
    {"category": "Steam Boiler", "discipline": "Mechanical", "make": "Miura", "model": "LX-300", "spec": "300 BHP / 10 barg", "tag_prefix": "BLR"},
    {"category": "Heat Exchanger", "discipline": "Mechanical", "make": "Alfa Laval", "model": "M10-BWFG", "spec": "Plate / 250 kW", "tag_prefix": "HX"},

    # Material handling
    {"category": "Belt Conveyor", "discipline": "Mechanical", "make": "Siemens", "model": "Belt drive 250 kW", "spec": "120 m × 800 mm belt", "tag_prefix": "BC"},
    {"category": "Bucket Elevator", "discipline": "Mechanical", "make": "Beumer", "model": "BE 250", "spec": "250 t/h cement", "tag_prefix": "BE"},
    {"category": "Overhead Crane", "discipline": "Mechanical", "make": "Konecranes", "model": "CXT NEO 10t", "spec": "10 ton SWL × 25 m span", "tag_prefix": "CR"},
    {"category": "Forklift", "discipline": "Mechanical", "make": "Toyota", "model": "8FG25", "spec": "2.5 ton LPG", "tag_prefix": "FL"},

    # UPS / power conditioning
    {"category": "UPS", "discipline": "Electrical", "make": "APC", "model": "Symmetra PX 250", "spec": "250 kVA / 480V", "tag_prefix": "UPS"},
    {"category": "UPS", "discipline": "Electrical", "make": "Eaton", "model": "9395", "spec": "825 kVA / 480V", "tag_prefix": "UPS"},
    {"category": "Transformer", "discipline": "Electrical", "make": "Schneider", "model": "Trihal Cast Resin", "spec": "2000 kVA / 13.8kV/480V", "tag_prefix": "TX"},
    {"category": "Switchgear", "discipline": "Electrical", "make": "ABB", "model": "UniGear ZS1", "spec": "13.8 kV / 1250A", "tag_prefix": "SWG"},

    # Process / utility
    {"category": "Dust Collector", "discipline": "Mechanical", "make": "Donaldson Torit", "model": "DFO 4-32", "spec": "32 cartridges / 50000 m³/h", "tag_prefix": "DC"},
    {"category": "Bag Filter", "discipline": "Mechanical", "make": "Donaldson", "model": "Pulse-Jet PJBH", "spec": "120 bags", "tag_prefix": "BF"},
    {"category": "Roots Blower", "discipline": "Mechanical", "make": "Howden", "model": "RBS-450", "spec": "30 kW / 2400 m³/h", "tag_prefix": "BLW"},
    {"category": "Hydraulic Power Unit", "discipline": "Mechanical", "make": "Bosch Rexroth", "model": "ABPAC", "spec": "37 kW / 200 bar", "tag_prefix": "HPU"},
    {"category": "Pressure Vessel", "discipline": "Mechanical", "make": "Local Fab", "model": "ASME Sec VIII", "spec": "5 m³ / 12 barg", "tag_prefix": "PV"},

    # Manufacturing equipment
    {"category": "CNC Lathe", "discipline": "Mechanical", "make": "Mazak", "model": "QT-15N", "spec": "ø250 × 500 mm", "tag_prefix": "LATH"},
    {"category": "CNC Mill", "discipline": "Mechanical", "make": "Haas", "model": "VF-3", "spec": "1016 × 508 × 635 mm travel", "tag_prefix": "MILL"},
    {"category": "Press Brake", "discipline": "Mechanical", "make": "Amada", "model": "HFE 80-25", "spec": "80 ton × 2500 mm", "tag_prefix": "PB"},
    {"category": "Welder", "discipline": "Electrical", "make": "Lincoln Electric", "model": "Idealarc DC-1500", "spec": "1500A DC", "tag_prefix": "WLD"},

    # Instrumentation
    {"category": "Flow Meter", "discipline": "Instrumentation", "make": "Endress+Hauser", "model": "Promag 50W", "spec": "DN 100 / 4-20 mA", "tag_prefix": "FT"},
    {"category": "Pressure Transmitter", "discipline": "Instrumentation", "make": "Rosemount", "model": "3051C", "spec": "0-10 barg / HART", "tag_prefix": "PT"},
    {"category": "Temperature Transmitter", "discipline": "Instrumentation", "make": "Yokogawa", "model": "YTA610", "spec": "Pt100 / 0-200°C", "tag_prefix": "TT"},
    {"category": "PLC", "discipline": "Instrumentation", "make": "Siemens", "model": "S7-1500 CPU 1516", "spec": "Profinet IO", "tag_prefix": "PLC"},
]
