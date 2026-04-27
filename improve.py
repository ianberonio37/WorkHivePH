"""
WorkHive Platform Guardian — Phase 5: Continuous Improvement
=============================================================
Searches the web for updates that affect any of the 39 validators.
Maps findings to concrete platform opportunities and business value.

Topics cover every validator cluster:
  - Engineering standards (NFPA, ISO, ASHRAE, IEC, PEC, PSME)
  - AI/LLM technology (Groq, pgvector, RAG, context management)
  - Security (OWASP, SAML, WebAuthn, IEC 62443, Philippines PDPA)
  - Mobile/PWA/Accessibility (WCAG, iOS Safari, Service Workers)
  - Enterprise integration (SAP, MQTT, webhooks, digital twin)
  - Performance/database (PostgreSQL, Supabase, CDN)
  - Predictive analytics (ISO 13374, ML patterns)

Usage:
  python improve.py              # full search (all topics, ~5 min)
  python improve.py --fast       # weekly + monthly topics only (~2 min)
  python improve.py --security   # security topics only (run weekly)
  python improve.py --dry-run    # show topics without searching
  python improve.py --topic calc # specific topic group

Output:
  improvement_backlog.json  — scored items with validator links + opportunities
  (merges with existing backlog, no duplicates)

Business value levels:
  enterprise_blocker  — enterprise client cannot sign without this
  revenue_enabler     — unlocks a new paid tier or feature
  operational         — makes platform faster/more reliable
  standard_currency   — keeps engineering calcs legally compliant

Check frequencies:
  weekly    — security vulnerabilities, CVEs, API breaking changes
  monthly   — AI models, library updates, Supabase releases
  quarterly — engineering standards (NFPA, ISO, IEC, ASHRAE, PEC)
"""
import urllib.request, urllib.parse, json, re, sys, datetime, time, os

DRY_RUN    = "--dry-run"   in sys.argv
FAST_MODE  = "--fast"      in sys.argv
SEC_MODE   = "--security"  in sys.argv
BACKLOG    = "improvement_backlog.json"
HEALTH     = "platform_health.json"

# ── Topic definitions ─────────────────────────────────────────────────────────
# Each topic: id, group, label, query, keywords, affects (validator IDs),
#             priority (HIGH/MEDIUM/LOW), business_value, check_frequency,
#             opportunity (what to build if this fires), skip_fast

TOPICS = [

    # ══════════════════════════════════════════════════════
    # ENGINEERING STANDARDS
    # ══════════════════════════════════════════════════════

    {
        "id":             "nfpa72-update",
        "group":          "Engineering Standards",
        "label":          "NFPA 72 Fire Alarm Code — latest edition",
        "query":          "NFPA 72 fire alarm signaling code latest edition 2025 amendment",
        "keywords":       ["2022", "2025", "amendment", "edition", "update", "revised"],
        "validator_ids":  ["calc-suite"],
        "affects":        "Fire Alarm Battery Standby calc",
        "priority":       "HIGH",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update NFPA 72 §10.6 battery standby formula if new edition published",
        "skip_fast":      False,
    },
    {
        "id":             "nfpa92-update",
        "group":          "Engineering Standards",
        "label":          "NFPA 92 Smoke Control — latest edition",
        "query":          "NFPA 92 smoke control stairwell pressurization standard 2024 2025",
        "keywords":       ["2021", "2024", "2025", "edition", "amendment", "update"],
        "validator_ids":  ["calc-suite"],
        "affects":        "Stairwell Pressurization calc",
        "priority":       "HIGH",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update 12.5 Pa differential pressure limits if revised",
        "skip_fast":      False,
    },
    {
        "id":             "nfpa13-update",
        "group":          "Engineering Standards",
        "label":          "NFPA 13 Sprinkler Systems — latest edition",
        "query":          "NFPA 13 automatic sprinkler systems standard 2022 2025 edition",
        "keywords":       ["2022", "2025", "edition", "update", "amendment"],
        "validator_ids":  ["calc-suite"],
        "affects":        "Fire Sprinkler Hydraulic calc",
        "priority":       "HIGH",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update K-factor and hose allowance tables if new edition",
        "skip_fast":      True,
    },
    {
        "id":             "iso281-update",
        "group":          "Engineering Standards",
        "label":          "ISO 281 Bearing Life — latest edition",
        "query":          "ISO 281 rolling bearing dynamic load ratings life calculation 2024 2025",
        "keywords":       ["2007", "2024", "2025", "amendment", "revision"],
        "validator_ids":  ["calc-suite"],
        "affects":        "Bearing Life (L10) calc",
        "priority":       "HIGH",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Verify L10 life adjustment factors match latest ISO 281 Annex B",
        "skip_fast":      False,
    },
    {
        "id":             "iec62305-update",
        "group":          "Engineering Standards",
        "label":          "IEC 62305 Lightning Protection — latest edition",
        "query":          "IEC 62305 lightning protection standard 2024 2025 revision edition",
        "keywords":       ["2024", "2025", "revision", "amendment", "edition"],
        "validator_ids":  ["calc-suite", "drawings"],
        "affects":        "Lightning Protection System calc + LPS zone diagram",
        "priority":       "HIGH",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update rolling sphere radii and mesh size tables if revised",
        "skip_fast":      True,
    },
    {
        "id":             "ashrae901-update",
        "group":          "Engineering Standards",
        "label":          "ASHRAE 90.1 Energy Efficiency — latest edition",
        "query":          "ASHRAE 90.1 energy standard buildings 2022 2025 update LPD",
        "keywords":       ["2022", "2025", "lighting power density", "update", "amendment"],
        "validator_ids":  ["calc-suite"],
        "affects":        "Lighting Design, AHU Sizing, Chiller calcs (LPD limits)",
        "priority":       "MEDIUM",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update space-type LPD limits table in Lighting Design calc",
        "skip_fast":      True,
    },
    {
        "id":             "pec-update",
        "group":          "Engineering Standards",
        "label":          "Philippine Electrical Code — latest edition",
        "query":          "Philippine Electrical Code PEC 2024 2025 latest edition DOE amendment",
        "keywords":       ["2024", "2025", "edition", "update", "DOE", "amendment"],
        "validator_ids":  ["calc-suite"],
        "affects":        "All electrical calcs (Wire Sizing, Short Circuit, Load Schedule)",
        "priority":       "HIGH",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update PEC voltage drop limits and conductor sizing tables",
        "skip_fast":      False,
    },
    {
        "id":             "dole-oshs-update",
        "group":          "Engineering Standards",
        "label":          "DOLE OSHS noise limits — latest update",
        "query":          "DOLE OSHS occupational safety health noise limits Philippines 2024 2025",
        "keywords":       ["2024", "2025", "85 dBA", "90 dBA", "update", "amendment"],
        "validator_ids":  ["calc-suite"],
        "affects":        "Noise/Acoustics calc (DOLE D.O. 13 TWA limits)",
        "priority":       "MEDIUM",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update TWA exposure limits if DOLE D.O. 13 is revised",
        "skip_fast":      True,
    },
    {
        "id":             "asme-bpvc-update",
        "group":          "Engineering Standards",
        "label":          "ASME BPVC Section VIII Pressure Vessels — 2025",
        "query":          "ASME BPVC section VIII pressure vessel 2025 edition addenda update",
        "keywords":       ["2023", "2025", "addenda", "edition", "revision", "code case"],
        "validator_ids":  ["calc-suite"],
        "affects":        "Pressure Vessel design calc",
        "priority":       "HIGH",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update allowable stress values and joint efficiency tables",
        "skip_fast":      True,
    },
    {
        "id":             "iso10816-update",
        "group":          "Engineering Standards",
        "label":          "ISO 10816 / ISO 20816 Vibration — latest edition",
        "query":          "ISO 10816 ISO 20816 machinery vibration limits 2024 2025 revision update",
        "keywords":       ["2024", "2025", "revision", "amendment", "20816", "replaces"],
        "validator_ids":  ["calc-suite", "predictive"],
        "affects":        "Vibration Analysis calc + Predictive Analytics MTBF thresholds",
        "priority":       "MEDIUM",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update vibration severity zones A/B/C/D if ISO 20816 supersedes",
        "skip_fast":      True,
    },
    {
        "id":             "ieee80-update",
        "group":          "Engineering Standards",
        "label":          "IEEE 80 Grounding Systems — latest edition",
        "query":          "IEEE 80 guide safety metal substations grounding 2025 revision edition",
        "keywords":       ["2013", "2023", "2025", "revision", "edition", "update"],
        "validator_ids":  ["calc-suite"],
        "affects":        "Earthing / Grounding System calc",
        "priority":       "HIGH",
        "business_value": "standard_currency",
        "check_frequency":"quarterly",
        "opportunity":    "Update touch and step voltage tolerable limit formulas",
        "skip_fast":      True,
    },

    # ══════════════════════════════════════════════════════
    # AI / LLM TECHNOLOGY
    # ══════════════════════════════════════════════════════

    {
        "id":             "groq-model-updates",
        "group":          "AI Technology",
        "label":          "Groq new models and free-tier TPM limits 2025",
        "query":          "Groq AI new models 2025 free tier tokens per minute limits llama4",
        "keywords":       ["2025", "llama-4", "new model", "TPM", "rate limit", "free tier"],
        "validator_ids":  ["groq-fallback"],
        "affects":        "Groq fallback chain — new models should be added in TPM order",
        "priority":       "HIGH",
        "business_value": "operational",
        "check_frequency":"monthly",
        "opportunity":    "Add new high-TPM Groq models to fallback chain, retire deprecated ones",
        "skip_fast":      False,
    },
    {
        "id":             "pgvector-updates",
        "group":          "AI Technology",
        "label":          "pgvector new version — HNSW index and performance 2025",
        "query":          "pgvector 0.7 0.8 HNSW index cosine similarity performance 2025",
        "keywords":       ["HNSW", "0.7", "0.8", "2025", "faster", "index", "performance"],
        "validator_ids":  ["vector-schema"],
        "affects":        "Vector knowledge base schema — IVFFlat may be superseded by HNSW",
        "priority":       "MEDIUM",
        "business_value": "operational",
        "check_frequency":"monthly",
        "opportunity":    "Migrate IVFFlat indexes to HNSW for 10x faster similarity search",
        "skip_fast":      False,
    },
    {
        "id":             "rag-architecture-2025",
        "group":          "AI Technology",
        "label":          "Agentic RAG and Graph RAG patterns 2025",
        "query":          "agentic RAG graph RAG industrial maintenance AI patterns 2025",
        "keywords":       ["agentic", "graph RAG", "2025", "self-evaluation", "entity", "knowledge graph"],
        "validator_ids":  ["vector-schema", "knowledge-freshness", "context-window"],
        "affects":        "RAG pipeline — graph RAG would connect fault/skill/PM knowledge",
        "priority":       "MEDIUM",
        "business_value": "revenue_enabler",
        "check_frequency":"monthly",
        "opportunity":    "Build entity relationship graph: asset → fault → skill → PM (Graph RAG)",
        "skip_fast":      True,
    },
    {
        "id":             "nomic-embed-updates",
        "group":          "AI Technology",
        "label":          "nomic-embed-text model updates — new dimensions",
        "query":          "nomic-embed-text v2 2025 new dimensions embedding model update Groq",
        "keywords":       ["v2", "2025", "768", "1024", "new model", "update", "dimensions"],
        "validator_ids":  ["vector-schema"],
        "affects":        "pgvector vector(384) dimension — must match embedding model",
        "priority":       "HIGH",
        "business_value": "operational",
        "check_frequency":"monthly",
        "opportunity":    "Migration plan: re-embed all knowledge tables if model dimensions change",
        "skip_fast":      False,
    },
    {
        "id":             "supabase-edge-deno-updates",
        "group":          "AI Technology",
        "label":          "Supabase Edge Functions Deno runtime updates 2025",
        "query":          "Supabase Edge Functions Deno 2.0 2025 breaking changes new APIs",
        "keywords":       ["Deno 2", "2025", "breaking", "new API", "runtime", "update"],
        "validator_ids":  ["edge-contracts", "groq-fallback"],
        "affects":        "All 6 edge functions — Deno upgrades may break import URLs",
        "priority":       "HIGH",
        "business_value": "operational",
        "check_frequency":"monthly",
        "opportunity":    "Update Deno import URLs in edge functions to new registry format",
        "skip_fast":      False,
    },
    {
        "id":             "llm-context-patterns",
        "group":          "AI Technology",
        "label":          "LLM context compression and MEMENTO patterns 2025",
        "query":          "LLM context window management compression KV cache reduction 2025 patterns",
        "keywords":       ["compression", "KV cache", "2025", "sliding window", "summarization", "MEMENTO"],
        "validator_ids":  ["context-window"],
        "affects":        "assistant.html sessionMessages — unbounded growth over long sessions",
        "priority":       "MEDIUM",
        "business_value": "operational",
        "check_frequency":"monthly",
        "opportunity":    "Add session summary compression to assistant.html for long shifts",
        "skip_fast":      True,
    },
    {
        "id":             "ai-governance-nist",
        "group":          "AI Technology",
        "label":          "NIST AI Risk Management Framework updates 2025",
        "query":          "NIST AI RMF artificial intelligence risk management framework 2025 update",
        "keywords":       ["2025", "NIST", "RMF", "AI risk", "governance", "trustworthy"],
        "validator_ids":  ["ai-attribution", "compliance"],
        "affects":        "AI output attribution, enterprise compliance baseline",
        "priority":       "MEDIUM",
        "business_value": "enterprise_blocker",
        "check_frequency":"quarterly",
        "opportunity":    "Add AI governance statement to enterprise compliance checklist",
        "skip_fast":      True,
    },
    {
        "id":             "supabase-realtime-v2",
        "group":          "AI Technology",
        "label":          "Supabase Realtime Broadcast and filtered subscriptions 2025",
        "query":          "Supabase Realtime broadcast filtered postgres changes 2025 performance",
        "keywords":       ["broadcast", "filter", "2025", "performance", "channel", "presence"],
        "validator_ids":  ["hive", "notifications"],
        "affects":        "hive.html realtime channels — filter server-side reduces bandwidth",
        "priority":       "MEDIUM",
        "business_value": "operational",
        "check_frequency":"monthly",
        "opportunity":    "Apply server-side channel filters to reduce hive board bandwidth",
        "skip_fast":      False,
    },

    # ══════════════════════════════════════════════════════
    # SECURITY
    # ══════════════════════════════════════════════════════

    {
        "id":             "owasp-top10-2025",
        "group":          "Security",
        "label":          "OWASP Top 10 Web Security — 2025 update",
        "query":          "OWASP Top 10 web application security vulnerabilities 2025 update",
        "keywords":       ["2025", "new", "update", "A01", "A02", "injection", "XSS", "SSRF"],
        "validator_ids":  ["xss", "input-guards", "data-governance"],
        "affects":        "XSS/escHtml coverage, input guards, governance checks",
        "priority":       "HIGH",
        "business_value": "enterprise_blocker",
        "check_frequency":"monthly",
        "opportunity":    "Verify new OWASP categories are covered by existing validators",
        "skip_fast":      False,
    },
    {
        "id":             "owasp-mobile-2025",
        "group":          "Security",
        "label":          "OWASP Mobile Top 10 — 2025 update",
        "query":          "OWASP Mobile Top 10 security 2024 2025 update mobile application",
        "keywords":       ["2024", "2025", "M1", "M2", "mobile", "update", "insecure"],
        "validator_ids":  ["mobile", "xss"],
        "affects":        "Mobile UX compliance, client-side security",
        "priority":       "MEDIUM",
        "business_value": "enterprise_blocker",
        "check_frequency":"monthly",
        "opportunity":    "Add OWASP Mobile checks to mobile validator (e.g. M9: insecure data storage)",
        "skip_fast":      True,
    },
    {
        "id":             "saml-oidc-2025",
        "group":          "Security",
        "label":          "SAML 2.0 / OpenID Connect security advisories 2025",
        "query":          "SAML 2.0 OpenID Connect OIDC security advisory 2024 2025 vulnerability",
        "keywords":       ["2024", "2025", "advisory", "vulnerability", "CVE", "Supabase SSO"],
        "validator_ids":  ["sso-readiness", "compliance"],
        "affects":        "SSO readiness, Supabase Auth SAML integration",
        "priority":       "HIGH",
        "business_value": "enterprise_blocker",
        "check_frequency":"weekly",
        "opportunity":    "Review Supabase SSO config against any published SAML/OIDC CVEs",
        "skip_fast":      False,
    },
    {
        "id":             "webhook-security-2025",
        "group":          "Security",
        "label":          "Webhook security patterns and HMAC best practices 2025",
        "query":          "webhook security HMAC signature verification idempotency best practices 2025",
        "keywords":       ["HMAC", "2025", "signature", "replay attack", "idempotency", "timing safe"],
        "validator_ids":  ["idempotency", "integration-security"],
        "affects":        "Webhook HMAC verification, idempotency table pattern",
        "priority":       "MEDIUM",
        "business_value": "enterprise_blocker",
        "check_frequency":"monthly",
        "opportunity":    "Add timing-safe HMAC comparison to webhook handler pattern",
        "skip_fast":      True,
    },
    {
        "id":             "philippines-pdpa-update",
        "group":          "Security",
        "label":          "Philippines Data Privacy Act (PDPA) amendments 2025",
        "query":          "Philippines Data Privacy Act NPC amendment circular 2024 2025 SaaS",
        "keywords":       ["2024", "2025", "NPC", "circular", "amendment", "SaaS", "consent"],
        "validator_ids":  ["compliance", "data-governance"],
        "affects":        "Enterprise compliance baseline, data governance",
        "priority":       "HIGH",
        "business_value": "enterprise_blocker",
        "check_frequency":"quarterly",
        "opportunity":    "Review NPC circulars for new SaaS data handling requirements",
        "skip_fast":      False,
    },
    {
        "id":             "iec62443-ot-security",
        "group":          "Security",
        "label":          "IEC 62443 Industrial OT Cybersecurity — 2025 update",
        "query":          "IEC 62443 industrial OT cybersecurity SCADA 2024 2025 update",
        "keywords":       ["2024", "2025", "IEC 62443", "OT", "SCADA", "update", "amendment"],
        "validator_ids":  ["iot-protocols", "digital-twin"],
        "affects":        "IoT/MQTT safety, digital twin schema security",
        "priority":       "MEDIUM",
        "business_value": "enterprise_blocker",
        "check_frequency":"quarterly",
        "opportunity":    "Add IEC 62443 security level requirements to IoT validator checks",
        "skip_fast":      True,
    },
    {
        "id":             "webauthn-passkeys-2025",
        "group":          "Security",
        "label":          "WebAuthn / Passkeys adoption for SaaS 2025",
        "query":          "WebAuthn passkeys SaaS industrial authentication 2025 Supabase",
        "keywords":       ["passkey", "2025", "WebAuthn", "FIDO2", "Supabase", "authentication"],
        "validator_ids":  ["sso-readiness"],
        "affects":        "SSO readiness — passkeys could replace password-based worker login",
        "priority":       "LOW",
        "business_value": "revenue_enabler",
        "check_frequency":"quarterly",
        "opportunity":    "Add passkey support via Supabase Auth as enterprise login alternative",
        "skip_fast":      True,
    },

    # ══════════════════════════════════════════════════════
    # MOBILE / PWA / ACCESSIBILITY
    # ══════════════════════════════════════════════════════

    {
        "id":             "wcag22-criteria",
        "group":          "Mobile & Accessibility",
        "label":          "WCAG 2.2 new success criteria — enterprise procurement",
        "query":          "WCAG 2.2 success criteria new 2024 2025 enterprise accessibility compliance",
        "keywords":       ["2.2", "focus", "dragging", "target size", "2024", "2025", "enterprise"],
        "validator_ids":  ["accessibility"],
        "affects":        "Accessibility baseline — WCAG 2.2 added Focus Appearance, Target Size",
        "priority":       "MEDIUM",
        "business_value": "enterprise_blocker",
        "check_frequency":"quarterly",
        "opportunity":    "Add WCAG 2.2 Focus Appearance and Target Size checks to accessibility validator",
        "skip_fast":      False,
    },
    {
        "id":             "ios-safari-pwa-2025",
        "group":          "Mobile & Accessibility",
        "label":          "iOS Safari PWA improvements — install and offline 2025",
        "query":          "iOS Safari PWA progressive web app improvements 2025 install offline",
        "keywords":       ["2025", "iOS 18", "install", "offline", "push notification", "home screen"],
        "validator_ids":  ["pwa"],
        "affects":        "PWA integrity — iOS Safari slowly adding PWA features",
        "priority":       "MEDIUM",
        "business_value": "revenue_enabler",
        "check_frequency":"monthly",
        "opportunity":    "Add Web Push notifications when iOS Safari supports it for PWAs",
        "skip_fast":      True,
    },
    {
        "id":             "service-worker-2025",
        "group":          "Mobile & Accessibility",
        "label":          "Service Worker offline-first patterns for industrial 2025",
        "query":          "service worker offline first industrial PWA patterns 2025 background sync",
        "keywords":       ["offline", "background sync", "2025", "cache", "IndexedDB", "workbox"],
        "validator_ids":  ["pwa", "mobile"],
        "affects":        "PWA offline capability — critical for field workers in low-signal areas",
        "priority":       "MEDIUM",
        "business_value": "revenue_enabler",
        "check_frequency":"quarterly",
        "opportunity":    "Add offline logbook entry queue with background sync when connection returns",
        "skip_fast":      True,
    },

    # ══════════════════════════════════════════════════════
    # ENTERPRISE INTEGRATION
    # ══════════════════════════════════════════════════════

    {
        "id":             "sap-btp-api-2025",
        "group":          "Enterprise Integration",
        "label":          "SAP BTP / S4HANA Plant Maintenance API updates 2025",
        "query":          "SAP S/4HANA Plant Maintenance PM API 2025 REST OData update change",
        "keywords":       ["2025", "OData v4", "REST", "API", "PM", "plant maintenance", "update"],
        "validator_ids":  ["idempotency", "integration-security"],
        "affects":        "SAP PM integration — OData v4 may change field mappings",
        "priority":       "HIGH",
        "business_value": "enterprise_blocker",
        "check_frequency":"quarterly",
        "opportunity":    "Map SAP OData v4 PM fields to external_sync table schema",
        "skip_fast":      False,
    },
    {
        "id":             "mqtt5-features",
        "group":          "Enterprise Integration",
        "label":          "MQTT 5.0 shared subscriptions and QoS 2 patterns",
        "query":          "MQTT 5.0 shared subscriptions QoS 2 industrial IoT 2025 multi-tenant",
        "keywords":       ["MQTT 5", "shared subscription", "QoS 2", "2025", "multi-tenant", "topic alias"],
        "validator_ids":  ["iot-protocols"],
        "affects":        "IoT/MQTT safety — MQTT 5.0 enables proper multi-tenant sensor routing",
        "priority":       "MEDIUM",
        "business_value": "enterprise_blocker",
        "check_frequency":"quarterly",
        "opportunity":    "Upgrade MQTT pattern to v5 with shared subscriptions for hive-scoped sensors",
        "skip_fast":      True,
    },
    {
        "id":             "iso23247-digital-twin",
        "group":          "Enterprise Integration",
        "label":          "ISO 23247 Digital Twin manufacturing standard",
        "query":          "ISO 23247 digital twin manufacturing framework 2024 2025 update",
        "keywords":       ["ISO 23247", "2024", "2025", "digital twin", "observable", "update"],
        "validator_ids":  ["digital-twin"],
        "affects":        "Digital twin schema — ISO 23247 defines required asset representation",
        "priority":       "MEDIUM",
        "business_value": "revenue_enabler",
        "check_frequency":"quarterly",
        "opportunity":    "Extend assets table with ISO 23247 mandatory fields (install_date, serial_number)",
        "skip_fast":      True,
    },
    {
        "id":             "rest-idempotency-rfc",
        "group":          "Enterprise Integration",
        "label":          "IETF Idempotency-Key HTTP header RFC status 2025",
        "query":          "IETF idempotency key HTTP header RFC draft 2025 standard",
        "keywords":       ["RFC", "2025", "Idempotency-Key", "header", "standard", "draft"],
        "validator_ids":  ["idempotency"],
        "affects":        "Webhook idempotency — HTTP standard for idempotency keys",
        "priority":       "LOW",
        "business_value": "operational",
        "check_frequency":"quarterly",
        "opportunity":    "Add Idempotency-Key header support to outbound webhook framework",
        "skip_fast":      True,
    },

    # ══════════════════════════════════════════════════════
    # PERFORMANCE / DATABASE
    # ══════════════════════════════════════════════════════

    {
        "id":             "postgresql-17-features",
        "group":          "Performance",
        "label":          "PostgreSQL 17 features and query performance 2025",
        "query":          "PostgreSQL 17 new features performance improvements 2025 Supabase",
        "keywords":       ["PostgreSQL 17", "2025", "performance", "new feature", "incremental sort"],
        "validator_ids":  ["performance", "vector-schema"],
        "affects":        "Query performance, pgvector index efficiency",
        "priority":       "MEDIUM",
        "business_value": "operational",
        "check_frequency":"quarterly",
        "opportunity":    "Enable PostgreSQL 17 incremental sort for logbook analytics queries",
        "skip_fast":      True,
    },
    {
        "id":             "supabase-rls-auth",
        "group":          "Performance",
        "label":          "Supabase Auth + RLS patterns for multi-tenant 2025",
        "query":          "Supabase Auth row level security RLS multi-tenant 2025 patterns JWT",
        "keywords":       ["RLS", "auth.uid", "JWT", "multi-tenant", "2025", "policy"],
        "validator_ids":  ["sso-readiness", "tenant-boundary"],
        "affects":        "SSO migration path — RLS is the next step after Supabase Auth",
        "priority":       "HIGH",
        "business_value": "enterprise_blocker",
        "check_frequency":"monthly",
        "opportunity":    "Design RLS policies for hive_id isolation before Supabase Auth migration",
        "skip_fast":      False,
    },
    {
        "id":             "fastapi-pydantic-v2",
        "group":          "Performance",
        "label":          "FastAPI + Pydantic v2 field aliases and validators 2025",
        "query":          "FastAPI pydantic v2 field alias validator best practices 2025",
        "keywords":       ["pydantic v2", "alias", "field_validator", "2025", "performance"],
        "validator_ids":  ["calc-suite"],
        "affects":        "Python API field alias patterns (4 sync points per calc type)",
        "priority":       "MEDIUM",
        "business_value": "operational",
        "check_frequency":"monthly",
        "opportunity":    "Migrate Python calc API to Pydantic v2 alias_generator for consistent naming",
        "skip_fast":      True,
    },

    # ══════════════════════════════════════════════════════
    # PREDICTIVE ANALYTICS / DIGITAL TWIN
    # ══════════════════════════════════════════════════════

    {
        "id":             "iso13374-condition-monitoring",
        "group":          "Predictive Analytics",
        "label":          "ISO 13374 Machinery Condition Monitoring — 2025 update",
        "query":          "ISO 13374 machinery condition monitoring data processing 2025",
        "keywords":       ["ISO 13374", "2025", "condition monitoring", "MIMOSA", "update"],
        "validator_ids":  ["predictive", "digital-twin"],
        "affects":        "MTBF/MTTR calculations, digital twin health snapshots",
        "priority":       "MEDIUM",
        "business_value": "revenue_enabler",
        "check_frequency":"quarterly",
        "opportunity":    "Align pm_knowledge health_summary fields with ISO 13374 data model",
        "skip_fast":      True,
    },
    {
        "id":             "ml-ops-patterns-2025",
        "group":          "Predictive Analytics",
        "label":          "MLOps data quality and model monitoring patterns 2025",
        "query":          "MLOps data quality validation production AI monitoring 2025 patterns",
        "keywords":       ["2025", "data quality", "drift", "monitoring", "validation", "feature store"],
        "validator_ids":  ["predictive", "vector-schema", "knowledge-freshness"],
        "affects":        "Predictive analytics data quality, embedding freshness monitoring",
        "priority":       "MEDIUM",
        "business_value": "revenue_enabler",
        "check_frequency":"quarterly",
        "opportunity":    "Add embedding drift detection: flag assets not re-embedded in 30+ days",
        "skip_fast":      True,
    },
]


# ── Business value labels ─────────────────────────────────────────────────────
BV_LABELS = {
    "enterprise_blocker": "Enterprise Blocker",
    "revenue_enabler":    "Revenue Enabler",
    "operational":        "Operational",
    "standard_currency":  "Standards",
}

# ── Frequency labels ──────────────────────────────────────────────────────────
FREQ_LABELS = {
    "weekly":    "[WEEKLY]",
    "monthly":   "[MONTHLY]",
    "quarterly": "[QUARTERLY]",
}


# ── DuckDuckGo free search ─────────────────────────────────────────────────────
def ddg_search(query, timeout=15):
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", errors="replace")

        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>',   html, re.DOTALL)
        urls     = re.findall(r'result__url[^>]*>\s*(https?://[^\s<]+)', html)

        def strip_html(s):
            return re.sub(r'<[^>]+>', ' ', s).strip()

        clean_snippets = [strip_html(s)[:200] for s in snippets[:5]]
        clean_titles   = [strip_html(t)[:100] for t in titles[:5]]
        combined = " | ".join(filter(None, clean_titles[:3] + clean_snippets[:3]))
        first_url = urls[0].strip() if urls else ""
        return combined[:600], first_url
    except Exception:
        return "", ""


# ── Score a finding ────────────────────────────────────────────────────────────
def score_finding(topic, text):
    text_l = text.lower()
    found  = [kw for kw in topic["keywords"] if kw.lower() in text_l]
    score  = min(100, len(found) * 20)
    years_in_text = re.findall(r'\b202[3-9]\b', text)
    if years_in_text:
        score = min(100, score + 20)
    if score >= 60:
        assessment = "Strong signal — review immediately"
    elif score >= 30:
        assessment = "Moderate signal — check when relevant"
    else:
        assessment = "Weak signal — file for reference"
    return score, found, assessment


# ── Backlog helpers ───────────────────────────────────────────────────────────
def load_backlog():
    if not os.path.exists(BACKLOG):
        return []
    try:
        with open(BACKLOG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_backlog(items):
    with open(BACKLOG, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def dedup(existing, new_items):
    """Merge new items into existing backlog.
    Preserves status (dismissed/done) set by the user unless score jumps
    significantly (>= 60) — a strong new signal overrides a previous dismiss.
    """
    existing_map = {i["id"]: i for i in existing}
    merged = list(existing)
    existing_ids = {i["id"] for i in existing}

    for item in new_items:
        prev = existing_map.get(item["id"])
        if prev is None:
            merged.append(item)
            existing_ids.add(item["id"])
        else:
            # Preserve user status (dismissed/done) unless signal is very strong
            prev_status = prev.get("status")
            if prev_status and item.get("score", 0) < 60:
                item["status"] = prev_status  # keep dismiss / done / in_progress
            for i, e in enumerate(merged):
                if e["id"] == item["id"]:
                    merged[i] = item
                    break
    return merged


# ── Update platform_health.json ───────────────────────────────────────────────
def update_health(backlog):
    try:
        with open(HEALTH, encoding="utf-8") as f:
            health = json.load(f)
    except Exception:
        return
    health["improvement_backlog"] = {
        "total":        len(backlog),
        "high":         sum(1 for i in backlog if i.get("priority") == "HIGH"   and i.get("score", 0) >= 30),
        "medium":       sum(1 for i in backlog if i.get("priority") == "MEDIUM" and i.get("score", 0) >= 20),
        "low":          sum(1 for i in backlog if i.get("priority") == "LOW"),
        "enterprise_blockers": sum(1 for i in backlog if i.get("business_value") == "enterprise_blocker" and i.get("score", 0) >= 30),
        "revenue_enablers":    sum(1 for i in backlog if i.get("business_value") == "revenue_enabler"    and i.get("score", 0) >= 30),
        "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(HEALTH, "w", encoding="utf-8") as f:
        json.dump(health, f, indent=2)


# ── Platform Opportunity Table ────────────────────────────────────────────────
def print_opportunity_table(high_items):
    """Print a table of platform opportunities from high-signal findings."""
    if not high_items:
        return
    print("\n" + "─" * 72)
    print("  PLATFORM OPPORTUNITY SCAN\n")
    print(f"  {'Opportunity':<42} {'Validator':<20} {'Value':<18} {'Pri'}")
    print(f"  {'─'*42} {'─'*20} {'─'*18} {'─'*4}")
    bv_order = {"enterprise_blocker": 0, "revenue_enabler": 1, "operational": 2, "standard_currency": 3}
    for item in sorted(high_items, key=lambda x: (bv_order.get(x.get("business_value", ""), 4), -x.get("score", 0))):
        opp   = item.get("opportunity", item["label"])[:40]
        val_s = ", ".join(item.get("validator_ids", []))[:18]
        bv    = BV_LABELS.get(item.get("business_value", ""), "")[:16]
        pri   = item.get("priority", "")[:4]
        print(f"  {opp:<42} {val_s:<20} {bv:<18} {pri}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Filter topics by mode
    topic_filter = None
    for a in sys.argv:
        if a.startswith("--topic="):
            topic_filter = a.split("=")[1].lower()

    def include(t):
        if topic_filter:
            return topic_filter in t["group"].lower() or topic_filter in t["id"]
        if SEC_MODE:
            return t["check_frequency"] == "weekly"
        if FAST_MODE:
            return t["check_frequency"] in ("weekly", "monthly") and not t.get("skip_fast")
        return True

    active_topics = [t for t in TOPICS if include(t)]

    mode_label = "SECURITY mode" if SEC_MODE else ("FAST mode" if FAST_MODE else "FULL mode")
    print("\n" + "=" * 72)
    print("  WorkHive Platform Guardian — Continuous Improvement")
    print(f"  {now_str}  |  {mode_label}  |  {len(active_topics)} topics  |  {'DRY RUN' if DRY_RUN else 'WRITE mode'}")
    print("=" * 72)
    print(f"\n  Topics cover {len(set(t['validator_ids'][0] for t in active_topics if t['validator_ids']))} validator clusters\n")

    new_items  = []
    group_seen = set()

    for topic in active_topics:
        if topic["group"] not in group_seen:
            group_seen.add(topic["group"])
            print(f"\n  [{topic['group'].upper()}]")

        freq_tag = FREQ_LABELS.get(topic["check_frequency"], "")
        print(f"  {freq_tag:11s}  {topic['label']:<50}", end="", flush=True)

        if DRY_RUN:
            print("  SKIP (dry-run)")
            score, found, assessment = 0, [], "dry-run"
            snippet, url = "(dry-run — no search performed)", ""
        else:
            snippet, url = ddg_search(topic["query"])
            score, found, assessment = score_finding(topic, snippet)
            priority_marker = {"HIGH": "!!", "MEDIUM": "! ", "LOW": "  "}.get(topic["priority"], "  ")
            print(f"  {priority_marker} score={score:3d}  {len(found)} signal(s)")
            time.sleep(0.5)

        new_items.append({
            "id":             topic["id"],
            "group":          topic["group"],
            "label":          topic["label"],
            "priority":       topic["priority"],
            "business_value": topic.get("business_value", "operational"),
            "check_frequency":topic.get("check_frequency", "quarterly"),
            "score":          score,
            "signals":        found,
            "assessment":     assessment,
            "affects":        topic["affects"],
            "validator_ids":  topic.get("validator_ids", []),
            "opportunity":    topic.get("opportunity", ""),
            "snippet":        snippet[:300],
            "url":            url,
            "query":          topic["query"],
            "checked_at":     now_str,
        })

    # High-signal findings summary
    high_signal = [i for i in new_items if i["score"] >= 40]
    print(f"\n{'=' * 72}")
    print(f"\n  {'FINDINGS (' + str(len(high_signal)) + ')' if high_signal else 'No strong signals found'}\n")

    if high_signal:
        for item in sorted(high_signal, key=lambda x: -x["score"]):
            bv_label = BV_LABELS.get(item.get("business_value", ""), "")
            print(f"  [{item['priority']:6s}] [{bv_label:18s}]  {item['label']}")
            print(f"           Signals:     {', '.join(item['signals'][:5])}")
            print(f"           Opportunity: {item.get('opportunity','')[:65]}")
            print(f"           Validators:  {', '.join(item.get('validator_ids',[]))}")
            if item["url"]:
                print(f"           Source:      {item['url'][:65]}")
            print()

    # Platform Opportunity Table
    print_opportunity_table([i for i in new_items if i["score"] >= 30 or DRY_RUN])

    # Merge and save
    existing = load_backlog()
    merged   = dedup(existing, new_items)

    if not DRY_RUN:
        save_backlog(merged)
        update_health(merged)
        print(f"  Saved {BACKLOG}  ({len(merged)} total items)")
        print(f"  Updated {HEALTH} with backlog summary\n")

    # Stats by business value
    h  = sum(1 for i in merged if i["priority"] == "HIGH"   and i.get("score", 0) >= 30)
    m  = sum(1 for i in merged if i["priority"] == "MEDIUM" and i.get("score", 0) >= 20)
    lo = sum(1 for i in merged if i["priority"] == "LOW")
    eb = sum(1 for i in merged if i.get("business_value") == "enterprise_blocker" and i.get("score", 0) >= 30)
    re_ = sum(1 for i in merged if i.get("business_value") == "revenue_enabler"    and i.get("score", 0) >= 30)
    print(f"  Backlog:  {h} HIGH  {m} MEDIUM  {lo} LOW")
    print(f"  By value: {eb} Enterprise Blockers  {re_} Revenue Enablers\n")
    print(f"  Run modes:")
    print(f"    python improve.py --security   # weekly security check only")
    print(f"    python improve.py --fast       # weekly + monthly topics")
    print(f"    python improve.py              # full quarterly sweep\n")


if __name__ == "__main__":
    main()
