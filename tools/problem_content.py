# -*- coding: utf-8 -*-
"""Problem/solution page content — closes the last open `demand_gap` query.

`demand-reduce-downtime` ("how to reduce unplanned equipment downtime in a factory")
was the one query in prompt_audit_queries.json still marked GAP with no page behind it.
High-intent problem queries are exactly what AI engines answer, and the answer format
they reward is an ordered procedure with numbers attached, not an essay.

Rendered through build_pillar_pages._page(), so it inherits the /learn article template,
schema graph, and every gate the other articles pass.
"""

PROBLEM_PAGES = [
    {
        "slug": "reduce-unplanned-downtime-guide",
        "cta": ("/#join", "Try WorkHive free", "Free at the worker tier, offline-first, built for Philippine plants."),
        "title": "How to Reduce Unplanned Equipment Downtime in a Factory",
        "description": "A four-step, evidence-based path to cutting unplanned downtime: measure it by cause, fix the recurring few at root cause, hold PM compliance above 90%, and monitor the critical assets.",
        "keywords": "reduce unplanned downtime, equipment downtime, downtime reduction, unplanned downtime causes, Pareto downtime analysis, preventive maintenance ROI",
        "section": "Reliability",
        "crumb": "Reduce unplanned downtime",
        "pill": "Reliability & Metrics",
        "h1": "How to reduce unplanned equipment downtime",
        "readmins": 8,
        "answer_first": (
            "Cut unplanned downtime in four steps, in this order: "
            "<strong>(1) measure it by cause</strong> so you know what actually stops the line, "
            "<strong>(2) fix the recurring few at root cause</strong> instead of repeatedly "
            "restoring them, <strong>(3) hold PM compliance above the SMRP benchmark of 90%</strong>, "
            "and <strong>(4) add condition monitoring to the critical assets only</strong>. "
            "Most plants find their downtime hours concentrated in a small minority of assets, "
            "which is why measurement comes first &mdash; and preventive maintenance done on "
            "schedule runs <strong>12-18% cheaper</strong> than the reactive repair it "
            "replaces. Programmes that follow this order typically report a <strong>15 to 25% "
            "reduction in unplanned downtime by month 18</strong>."),
        "sections": [
            {"id": "why-it-persists", "h2": "Why downtime persists in most plants",
             "html": "<p>Unplanned downtime rarely persists because nobody is working hard. It persists because the work is aimed by memory rather than by data. The senior mechanic knows which machine is &ldquo;always a problem,&rdquo; so attention flows there &mdash; but nobody can say how many hours it actually cost last quarter, or whether it was one failure mode or six.</p>"
                     "<p>Three patterns keep it in place: failures get restored but never diagnosed, so the same one returns; preventive work slips quietly because nothing chases it; and the plant has no downtime record, so improvement cannot be proven and therefore cannot be funded.</p>"},
            {"id": "step-1-measure", "h2": "Step 1 — measure downtime by cause",
             "html": "<p>You cannot Pareto what you have not recorded. Capture, for every stoppage: the asset, the start and end time, and the cause. That is enough to rank losses. The discipline that makes it survivable is capturing it <em>at the asset, when it happens</em> &mdash; see <a href=\"/learn/start-digital-logbook-philippine-factory/\">how to start a digital logbook</a>.</p>"
                     "<p>After four weeks you will have a ranked list, and it is almost always lopsided: a small set of assets and failure modes accounts for most of the hours. That list is your work order for the next quarter. Track the result with the metrics in the <a href=\"/learn/maintenance-metrics-reliability-guide/\">maintenance metrics guide</a>.</p>"},
            {"id": "step-2-root-cause", "h2": "Step 2 — fix the recurring few at root cause",
             "html": "<p>Restoring a machine is not the same as fixing it. For each top failure mode, ask what condition produced it: lubrication, alignment, contamination, operating outside design, or a deferred PM. <a href=\"/learn/fmea-worked-example-philippine-bottling-line/\">FMEA</a> gives a structured way to rank by risk, and <a href=\"/learn/reliability-centered-maintenance-philippine-plants/\">RCM</a> picks the right strategy per mode instead of applying the same PM to everything.</p>"
                     "<p>The test of a root-cause fix is simple: the interval to the next identical failure gets longer. If MTBF is flat, the cause was not addressed.</p>"},
            {"id": "step-3-pm-compliance", "h2": "Step 3 — hold PM compliance above 90%",
             "html": "<p>PM compliance is the leading indicator &mdash; it moves before MTBF does. The SMRP benchmark is at least <strong>90%</strong> of preventive tasks completed on time, and <strong>95%+</strong> for critical assets. &ldquo;On time&rdquo; has a precise definition worth knowing: completed by the due date plus 20% of the task's own frequency, capped at 28 days &mdash; so a monthly PM has roughly a six-day window, not a whole month. Below 80% the programme is not functioning; below 90% it is not protective.</p>"
                     "<p>Two rules make it stick: schedule work the crew can actually do (an over-ambitious plan produces 40% compliance and cynicism), and make overdue work visible to a named owner. Start from <a href=\"/learn/free-pm-checklist-templates/\">free PM checklist templates</a> rather than a blank sheet.</p>"},
            {"id": "step-4-condition-monitoring", "h2": "Step 4 — monitor the critical assets only",
             "html": "<p>Condition monitoring is where plants overspend first and benefit last. Applied to the critical few from step 1, it catches failures before they stop the line; applied everywhere, it produces alerts nobody reads.</p>"
                     "<p>Start at the cheapest tier that answers a real question &mdash; phone-based vibration screening and thermography cover a lot of ground before any sensor purchase. See <a href=\"/learn/predictive-maintenance-on-a-budget-philippines/\">predictive maintenance on a budget</a> and set bands using <a href=\"/learn/predictive-alert-thresholds-plants/\">ISO 10816 alert thresholds</a>.</p>"},
            {"id": "what-to-expect", "h2": "What to expect, and in what order",
             "html": "<table><thead><tr><th>Horizon</th><th>What changes</th></tr></thead><tbody>"
                     "<tr><td>Month 1-2</td><td>Downtime recorded by cause; the Pareto is visible for the first time</td></tr>"
                     "<tr><td>Month 3-6</td><td>Top failure modes addressed at root cause; PM compliance climbing toward 90%</td></tr>"
                     "<tr><td>Month 6-12</td><td>MTBF rising on treated assets; condition monitoring on the critical few</td></tr>"
                     "<tr><td>Month 12-18</td><td>Typically 15-25% reduction in unplanned downtime; 35-50% in mature programmes</td></tr>"
                     "</tbody></table>"
                     "<p>The order matters more than the speed. Plants that buy sensors before they have a downtime record almost always end up with data they cannot act on.</p>"},
        ],
        "faqs": [
            ("What causes most unplanned downtime?", "In most plants the hours concentrate in a small minority of assets and a handful of repeating failure modes — commonly lubrication, misalignment, contamination, operating outside design conditions, and deferred preventive work. Recording downtime by cause for four weeks usually makes the concentration obvious."),
            ("How much can unplanned downtime realistically be reduced?", "Programmes that measure first, fix root causes, and hold PM compliance above 90% commonly report a 15 to 25% reduction in unplanned downtime by month 18, with mature programmes reaching 35 to 50%. Treat those as widely-reported industry ranges rather than a published standard — the figure that IS standardised is the SMRP PM-compliance benchmark of 90%."),
            ("Is preventive maintenance actually cheaper than fixing breakdowns?", "Yes, though the honest figure is smaller than the ratios often quoted. The US Department of Energy's O&M Best Practices Guide puts a preventive programme at roughly 12-18% cheaper than running reactive, and a predictive layer adds a further 8-12%. Facilities that lean heavily on reactive work can find savings opportunities above 30-40%. None of that counts lost production, expedited freight, or overtime."),
            ("Do I need sensors to reduce downtime?", "Not to start, and buying them first is the most common mistake. Measurement and PM discipline deliver the early gains; condition monitoring pays off once you know which assets are critical and which failure modes you are hunting."),
            ("What is the single first step?", "Record every stoppage with asset, duration and cause. Without that record you cannot rank losses, prove improvement, or justify spending — and improvement that cannot be proven does not get funded."),
        ],
        "sources": [
            "<a href=\"https://smrp.org/\">SMRP</a>, <strong>Best Practices Metrics, 6th Edition</strong> — PM schedule compliance benchmark 90% (95%+ for critical assets); a PM counts as on time if completed by the due date + 20% of its frequency, capped at 28 days. Downtime-reduction ranges quoted here are widely-reported industry outcomes, not an SMRP-published figure.",
            "<a href=\"https://www.energy.gov/femp/articles/operations-and-maintenance-best-practices-guide-achieving-operational-efficiency\">US Department of Energy / PNNL</a>, <strong>Operations &amp; Maintenance Best Practices Guide, Release 3.0</strong> (preventive vs reactive cost savings: 12-18%; predictive adds 8-12%).",
            "<a href=\"https://www.iso.org/standard/64076.html\">ISO 14224</a>, <strong>Reliability and maintenance data collection</strong>; ISO 10816-3 (vibration severity).",
            "Related: <a href=\"/learn/maintenance-metrics-reliability-guide/\">Maintenance metrics guide</a> &middot; <a href=\"/learn/predictive-maintenance-on-a-budget-philippines/\">Predictive maintenance on a budget</a>.",
        ],
    },
]
