"""
Single source of truth for WorkHive public page lists.

Replaces hardcoded slug lists previously duplicated across:
  - validate_em_dash.py
  - validate_contact_consistency.py
  - validate_ga4_coverage.py
  - validate_audience_block.py
  - validate_tool_aligned_cta.py
  - validate_sitemap_sync.py
  - validate_llms_sync.py
  - validate_seo.py
  - tools/wire_ga4.py

Adding a new /learn/ article = append one tuple to LEARN_ARTICLES below + run
`python tools/scaffold_article.py` which auto-updates sitemap.xml + llms.txt +
runs `wire_ga4.py`. The 10 validators all read this file and stay in sync.

Each LEARN_ARTICLES tuple: (slug, title, tool_path, tool_name)
  slug:      URL slug under /learn/<slug>/
  title:     human-readable article title (used in <title>, og:title, JSON-LD)
  tool_path: WorkHive tool the article funnels readers to (root-absolute)
  tool_name: how the tool is referred to in body text (validator checks this
             string appears in the article body at least once)
"""

# ── Site-wide root + stub pages (indexable but tool-agnostic) ─────────────────

LANDING_PAGE   = "index.html"
STUB_PAGES     = [
    "about/index.html",
    "privacy-policy/index.html",
    "terms-of-service/index.html",
]
LEARN_HUB_PAGE = "learn/index.html"

# ── /learn/ article catalog ───────────────────────────────────────────────────
# Wave 1 (24 articles, shipped 2026-05-17): tool-aligned articles, one per tool.
# Wave 2 (12 articles, shipped 2026-05-18): methodology, career, sector, PH
# compliance, tool-deep-dive coverage gaps identified in the Wave-1 audit.

LEARN_ARTICLES = [
    # ── Wave 1 ────────────────────────────────────────────────────────────────
    ("start-digital-logbook-philippine-factory",          "How to Start a Digital Logbook in a Philippine Factory",          "/logbook.html",             "Logbook"),
    ("what-is-oee-how-to-calculate",                      "What is OEE and How Do I Calculate It?",                          "/analytics.html",          "Analytics"),
    ("mtbf-vs-mttr-for-supervisors",                      "MTBF vs MTTR for Supervisors, Engineers, and Planners",           "/analytics.html",          "Analytics"),
    ("maintenance-shift-handover-template",               "How to Write a Maintenance Shift Handover (Template Included)",   "/shift-brain.html",         "Shift Brain"),
    ("spare-parts-inventory-philippine-plants",           "Spare Parts Inventory for Philippine Plants",                     "/inventory.html",           "Inventory"),
    ("free-pm-checklist-templates",                       "Free PM Checklist Templates for Industrial Maintenance",          "/pm-scheduler.html",        "PM Scheduler"),
    ("skill-matrix-for-maintenance-technicians",          "How to Build a Skill Matrix for Maintenance Technicians",         "/skillmatrix.html",         "Skill Matrix"),
    ("dilo-wilo-day-planner-supervisors",                 "DILO, WILO, MILO, YILO: Day Planner Method for Supervisors",      "/dayplanner.html",          "Day Planner"),
    ("free-engineering-calculators-philippine-plants",    "Free Engineering Design Calculators for Philippine Plants",       "/engineering-design.html",  "Engineering Design"),
    ("ai-work-assistant-maintenance-technicians",         "AI Work Assistant for Every Industrial Worker",                   "/assistant.html",           "AI Assistant"),
    ("predictive-maintenance-on-a-budget-philippines",    "Predictive Maintenance on a Budget (Philippines)",                "/analytics.html",          "Analytics"),
    ("connecting-workhive-to-sap-maximo-cmms",            "Connecting WorkHive to SAP, IBM Maximo, and Other CMMS",          "/integrations.html",       "Integrations"),
    ("voice-to-text-maintenance-philippine-plant-floor",  "Voice-to-Text on the Philippine Plant Floor",                     "/voice-journal.html",       "Voice Journal"),
    ("building-asset-register-zero-budget",               "Building an Asset Register from Scratch (Zero-Budget, ISO 14224)","/asset-hub.html",           "Asset Hub"),
    # T174 (2026-08-28): tool_path was "/hive.html", and the article it points at is titled "Plant
    # Turnaround and Maintenance Project Planning". It names "Project Manager" 14 times, headlines
    # "WorkHive Project Manager runs the 6 steps end to end", and its own CTA is
    # <a href="/project-manager.html">Open Project Manager</a>. "Hive" appears twice, once inside
    # "WorkHive". The registry and the article disagreed, and the registry lost.
    # Consequence while it stood: learn-link.js keys the page-guide chip off tool_path, so the
    # project-planning guide was offered on the HIVE BOARD and project-manager.html - the most
    # complex page on the platform - had no guide at all. One of six pages with that gap, and the
    # only one where the guide already existed and was simply pointed at the wrong door.
    ("maintenance-project-planning-template",             "Maintenance Project Planning (Free Template for PH Plants)",      "/project-manager.html",     "Project Manager"),
    ("joining-and-growing-your-hive",                     "Joining and Growing Your WorkHive Hive (Multi-Tenant Guide)",     "/hive.html",                "Hive"),
    ("industrial-community-of-practice-philippines",      "Industrial Community of Practice for Philippine Plant Teams",     "/community.html",           "Community"),
    ("gamifying-maintenance-for-engagement",              "Gamifying Maintenance for Technician Engagement",                 "/achievements.html",       "Achievements"),
    ("industrial-marketplace-philippine-specialists",     "Industrial Marketplace for Philippine Specialists",               "/marketplace.html",         "Marketplace"),
    ("predictive-alert-thresholds-plants",                "Predictive Alert Thresholds for Industrial Plants",               "/alert-hub.html",          "Alert Hub"),
    ("dole-iso-audit-trail-from-logbook",                 "DOLE OSHS and ISO Audit Trail from Your Logbook",                 "/audit-log.html",           "Audit"),
    ("ai-quality-and-roi-stage-2-plants",                 "Measuring AI Quality and ROI for Stage 2+ Industrial Plants",     "/ai-quality.html",         "AI Quality"),
    ("sensor-cmms-gateway-operations",                    "Sensor and CMMS Gateway Operations for Industrial Plants",        "/plant-connections.html",  "Plant Connections"),
    ("ph-industrial-benchmarks-intelligence",             "PH Industrial Benchmarks and Intelligence Reports (Free)",        "/ph-intelligence.html",    "PH Intelligence"),
    # Gap found by the Content Grounding Gate 2026-06-10: Resume Builder had no
    # article and was invisible to SEO/GEO (nav-only uncovered).
    ("resume-builder-for-filipino-industrial-workers",    "Build an ATS-Ready Resume from Your Plant Work History",          "/resume.html",              "Resume Builder"),

    # ── Wave 2 (2026-05-18): methodology + career + sector + compliance ───────
    ("reliability-centered-maintenance-philippine-plants","Reliability-Centered Maintenance (RCM) for Philippine Plants",    "/pm-scheduler.html",        "PM Scheduler"),
    ("fmea-worked-example-philippine-bottling-line",      "FMEA Worked Example: a Philippine Bottling Line",                 "/asset-hub.html",           "Asset Hub"),
    ("loto-procedures-dole-oshs-template",                "Lock-Out Tag-Out (LOTO) Procedures: DOLE OSHS Template",          "/audit-log.html",           "Audit"),
    ("vibration-analysis-on-a-phone-budget",              "Vibration Analysis on a Phone Budget (Philippine PdM)",           "/voice-journal.html",       "Voice Journal"),
    ("thermography-for-pm-philippine-plants",             "Thermography for Preventive Maintenance in Philippine Plants",    "/pm-scheduler.html",        "PM Scheduler"),
    ("ra-11285-energy-efficiency-plant-checklist",        "RA 11285 Energy Efficiency: a Plant-Floor Compliance Checklist",  "/audit-log.html",           "Audit"),
    ("tesda-nc-mapping-to-skill-matrix",                  "Mapping TESDA NC II and NC III to Your Skill Matrix",             "/skillmatrix.html",         "Skill Matrix"),
    ("ofw-engineer-portable-portfolio",                   "How OFW-Track Engineers Build a Portable Maintenance Portfolio",  "/skillmatrix.html",         "Skill Matrix"),
    ("psme-iiee-piche-which-association-to-join",         "PSME, IIEE, PIChE: Which Philippine Engineering Association?",    "/community.html",           "Community"),
    ("food-beverage-plant-maintenance-philippines",       "Maintenance in Philippine Food and Beverage Plants",              "/hive.html",                "Hive"),
    ("power-plant-reliability-metrics-philippines",       "Power Plant Reliability Metrics in the Philippines",              "/analytics-report.html",    "Analytics"),
    ("bms-facilities-maintenance-peza-buildings",         "BMS and Facilities Maintenance in PEZA Buildings",                "/hive.html",                "Hive"),

    # ── Wave 3 (2026-07-02): the Asset Brain 360 intelligence layer ───────────
    # Gap found by the content-grounding sweep: building-asset-register covers
    # CREATING the register; nothing covers the live per-machine brain you get
    # AFTER — QR scan -> full timeline + parts-that-fit + AI Q&A + the per-asset
    # predictive risk score (which folded here when predictive.html retired).
    ("asset-brain-360-one-machine-history-philippine-plant","Asset Brain 360: Every Machine's Full History in One QR Scan",   "/asset-hub.html",           "Asset Hub"),

    # ── Wave 4 (2026-07-03): the "your AI works for you / save time" layer ─────
    # Gaps: shift-brain had only a handover TEMPLATE article (not the autonomous
    # planner); alert-hub had only a THRESHOLDS article (not the unified inbox).
    ("autonomous-shift-planning-philippine-plants",       "Autonomous Shift Planning: the AI Brief That Tells Your Crew What to Fix First", "/shift-brain.html",  "Shift Brain"),
    ("plant-alert-inbox-amc-daily-brief",                 "One Alert Inbox for the Whole Plant: Risk, PM, Stock, and the 6 AM Brief",       "/alert-hub.html",    "Alert Hub"),

    # ── Wave 5 (2026-07-03): the interconnected ANALYTICS hub (analytics has the
    # most connects_to of any un-articled feature: logbook -> engine -> predictive
    # -> reports -> intelligence). The engine + its print-ready report deliverable.
    ("four-phases-maintenance-analytics-philippine-plants","The 4 Phases of Maintenance Analytics: From What Happened to What To Do Next",   "/analytics.html",         "Analytics"),
    ("print-ready-maintenance-analytics-report",          "The Print-Ready Maintenance Report Your Management Actually Reads",              "/analytics-report.html",  "Analytics Report"),
    # ── Wave 6 (2026-07-07): pillar overview + AI companion capabilities ───────
    # L4-exempt: a platform OVERVIEW legitimately links all 26 tools, and its declared
    # target is the landing page, which is not a tool anchor - the check cannot apply.
    ("what-is-workhive-complete-platform-guide",          "What is WorkHive? The Complete Guide to the Free Platform for Filipino Industrial Teams", "/index.html",       "WorkHive"),
    ("workhive-ai-companion-complete-capabilities",       "The WorkHive AI Companion: Everything It Can Do (and How to Get the Most From It)",         "/assistant.html",   "AI Companion"),
]


# ── Derived helpers (validators import these) ─────────────────────────────────

def learn_slugs() -> list:
    """Just the slug strings, in catalog order."""
    return [a[0] for a in LEARN_ARTICLES]


def learn_paths() -> list:
    """Filesystem-relative paths to every /learn/ article."""
    return [f"learn/{a[0]}/index.html" for a in LEARN_ARTICLES]


def all_public_pages() -> list:
    """Every page that should be indexed, GA4-wired, and in sitemap.xml.
    Order: landing, stubs, learn hub, then article catalog."""
    return [LANDING_PAGE] + STUB_PAGES + [LEARN_HUB_PAGE] + learn_paths()


def all_public_surfaces() -> list:
    """All_public_pages + the non-HTML public files (llms.txt, sitemap, robots).
    Used by contact_consistency validator that scans for stale email refs."""
    return all_public_pages() + ["llms.txt", "sitemap.xml", "robots.txt"]


def article_tool_map() -> dict:
    """slug -> (tool_path, tool_name) for the tool-aligned CTA validator."""
    return {a[0]: (a[2], a[3]) for a in LEARN_ARTICLES}


def article_title_map() -> dict:
    """slug -> title for sitemap.xml / llms.txt scaffolding."""
    return {a[0]: a[1] for a in LEARN_ARTICLES}


def sitemap_urls() -> list:
    """URLs (without the https://workhiveph.com prefix) expected in sitemap.xml."""
    return [
        "/",
        "/learn/",
        "/about/",
        "/privacy-policy/",
        "/terms-of-service/",
    ] + [f"/learn/{s}/" for s in learn_slugs()]
