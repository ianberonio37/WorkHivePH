"""Seed industry_standards with Day 2 Azure $200 sprint additions.

The Phase 6F migration (20260513000007) already inserts 10 baseline standards:
  PSME, PEC, PSAE, ISO 14224, ISO 55000, IEC 62305, NFPA 13, ASHRAE 90.1,
  SAE JA 1011, AIAG-VDA FMEA.

This seeder adds 11 more standards referenced by the platform's 53 engineering
calculations and analytics surfaces (MTBF, OEE, RCM, predictive maintenance).
Idempotent via ON CONFLICT (standard_code) DO UPDATE.
"""

# Day 2 additions — standards referenced in engineering-design.html (53 calcs)
# and analytics-report.html (MTBF/RCM/predictive). These are tied to the
# Azure $200 sprint's industry_standards expansion (Layer 2 doc mining target).
DAY2_STANDARDS = [
    # === Reliability & Predictive Maintenance ===
    {
        "standard_code":   "ISO 13381-1:2015",
        "family":          "iso",
        "title":           "Condition monitoring and diagnostics of machines — Prognostics — Part 1: General guidelines",
        "current_version": "2015",
        "effective_year":  2015,
        "jurisdiction":    "global",
        "source_url":      "https://www.iso.org/standard/51436.html",
        "notes":           "Used by analytics-report.html for RUL forecasting and predictive insights (line 1255).",
    },
    {
        "standard_code":   "SAE JA 1012:2011",
        "family":          "sae",
        "title":           "A Guide to the Reliability-Centered Maintenance (RCM) Standard",
        "current_version": "2011",
        "effective_year":  2011,
        "jurisdiction":    "global",
        "source_url":      "https://www.sae.org/standards/content/ja1012_201108/",
        "notes":           "Companion implementation guide to JA1011 (already seeded). Used in reliability seeder for RCM decisions.",
    },

    # === HVAC ===
    {
        "standard_code":   "ASHRAE 62.1:2019",
        "family":          "ashrae",
        "title":           "Ventilation and Acceptable Indoor Air Quality",
        "current_version": "2019",
        "effective_year":  2019,
        "jurisdiction":    "global",
        "source_url":      "https://www.ashrae.org/technical-resources/bookstore/standards-62-1-62-2",
        "notes":           "Used by HVAC engineering calcs (ventilation rate procedure, outdoor air flow).",
    },
    {
        "standard_code":   "ASHRAE 55:2020",
        "family":          "ashrae",
        "title":           "Thermal Environmental Conditions for Human Occupancy",
        "current_version": "2020",
        "effective_year":  2020,
        "jurisdiction":    "global",
        "source_url":      "https://www.ashrae.org/technical-resources/bookstore/standard-55",
        "notes":           "PMV/PPD thermal comfort model. Used in HVAC comfort calcs.",
    },

    # === Electrical ===
    {
        "standard_code":   "IEC 60364-5-52:2009",
        "family":          "iec",
        "title":           "Low-voltage electrical installations — Selection and erection of wiring systems",
        "current_version": "2009",
        "effective_year":  2009,
        "jurisdiction":    "global",
        "source_url":      "https://webstore.iec.ch/publication/1875",
        "notes":           "Cable sizing, voltage drop calcs. Used by electrical engineering calcs.",
    },
    {
        "standard_code":   "IEC 61508:2010",
        "family":          "iec",
        "title":           "Functional safety of electrical/electronic/programmable electronic safety-related systems",
        "current_version": "2010",
        "effective_year":  2010,
        "jurisdiction":    "global",
        "source_url":      "https://webstore.iec.ch/publication/22273",
        "notes":           "Safety Integrity Level (SIL) framework for safety instrumented systems.",
    },
    {
        "standard_code":   "NFPA 70E:2024",
        "family":          "nfpa",
        "title":           "Standard for Electrical Safety in the Workplace",
        "current_version": "2024",
        "effective_year":  2024,
        "jurisdiction":    "global",
        "source_url":      "https://www.nfpa.org/codes-and-standards/all-codes-and-standards/list-of-codes-and-standards/detail?code=70E",
        "notes":           "Arc flash boundary calcs, PPE selection. Anchors Layer 3.2 arc/spark detector training rationale.",
    },

    # === ICS / Industrial ===
    {
        "standard_code":   "NIST SP 800-82r3",
        "family":          "other",
        "title":           "Guide to Operational Technology (OT) Security",
        "current_version": "Revision 3",
        "effective_year":  2023,
        "jurisdiction":    "global",
        "source_url":      "https://csrc.nist.gov/pubs/sp/800/82/r3/final",
        "notes":           "ICS/SCADA/PLC security framework. Anchors Phase 5 enterprise compliance posture.",
    },

    # === Philippine-specific (your home market) ===
    {
        "standard_code":   "DOLE D.O. 198-18",
        "family":          "philippine",
        "title":           "Occupational Safety and Health Standards (Implementing Rules and Regulations of RA 11058)",
        "current_version": "2018",
        "effective_year":  2018,
        "jurisdiction":    "PH",
        "source_url":      "https://www.dole.gov.ph",
        "notes":           "PH OSH baseline for any industrial maintenance work. Cross-links to logbook permit_to_work.",
    },
    {
        "standard_code":   "DOH AO 2007-0036",
        "family":          "philippine",
        "title":           "Guidelines on the Issuance of License to Operate Hospitals (Equipment & Maintenance Provisions)",
        "current_version": "2007",
        "effective_year":  2007,
        "jurisdiction":    "PH",
        "source_url":      "https://doh.gov.ph",
        "notes":           "PH hospital equipment maintenance requirements. Relevant when WorkHive expands to healthcare facilities.",
    },
    {
        "standard_code":   "DENR DAO 2013-22",
        "family":          "philippine",
        "title":           "Revised Procedures and Standards for the Management of Hazardous Wastes",
        "current_version": "2013",
        "effective_year":  2013,
        "jurisdiction":    "PH",
        "source_url":      "https://emb.gov.ph",
        "notes":           "PH hazwaste handling — relevant for oil drains, used lubricants, contaminated parts.",
    },
]


def seed_industry_standards(client, log) -> dict:
    """Adds Day 2 Azure sprint standards on top of the 10 baseline rows from
    the Phase 6F migration. Idempotent: re-running updates existing rows."""
    log("Seeding industry_standards (Day 2 Azure sprint additions)...")

    if not DAY2_STANDARDS:
        return {"industry_standards_count": 0}

    inserted = 0
    updated = 0

    # Check which already exist (likely none from this list, but cheap to check)
    existing_codes = set()
    try:
        res = client.table("industry_standards").select("standard_code").execute()
        existing_codes = {r["standard_code"] for r in (res.data or [])}
    except Exception as e:
        log(f"  warning: could not pre-check existing rows: {e}")

    # Use upsert to handle re-runs (PostgREST will use the unique constraint
    # on standard_code via the ON CONFLICT clause defined in the migration).
    try:
        res = client.table("industry_standards").upsert(
            DAY2_STANDARDS,
            on_conflict="standard_code",
        ).execute()
        affected = len(res.data or [])
        for row in DAY2_STANDARDS:
            if row["standard_code"] in existing_codes:
                updated += 1
            else:
                inserted += 1
        log(f"  upserted {affected} industry_standards rows ({inserted} new, {updated} updated)")
    except Exception as e:
        log(f"  ERROR upserting industry_standards: {e}")
        return {"industry_standards_count": 0}

    # Total row count after insert
    try:
        res = client.table("industry_standards").select("id", count="exact").execute()
        total = res.count or 0
        log(f"  industry_standards total rows: {total}")
    except Exception:
        total = inserted + updated

    return {
        "industry_standards_count":   inserted,
        "industry_standards_updated": updated,
        "industry_standards_total":   total,
    }
