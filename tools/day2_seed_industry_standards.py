#!/usr/bin/env python3
"""
Day 2: Seed industry_standards table + knowledge_base chunks.

Two-phase approach:
1. METADATA SEED: All 14 major industrial standards (ISO/SAE/ASHRAE/IEC/NFPA/NIST)
   - Public domain summaries from Wikipedia + standards body abstracts
   - Mapped to your 53 engineering calculations + analytics KPIs
   - Goes into industry_standards table

2. FULL-TEXT SEED: PDFs downloaded by day2_free_standards_download.py
   - Submitted to Doc Intelligence for text extraction
   - Chunked into knowledge_base (300-word chunks for RAG)

Output: supabase/seed/day2_industry_standards.sql
"""

import os
import sys
import io
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load environment
env_path = Path(__file__).parent.parent / ".env.azure"
load_dotenv(env_path)

ENDPOINT = os.getenv("AZURE_DOC_INTELLIGENCE_ENDPOINT")
API_KEY = os.getenv("AZURE_DOC_INTELLIGENCE_KEY")

# ============================================================================
# METADATA SEED: 14 Major Industrial Standards (Public Domain Summaries)
# ============================================================================

STANDARDS_METADATA = [
    # === RELIABILITY & MAINTENANCE ===
    {
        "code": "ISO 14224:2016",
        "title": "Petroleum, petrochemical and natural gas industries -- Collection and exchange of reliability and maintenance data for equipment",
        "discipline": "reliability",
        "category": "equipment_taxonomy",
        "applicability": ["mechanical", "electrical", "HVAC"],
        "key_concepts": [
            "Equipment taxonomy (9 hierarchical levels)",
            "Failure modes and mechanisms (15 standard codes)",
            "Maintenance task classification",
            "Reliability data collection format"
        ],
        "calc_links": ["MTBF", "MTTR", "availability"],
        "summary": "ISO 14224 provides a uniform basis for collecting reliability and maintenance (RM) data in computerized systems. Defines standard 9-level equipment taxonomy and 15 failure mode codes used globally for benchmarking equipment performance."
    },
    {
        "code": "ISO 13381-1:2015",
        "title": "Condition monitoring and diagnostics of machines -- Prognostics -- Part 1: General guidelines",
        "discipline": "predictive_maintenance",
        "category": "prognostics",
        "applicability": ["mechanical", "electrical"],
        "key_concepts": [
            "Failure prognosis methodology",
            "Remaining useful life (RUL) prediction",
            "Time-to-failure forecasting",
            "Condition monitoring integration"
        ],
        "calc_links": ["MTBF_forecast", "RUL", "failure_prediction"],
        "summary": "Provides general guidelines for prognostics in machine condition monitoring. Defines the framework for predicting remaining useful life and time to failure based on monitored degradation parameters."
    },
    {
        "code": "SAE JA1011:2009",
        "title": "Evaluation Criteria for Reliability-Centered Maintenance (RCM) Processes",
        "discipline": "reliability",
        "category": "RCM",
        "applicability": ["all"],
        "key_concepts": [
            "7-question RCM framework",
            "Failure mode and effects analysis (FMEA)",
            "Task selection logic tree",
            "Hidden vs evident failure classification"
        ],
        "calc_links": ["criticality", "FMEA_score"],
        "summary": "SAE JA1011 defines the minimum criteria that any process must meet to be called RCM. Mandates the 7 RCM questions and provides framework for selecting between predictive, preventive, and corrective tasks."
    },
    {
        "code": "SAE JA1012:2002",
        "title": "A Guide to the Reliability-Centered Maintenance (RCM) Standard",
        "discipline": "reliability",
        "category": "RCM",
        "applicability": ["all"],
        "key_concepts": [
            "RCM implementation guide",
            "Decision logic for maintenance tasks",
            "Default actions framework",
            "Run-to-failure justification"
        ],
        "calc_links": ["RCM_decision", "task_selection"],
        "summary": "Companion guide to JA1011. Provides detailed guidance on implementing RCM including decision diagrams, default actions, and when run-to-failure is acceptable."
    },

    # === HVAC ===
    {
        "code": "ASHRAE 90.1-2019",
        "title": "Energy Standard for Buildings Except Low-Rise Residential Buildings",
        "discipline": "HVAC",
        "category": "energy_efficiency",
        "applicability": ["HVAC", "lighting", "envelope"],
        "key_concepts": [
            "Building envelope requirements",
            "HVAC efficiency minimums (EER, IEER, COP)",
            "Service water heating",
            "Lighting power density",
            "Climate zones (8 zones globally)"
        ],
        "calc_links": ["EER", "COP", "SEER", "HVAC_load"],
        "summary": "Industry-standard for commercial building energy efficiency. Defines minimum efficiency for HVAC equipment, building envelope U-values, and operational requirements. Used as basis for green building certifications (LEED)."
    },
    {
        "code": "ASHRAE 62.1-2019",
        "title": "Ventilation and Acceptable Indoor Air Quality",
        "discipline": "HVAC",
        "category": "ventilation",
        "applicability": ["HVAC", "IAQ"],
        "key_concepts": [
            "Ventilation rate procedure (Rp + Ra method)",
            "IAQ procedure (mass balance)",
            "Outdoor air quality classification",
            "Filtration requirements (MERV ratings)"
        ],
        "calc_links": ["ventilation_rate", "outdoor_air_flow", "CFM"],
        "summary": "Defines minimum ventilation rates and IAQ requirements for commercial buildings. Provides Rp (people-based) + Ra (area-based) calculation methodology used in HVAC system sizing."
    },
    {
        "code": "ASHRAE 55-2020",
        "title": "Thermal Environmental Conditions for Human Occupancy",
        "discipline": "HVAC",
        "category": "thermal_comfort",
        "applicability": ["HVAC", "comfort"],
        "key_concepts": [
            "PMV/PPD thermal comfort model",
            "Adaptive comfort method",
            "Operative temperature range",
            "Humidity limits (30-65% RH typical)"
        ],
        "calc_links": ["PMV", "operative_temp", "comfort_index"],
        "summary": "Defines acceptable thermal environment for human occupancy. Provides PMV (Predicted Mean Vote) model and adaptive comfort method for setting HVAC setpoints."
    },

    # === ELECTRICAL ===
    {
        "code": "IEC 60364-5-52",
        "title": "Low-voltage electrical installations -- Selection and erection of electrical equipment -- Wiring systems",
        "discipline": "electrical",
        "category": "wiring",
        "applicability": ["electrical"],
        "key_concepts": [
            "Cable sizing methodology",
            "Current-carrying capacity tables",
            "Voltage drop calculations (3% lighting, 5% other)",
            "Protective conductor sizing"
        ],
        "calc_links": ["cable_size", "voltage_drop", "ampacity"],
        "summary": "International standard for low-voltage electrical wiring systems. Defines cable sizing, current-carrying capacity, and voltage drop limits used in electrical design calculations."
    },
    {
        "code": "IEC 61508:2010",
        "title": "Functional safety of electrical/electronic/programmable electronic safety-related systems",
        "discipline": "electrical",
        "category": "functional_safety",
        "applicability": ["safety_systems"],
        "key_concepts": [
            "Safety Integrity Level (SIL 1-4)",
            "Probability of failure on demand (PFD)",
            "Risk reduction factor (RRF)",
            "Hardware fault tolerance"
        ],
        "calc_links": ["SIL", "PFD", "RRF"],
        "summary": "Defines safety lifecycle for E/E/PE safety-related systems. Establishes SIL levels and probability targets for safety instrumented systems in industrial applications."
    },
    {
        "code": "IEC 62305",
        "title": "Protection against lightning",
        "discipline": "electrical",
        "category": "lightning_protection",
        "applicability": ["electrical", "structural"],
        "key_concepts": [
            "Lightning protection levels (LPL I-IV)",
            "Risk assessment (R1-R4)",
            "Air termination, down conductor, earth termination",
            "Surge protective devices (SPDs)"
        ],
        "calc_links": ["lightning_risk", "rolling_sphere", "mesh_method"],
        "summary": "International standard for lightning protection systems (LPS). Defines protection levels, risk assessment methodology, and design requirements for LPS components."
    },
    {
        "code": "NFPA 70E-2024",
        "title": "Standard for Electrical Safety in the Workplace",
        "discipline": "electrical",
        "category": "electrical_safety",
        "applicability": ["electrical_safety"],
        "key_concepts": [
            "Arc flash boundary calculations",
            "PPE category requirements",
            "Approach boundaries (limited, restricted)",
            "Energized work permits"
        ],
        "calc_links": ["arc_flash_energy", "boundary_distance", "PPE_level"],
        "summary": "US standard for electrical workplace safety. Defines arc flash hazard analysis, approach boundaries, and PPE selection. Critical for Layer 3.2 arc/spark detector application."
    },

    # === FIRE PROTECTION ===
    {
        "code": "NFPA 13-2022",
        "title": "Standard for the Installation of Sprinkler Systems",
        "discipline": "fire_protection",
        "category": "sprinkler",
        "applicability": ["fire_protection"],
        "key_concepts": [
            "Occupancy hazard classification (LH, OH1-4, EH1-2)",
            "Density/area design method",
            "Hydraulic calculations",
            "Sprinkler spacing (max coverage 225 ft²/head)"
        ],
        "calc_links": ["sprinkler_density", "hydraulic", "coverage_area"],
        "summary": "US standard for automatic sprinkler system design. Defines occupancy hazard classification, design density/area method, and hydraulic calculation procedures."
    },

    # === ICS / INDUSTRIAL ===
    {
        "code": "NIST SP 800-82r3",
        "title": "Guide to Industrial Control Systems (ICS) Security",
        "discipline": "ICS_security",
        "category": "industrial_security",
        "applicability": ["SCADA", "PLC", "DCS"],
        "key_concepts": [
            "Defense in depth",
            "ICS network segmentation (Purdue Model)",
            "OT/IT integration security",
            "Incident response for ICS"
        ],
        "calc_links": ["security_risk", "exposure_score"],
        "summary": "NIST guide for securing industrial control systems including SCADA, DCS, and PLC. Defines defense-in-depth strategies, Purdue Model network segmentation, and OT-specific incident response."
    },
    {
        "code": "ISO 55000:2014",
        "title": "Asset management -- Overview, principles and terminology",
        "discipline": "asset_management",
        "category": "asset_management",
        "applicability": ["all"],
        "key_concepts": [
            "Asset management system (AMS)",
            "Strategic asset management plan (SAMP)",
            "Value realization from assets",
            "Risk-based asset decisions"
        ],
        "calc_links": ["asset_value", "lifecycle_cost", "criticality"],
        "summary": "ISO 55000 establishes vocabulary and principles for asset management. Provides framework for SAMP development and value-driven asset decision-making."
    }
]

# ============================================================================
# Build SQL Seed File
# ============================================================================

print("\n" + "="*80)
print("DAY 2: BUILDING industry_standards SEED FILE")
print("="*80)

seed_dir = Path(__file__).parent.parent / "supabase" / "seed"
seed_dir.mkdir(parents=True, exist_ok=True)
seed_file = seed_dir / "day2_industry_standards.sql"

sql_lines = [
    "-- ============================================================",
    "-- Day 2: industry_standards seed",
    f"-- Generated: {datetime.now().isoformat()}",
    f"-- Total standards: {len(STANDARDS_METADATA)}",
    "-- ============================================================",
    "",
    "-- Clear existing (idempotent re-run)",
    "DELETE FROM industry_standards WHERE code IN (",
    "  " + ", ".join(f"'{s['code']}'" for s in STANDARDS_METADATA),
    ");",
    "",
    "INSERT INTO industry_standards (",
    "  code, title, discipline, category, applicability, key_concepts,",
    "  calc_links, summary, source, created_at",
    ") VALUES"
]

values_lines = []
for std in STANDARDS_METADATA:
    # Escape single quotes in text fields
    title = std['title'].replace("'", "''")
    summary = std['summary'].replace("'", "''")
    key_concepts = "ARRAY[" + ", ".join(f"'{k.replace(chr(39), chr(39)+chr(39))}'" for k in std['key_concepts']) + "]"
    applicability = "ARRAY[" + ", ".join(f"'{a}'" for a in std['applicability']) + "]"
    calc_links = "ARRAY[" + ", ".join(f"'{c}'" for c in std['calc_links']) + "]"

    values_lines.append(f"""  (
    '{std['code']}',
    '{title}',
    '{std['discipline']}',
    '{std['category']}',
    {applicability},
    {key_concepts},
    {calc_links},
    '{summary}',
    'public_domain_summary',
    NOW()
  )""")

sql_lines.append(",\n".join(values_lines) + ";")
sql_lines.append("")
sql_lines.append(f"-- Inserted {len(STANDARDS_METADATA)} standards")

seed_file.write_text("\n".join(sql_lines), encoding='utf-8')

print(f"\n[OK] Wrote seed file: {seed_file}")
print(f"     Total standards: {len(STANDARDS_METADATA)}")
print(f"     File size: {seed_file.stat().st_size / 1024:.1f} KB")

# Discipline breakdown
print("\nDiscipline breakdown:")
disciplines = {}
for std in STANDARDS_METADATA:
    d = std['discipline']
    disciplines[d] = disciplines.get(d, 0) + 1
for d, count in sorted(disciplines.items()):
    print(f"  {d}: {count}")

# ============================================================================
# Phase 2: Doc Intelligence batch on downloaded PDFs
# ============================================================================

print("\n" + "="*80)
print("PHASE 2: SUBMIT DOWNLOADED PDFS TO DOC INTELLIGENCE")
print("="*80)

standards_dir = Path(r"c:\wh-datasets\standards")
manifest_file = standards_dir / "_manifest.json"

if not manifest_file.exists():
    print("\n[SKIP] No downloads manifest found. Run day2_free_standards_download.py first.")
    sys.exit(0)

manifest = json.loads(manifest_file.read_text())
downloaded = [r for r in manifest['results'] if r['status'] in ('downloaded', 'exists') and r.get('file')]

print(f"\nFound {len(downloaded)} PDFs ready for Doc Intelligence:")
for r in downloaded:
    print(f"  - {r['name']} ({r.get('size_mb', 0):.1f} MB)")

if not downloaded:
    print("\n[SKIP] No PDFs to process.")
    sys.exit(0)

if not ENDPOINT or not API_KEY:
    print("\n[ERROR] AZURE_DOC_INTELLIGENCE_ENDPOINT or KEY missing")
    sys.exit(1)

# Submit each PDF to Doc Intelligence
print("\nSubmitting PDFs to Doc Intelligence Read model...")
analyze_url = f"{ENDPOINT.rstrip('/')}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2023-07-31"
headers = {
    "Ocp-Apim-Subscription-Key": API_KEY,
    "Content-Type": "application/octet-stream"
}

pending_jobs = []
for r in downloaded:
    pdf_path = Path(r['file'])
    if not pdf_path.exists():
        continue

    print(f"\n  Submitting: {pdf_path.name}")
    try:
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        response = requests.post(analyze_url, headers=headers, data=pdf_bytes, timeout=120)

        if response.status_code == 202:
            operation_location = response.headers.get("Operation-Location")
            print(f"    [OK] Submitted. Polling URL stored.")
            pending_jobs.append({
                "name": r['name'],
                "file": str(pdf_path),
                "operation_location": operation_location,
                "submitted_at": datetime.now().isoformat()
            })
        else:
            print(f"    [FAIL] HTTP {response.status_code}: {response.text[:200]}")

    except Exception as e:
        print(f"    [ERROR] {e}")

# Save pending jobs
jobs_file = standards_dir / "_doc_intelligence_jobs.json"
with open(jobs_file, 'w', encoding='utf-8') as f:
    json.dump({
        "submitted_at": datetime.now().isoformat(),
        "pending_jobs": pending_jobs
    }, f, indent=2)

print(f"\n[OK] Saved jobs to: {jobs_file}")
print(f"     Submitted: {len(pending_jobs)} jobs")
print(f"\nNext: python tools/day2_poll_doc_intelligence.py")
print("(This will poll for results, parse text, chunk for knowledge_base)")
