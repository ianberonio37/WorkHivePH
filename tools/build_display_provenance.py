#!/usr/bin/env python3
"""
build_display_provenance.py  --  Phase E (E2) of the INTERACTIVE_LINEAGE_ROADMAP.

Turns Phase B's resolved anchor chains into a SLIM, client-consumable map that
powers the "where did this come from?" provenance hover on every page.

Reuse-first: composes display_anchor_sources.json (Phase B) + display_ladder.json
(Phase E1) verbatim — no new parsing. Only RESOLVED anchors get a provenance entry
(an unresolved anchor has no canonical chain to show; it's the E3 residual).

OUT: display_provenance.json
       { "<page.html>": { "<element-id>": {
           "rung": "predictive", "via": "formula_contract",
           "label": "Risk Score (composite, 6-factor)",
           "lines": ["Source: Risk Score (composite, 6-factor)",
                     "Inputs: pm_overdue, repeat_fault, ...",
                     "Standard: WorkHive ... rubric",
                     "Reads: v_risk_truth"] } } }
Run: python tools/build_display_provenance.py
"""
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "display_anchor_sources.json")
LAD = os.path.join(ROOT, "display_ladder.json")
OUT = os.path.join(ROOT, "display_provenance.json")

RESOLVED = ("RESOLVED", "RESOLVED_KPI", "RESOLVED_JS", "RESOLVED_VERIFIED")

# ── USER-VOICE translation (feedback_provenance_user_voice_not_internals) ──────
# A "where did this come from?" hover a maintenance worker reads must NEVER show
# platform internals (view names, column names, "IndexedDB", Gartner rung words).
# The canonical token stays in the artifact (the `source`/`rung` fields, for dev +
# any gate); the RENDERED lines are translated to the user's mental model here.
SOURCE_PLAIN = {
    "logbook": "your logbook entries", "v_logbook_truth": "your logbook entries",
    "shift_plans": "your shift plan",
    "amc_briefings": "today's maintenance briefing",
    "asset_nodes": "your asset register", "v_asset_truth": "your asset register",
    "platform_health.json": "the platform status report",
    "v_worker_achievements_truth": "your achievements", "worker_achievements": "your achievements",
    "v_risk_truth": "the risk scores", "asset_risk_scores": "the risk scores",
    "v_inventory_items_truth": "your inventory", "inventory_items": "your inventory",
    "analytics-orchestrator": "the analytics engine",
    "v_marketplace_listings_truth": "the marketplace listings",
    "computeListingQuality": "your listing quality score",
    "v_anomaly_truth": "the anomaly detector", "anomaly_signals": "the anomaly detector",
    "v_pf_truth": "the condition-monitoring analysis",
    "v_community_posts_truth": "community posts", "community_posts": "community posts",
    "community_xp": "your community activity",
    "schedule_items": "your schedule",
    "get_adoption_risk_current": "the team adoption check",
    "integration_configs": "your connected systems",
    "v_pm_scope_items_truth": "your PM schedule", "pm_assets": "your PM assets",
    "v_marketplace_orders_truth": "your marketplace orders",
    "ph_intelligence_reports": "the Philippine maintenance benchmark",
    "get_pm_compliance_smrp": "your PM compliance",
    "projects": "your projects",
    "v_skill_badges_truth": "your skill badges", "skill_profiles": "your skill profile",
    "voice_journal_entries": "your voice journal",
    # non-tabular, agent-verified sources — described in plain terms
    "hive-community-presence (Supabase Realtime presence)": "who's online right now",
    "presenceChannel.presenceState": "who's online right now",
    "IndexedDB offline write-queue (getPendingEntries)": "items saved on your device, waiting to sync",
    "wh_guard_hist (localStorage validator run history)": "this device's check history",
    "client-parsed import file rows": "the file you're importing",
    "good/total units (production-output form inputs)": "the good vs total units you entered",
    "client-side exam grading (answers vs answer key)": "your exam answers",
}
# USER-VOICE "what this shows" — a maintenance worker reads this. The agent-authored
# `what` fields are developer descriptions ("count pill", "items.length", "Plain-Read
# verdict headline", raw formulas); these replace them with a short plain statement of
# what the NUMBER means. Keyed "<page.html>|<element-id>". Missing -> fall back to a
# stripped agent `what`. (feedback_provenance_user_voice_not_internals — the glass is
# worker-voice; no code refs, no UI-element nouns, no unexplained acronyms.)
USER_LABELS = {
    "achievements.html|ac-card-level": "Your total level across all 12 achievement areas",
    "achievements.html|hero-tier-label": "Your technician tier, from your highest achievement level",
    "achievements.html|ac-verdict-label": "A plain-language read of your weekly progress",
    "alert-hub.html|anomaly-engine-count": "How many unusual sensor signals were detected (top 5)",
    "alert-hub.html|amc-stat-assets": "High-risk assets in today's briefing",
    "alert-hub.html|amc-stat-crew": "Crew alerts in today's briefing",
    "alert-hub.html|amc-stat-parts": "Parts to stage in today's briefing",
    "alert-hub.html|amc-stat-pms": "PMs due in today's briefing",
    "analytics.html|an-verdict-label": "A plain-language read of your reliability (uptime, breakdowns, PM compliance)",
    "asset-hub.html|ah-card-total": "Approved assets registered in this hive",
    "asset-hub.html|detail-level": "Where this asset sits in the equipment hierarchy",
    "asset-hub.html|pf-pf-days": "Days of warning between an early failure sign and actual failure",
    "asset-hub.html|risk-days": "Estimated days until this asset could fail",
    "asset-hub.html|risk-score-num": "This asset's failure-risk score",
    "asset-hub.html|ah-verdict-label": "A plain-language status of this hive's assets",
    "asset-hub.html|pending-assets-count": "Asset submissions waiting for approval",
    "community.html|mod-count": "Flagged posts waiting for review",
    "community.html|presence-bar": "Which teammates are online right now",
    "community.html|profile-xp": "Your total community points",
    "dayplanner.html|dp-verdict-label": "A plain-language read of how manageable your day looks",
    "dayplanner.html|sidebar-count-bar": "How full your day is with open logbook items",
    "dayplanner.html|sidebar-count-label": "Open logbook items on your plan",
    "founder-console.html|ring-pct-label": "Overall status: all clear, attention, or action needed",
    "founder-console.html|ring-pct-num": "Percentage of checks passing",
    "hive.html|adoption-risk-score": "How well your team is adopting the platform (0-100)",
    "hive.html|presence-bar": "Which workers are online right now",
    "hive.html|ss-verdict-label": "A plain-language read of hive health (logbook, PM, inventory, adoption)",
    "hive.html|welcome-log-count": "How many logbook entries you've made",
    "hive.html|welcome-parts-count": "How many of your logbook entries are closed",
    "integrations.html|it-verdict-label": "A plain-language status of your connected systems",
    "integrations.html|preview-count-label": "Valid rows that will import from your file",
    "inventory.html|stat-total": "Parts in your inventory right now",
    "inventory.html|inv-count-label": "How many parts you're viewing out of the total",
    "inventory.html|inv-verdict-label": "A plain-language read of your stock health",
    "logbook.html|quality-pct-value": "Quality %: good units out of the total units you entered",
    "logbook.html|logbook-count-label": "How many entries you're viewing out of the total",
    "logbook.html|machine-count": "How many different machines you've logged",
    "logbook.html|offline-queue-count": "Entries saved on your device, waiting to sync",
    "logbook.html|open-count": "How many of your entries are still open",
    "logbook.html|open-jobs-count": "Open jobs on this panel",
    "logbook.html|pm-tasks-count": "PM tasks that need your attention",
    "logbook.html|total-count": "Your total number of logbook entries",
    "marketplace-seller.html|ps-earned": "Your total earnings (after the 5% platform fee)",
    "marketplace.html|mk-card-total": "Listings that match the current filter",
    "marketplace.html|quality-bar": "How complete your listing is (0-100)",
    "marketplace.html|quality-score-num": "Your listing quality score out of 100",
    "marketplace.html|mk-verdict-label": "A plain-language summary of the listings",
    "ph-intelligence.html|ph-verdict-label": "A plain-language read of the latest regional report",
    "platform-health.html|health-label": "Overall status: healthy, review, or action",
    "platform-health.html|health-num": "Overall platform health score (0-100)",
    "platform-health.html|streak-num": "How many checks in a row passed cleanly",
    "pm-scheduler.html|pm-count-label": "How many assets you're viewing out of the total",
    "pm-scheduler.html|pm-verdict-label": "A plain-language read of your PM compliance",
    "predictive.html|pr-verdict-label": "A plain-language read of your fleet's risk",
    "predictive.html|trend-label": "Whether breakdowns are trending up or down",
    "project-manager.html|pm-verdict-label": "A plain-language read of your projects' health",
    "shift-brain.html|carry-count": "Open items carried over from the last shift",
    "shift-brain.html|parts-count": "Low-stock parts to pre-stage for this shift",
    "shift-brain.html|pms-count": "PM tasks due during this shift",
    "shift-brain.html|risk-count": "Top-risk assets flagged for this shift",
    "shift-brain.html|sb-verdict-label": "A plain-language read of how heavy this shift is",
    "skillmatrix.html|result-score": "Your exam score out of 10",
    "skillmatrix.html|sm-verdict-label": "A plain-language read of your skills vs targets",
    "voice-journal.html|entry-count": "How many journal entries are showing",
}

# Gartner ladder rung -> a plain word a worker reads (drops the jargon, keeps the signal).
RUNG_PLAIN = {
    "descriptive": "Current measure",
    "diagnostic": "What's happening",
    "predictive": "Forecast",
    "prescriptive": "Recommended action",
}


def plain_source(reads):
    """Translate a canonical source token/string into the user's mental model.
    Composite ('a + b + c') translates each part. Falls back to a SAFE generic —
    never the raw token (a worker must never see `v_risk_truth`)."""
    if not reads:
        return None
    r = str(reads).strip()
    if r in SOURCE_PLAIN:
        return SOURCE_PLAIN[r]
    if " + " in r:
        seen, parts = set(), []
        for p in r.split(" + "):
            t = _plain_part(p.strip())
            if t and t not in seen:
                seen.add(t)
                parts.append(t)
        if parts:
            return ", ".join(parts)
    return _plain_part(r)


def _plain_part(p):
    if p in SOURCE_PLAIN:
        return SOURCE_PLAIN[p]
    base = re.split(r"[ (]", p)[0]  # strip a parenthetical / trailing words
    return SOURCE_PLAIN.get(base, "your platform data")

# E3 curated promotions (2026-06-29): js-heuristic binds HAND-VERIFIED by reading
# the actual render site (the element's textContent is assigned from this query).
# These are correct data displays the formula-contract gate couldn't see; promoting
# them expands trustworthy provenance WITHOUT the false-match risk (each was Read-
# confirmed, not token-guessed). Only applied if the anchor is RESOLVED in Phase B.
VERIFIED_JS_PROVENANCE = {
    ("asset-hub.html", "pf-pf-days"): {
        "rung": "predictive",
        "label": "P-F interval (days)",
        "lines": ["Reads: v_pf_truth",
                  "What: days from a detectable warning sign to functional failure",
                  "Standard: SAE JA1011 §6 (P-F interval)"]},
    ("community.html", "profile-xp"): {
        "rung": "descriptive",
        "label": "Your community XP",
        "lines": ["Reads: community_xp.xp_total",
                  "What: total XP earned from posts and replies (DB-trigger maintained)"]},
    ("logbook.html", "open-count"): {
        "rung": "diagnostic",
        "label": "Open work orders",
        "lines": ["Reads: logbook (status = Open)",
                  "What: count of open logbook jobs in your current view"]},
    ("logbook.html", "total-count"): {
        "rung": "descriptive",
        "label": "Total logbook entries",
        "lines": ["Reads: logbook",
                  "What: count of your logbook records in the current view"]},
    ("hive.html", "welcome-log-count"): {
        "rung": "descriptive",
        "label": "Your logbook entries",
        "lines": ["Reads: v_logbook_truth (your entries)",
                  "What: count of logbook records you have authored"]},
    ("logbook.html", "machine-count"): {
        "rung": "descriptive",
        "label": "Machines logged",
        "lines": ["Reads: logbook (distinct machine values)",
                  "What: number of unique machines in your current logbook view"]},
    ("logbook.html", "open-jobs-count"): {
        "rung": "diagnostic",
        "label": "Open jobs",
        "lines": ["Reads: logbook (status = Open)",
                  "What: count of open jobs for this asset/view"]},
    ("community.html", "mod-count"): {
        "rung": "diagnostic",
        "label": "Moderation queue",
        "lines": ["Reads: community_posts (flagged = true)",
                  "What: count of flagged posts awaiting supervisor review"]},
    ("asset-hub.html", "risk-score-num"): {
        "rung": "predictive",
        "label": "Asset risk score",
        "lines": ["Reads: v_risk_truth (risk_score)",
                  "What: this asset's composite failure-risk score",
                  "Standard: WorkHive asset risk composite (6-factor)"]},
    ("asset-hub.html", "risk-days"): {
        "rung": "predictive",
        "label": "Days to failure (estimate)",
        "lines": ["Reads: v_risk_truth (days_until_failure)",
                  "What: estimated run-days until functional failure"]},
}

# Generic element-id tokens that carry no semantic signal — a formula match on
# ONLY these is a loose/false match (e.g. `ah-card-total` -> "Pump Total Dynamic
# Head" on the shared word "total"). A trustworthy formula match must share a
# SPECIFIC token (risk, health, quality, pf, anomaly, exam, level, tier, ...).
GENERIC_TOKENS = {
    "total", "count", "num", "value", "label", "bar", "stat", "card", "pct",
    "strip", "verdict", "the", "a", "of", "id", "row", "list", "item", "panel",
    "score", "days", "tier", "level",  # too generic ALONE; allowed only alongside a stronger token
}
# A SMALL set of specific tokens are strong enough to trust on their own
# (NOT "quality"/"score"/"tier" — those are cross-domain words that need
# page-domain agreement, see below).
STRONG_ALONE = {"risk", "health", "anomaly", "exam", "adoption",
                "mtbf", "mttr", "weibull", "downtime", "compliance"}
# Domain words a formula may name (its "home" surface). If a formula names one
# of these, a match is only trustworthy when that domain word also appears on
# the anchor's page (filename) or in the element id — else it's a cross-domain
# false match (e.g. logbook's `quality-pct-value` token-matching a MARKETPLACE
# "Seller Quality Score"). Strong-alone tokens bypass this (they're unambiguous).
DOMAIN_WORDS = {"marketplace", "inventory", "logbook", "pm", "skill", "asset",
                "hive", "community", "platform", "adoption", "dayplanner",
                "predictive", "analytics", "seller", "pump"}


def _toks(s):
    return set(t for t in re.split(r"[^a-z0-9]+", str(s).lower()) if t)


def is_trustworthy(anchor, src):
    """Only surface provenance we're confident is CORRECT (a trust UI must not
    show a confidently-wrong source). Trustworthy = a formula-contract match that
    shares a specific (non-generic) token with the formula name. The loose
    js-parse-heuristic resolutions and no-shared-token formula matches are the
    E3 residual (need Phase B.2 semantic hardening) and are excluded, not faked."""
    # A verified_bind is Read-confirmed ground truth (each was adversarially verified
    # against the render site by the lineage-anchor-resolve workflow) — trust it.
    if src.get("via") == "verified_bind":
        return True
    if src.get("via") != "formula_contract":
        return False
    chain = src.get("chain") or []
    # Must resolve UNAMBIGUOUSLY to a single formula. A token match that attached
    # multiple formulas (e.g. "risk" -> both Adoption Risk Score AND asset Risk
    # Score) can't tell the user which one this number IS -> E3 residual, excluded.
    distinct = {(h.get("name") or h.get("formula_id") or h.get("metric"))
                for h in chain if (h.get("name") or h.get("formula_id") or h.get("metric"))}
    if len(distinct) != 1:
        return False
    name = next(iter(distinct))
    idt = _toks(anchor.get("id"))
    nmt = _toks(name)
    shared = idt & nmt
    if shared & STRONG_ALONE:
        return True
    # need at least one shared SPECIFIC (non-generic) token
    specific = shared - GENERIC_TOKENS
    if not specific:
        return False
    # cross-domain guard: if the formula names a home domain, that domain word
    # must appear on this anchor's page or in its id (else it's a token match
    # bleeding across surfaces, e.g. logbook quality -> marketplace seller quality).
    formula_domains = nmt & DOMAIN_WORDS
    if formula_domains:
        page_id_toks = _toks(anchor.get("page")) | idt
        if not (formula_domains & page_id_toks):
            return False
    return True


def exclusion_reason(anchor, src):
    """Why a RESOLVED anchor is NOT yet shown — the actionable E3 / B.2 worklist.
    Each reason maps to a concrete hardening move."""
    via = src.get("via")
    if via != "formula_contract":
        # js-parse heuristic (nearest .from()). Sub-classify so B.2 can attack it
        # correctly: many of these element-ids are UI CHROME (a control/label/counter),
        # NOT a data display — they have NO data provenance, and "nearest .from()"
        # bound them to an unrelated query. Those should be EXCLUDED from the
        # data-display denominator, not bound. The rest are genuine data values
        # whose element-id needs the formula-grade query bind.
        aid = (anchor.get("id") or "").lower()
        CHROME_HINTS = ("conn-label", "char-count", "-toggle", "toggle-", "picker",
                        "refresh-label", "filter", "-strip", "strip-", "sheet-save",
                        "save-label", "mic-", "-btn", "btn-", "progress-label", "verdict-label")
        if any(h in aid for h in CHROME_HINTS):
            return ("ui_chrome",
                    "E3: this element-id is UI CHROME (control/label/counter), not a data "
                    "display — EXCLUDE from the data denominator (no provenance to bind).")
        return ("data_needs_bind",
                "B.2: genuine data value — bind this element-id to the EXACT query/RPC that "
                "writes it (current resolution is nearest-.from() heuristic, verify + promote).")
    chain = src.get("chain") or []
    distinct = {(h.get("name") or h.get("formula_id") or h.get("metric"))
                for h in chain if (h.get("name") or h.get("formula_id") or h.get("metric"))}
    if len(distinct) != 1:
        names = ", ".join(sorted(x for x in distinct if x)) or "(none)"
        return ("ambiguous_multi_formula",
                f"B.2: token matched MULTIPLE formulas [{names}] — disambiguate to the one "
                "this display actually reads (page/element context).")
    name = next(iter(distinct)) or ""
    idt = _toks(anchor.get("id"))
    nmt = _toks(name)
    shared = idt & nmt
    if not (shared - GENERIC_TOKENS) and not (shared & STRONG_ALONE):
        return ("generic_token_match",
                f"B.2: matched '{name}' only on a generic token {sorted(shared) or '[]'} "
                "(e.g. total/count/card) — a loose/false match; verify the real source.")
    return ("cross_domain",
            f"B.2: '{name}' is a different surface's formula (page-domain mismatch) — "
            "rebind to this page's own source.")


def chain_lines(src):
    """Human-readable 'where from' lines from a resolved source chain."""
    lines = []
    via = src.get("via")
    for hop in (src.get("chain") or []):
        name = hop.get("name") or hop.get("formula_id") or hop.get("metric")
        if name:
            lines.append(f"Source: {name}")
        inputs = hop.get("inputs") or []
        if inputs:
            shown = ", ".join(str(i) for i in inputs[:6])
            if len(inputs) > 6:
                shown += f", +{len(inputs) - 6} more"
            lines.append(f"Inputs: {shown}")
        std = hop.get("standard_cite") or hop.get("standard")
        if std:
            lines.append(f"Standard: {std}")
        unit = hop.get("unit")
        if unit:
            lines.append(f"Unit: {unit}")
        reads = hop.get("view") or hop.get("table") or hop.get("rpc") or hop.get("reads")
        if reads:
            lines.append(f"Reads: {reads}")
    if not lines:
        # JS-heuristic resolution: at least name the query source.
        q = src.get("source") or src.get("from") or src.get("table") or src.get("query")
        if q:
            lines.append(f"Reads: {q}")
    return lines, via


def main():
    b = json.load(open(B, encoding="utf-8"))
    rung_by = {}
    if os.path.exists(LAD):
        for r in json.load(open(LAD, encoding="utf-8"))["displays"]:
            rung_by[(r["page"], r["id"])] = r["rung"]

    pages = defaultdict(dict)
    n = 0
    excluded_low_confidence = 0
    residual = []  # E3 worklist: RESOLVED anchors not yet trustworthy enough to show
    for a in b["anchors"]:
        if a.get("status") not in RESOLVED:
            continue
        aid = a.get("id")
        if not aid:
            continue
        src = a.get("source") or {}
        # Trust gate: only surface provenance we're confident is CORRECT.
        if not is_trustworthy(a, src):
            excluded_low_confidence += 1
            kind, fix = exclusion_reason(a, src)
            residual.append({"page": a.get("page"), "id": aid, "kind": kind, "fix": fix})
            continue
        # USER-VOICE render (feedback_provenance_user_voice_not_internals): a worker
        # reads this — show plain "what it shows" + plain "based on", NEVER a view/
        # column/tech name or a Gartner rung word. Canonical tokens are kept in the
        # `source`/`rung` fields (machine plane) but are not rendered.
        chain0 = (src.get("chain") or [{}])[0]
        what = USER_LABELS.get(f"{a['page']}|{aid}") or chain0.get("name") or aid
        rung = rung_by.get((a["page"], aid), "descriptive")
        canon = (src.get("reads") or chain0.get("view") or chain0.get("table")
                 or chain0.get("rpc") or chain0.get("reads"))
        based = plain_source(canon)
        lines = [f"Shows: {what}"]
        if based:
            lines.append(f"Based on: {based}")
        std = chain0.get("standard_cite") or chain0.get("standard")
        if std and re.search(r"\b(SAE|SMRP|ISO|IEC|NFPA|API|ASME|OEE|JA1011|MIL)\b", str(std)):
            lines.append(f"Standard: {std}")
        pages[a["page"]][aid] = {
            "rung": rung,                                       # canonical (color + analysis)
            "rung_label": RUNG_PLAIN.get(rung, "Current measure"),  # plain, rendered as the badge
            "via": src.get("via"),
            "label": what,
            "source": canon,                                    # canonical, NOT rendered
            "lines": lines,                                     # user-voice only, rendered
        }
        n += 1

    # E3 curated promotions — Read-verified js-heuristic data binds. Applied only
    # when the anchor is RESOLVED in Phase B (stay grounded) and not already shown.
    resolved_ids = {(a.get("page"), a.get("id")) for a in b["anchors"] if a.get("status") in RESOLVED}
    residual_keys = {(r["page"], r["id"]) for r in residual}
    for (pg, eid), entry in VERIFIED_JS_PROVENANCE.items():
        if (pg, eid) not in resolved_ids:
            continue  # anchor no longer present/resolved — skip the stale promotion
        if eid in pages.get(pg, {}):
            continue  # already shown via a formula match
        # Re-render the curated entry in USER VOICE too (its hand-written lines carry
        # raw "Reads: <view>" tokens). Translate the "Reads:" line via plain_source.
        uv_lines = []
        for ln in entry["lines"]:
            if ln.startswith("Reads:"):
                p = plain_source(ln.split(":", 1)[1].strip())
                if p:
                    uv_lines.append(f"Based on: {p}")
            elif ln.startswith(("What:", "Source:")):
                uv_lines.append("Shows: " + ln.split(":", 1)[1].strip())
            elif ln.startswith("Standard:"):
                uv_lines.append(ln)
            # drop Inputs/Unit (column names / jargon)
        if not any(l.startswith("Shows:") for l in uv_lines):
            uv_lines.insert(0, f"Shows: {entry['label']}")
        pages[pg][eid] = {"rung": entry["rung"], "rung_label": RUNG_PLAIN.get(entry["rung"], "Current measure"),
                          "via": "js_verified", "label": entry["label"],
                          "source": None, "lines": uv_lines}
        n += 1
        if (pg, eid) in residual_keys:  # it's now shown, not residual
            residual = [r for r in residual if (r["page"], r["id"]) != (pg, eid)]
            excluded_low_confidence -= 1

    out = {
        "_doc": "Per-page display provenance (Phase E2). Powers the 'where did this come from?' "
                "hover. Keyed page -> element-id -> {rung, via, label, lines[]}. ONLY high-confidence "
                "anchors appear (formula-contract match sharing a specific token with the formula) so "
                "the hover never shows a confidently-WRONG source; loose js-heuristic + no-shared-token "
                "matches are the E3 residual (Phase B.2 hardening), excluded not faked. Built by "
                "tools/build_display_provenance.py from display_anchor_sources.json + display_ladder.json.",
        "totals": {
            "trustworthy_shown": n,
            "excluded_low_confidence": excluded_low_confidence,
            "pages_with_provenance": len(pages),
        },
        "pages": dict(pages),
        "e3_residual": residual,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2)

    # E3 worklist (synthesis-as-deliverable): the residual, grouped by fix-kind so
    # B.2 can attack it by class, not one anchor at a time.
    OUT_MD = os.path.join(ROOT, "display_provenance.md")
    by_kind = defaultdict(list)
    for r in residual:
        by_kind[r["kind"]].append(r)
    KIND_TITLE = {
        "data_needs_bind":         "Data value — needs formula-grade element-id→query bind",
        "ui_chrome":               "UI chrome (control/label/counter) — EXCLUDE, no data provenance",
        "js_heuristic":            "Heuristic-only (nearest `.from()`, not verified)",
        "ambiguous_multi_formula": "Ambiguous — matched multiple formulas",
        "generic_token_match":     "Loose/false match on a generic token",
        "cross_domain":            "Cross-domain match (wrong surface's formula)",
        "no_lines":                "Resolved but no renderable chain",
    }
    lines = ["# Display Provenance — Phase E2 + E3 worklist\n",
             "_Generated by `tools/build_display_provenance.py`._\n",
             f"- **Trustworthy provenance shown (zero-wrong):** {n} across {len(pages)} pages",
             f"- **E3 residual (resolved but not yet trustworthy):** {len(residual)} — the B.2 hardening backlog\n",
             "## Trustworthy (live on the 'where did this come from?' hover)\n",
             "| Page | Element | Source |", "|---|---|---|"]
    for pg in sorted(pages):
        for eid, p in pages[pg].items():
            lines.append(f"| {pg} | `{eid}` | {p['label']} |")
    lines.append("\n## E3 residual — by fix-class (attack by class, not per-anchor)\n")
    for kind in ("data_needs_bind", "ui_chrome", "ambiguous_multi_formula", "cross_domain",
                 "generic_token_match", "js_heuristic", "no_lines"):
        items = by_kind.get(kind)
        if not items:
            continue
        lines.append(f"### {KIND_TITLE.get(kind, kind)} — {len(items)}\n")
        lines.append(f"_{items[0]['fix']}_\n")
        lines.append("| Page | Element |", )
        lines.append("|---|---|")
        for r in items:
            lines.append(f"| {r['page']} | `{r['id']}` |")
        lines.append("")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"[display_provenance] {n} trustworthy anchors across {len(pages)} pages -> {OUT}")
    print(f"  excluded (low-confidence, = E3 residual): {excluded_low_confidence}")
    print(f"  E3 worklist by class: " + ", ".join(f"{k}={len(v)}" for k, v in by_kind.items()))
    for pg in sorted(pages):
        print(f"  {pg}: {len(pages[pg])}")


if __name__ == "__main__":
    main()
