"""CMMS field schemas, status mappings, and Philippine industry profiles.

Defines the field names each CMMS system uses and how they map to WorkHive.
Pure constants -- no logic here.
"""

# ---------------------------------------------------------------------------
# Dataset size presets
# ---------------------------------------------------------------------------

DATASET_SIZES = {
    "small":  {"assets": 10,  "work_orders":   50, "pm_schedules":  5, "parts": 15},
    "medium": {"assets": 50,  "work_orders":  500, "pm_schedules": 20, "parts": 50},
    "large":  {"assets": 200, "work_orders": 5000, "pm_schedules": 80, "parts": 200},
}

HISTORY_DAYS = {
    "small":  90,
    "medium": 365,
    "large":  730,
}


# ---------------------------------------------------------------------------
# SAP PM -- field name definitions and code mappings
# ---------------------------------------------------------------------------

SAP_WO_FIELDS = [
    "AUFNR",     # Work order number (12-digit, zero-padded)
    "AUART",     # Order type (PM01/PM02/PM03)
    "LTXT",      # Long text description
    "ISTAT",     # System status code
    "ARBEI",     # Actual work hours
    "ERDAT",     # Creation date (YYYY-MM-DD)
    "AEDAT",     # Last changed date
    "RUCKMDAT",  # Confirmation/completion date
    "EQUNR",     # Equipment number
    "KOSTL",     # Cost center
    "PRIOK",     # Priority (1=Very High, 2=High, 3=Medium, 4=Low)
    "ARBPL",     # Work center
    "QMNUM",     # Quality notification (breakdown source)
]

SAP_ASSET_FIELDS = [
    "EQUNR",    # Equipment number (tag ID)
    "EQKTX",    # Description
    "EQART",    # Equipment category code
    "ILOAN",    # Functional location (area)
    "INBDT",    # Installation date
    "HERST",    # Manufacturer
    "TYPBZ",    # Model / type designation
    "TIDNR",    # Serial number
    "KOSTL",    # Cost center
    "WERKS",    # Plant code
]

SAP_PM_FIELDS = [
    "PLAN_NO",      # Maintenance plan number
    "EQUNR",        # Equipment
    "CYCLE_DAYS",   # Interval in days
    "LAST_DONE",    # Last completion date
    "NEXT_DUE",     # Next due date
    "TASK_DESC",    # Task description
    "TASK_LIST",    # Task list reference code
    "IWERK",        # Maintenance plant
    "STATUS",       # ACTIVE / INACTIVE
]

SAP_INVENTORY_FIELDS = [
    "MATNR",    # Material number (10-digit, zero-padded)
    "MAKTX",    # Material description
    "MEINS",    # Base unit of measure (EA, L, KG, M, SET)
    "MENGE",    # Unrestricted stock quantity
    "MINBE",    # Reorder point
    "EISBE",    # Safety stock
    "WERKS",    # Plant
    "LGORT",    # Storage location
]

# SAP system status codes -> WorkHive status
SAP_ISTAT_TO_STATUS = {
    "I0001": "Open",        # Created
    "I0002": "Open",        # Released
    "I0008": "Open",        # Confirmed (partial)
    "I0045": "Closed",      # Technically complete (TECO)
    "I0076": "Cancelled",   # Deleted
}

# SAP order type -> WorkHive maintenance_type
SAP_AUART_TO_TYPE = {
    "PM01": "Preventive Maintenance",
    "PM02": "Breakdown / Corrective",
    "PM03": "Breakdown / Corrective",
}

# SAP priority -> WorkHive category label
SAP_PRIOK_TO_PRIORITY = {
    "1": "critical",
    "2": "high",
    "3": "medium",
    "4": "low",
}

# Closed statuses (RUCKMDAT will be populated for these)
SAP_CLOSED_STATUSES = {"I0045", "I0076"}


# ---------------------------------------------------------------------------
# IBM Maximo -- field name definitions and code mappings
# ---------------------------------------------------------------------------

MAXIMO_WO_FIELDS = [
    "WONUM",        # Work order number (e.g., WO-00001)
    "DESCRIPTION",  # Description
    "STATUS",       # WAPPR / APPR / INPRG / COMP / CLOSE / CAN
    "WORKTYPE",     # PM / CM / EM
    "ACTLABHRS",    # Actual labor hours
    "REPORTDATE",   # Report/creation date (ISO datetime)
    "TARGSTARTDATE",# Target start date
    "ACTFINISH",    # Actual finish date
    "ASSETNUM",     # Asset number
    "LOCATION",     # Location code
    "PRIORITY",     # 1-4
    "GLACCOUNT",    # GL account / cost center
]

MAXIMO_ASSET_FIELDS = [
    "ASSETNUM",     # Asset number (tag ID)
    "DESCRIPTION",  # Description
    "ASSETTYPE",    # Asset type
    "LOCATION",     # Location
    "INSTALLDATE",  # Installation date
    "MANUFACTURER", # Manufacturer
    "MODEL",        # Model
    "SERIALNUM",    # Serial number
    "SITEID",       # Site identifier
]

MAXIMO_PM_FIELDS = [
    "PMNUM",        # PM number
    "ASSETNUM",     # Asset
    "FREQUENCY",    # Frequency value
    "FREQUNIT",     # DAYS / WEEKS / MONTHS / YEARS
    "LASTCOMPDATE", # Last completion date
    "NEXTDUEDATE",  # Next due date
    "DESCRIPTION",  # Task description
    "SITEID",       # Site
    "STATUS",       # ACTIVE / INACTIVE
]

MAXIMO_INVENTORY_FIELDS = [
    "ITEMNUM",      # Item number
    "DESCRIPTION",  # Description
    "ORDERUNIT",    # Order unit (EACH, L, KG, M)
    "CURBAL",       # Current balance
    "REORDER",      # Reorder point
    "SITEID",       # Site
    "LOCATION",     # Storeroom location
]

MAXIMO_STATUS_TO_STATUS = {
    "WAPPR": "Open",
    "APPR":  "Open",
    "INPRG": "Open",
    "COMP":  "Closed",
    "CLOSE": "Closed",
    "CAN":   "Cancelled",
}

MAXIMO_WORKTYPE_TO_TYPE = {
    "PM": "Preventive Maintenance",
    "CM": "Breakdown / Corrective",
    "EM": "Breakdown / Corrective",
}


# ---------------------------------------------------------------------------
# Generic REST -- flat field names
# ---------------------------------------------------------------------------

GENERIC_WO_FIELDS = [
    "work_order_no",    # String identifier
    "description",      # Description
    "type",             # preventive / corrective / emergency
    "status",           # open / closed / cancelled
    "actual_hours",     # Float
    "created_date",     # ISO datetime
    "closed_date",      # ISO datetime or null
    "asset_tag",        # Asset identifier
    "location",         # Location string
    "priority",         # low / medium / high / critical
    "reported_by",      # Worker name
]

GENERIC_ASSET_FIELDS = [
    "asset_tag",        # Identifier
    "name",             # Description
    "category",         # Equipment category
    "location",         # Location
    "installed_date",   # ISO date
    "manufacturer",     # Manufacturer
    "model",            # Model
    "serial_no",        # Serial number
]

GENERIC_PM_FIELDS = [
    "pm_id",            # Identifier
    "asset_tag",        # Asset
    "interval_days",    # Maintenance interval
    "last_done",        # ISO date
    "next_due",         # ISO date
    "task",             # Description
    "status",           # active / inactive
]

GENERIC_INVENTORY_FIELDS = [
    "part_number",      # Identifier
    "description",      # Description
    "unit",             # each / litre / kg / metre / set
    "qty_on_hand",      # Quantity
    "reorder_point",    # Reorder point
    "location",         # Storage location
]

GENERIC_TYPE_TO_TYPE = {
    "preventive": "Preventive Maintenance",
    "corrective":  "Breakdown / Corrective",
    "emergency":   "Breakdown / Corrective",
}

GENERIC_STATUS_TO_STATUS = {
    "open":      "Open",
    "closed":    "Closed",
    "cancelled": "Cancelled",
}


# ---------------------------------------------------------------------------
# Philippine industry profiles
# ---------------------------------------------------------------------------

INDUSTRY_PROFILES = {
    "food_processing": {
        "label": "Food Processing",
        "equipment_categories": [
            "Centrifugal Pump", "Air Compressor", "Chiller",
            "Belt Conveyor", "Steam Boiler", "Heat Exchanger",
            "Air Handling Unit",
        ],
        "locations": [
            "Production Hall A", "Production Hall B", "CIP Room",
            "Cold Storage 1", "Cold Storage 2", "Boiler Room",
            "Utility Room", "Receiving Area", "Packaging Line",
        ],
        "cost_center": "CC-FP-MAINT",
        "plant_code":  "PH01",
        "site_id":     "FPPHL01",
        "company":     "Pacific Food Industries Corp.",
    },
    "cement": {
        "label": "Cement / Mining",
        "equipment_categories": [
            "Belt Conveyor", "Bucket Elevator", "Air Compressor",
            "Dust Collector", "Bag Filter", "Roots Blower",
            "AC Motor",
        ],
        "locations": [
            "Quarry", "Raw Mill", "Kiln Area", "Cement Mill",
            "Packing Plant", "Power House", "Crusher Station",
            "Homogenizing Silo",
        ],
        "cost_center": "CC-CEM-MAINT",
        "plant_code":  "PH02",
        "site_id":     "CEMPHL01",
        "company":     "Southern Mindanao Cement Corp.",
    },
    "power": {
        "label": "Power Generation",
        "equipment_categories": [
            "Genset", "Transformer", "Switchgear",
            "Cooling Tower", "AC Motor", "UPS",
        ],
        "locations": [
            "Engine Hall A", "Engine Hall B", "Switchyard",
            "Control Room", "Cooling Tower Bay",
            "Auxiliary Building", "Fuel Farm",
        ],
        "cost_center": "CC-PWR-MAINT",
        "plant_code":  "PH03",
        "site_id":     "PWRPHL01",
        "company":     "Visayas Power Generation Inc.",
    },
    "oil_gas": {
        "label": "Oil & Gas / Petrochemical",
        "equipment_categories": [
            "Reciprocating Compressor", "Process Pump",
            "Pressure Vessel", "Heat Exchanger",
            "Flow Meter", "Pressure Transmitter",
        ],
        "locations": [
            "Process Area A", "Process Area B", "Tank Farm",
            "Compressor Station", "Flare Stack Area",
            "Control Building", "Offloading Jetty",
        ],
        "cost_center": "CC-OG-MAINT",
        "plant_code":  "PH04",
        "site_id":     "OGPHL01",
        "company":     "Batangas Petrochem Terminal Inc.",
    },
    "manufacturing": {
        "label": "Discrete Manufacturing",
        "equipment_categories": [
            "CNC Lathe", "CNC Mill", "Press Brake",
            "AC Motor", "VFD", "Hydraulic Power Unit",
        ],
        "locations": [
            "Machine Shop A", "Machine Shop B",
            "Assembly Line 1", "Assembly Line 2",
            "Heat Treatment Bay", "Maintenance Workshop",
            "QC Lab",
        ],
        "cost_center": "CC-MFG-MAINT",
        "plant_code":  "PH05",
        "site_id":     "MFGPHL01",
        "company":     "Laguna Precision Manufacturing Corp.",
    },
}

# Default when no industry is specified
DEFAULT_INDUSTRY = "food_processing"


# ---------------------------------------------------------------------------
# PM task templates per equipment category (interval in days)
# ---------------------------------------------------------------------------

PM_TASKS_BY_CATEGORY = {
    "Centrifugal Pump": [
        ("Bearing lubrication and inspection",            30),
        ("Mechanical seal inspection and gland check",    90),
        ("Coupling alignment check",                     180),
        ("Full overhaul -- impeller, wear rings, shaft", 365),
    ],
    "Process Pump": [
        ("Bearing and seal inspection",       30),
        ("Gasket and flange integrity check", 90),
        ("Performance curve verification",   365),
    ],
    "Genset": [
        ("Engine oil and filter change",             90),
        ("Air filter and fuel filter service",       90),
        ("Battery load test and terminal clean",    180),
        ("Coolant flush and thermostat inspection", 365),
        ("Full 1000-hour service",                  365),
    ],
    "Air Compressor": [
        ("Oil filter and separator element change",  90),
        ("Air intake filter service",                90),
        ("Belt tension and pulley inspection",      180),
        ("Valve plate inspection -- reciprocating", 180),
        ("Full compressor overhaul",               3650),
    ],
    "AC Motor": [
        ("Bearing lubrication per IEC schedule",       90),
        ("Insulation resistance test (Megger 500V)",  365),
        ("Vibration baseline and spectrum analysis",  180),
        ("Terminal box and cable gland inspection",   365),
    ],
    "VFD": [
        ("Heatsink and fan dust removal",  90),
        ("Control card and bus bar torque check", 365),
        ("Parameter backup and firmware log",    180),
    ],
    "Chiller": [
        ("Condenser tube cleaning (mechanical)",  365),
        ("Refrigerant charge and leak check",     180),
        ("Compressor oil sample and analysis",    365),
        ("Hot gas bypass valve functional test",  180),
    ],
    "Cooling Tower": [
        ("Drift eliminator inspection and clean",  90),
        ("Fan blade pitch and balance check",     180),
        ("Water treatment chemistry sample",       30),
    ],
    "Steam Boiler": [
        ("Burner calibration and combustion test",    90),
        ("Safety valve lift test",                   180),
        ("Feedwater treatment and blowdown",          30),
        ("Annual inspection -- fire-side and shell", 365),
    ],
    "Transformer": [
        ("Oil sample -- dissolved gas analysis",   365),
        ("Cooling fan and radiator inspection",    180),
        ("Tap changer inspection",                 365),
    ],
    "Belt Conveyor": [
        ("Belt tension and tracking adjustment",   30),
        ("Idler roller inspection and greasing",   90),
        ("Drive sprocket and coupling check",     180),
    ],
    "Dust Collector": [
        ("Filter cartridge differential pressure check", 30),
        ("Pulse jet solenoid valve test",                90),
        ("Full cartridge replacement",                  365),
    ],
    "default": [
        ("Routine inspection and lubrication",   90),
        ("Functional test and parameter check", 180),
        ("Overhaul and parts replacement",      365),
    ],
}


# ---------------------------------------------------------------------------
# Unit of measure mapping (parts)
# ---------------------------------------------------------------------------

PART_UNITS = {
    "filter":       "EA",
    "bearing":      "EA",
    "seal":         "EA",
    "gasket":       "EA",
    "belt":         "EA",
    "valve":        "EA",
    "relay":        "EA",
    "fan":          "EA",
    "oil":          "L",
    "grease":       "KG",
    "coolant":      "L",
    "refrigerant":  "KG",
    "tape":         "EA",
    "cable":        "M",
    "panel":        "EA",
    "default":      "EA",
}


def unit_for_part(description: str) -> str:
    desc_lower = description.lower()
    for keyword, unit in PART_UNITS.items():
        if keyword in desc_lower:
            return unit
    return PART_UNITS["default"]
