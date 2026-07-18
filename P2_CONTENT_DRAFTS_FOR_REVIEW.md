# P2 Content Drafts — for Ian's voice review

_Generated 2026-06-30 by the `p2-content-drafts` workflow (6 grounded answer-first openers + 1 comparison table, each adversarially verified). These are DRAFTS, NOT applied to the live articles — article voice stays yours. Approve / edit, then I (or you) inject the approved opener as the first paragraph under each article's H1 and re-run `extractability_gate` to flip its `answer_first` count toward 0._

## The 6 answer-first openers (the articles `extractability_gate` flagged as lacking one)

### joining-and-growing-your-hive  ·  51w  ·  verify: PASS

**Core question:** What is a WorkHive hive, and how do I join one or use it on my own?

**Draft opener:**

> A WorkHive hive is your plant's isolated workspace holding its assets, logbook, PM schedules, and people. Use it solo, kept private to you, or join a plant hive once a supervisor approves your request. Four role levels control access, and Supabase Row-Level Security keeps every other hive's data fully out of reach.

<sub>Grounded in: Grounded on the existing "Short answer" block (lines 237-239) and body sections: "What a hive is, in concrete terms" (hive holds People/Assets/History/Schedules), "Solo mode" (private personal hive of one), "How to join an existing plant hive" (supervisor approves the request), "The 4 role levels" heading and table, and "Data isolation between hives" plus the Sources list (Supabase Row-Level Secur</sub>

### loto-procedures-dole-oshs-template  ·  48w  ·  verify: PASS

**Core question:** How do I create a Lock-Out Tag-Out (LOTO) procedure for my equipment that complies with DOLE OSHS Rule 1063?

**Draft opener:**

> To create a compliant LOTO procedure, write one from the DOLE OSHS Rule 1063 template and run the 7-step lockout sequence on each machine, like a 480V Pump P-204B. Sign-off and an audit trail prove it was followed. In the Philippines, non-compliance can cost fines of up to PHP 180,000.

<sub>Grounded in: Grounded on the body's structure and claims: the "LOTO Procedure Template based on DOLE OSHS Rule 1063" heading (line 194); the 7-step lockout sequence list (lines 201-209) explicitly named throughout; the recurring "480V Pump P-204B" worked example (lines 200, 214-217); the "Sign-off Requirements and Audit Log" section (lines 218-222) where the planner/shift in-charge verify and the Audit Log kee</sub>

### reliability-centered-maintenance-philippine-plants  ·  54w  ·  verify: PASS

**Core question:** What is Reliability-Centered Maintenance and how do I use it to cut downtime and costs in a Philippine plant?

**Draft opener:**

> Reliability-Centered Maintenance prioritizes plant upkeep by failure consequence and P-F interval, so you fix what actually causes downtime instead of servicing everything on a fixed calendar. For a Cabuyao bottling line where a pump stoppage costs PHP 180,000 per hour, RCM targets that risk first, and it aligns with DOLE OSHS proactive-maintenance guidelines.

<sub>Grounded in: Grounded on the "What is RCM?" section (line 191: "not all equipment failures are equal and that some failures have more significant consequences than others"), the "P-F Intervals" section (line 210, defining the P-F interval), the worked example (line 208: a Cabuyao bottling-line pump failure causes "a loss of PHP 180,000 per hour"; lines 219-223 on Pump P-204B), and the FAQ (line 237: "RCM align</sub>

### sensor-cmms-gateway-operations  ·  59w  ·  verify: PASS

**Core question:** How do I actually operate the edge gateway that bridges my plant's OT sensors and CMMS to WorkHive day to day?

**Draft opener:**

> Operate the Plant Connections gateway daily, not install-and-forget. Three things keep it reliable: a 5-minute edge-gateway health check each shift, a current sensor inventory with health status, and an OT/IT cybersecurity boundary (built on ISA/IEC 62443) that IT and reliability both signed off. Skip the check and gateway problems surface 6 to 18 hours late, as missing alerts.

<sub>Grounded in: The answer-first summary block (line 288) and the three section bodies: "Daily 5-minute gateway health check" (lines 310-313), "Sensor inventory and health rotation" (lines 314-317), and "OT/IT cybersecurity boundary" (lines 318-321). The "6 to 18 hours late" consequence is stated verbatim at line 313 and in the FAQ (line 335). The IEC 62443 reference is in the Sources section (line 343). The "IT </sub>

### skill-matrix-for-maintenance-technicians  ·  50w  ·  verify: PASS

**Core question:** How do I build a skill matrix for maintenance technicians (and the wider industrial team)?

**Draft opener:**

> Build a skill matrix as a grid of every worker against every required competency, scoring each cell on a 4-level scale (1 aware, 2 assisted, 3 independent, 4 instructor) drawn from ISO 18404. Assess each cell with the 3-input rule: certificates, tagged logbook history, and a Level 4 practical sign-off.

<sub>Grounded in: Grounded on the H1 ("How to build a skill matrix for industrial workers") and the body. The grid definition + 4-level scale comes from the "#four-levels" section and FAQ ("A 4-level scale works well... Level 1 (aware)... Level 4 (instructor)"). The ISO 18404:2015 reference is in the Sources list as "the source for the 4-level competency scale model adapted here." The 3-input rule and its three inp</sub>

### spare-parts-inventory-philippine-plants  ·  54w  ·  verify: PASS

**Core question:** How do I run a spare parts inventory in a Philippine plant so the right part is on the shelf when a technician needs it?

**Draft opener:**

> Run your spare parts inventory on three disciplines: ABC classification, FIFO on every shelf, and reorder points built from real usage history (the APICS/ASCM CPIM methods this guide uses). It matters because 40 to 50 percent of MTTR in Philippine plants is just waiting for the part to arrive, and a well-run storeroom cuts that.

<sub>Grounded in: Grounded on the article's own "Short answer" block (lines 301-303) and the three H2 sections it names: "ABC analysis explained" (#abc-analysis), "FIFO discipline (it is paint, not software)" (#fifo), and "The reorder point formula" (#reorder-point). The "40 to 50 percent of MTTR is parts-waiting" claim is stated verbatim in the MTTR-link section (line 402) and the FAQ (line 448). The APICS/ASCM CP</sub>

---

### Correction to apply before publishing `spare-parts-inventory-philippine-plants`

The adversarial verifier flagged an **attribution overreach**: the draft's parenthetical `(the APICS/ASCM CPIM methods this guide uses)` reads as crediting ALL THREE disciplines (ABC, FIFO, reorder points) to APICS/ASCM CPIM. But the article attributes CPIM only to **ABC classification + reorder-point formulas** — FIFO is framed as a non-software, paint-on-the-shelf discipline, not a CPIM method. **Fix:** scope the parenthetical, e.g.:

> Run your spare parts inventory on three disciplines: ABC classification, FIFO on every shelf, and reorder points built from real usage history (ABC and reorder points follow APICS/ASCM CPIM methods). It matters because 40 to 50 percent of MTTR in Philippine plants is just waiting for the part to arrive, and a well-run storeroom cuts that.

---

## Comparison table — WorkHive (free) vs a typical paid CMMS

_For a Filipino maintenance team, WorkHive covers the daily essentials (logbook, PM scheduling, engineering calculators, mobile and voice capture) for free, where a typical paid CMMS charges per seat and asks for a multi-week onboarding project first._

| Capability | WorkHive (free) | Typical paid CMMS |
|---|---|---|
| Cost to run a plant | Free to use, no per-seat fee. A whole crew (technicians, supervisors, engineers) can be on it without the headcount math. | Often around $20 to $50 per user per month, billed in USD. For a 20-person team that is a real PHP line item every month before you log a single repair. |
| Maintenance logbook | Digital Maintenance Logbook is the foundation layer: every repair, failure and fix recorded, and it feeds the dashboard, handover, PM and AI assistant. | Work-order or logbook module included, but usually only on a paid tier and behind the per-seat license. |
| PM scheduling | PM Checklist (PM Scheduler) plans preventive work so PMs do not pile up, and each completed PM flows back into the logbook and dashboard. | Preventive maintenance scheduling is a core feature, generally available only on higher-priced plans. |
| Engineering calculators | Built-in Engineering Design Calculator runs calcs to Philippine engineering standards and saves each result as a permanent reference. Bundled at no cost. | Engineering and design calculators are rarely part of a CMMS. Teams reach for separate paid tools or spreadsheets. |
| Mobile and voice capture | Log entries by typing or by voice straight from the plant floor (voice transcribe and voice command), so a technician with gloves and a phone can still record the fix. | Mobile apps exist on most paid platforms, but voice-to-text logging is uncommon and often an add-on. |
| Onboarding time | Sign up and start logging the same day, with no implementation project. The free tier is the working product, not a trial. | Typically weeks of onboarding, data migration and configuration, sometimes a paid implementation package before go-live. |
| DOLE / ISO audit trail | Audit Log and Compliance records every supervisor and worker action with timestamp and actor, ready for ISO or regulator review (DOLE OSHS, ISO audits). | Audit logging is usually reserved for enterprise tiers and priced accordingly. |
| Predictive and AI | Predictive Analytics scores assets by failure risk (Weibull, P-F intervals, FMEA) with Auto-Staging of parts, plus an AI assistant that gets smarter as the logbook grows. Included free. | Predictive and AI modules are typically premium upsells on top of the base per-seat license. |
| Connect to existing CMMS | CMMS Integrations offer two-way sync with SAP PM, IBM Maximo and Fiix, so a plant can adopt WorkHive without abandoning its current system. | Integrations are often professional-services work, billed as a separate paid project. |

<sub>Grounded in: Every WorkHive cell maps to a real catalog feature in platform_catalog.json: Cost = the platform's free-tier positioning (free industrial-maintenance platform); Maintenance logbook = id 'logbook' ("Foundation layer... recorded by typing, by voice, or by voice command"); PM scheduling = id 'pm-scheduler' / PM Checklist ("Prevention layer... each completed PM feeds the logbook, the dashboard"); Engineering calculators = id 'engineering-design' ("Every calculation done to Philippine engineering sta</sub>

> Note: the 'Typical paid CMMS' figures are deliberately GENERIC (no vendor named, no price claimed as verified) — direction-credible category facts, per the evidence-honesty discipline.
