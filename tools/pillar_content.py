# -*- coding: utf-8 -*-
"""Content data for build_pillar_pages.py — the 3 missing cluster pillars (playbook §3.3).
Each pillar: answer-first opener (with a statistic) + sections that link the cluster's existing
/learn articles and the /tools/ calculators + FAQ + cited sources (Princeton GEO triad)."""

PILLARS = [
    # ── Cluster 1: Reliability & Metrics ──────────────────────────────────────
    {
        "slug": "maintenance-metrics-reliability-guide",
        "title": "Maintenance Metrics Guide: OEE, MTBF, MTTR & Reliability for Philippine Plants",
        "description": "The five maintenance metrics every Philippine plant should track — OEE, MTBF, MTTR, availability, and PM compliance — with formulas, worked examples, and free calculators.",
        "keywords": "maintenance metrics, OEE, MTBF, MTTR, availability, PM compliance, reliability KPIs, Philippine plant, SMRP, ISO 14224",
        "section": "Reliability",
        "crumb": "Maintenance metrics guide",
        "pill": "Reliability & Metrics",
        "h1": "Maintenance metrics: OEE, MTBF, MTTR & reliability, explained for Philippine plants",
        "readmins": 9,
        "answer_first": (
            "The five metrics every Philippine plant should track are <strong>OEE</strong> "
            "(Overall Equipment Effectiveness = Availability &times; Performance &times; Quality; "
            "world-class is 85%), <strong>MTBF</strong> (Mean Time Between Failures = operating hours "
            "&divide; number of failures), <strong>MTTR</strong> (Mean Time To Repair = total repair "
            "time &divide; number of repairs), <strong>Availability</strong> (MTBF &divide; (MTBF + MTTR)), "
            "and <strong>PM compliance</strong> (PMs completed on time &divide; PMs scheduled; the SMRP "
            "benchmark is &ge;90%). Together they turn &ldquo;the line keeps breaking&rdquo; into a number "
            "you can act on."),
        "sections": [
            {"id": "why", "h2": "Why maintenance metrics matter",
             "html": "<p>Most Philippine plants run maintenance on memory and firefighting: the senior mechanic knows which pump is &ldquo;always a problem,&rdquo; and everyone reacts when a line stops. The trouble is that memory does not scale, does not transfer when the senior mechanic retires, and cannot be put in a budget request. Metrics fix that. A plant that measures reliability can say &ldquo;this filler cost us 62 hours of downtime last quarter, and 80% of it was the same bearing&rdquo; &mdash; a sentence that unlocks a purchase order.</p>\n      <p>Reliability metrics also standardise language across shifts and disciplines. When maintenance, production, and management all agree that availability means <code>MTBF &divide; (MTBF + MTTR)</code>, the morning meeting stops being an argument about whose fault the downtime was and starts being a decision about where to spend the next peso.</p>"},
            {"id": "oee", "h2": "OEE — Overall Equipment Effectiveness",
             "html": "<p><strong>OEE = Availability &times; Performance &times; Quality.</strong> It is the single number that captures how much saleable output a line actually produced versus its theoretical maximum. Worked example for a bottling line: available 90% of planned time, running at 95% of rated speed, producing 98% good bottles &rarr; OEE = 0.90 &times; 0.95 &times; 0.98 = <strong>83.8%</strong>. World-class is 85%; a typical plant sits at 40&ndash;60%, so the gap is usually enormous and cheap to close.</p>\n      <p>The trap is measuring only one factor. A line that looks 90% &ldquo;available&rdquo; but runs slow and scraps 5% of output is really at ~80% OEE. See the full method in <a href=\"/learn/what-is-oee-how-to-calculate/\">What is OEE and how to calculate it</a>, and read the four maturity stages in <a href=\"/learn/four-phases-maintenance-analytics-philippine-plants/\">the four phases of maintenance analytics</a>.</p>"},
            {"id": "mtbf", "h2": "MTBF and MTTR — the reliability pair",
             "html": "<p><strong>MTBF</strong> measures how <em>reliable</em> an asset is; <strong>MTTR</strong> measures how <em>maintainable</em> it is. A pump that runs 4,000 hours and fails 5 times has MTBF = 4,000 &divide; 5 = <strong>800 hours</strong>. If those five repairs took 40 hours total, MTTR = 40 &divide; 5 = <strong>8 hours</strong>. Push MTBF up with better PM and root-cause fixes; push MTTR down with spares availability, standard work, and good documentation.</p>\n      <p>The two are often confused, which leads to the wrong fix (buying spares when the real problem is repeat failures). The plain-language breakdown is in <a href=\"/learn/mtbf-vs-mttr-for-supervisors/\">MTBF vs MTTR for supervisors</a>.</p>"},
            {"id": "availability", "h2": "Availability and how the metrics chain together",
             "html": "<p><strong>Availability = MTBF &divide; (MTBF + MTTR).</strong> Using the pump above: 800 &divide; (800 + 8) = <strong>99.0%</strong>. Notice that availability is what OEE&rsquo;s first factor comes from &mdash; the metrics are not separate scoreboards, they are one chain: reduce failures (MTBF &uarr;) and speed repairs (MTTR &darr;), and availability, then OEE, then output all rise together.</p>\n      <table><thead><tr><th>Metric</th><th>Formula</th><th>Good target</th></tr></thead><tbody><tr><td>OEE</td><td>Availability &times; Performance &times; Quality</td><td>&ge;85% (world-class)</td></tr><tr><td>MTBF</td><td>Operating hours &divide; failures</td><td>Rising trend</td></tr><tr><td>MTTR</td><td>Repair time &divide; repairs</td><td>Falling trend</td></tr><tr><td>Availability</td><td>MTBF &divide; (MTBF + MTTR)</td><td>&ge;95%</td></tr><tr><td>PM compliance</td><td>PMs on time &divide; PMs scheduled</td><td>&ge;90% (SMRP)</td></tr></tbody></table>"},
            {"id": "pm-compliance", "h2": "PM compliance — the leading indicator",
             "html": "<p>OEE, MTBF, and MTTR are <em>lagging</em> indicators: they tell you what already broke. <strong>PM compliance</strong> &mdash; the percentage of preventive tasks done on schedule &mdash; is the <em>leading</em> indicator that predicts them. The SMRP benchmark is &ge;90% schedule compliance; plants that hold that line see MTBF climb within a quarter. Start with a real checklist, not a spreadsheet that nobody updates: <a href=\"/learn/free-pm-checklist-templates/\">free PM checklist templates</a>.</p>"},
            {"id": "ladder", "h2": "Climbing the reliability ladder: RCM, FMEA, and predictive alerts",
             "html": "<p>Once the basics are measured, the next rungs are analytical. <strong>FMEA</strong> (Failure Mode and Effects Analysis) ranks what to fix first by risk &mdash; see a full <a href=\"/learn/fmea-worked-example-philippine-bottling-line/\">FMEA worked example on a Philippine bottling line</a>. <strong>RCM</strong> (Reliability-Centered Maintenance) then decides the right strategy per failure mode: <a href=\"/learn/reliability-centered-maintenance-philippine-plants/\">RCM for Philippine plants</a>. Finally, <strong>condition-based alert thresholds</strong> catch failures before they happen &mdash; the ISO 10816 vibration bands and how to set them are in <a href=\"/learn/predictive-alert-thresholds-plants/\">predictive alert thresholds</a>.</p>"},
            {"id": "tools", "h2": "Free calculators and next steps",
             "html": "<p>Turn the formulas into numbers with the free WorkHive calculators &mdash; each shows a worked example and works offline: <a href=\"/tools/bearing-life-calculator/\">Bearing Life (L10)</a>, <a href=\"/tools/vibration-isolation-calculator/\">Vibration Isolation</a>, and the full <a href=\"/learn/free-engineering-calculators-philippine-plants/\">engineering calculator suite</a>. To start recording the raw data these metrics need, begin with a <a href=\"/learn/start-digital-logbook-philippine-factory/\">digital logbook</a> &mdash; undocumented downtime cannot be measured, and unmeasured downtime never gets fixed.</p>"},
        ],
        "faqs": [
            ("What is a good OEE for a Philippine plant?", "85% is considered world-class OEE. Most plants start at 40 to 60%, so there is usually a large, low-cost gap to close by attacking availability losses first (unplanned downtime and changeovers), then speed losses, then quality losses."),
            ("What is the difference between MTBF and MTTR?", "MTBF (Mean Time Between Failures) measures reliability — how long an asset runs before it fails, calculated as operating hours divided by the number of failures. MTTR (Mean Time To Repair) measures maintainability — how long a repair takes, calculated as total repair time divided by the number of repairs. You raise MTBF with better PM; you lower MTTR with spares and standard work."),
            ("How do I calculate availability?", "Availability = MTBF divided by (MTBF + MTTR). For a pump with MTBF 800 hours and MTTR 8 hours, availability is 800 / 808 = 99.0%. This is the same availability figure that feeds the first factor of OEE."),
            ("What PM compliance should I target?", "The Society for Maintenance and Reliability Professionals (SMRP) benchmark is at least 90% schedule compliance — the percentage of preventive maintenance tasks completed on or before their due date. It is the leading indicator that drives MTBF and OEE upward."),
            ("Do I need software to track these metrics?", "No. You can start with a disciplined logbook and a checklist. The value is in consistent recording, not the tool. WorkHive is a free, offline-first platform that captures the downtime, repair, and PM data these metrics need without any subscription."),
        ],
        "sources": [
            "Society for Maintenance and Reliability Professionals (SMRP), <strong>Best Practices Metrics (5.4 PM Compliance, 5.1 OEE)</strong>.",
            "ISO 14224, <strong>Collection and exchange of reliability and maintenance data for equipment</strong>.",
            "ISO 10816-3, <strong>Mechanical vibration — evaluation of machine vibration</strong>.",
            "Related WorkHive guides: <a href=\"/learn/what-is-oee-how-to-calculate/\">OEE</a> &middot; <a href=\"/learn/mtbf-vs-mttr-for-supervisors/\">MTBF vs MTTR</a> &middot; <a href=\"/learn/reliability-centered-maintenance-philippine-plants/\">RCM</a>.",
        ],
    },
    # ── Cluster 2: Getting Started / Digital Maintenance ──────────────────────
    {
        "slug": "start-digital-maintenance-guide",
        "title": "How to Start Digital Maintenance in a Philippine Factory (Zero-Budget Guide)",
        "description": "A four-step, zero-budget path to digital maintenance for a small Philippine plant — digital logbook, asset register, PM scheduling, and shift handover — with free templates and a 30-day rollout.",
        "keywords": "digital maintenance, digital logbook, asset register, CMMS, preventive maintenance schedule, shift handover, small factory Philippines, free CMMS",
        "section": "Getting Started",
        "crumb": "Start digital maintenance",
        "pill": "Getting Started",
        "h1": "How to start digital maintenance in a Philippine factory, step by step",
        "readmins": 8,
        "answer_first": (
            "To go from spreadsheets to digital maintenance, do four things in order: "
            "(1) start a <strong>digital logbook</strong> so every job is recorded the day it happens; "
            "(2) build an <strong>asset register</strong> using ISO 14224 hierarchy so every record is "
            "tagged to equipment; (3) turn recurring jobs into a <strong>preventive-maintenance schedule</strong>; "
            "and (4) run a structured <strong>shift handover</strong> so nothing is lost between crews. "
            "A small plant can complete all four in about 30 days at zero software cost &mdash; and studies "
            "show preventive maintenance costs 3&ndash;9 times less than the reactive repairs it prevents."),
        "sections": [
            {"id": "why", "h2": "Why digitise maintenance at all",
             "html": "<p>The spreadsheet a plant inherits from a departed engineer is a liability: the formulas drift, the tabs multiply, and the one person who understood it is gone. Digital maintenance replaces that with structured, searchable, portable records. The payoff is not fancy dashboards &mdash; it is that a technician can answer &ldquo;when did we last replace this seal, and why?&rdquo; in ten seconds instead of never. Preventive maintenance done on a schedule typically costs <strong>3 to 9 times less</strong> than the reactive breakdown it prevents, which is why the sequence below front-loads recording and scheduling.</p>"},
            {"id": "logbook", "h2": "Step 1 — the digital logbook",
             "html": "<p>Everything starts with capture. If a job is not written down the day it happens, the data is gone. A digital logbook takes 20 seconds per entry and immediately makes downtime, parts used, and repeat failures visible. The full rollout &mdash; including how to get technicians to actually use it &mdash; is in <a href=\"/learn/start-digital-logbook-philippine-factory/\">start a digital logbook in a Philippine factory</a>. For plants with spotty Wi-Fi, an offline-first logbook that syncs later is essential; that is a core WorkHive design choice.</p>"},
            {"id": "assets", "h2": "Step 2 — the asset register (ISO 14224)",
             "html": "<p>A logbook is only useful if every entry is tagged to a specific asset. That means building an <strong>asset register</strong> &mdash; a hierarchy of plant &rarr; system &rarr; equipment &rarr; component, following the ISO 14224 taxonomy so your data is comparable to industry benchmarks. You do not need a consultant or a budget; the step-by-step method is in <a href=\"/learn/building-asset-register-zero-budget/\">building an asset register on zero budget</a>.</p>"},
            {"id": "pm", "h2": "Step 3 — the preventive-maintenance schedule",
             "html": "<p>With assets and history in place, convert the recurring jobs (lubrication, inspections, filter changes) into a real PM schedule with due dates and owners. Track completion as PM compliance &mdash; aim for the SMRP &ge;90% benchmark. Start from proven <a href=\"/learn/free-pm-checklist-templates/\">free PM checklist templates</a> rather than a blank sheet, and read how the metrics prove the schedule is working in the <a href=\"/learn/maintenance-metrics-reliability-guide/\">maintenance metrics guide</a>.</p>"},
            {"id": "handover", "h2": "Step 4 — structured shift handover",
             "html": "<p>Most plant knowledge is lost in the 5 minutes between shifts. A structured handover &mdash; open work, abnormal conditions, pending parts &mdash; closes that gap and is the cheapest reliability win available. Use the ready-made format in <a href=\"/learn/maintenance-shift-handover-template/\">the maintenance shift handover template</a>. Voice capture in Tagalog or Taglish removes the &ldquo;I&rsquo;ll write it later&rdquo; excuse: see <a href=\"/learn/voice-to-text-maintenance-philippine-plant-floor/\">voice-to-text on the plant floor</a>.</p>"},
            {"id": "rollout", "h2": "The 30-day rollout",
             "html": "<p><strong>Week 1:</strong> logbook live, every job recorded. <strong>Week 2:</strong> asset register built for the critical line. <strong>Week 3:</strong> PM schedule loaded for those assets. <strong>Week 4:</strong> shift handover formalised and the first metrics reviewed. Do it on one critical line first, prove the value, then expand &mdash; a full-plant big-bang almost always stalls. Every step above uses free WorkHive tools, so the only cost is discipline.</p>"},
        ],
        "faqs": [
            ("Do I need to buy a CMMS to start digital maintenance?", "No. WorkHive is a free, offline-first maintenance platform, so a small plant can run a digital logbook, asset register, PM scheduler, and shift handover at zero software cost. The sequence and discipline matter more than the price of the tool."),
            ("What is the first step to digital maintenance?", "Start a digital logbook so every job is recorded the day it happens. Without captured data, none of the later steps — asset register, PM schedule, metrics — have anything to work with."),
            ("How long does it take a small factory to go digital?", "About 30 days if you focus on one critical line: logbook in week 1, asset register in week 2, PM schedule in week 3, and shift handover plus first metrics review in week 4. Then expand line by line rather than attempting the whole plant at once."),
            ("Why use ISO 14224 for the asset register?", "ISO 14224 gives a standard plant-to-component hierarchy and failure taxonomy, so your reliability data is structured consistently and can be compared against industry benchmarks instead of being trapped in one plant's ad-hoc naming."),
            ("Does it work if the plant floor has no reliable Wi-Fi?", "Yes, if the tool is offline-first. WorkHive captures entries locally and syncs when a connection returns, so technicians never lose data on the floor — a key requirement for Philippine plants with patchy coverage."),
        ],
        "sources": [
            "ISO 14224, <strong>Collection and exchange of reliability and maintenance data for equipment</strong>.",
            "SMRP, <strong>Best Practices Metric 5.4 (PM Compliance)</strong>.",
            "US Department of Energy, <strong>Operations &amp; Maintenance Best Practices Guide</strong> (preventive vs reactive cost ratio).",
            "Related WorkHive guides: <a href=\"/learn/start-digital-logbook-philippine-factory/\">Digital logbook</a> &middot; <a href=\"/learn/building-asset-register-zero-budget/\">Asset register</a> &middot; <a href=\"/learn/maintenance-shift-handover-template/\">Shift handover</a>.",
        ],
    },
    # ── Cluster 3: PH Compliance ──────────────────────────────────────────────
    {
        "slug": "ph-plant-compliance-guide",
        "title": "Philippine Plant Compliance Guide: DOLE OSHS, LOTO & RA 11285 Records",
        "description": "How Philippine plants meet DOLE OSHS, lockout/tagout (DO 198-18), and RA 11285 energy-efficiency requirements — and how a digital audit trail proves compliance during an inspection.",
        "keywords": "DOLE OSHS, lockout tagout, DO 198-18, RA 11285, energy efficiency, DENR, Philippine plant compliance, audit trail, permit to work, DOLE inspection",
        "section": "Compliance",
        "crumb": "PH plant compliance",
        "pill": "PH Compliance",
        "h1": "Philippine plant compliance: DOLE OSHS, LOTO, and RA 11285, proven by records",
        "readmins": 8,
        "answer_first": (
            "Three regimes cover most Philippine plant maintenance compliance: "
            "<strong>DOLE OSHS</strong> (the Occupational Safety and Health Standards, made mandatory and "
            "penalised under RA 11058 and DO 198-18) requires documented safety procedures and training; "
            "<strong>lockout/tagout</strong> under the same DO 198-18 requires a written, auditable "
            "energy-isolation procedure for every maintenance intervention; and <strong>RA 11285</strong> "
            "(the Energy Efficiency and Conservation Act) requires designated establishments to report "
            "energy use and run a conservation programme. In every case an inspector asks the same thing "
            "&mdash; <em>show me the records</em> &mdash; and a dated digital audit trail is the fastest "
            "way to pass. RA 11058 penalties for wilful violations reach <strong>&#8369;100,000 per day</strong>."),
        "sections": [
            {"id": "oshs", "h2": "DOLE OSHS and the audit trail",
             "html": "<p>The Occupational Safety and Health Standards are no longer advisory: RA 11058 and its IRR, DO 198-18, make them mandatory and set administrative fines of up to <strong>&#8369;100,000 per day</strong> for wilful violations. What an inspector actually checks is documentation &mdash; safety induction records, equipment inspection logs, incident reports, and permits. A digital logbook that timestamps every entry turns a frantic pre-inspection scramble into a search box. The full method is in <a href=\"/learn/dole-iso-audit-trail-from-logbook/\">building a DOLE/ISO audit trail from your logbook</a>.</p>"},
            {"id": "loto", "h2": "Lockout/tagout (LOTO) under DO 198-18",
             "html": "<p>Every maintenance task that exposes a worker to stored or live energy needs a documented lockout/tagout procedure &mdash; the isolation points, the sequence, the verification, and who signed off. LOTO is one of the highest-liability areas in a plant because the failure mode is a fatality, and it is one of the first things a DOLE inspector examines. Use the ready-made procedure and permit format in <a href=\"/learn/loto-procedures-dole-oshs-template/\">LOTO procedures and DOLE OSHS template</a>. Keep each completed permit in the record &mdash; a LOTO you performed but cannot prove is, to an auditor, a LOTO you did not perform.</p>"},
            {"id": "ra11285", "h2": "RA 11285 — energy efficiency reporting",
             "html": "<p>The Energy Efficiency and Conservation Act (RA 11285) requires <em>designated establishments</em> &mdash; those above defined energy-consumption thresholds &mdash; to appoint an energy manager, report annual energy consumption to the Department of Energy, and run a conservation programme. Maintenance is central: well-maintained motors, compressors, and steam systems are the single largest lever on industrial energy use. The plant-readiness checklist is in <a href=\"/learn/ra-11285-energy-efficiency-plant-checklist/\">the RA 11285 energy-efficiency checklist</a>, and the design side is covered by the free <a href=\"/tools/power-factor-correction-calculator/\">power factor correction</a> and <a href=\"/tools/compressed-air-calculator/\">compressed air</a> calculators.</p>"},
            {"id": "why-digital", "h2": "Why digital records win inspections",
             "html": "<p>Paper logbooks fail inspections in predictable ways: entries are missing, dates are ambiguous, the book is at the other end of the plant, or the one legible copy walked out with a resigned supervisor. A digital audit trail is timestamped, searchable, tamper-evident, and backed up. When an inspector asks for the last six months of LOTO permits or PM completions, the answer is a filtered list, not a storeroom search. This is the same &ldquo;documented work compounds&rdquo; principle behind the <a href=\"/learn/skill-matrix-for-maintenance-technicians/\">skill matrix</a> and the <a href=\"/learn/maintenance-metrics-reliability-guide/\">maintenance metrics guide</a>.</p>"},
            {"id": "tools", "h2": "Compliance toolkit",
             "html": "<p>Start the audit trail with a <a href=\"/learn/start-digital-maintenance-guide/\">digital maintenance rollout</a>, keep LOTO and permit records in the logbook, and use the free <a href=\"/learn/free-engineering-calculators-philippine-plants/\">engineering calculators</a> for the design-compliance side (electrical per PEC 2017, fire per NFPA, energy per RA 11285). Every WorkHive record carries a date stamp and the standard it references, which is exactly the form an auditor wants.</p>"},
        ],
        "faqs": [
            ("Is DOLE OSHS mandatory for a small plant?", "Yes. Republic Act 11058 and its implementing rules (DO 198-18) made the Occupational Safety and Health Standards mandatory for all workplaces, with administrative fines of up to 100,000 pesos per day for wilful violations. Documentation — training, inspections, permits — is what inspectors check."),
            ("What records prove lockout/tagout compliance?", "A written LOTO procedure per equipment (isolation points, sequence, verification) plus a completed, signed permit for each intervention. A digital logbook that timestamps and stores each permit makes them retrievable on demand during a DOLE inspection."),
            ("Who must comply with RA 11285?", "Designated establishments — those whose annual energy consumption exceeds the thresholds in the Energy Efficiency and Conservation Act — must appoint a certified energy manager, report annual consumption to the Department of Energy, and run a conservation programme. Good maintenance of motors, compressors, and steam systems is the largest practical lever."),
            ("Can a paper logbook pass a DOLE inspection?", "It can, but it fails often: missing entries, ambiguous dates, and records that cannot be located quickly. A timestamped, searchable digital audit trail passes far more reliably because the inspector's request becomes a filtered search instead of a storeroom hunt."),
            ("Does WorkHive help with compliance reporting?", "Yes. WorkHive timestamps every logbook entry, PM completion, and permit, and tags records to the applicable standard, producing the dated, searchable audit trail that DOLE OSHS, LOTO, and RA 11285 inspections require — at no software cost."),
        ],
        "sources": [
            "Republic Act 11058 and DOLE <strong>Department Order 198-18</strong> (OSH Standards, penalties, lockout/tagout).",
            "Republic Act 11285, <strong>Energy Efficiency and Conservation Act</strong>, and DOE implementing rules.",
            "DOLE, <strong>Occupational Safety and Health Standards (OSHS)</strong>, as amended.",
            "Related WorkHive guides: <a href=\"/learn/dole-iso-audit-trail-from-logbook/\">DOLE/ISO audit trail</a> &middot; <a href=\"/learn/loto-procedures-dole-oshs-template/\">LOTO procedures</a> &middot; <a href=\"/learn/ra-11285-energy-efficiency-plant-checklist/\">RA 11285 checklist</a>.",
        ],
    },
]
