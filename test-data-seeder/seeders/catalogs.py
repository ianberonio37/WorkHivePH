"""Auto-heal catalog tables that DB triggers FK into.

These tables are populated by migration INSERT blocks (with ON CONFLICT DO
NOTHING), but if a Reset run accidentally wipes them, no other seeder will
restore the rows. The next user action that fires a trigger writing to
worker_achievements (PM completion, logbook close, etc.) then 23503-fails on
the FK to achievement_definitions.

This seeder runs at the start of seed_everything to guarantee both catalogs
are populated before any feature seeder triggers a write.

Source of truth still lives in the migrations:
  - supabase/migrations/20260508000002_achievements.sql
  - supabase/migrations/20260428000006_equipment_reading_templates.sql
If you change the catalog rows in either migration, mirror the change here.
"""


ACHIEVEMENT_DEFINITIONS = [
    {"id": "wrench_chronicle",  "name": "Wrench Chronicle",   "description": "Log jobs, close them with detail, and build a record of your craft.",          "icon": "\U0001F527", "domain": "logbook",     "pillar": "competence"},
    {"id": "uptime_guardian",   "name": "Uptime Guardian",    "description": "Complete PM tasks on time and keep machines running.",                          "icon": "\U0001F6E1️", "domain": "pm",          "pillar": "competence"},
    {"id": "parts_warden",      "name": "Parts Warden",       "description": "Manage inventory, restock proactively, and link parts to jobs.",                "icon": "\U0001F4E6", "domain": "inventory",   "pillar": "competence"},
    {"id": "blueprint_master",  "name": "Blueprint Master",   "description": "Run engineering calculations and generate design reports.",                    "icon": "\U0001F4D0", "domain": "engineering", "pillar": "competence"},
    {"id": "failure_hunter",    "name": "Failure Hunter",     "description": "Close breakdown jobs with root causes. Understand failure, prevent repeats.",   "icon": "\U0001F3AF", "domain": "diagnostic",  "pillar": "competence"},
    {"id": "safety_sentinel",   "name": "Safety Sentinel",    "description": "Log safety events, flag hazards, and champion safe work practices.",            "icon": "⚠️", "domain": "safety",      "pillar": "autonomy"},
    {"id": "skill_climber",     "name": "Skill Climber",      "description": "Complete skill assessments and unlock competency badges.",                      "icon": "\U0001F4C8", "domain": "skill",       "pillar": "autonomy"},
    {"id": "knowledge_forger",  "name": "Knowledge Forger",   "description": "Write detailed entries and submit shift handover reports.",                    "icon": "\U0001F4DD", "domain": "knowledge",   "pillar": "autonomy"},
    {"id": "hive_architect",    "name": "Hive Architect",     "description": "Build and sustain your team. Invite members and approve submissions.",          "icon": "\U0001F3D7️", "domain": "team",        "pillar": "relatedness"},
    {"id": "voice_of_hive",     "name": "Voice of the Hive",  "description": "Post, reply, and contribute to your hive community.",                           "icon": "\U0001F5E3️", "domain": "community",   "pillar": "relatedness"},
    {"id": "shift_keeper",      "name": "Shift Keeper",       "description": "Submit shift handover reports on time with no gaps.",                           "icon": "\U0001F550", "domain": "shift",       "pillar": "relatedness"},
    {"id": "iron_worker",       "name": "Iron Worker",        "description": "Legendary composite achievement. Reach Level 50 in any 5 domains.",             "icon": "⚙️", "domain": "composite",   "pillar": "legendary"},
]


EQUIPMENT_READING_TEMPLATES = [
    {"category": "Mechanical",      "reading_key": "temperature_c", "label": "Temperature", "unit": "°C",   "placeholder": "85",   "sort_order": 1},
    {"category": "Mechanical",      "reading_key": "vibration_mms", "label": "Vibration",   "unit": "mm/s",      "placeholder": "4.5",  "sort_order": 2},
    {"category": "Mechanical",      "reading_key": "pressure_bar",  "label": "Pressure",    "unit": "bar",       "placeholder": "4.2",  "sort_order": 3},
    {"category": "Electrical",      "reading_key": "voltage_v",     "label": "Voltage",     "unit": "V",         "placeholder": "220",  "sort_order": 1},
    {"category": "Electrical",      "reading_key": "current_a",     "label": "Current",     "unit": "A",         "placeholder": "15",   "sort_order": 2},
    {"category": "Electrical",      "reading_key": "temperature_c", "label": "Temperature", "unit": "°C",   "placeholder": "65",   "sort_order": 3},
    {"category": "Hydraulic",       "reading_key": "pressure_bar",  "label": "Pressure",    "unit": "bar",       "placeholder": "180",  "sort_order": 1},
    {"category": "Hydraulic",       "reading_key": "flow_lpm",      "label": "Flow",        "unit": "L/min",     "placeholder": "45",   "sort_order": 2},
    {"category": "Hydraulic",       "reading_key": "temperature_c", "label": "Oil Temp",    "unit": "°C",   "placeholder": "55",   "sort_order": 3},
    {"category": "Pneumatic",       "reading_key": "pressure_bar",  "label": "Pressure",    "unit": "bar",       "placeholder": "6.5",  "sort_order": 1},
    {"category": "Pneumatic",       "reading_key": "temperature_c", "label": "Temperature", "unit": "°C",   "placeholder": "40",   "sort_order": 2},
    {"category": "Instrumentation", "reading_key": "signal_ma",     "label": "Signal",      "unit": "mA",        "placeholder": "12",   "sort_order": 1},
    {"category": "Instrumentation", "reading_key": "temperature_c", "label": "Temperature", "unit": "°C",   "placeholder": "35",   "sort_order": 2},
    {"category": "Lubrication",     "reading_key": "temperature_c", "label": "Oil Temp",    "unit": "°C",   "placeholder": "60",   "sort_order": 1},
    {"category": "Lubrication",     "reading_key": "pressure_bar",  "label": "Pressure",    "unit": "bar",       "placeholder": "3.5",  "sort_order": 2},
]


def seed_catalogs(client, log):
    """Idempotent upsert of catalog tables. Safe to run on every Seed Everything."""
    log("Ensuring catalog tables are populated...")

    client.table("achievement_definitions").upsert(
        ACHIEVEMENT_DEFINITIONS,
        on_conflict="id",
    ).execute()
    log(f"  upserted {len(ACHIEVEMENT_DEFINITIONS)} achievement_definitions")

    client.table("equipment_reading_templates").upsert(
        EQUIPMENT_READING_TEMPLATES,
        on_conflict="category,reading_key",
    ).execute()
    log(f"  upserted {len(EQUIPMENT_READING_TEMPLATES)} equipment_reading_templates")

    return {
        "achievement_definitions_count": len(ACHIEVEMENT_DEFINITIONS),
        "equipment_reading_templates_count": len(EQUIPMENT_READING_TEMPLATES),
    }
