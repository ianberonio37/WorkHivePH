"""
Backfill missing meta tags (description / og:title / og:image / canonical)
across the canonical 30-page inventory. Derives content from each page's
<title> tag; uses a shared og:image when absent.

Idempotent: only inserts tags that don't already exist on the page.
Run once to tighten the meta-description-coverage baseline from 83 -> 0.
"""
from __future__ import annotations
import re
import sys
import io
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

DEFAULT_OG_IMAGE = "https://workhiveph.com/brand_assets/og-social.png"

DEFAULT_DESCRIPTIONS = {
    "hive.html":             "Real-time hive dashboard for industrial maintenance teams. Track PM compliance, risk alerts, and team activity in one view.",
    "logbook.html":           "Industrial maintenance logbook. Log breakdowns, capture root causes, and build a searchable fault knowledge base.",
    "inventory.html":         "Spare parts inventory tracker for industrial maintenance. Low-stock alerts, reorder points, and consumption history.",
    "pm-scheduler.html":      "Preventive maintenance scheduler. Track overdue PMs, due-this-week tasks, and compliance against SMRP standards.",
    "analytics.html":         "Maintenance analytics: MTBF, MTTR, OEE, PM compliance trends with ISO 14224 / ISO 22400-2 / SMRP-aligned formulas.",
    "analytics-report.html":  "Print-ready maintenance analytics report. PDF-friendly layout with all 4 KPI phases + AI action plan + sign-off block.",
    "skillmatrix.html":       "Worker skill matrix for industrial maintenance teams. Track certifications, training gaps, and badge progress per technician.",
    "community.html":         "WorkHive community for Filipino industrial maintenance practitioners. Share fault patterns, ask questions, earn XP.",
    "public-feed.html":       "Public feed of industrial maintenance posts from WorkHive members across the Philippines.",
    "marketplace.html":       "Marketplace for industrial parts, training, and maintenance jobs. Trusted sellers vetted via Stripe Connect.",
    "marketplace-seller.html":"Seller dashboard for the WorkHive marketplace. Manage listings, inquiries, orders, and payouts.",
    "dayplanner.html":        "Day planner for industrial maintenance technicians. Schedule jobs against your hive's PM and risk priorities.",
    "engineering-design.html":"Engineering calculations: piping, electrical, thermal, mechanical sizing tools with PEC / ASHRAE / ASME alignment.",
    "assistant.html":         "AI maintenance assistant. Ask Zaniah or Hezekiah about your hive's data, get cited answers grounded in canonical KPIs.",
    "report-sender.html":     "Send maintenance reports to stakeholders. PDF delivery via Resend; recipient list per hive.",
    "platform-health.html":   "Platform health monitor: edge function latency, AI cost log, canonical drift, and uptime indicators.",
    "project-manager.html":   "Project management for industrial shutdowns and overhauls. Critical-path tracking, daily progress, predecessor links.",
    "integrations.html":      "CMMS / ERP integrations: SAP PM, IBM Maximo, OPC-UA / MQTT sensors, REST webhooks, SSO/SAML providers.",
    "ph-intelligence.html":   "Philippine Industrial Maintenance Intelligence Report. Monthly anonymized benchmarking across Filipino plants.",
    "project-report.html":    "Project shutdown / overhaul report. Critical-path completion, cost vs budget, risk register, sign-off.",
    "predictive.html":        "Predictive maintenance dashboard. Risk-tier ranking, Weibull MTBF, days-until-failure forecasts.",
    "ai-quality.html":        "AI quality + ROI for WorkHive. Eval scores, schema compliance, user-feedback rates, monthly cost.",
    "plant-connections.html": "Plant integration configs: gateway audit log, SSO providers, sensor topic map, retention policies.",
    "achievements.html":      "WorkHive worker achievements and badges. XP per skill domain, leaderboard, and progress tracking.",
    "asset-hub.html":         "Asset hub: 360 view per equipment with logbook, PMs, parts, edges, risk score, and reliability stats.",
    "shift-brain.html":       "AI shift brain: pre-generated shift plan with risk tops, PMs due, carry-forward items, parts to stage.",
    "alert-hub.html":         "Alert hub for supervisors: critical risk, anomaly engine, AMC briefings, parts staging recommendations.",
    "audit-log.html":         "Hive audit log: every CRUD + approval + permission change with actor, before/after, and timestamp.",
    "voice-journal.html":     "Voice-first journal for field workers. Speak entries, get private semantic recall across past shifts.",
}

TITLE_RE = re.compile(r"""<title[^>]*>(?P<t>[^<]+)</title>""", re.IGNORECASE)


def _slug_from_title(title: str) -> str:
    return title.replace("|", "·").strip()


def main() -> int:
    changed = 0
    for name in PAGES:
        page = ROOT / name
        if not page.exists():
            continue
        body = page.read_text(encoding="utf-8", errors="replace")
        original = body

        # Extract title for og:title / canonical use
        tm = TITLE_RE.search(body)
        title = tm.group("t").strip() if tm else name.replace(".html", "")
        og_title = _slug_from_title(title)
        canonical_url = "https://workhiveph.com/workhive/" + name

        # ── description ──
        desc_text = DEFAULT_DESCRIPTIONS.get(name) or f"{og_title} on WorkHive — free industrial maintenance tools for Filipino workers."
        if not re.search(r"""<meta\s+name=['"]description['"]""", body, re.IGNORECASE):
            tag = f'  <meta name="description" content="{desc_text}" />\n'
            body = re.sub(r"</title>", f"</title>\n{tag.rstrip()}", body, count=1, flags=re.IGNORECASE)

        # ── og:title ──
        if not re.search(r"""<meta\s+property=['"]og:title['"]""", body, re.IGNORECASE):
            tag = f'  <meta property="og:title" content="{og_title}" />\n'
            body = re.sub(r"(<meta\s+name=['\"]description[^>]+>)",
                          lambda m: m.group(1) + "\n" + tag.rstrip(), body, count=1)

        # ── og:image ──
        if not re.search(r"""<meta\s+property=['"]og:image['"]""", body, re.IGNORECASE):
            tag = f'  <meta property="og:image" content="{DEFAULT_OG_IMAGE}" />\n'
            body = re.sub(r"(<meta\s+property=['\"]og:title[^>]+>)",
                          lambda m: m.group(1) + "\n" + tag.rstrip(), body, count=1)

        # ── canonical ──
        if not re.search(r"""<link\s+rel=['"]canonical['"]""", body, re.IGNORECASE):
            tag = f'  <link rel="canonical" href="{canonical_url}" />\n'
            body = re.sub(r"(<meta\s+property=['\"]og:image[^>]+>)",
                          lambda m: m.group(1) + "\n" + tag.rstrip(), body, count=1)

        if body != original:
            page.write_text(body, encoding="utf-8")
            changed += 1
            print(f"  + {name}")

    print(f"\nUpdated {changed} pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
