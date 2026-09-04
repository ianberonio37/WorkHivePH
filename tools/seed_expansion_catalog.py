#!/usr/bin/env python3
"""seed_expansion_catalog.py — emit the 300 expansion rows (T201-T500) into the registry.

Token-economy discipline (CLAUDE.md): do NOT hand-invent 160 arcs. The learn/tools/edge waves
(T,U,V = 160) are mechanically derivable from real files on disk, so they are GENERATED here,
each row grounded in an actual page/function (no phantom surfaces). The 140 bespoke rows (W-AE)
are hand-authored below as (title, story) data — the authoring IS the spec — and emitted the same
compact way.

Every one of the 300 enters at status 'specced', pct 5, empty basis — honest: specced, not walked.
The gate (validate_trajectory_registry.py) permits specced/5 with no basis; a flattering pct would
be rejected, which is exactly the discipline the pct audit enforced on 2026-08-31.

  (default)  insert/replace T201-T500 in trajectory_registry.json (idempotent)
  --dry-run  print the counts and a sample, write nothing
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"

# ---- V wave: the 14 functions Wave I already charts, excluded so V is the 47 UNcharted ones ----
WAVE_I_FUNCTIONS = {
    "voice-action-router", "fmea-populator", "analytics-orchestrator", "asset-brain-query",
    "engineering-calc-agent", "resume-polish", "semantic-search", "hierarchical-summarizer",
    "temporal-rag-orchestrator", "data-fabric-normalizer", "ai-orchestrator",
    "semantic-fact-extractor", "ai-eval-runner", "ai-gateway",
}


def _title_of(html: Path) -> str:
    """Pull a real <title>, stripped of the site suffix — grounded in the page, not invented."""
    try:
        m = re.search(r"<title>(.*?)</title>", html.read_text(encoding="utf-8", errors="replace"),
                      re.I | re.S)
    except OSError:
        m = None
    if m:
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        t = re.split(r"\s*[|\-—·]\s*", t)[0].strip()  # drop " | WorkHive" style suffixes
        if t:
            return t
    return html.parent.name.replace("-", " ").title()


def _humanize(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def mechanical_rows() -> list[dict]:
    rows: list[dict] = []

    # ---- T: Public Learn funnel (T201-T253) — one per learn/*/ cluster ----
    learn = sorted(p for p in (ROOT / "learn").iterdir() if p.is_dir())
    for i, cluster in enumerate(learn):
        idx = cluster / "index.html"
        title = _title_of(idx) if idx.exists() else _humanize(cluster.name)
        rows.append({
            "id": f"T{201 + i}", "wave": "T", "status": "specced", "pct": 5, "basis": "",
            "title": f"Learn arrival: {title}",
            "pages": [f"learn/{cluster.name}/index.html"],
            "cells": ["narrow-320|assistive-tech|browser-ui|operate"],
        })

    # ---- U: Public Tools funnel (T254-T313) — one per tools/*-calculator/ ----
    calcs = sorted(p for p in (ROOT / "tools").iterdir() if p.is_dir() and p.name.endswith("-calculator"))
    for i, calc in enumerate(calcs):
        idx = calc / "index.html"
        title = _title_of(idx) if idx.exists() else _humanize(calc.name)
        rows.append({
            "id": f"T{254 + i}", "wave": "U", "status": "specced", "pct": 5, "basis": "",
            "title": f"Public calculator computes standalone: {title}",
            "pages": [f"tools/{calc.name}/index.html"],
            "cells": ["wide-1920|assistive-tech|browser-ui|operate"],
        })

    # ---- V: Edge-function layer (T314-T360) — one per UNcharted supabase/functions/* ----
    fns = sorted(p.name for p in (ROOT / "supabase" / "functions").iterdir()
                 if p.is_dir() and p.name != "_shared" and p.name not in WAVE_I_FUNCTIONS)
    for i, fn in enumerate(fns):
        rows.append({
            "id": f"T{314 + i}", "wave": "V", "status": "specced", "pct": 5, "basis": "",
            "title": f"Edge function contract & failure modes: {fn}",
            "pages": [f"supabase/functions/{fn}/index.ts"],
            "cells": ["fixed-kiosk-print|machine-client|api-direct|operate"],
        })

    assert sum(1 for r in rows if r["wave"] == "T") == 53, "T wave must be 53 learn clusters"
    assert sum(1 for r in rows if r["wave"] == "U") == 60, "U wave must be 60 calculators"
    assert sum(1 for r in rows if r["wave"] == "V") == 47, "V wave must be 47 uncharted functions"
    return rows


# =============================================================================================
# BESPOKE rows (W-AE, 140) — hand-authored. Each tuple is (title, story). The story is the spec
# seed; a named user story (persona x device x entry x intent) grounded in the real platform.
# =============================================================================================
BESPOKE = {
    # ---- W: Security & adversarial personas (T361-T384, 24) — OWASP classes x attacker stories --
    "W": [
        ("BOLA: guess another hive's asset id", "adversary enumerates /rest/v1/assets?id=<other-hive> hoping the ref, not RLS, is the only guard"),
        ("Broken function-level auth: worker hits admin RPC", "signed-in worker calls an owner-only RPC directly, betting the button was the only gate"),
        ("JWT-in-body trust", "attacker sends a claim in the request body hoping an edge function trusts it over the verified JWT"),
        ("Tenant boundary via forged hive_id", "attacker posts a write with someone else's hive_id to cross the tenant wall"),
        ("Mass assignment on profile update", "attacker adds role:owner to a profile PATCH hoping the column is unguarded"),
        ("IDOR on marketplace order", "buyer edits an order id in the URL to read a stranger's transaction and address"),
        ("Stored XSS in a logbook entry", "attacker plants <script> in free text hoping a consumer renders it unescaped"),
        ("SQL/PostgREST injection via filter param", "attacker crafts a filter operator to widen a query past its intended row set"),
        ("SSRF via a webhook/callback URL", "attacker points an outbound integration URL at an internal address"),
        ("Rate-limit / brute force on login", "attacker scripts the login edge function to credential-stuff"),
        ("Password-reset token reuse", "attacker replays a supervisor-reset-password token after it should have burned"),
        ("Enumerate users via signup error deltas", "attacker distinguishes 'exists' from 'created' by response timing/text"),
        ("Invite-code forgery / replay", "attacker crafts or reuses a hive invite code to self-join"),
        ("Privilege escalation via stale membership", "removed member's cached session still writes before the wall catches up"),
        ("File-upload content smuggling", "attacker uploads a mislabeled file to a storage bucket to bypass a MIME gate"),
        ("Signed-URL scope abuse", "attacker widens or reuses a storage signed URL past its object"),
        ("CSRF on a state-changing GET", "attacker tricks a session into a cross-site state change on a non-idempotent endpoint"),
        ("Webhook signature bypass (gcash-receipt-inbound)", "attacker posts a forged payment webhook without a valid signature to mark a txn paid"),
        ("Race to double-spend a marketplace credit", "attacker fires two concurrent redemptions of the same credit"),
        ("Exfil via export-hive-data as a low-role", "low-privilege member triggers a full-hive export they should not receive"),
        ("Prompt injection into an AI agent", "attacker plants instructions in user content that an AI orchestrator later executes"),
        ("Denial-of-wallet on a metered AI endpoint", "attacker loops an expensive AI call to exhaust the owner's budget"),
        ("Open redirect on return-url params", "attacker crafts ?return= to bounce a signed-in user to a phishing origin"),
        ("Audit-log tampering / gap", "attacker performs an action on a path that writes no audit row, hiding the trail"),
    ],
    # ---- X: Accessibility spectrum (T385-T402, 18) ----
    "X": [
        ("Screen-reader: complete a work order end-to-end", "a blind supervisor drives logbook->assign with NVDA/VoiceOver, intent = finish without sight"),
        ("Keyboard-only: no mouse anywhere", "a motor-impaired user tabs through every interactive control, focus never trapped or lost"),
        ("Low-vision at 400% zoom", "a partially-sighted user zooms to 400%; no content clipped, no horizontal scroll trap"),
        ("Color-blind: status conveyed beyond hue", "a deuteranope reads asset health where red/green alone would be ambiguous"),
        ("Switch-access single-input navigation", "a quadriplegic user drives the app with one switch and scanning"),
        ("Voice-control (Dragon/Voice Access)", "a user speaks 'click Assign' — every control has a spoken-accessible name"),
        ("Screen-magnifier follow-focus", "a low-vision user's magnifier follows focus and new content into the viewport"),
        ("Deaf/HoH: captions & no audio-only cues", "a Deaf user needs every audio alert mirrored visually (voice-journal playback captioned)"),
        ("Cognitive load: plain-language + steps", "a user with a cognitive disability needs a long form chunked and jargon explained"),
        ("Reduced-motion respected", "a vestibular-disorder user with prefers-reduced-motion sees no parallax/auto-animation"),
        ("Reflow at 320 CSS px (WCAG 1.4.10)", "content reflows to a single column at 320px with no loss of function"),
        ("Focus-visible on every control", "a keyboard user always sees where focus is; no invisible focus ring"),
        ("Form errors announced to AT", "a validation error is programmatically associated and announced, not just colored"),
        ("Live-region for async updates", "a screen-reader user hears a toast/status change via an aria-live region"),
        ("Touch target >=44px on phone", "a user with a tremor can hit every phone control without mis-tapping a neighbor"),
        ("Skip-link & landmark navigation", "a screen-reader user jumps past nav to main via a skip link and landmarks"),
        ("High-contrast / forced-colors mode", "a Windows High Contrast user retains all borders, icons and state"),
        ("Timeout & session-extend accessible", "a slow user is warned before a session/auto-save timeout and can extend it"),
    ],
    # ---- Y: New human personas (T403-T420, 18) ----
    "Y": [
        ("DOLE labor inspector reviews compliance", "a government inspector audits permit-to-work and shift records for a Philippine plant"),
        ("Insurance assessor verifies maintenance history", "an assessor needs tamper-evident asset maintenance history for a claim"),
        ("Procurement officer evaluates a marketplace seller", "a corporate buyer vets a seller's trust signals before a bulk order"),
        ("Night-shift lone operator", "a solo night-shift tech logs a fault at 3am with no supervisor online"),
        ("Regional manager across many hives", "a multi-site manager compares OEE across the hives they oversee"),
        ("Brand-new trainee, day one", "a fresh hire with zero context is onboarded into a hive and their first task"),
        ("Contractor working across multiple hives", "an external contractor switches between three client hives without data bleed"),
        ("External auditor with read-only, time-boxed access", "an ISO auditor gets scoped, expiring read access to evidence"),
        ("Finance controller reconciles marketplace payouts", "a controller ties GCash payouts to completed orders for the books"),
        ("Plant safety officer runs an incident review", "a safety officer reconstructs an incident from logbook + audit trail"),
        ("HR verifies a worker's skill matrix", "HR confirms certifications before assigning a regulated task"),
        ("Vendor/OEM support engineer", "an equipment vendor is granted a narrow window to diagnose one asset"),
        ("Executive on a quarterly board review", "a non-technical exec reads the platform's headline reliability KPIs"),
        ("Union representative checks fair scheduling", "a rep audits shift assignments for equity across workers"),
        ("Data-protection officer handles a subject request", "a DPO fulfils a GDPR/PDPA export/erasure request for one worker"),
        ("Retiring supervisor hands over a hive", "an outgoing supervisor transfers ownership and knowledge before leaving"),
        ("Seasonal surge temp worker", "a temp is added for a shutdown, works two weeks, is cleanly offboarded"),
        ("Regulator cross-checks a public tools claim", "a standards body verifies a public calculator matches the cited standard"),
    ],
    # ---- Z: Data pathology deep (T421-T438, 18) ----
    "Z": [
        ("Partial write: order paid, fulfilment row missing", "a half-committed transaction leaves the UI asserting a state the data denies"),
        ("Orphaned child after parent delete", "an asset is deleted but its work orders survive, pointing at nothing"),
        ("Timezone-crossing shift at midnight", "a shift spanning midnight in Asia/Manila is counted in the wrong day"),
        ("Float precision in a cost/hours rollup", "accumulated rounding drifts a financial total the user can check by hand"),
        ("Migration half-state as UX", "a user hits a page mid-migration where old and new columns disagree"),
        ("Duplicate rows from a double-submit", "a retried POST creates two identical records the list now shows twice"),
        ("Null-vs-zero conflation in a metric", "a missing reading is averaged as 0, deflating an availability number"),
        ("Stale cache after a write", "a user saves, navigates, and sees the pre-save value from a warm cache"),
        ("Unicode/emoji in names breaks a render", "a worker named with non-Latin script or emoji breaks a downstream label"),
        ("Very long text overflows every container", "a 10k-character logbook note must not break layout or truncate silently"),
        ("Clock skew between client and server", "a client with a wrong clock stamps events out of order"),
        ("Soft-deleted row leaks into an aggregate", "a soft-deleted asset still counts in a hive's totals"),
        ("Enum drift: a status value no code handles", "a legacy status value renders as a blank chip nobody planned for"),
        ("Cross-hive id collision in a shared table", "two hives' sequences collide in a table keyed without the hive"),
        ("Large dataset pagination correctness", "a hive with 50k assets pages without dropping or repeating rows"),
        ("Currency/precision at scale (centavos)", "GCash amounts in centavos survive rollup without a rounding leak"),
        ("Backfill leaves created_at in the future", "an import sets timestamps ahead of now, breaking 'recent' ordering"),
        ("Referential repair crosses the tenant boundary", "an automated fix touches a sibling hive's row — the boundary must hold"),
    ],
    # ---- AA: Financial & economic edge (T439-T454, 16) ----
    "AA": [
        ("Refund after a completed marketplace order", "a buyer disputes; the refund path must reverse credit and ledger cleanly"),
        ("Chargeback / reversed GCash payment", "a payment reverses post-fulfilment; the platform reconciles both sides"),
        ("Currency & tax on a cross-region sale", "a sale spanning tax jurisdictions computes the right line items"),
        ("AI credit exhausted mid-transaction", "an owner's AI budget runs out halfway through a multi-step agent run"),
        ("Fraud ring: coordinated fake reviews", "multiple colluding accounts inflate a seller's trust signals"),
        ("GCash webhook arrives late / out of order", "a delayed payment webhook lands after the timeout; state reconciles"),
        ("Double-charge on a retried checkout", "a network retry must not charge the buyer twice"),
        ("Payout to a since-deleted seller account", "a payout is owed to a seller who closed their account"),
        ("Price change mid-cart", "a listing's price changes between add-to-cart and checkout"),
        ("Subscription proration on plan change", "an owner upgrades mid-cycle; the invoice prorates correctly"),
        ("Negative-balance / overdraw guard", "a credit spend that would go negative is refused, not silently allowed"),
        ("Escrow release dispute", "buyer and seller disagree on delivery; escrow holds until resolved"),
        ("Tax-exempt / invoice-only buyer", "a corporate buyer needs an official receipt and tax handling"),
        ("Failed payout retry & idempotency", "a failed payout retries without paying twice"),
        ("Promo/discount stacking abuse", "a buyer stacks incompatible promos to underpay"),
        ("Financial report reconciles to the ledger", "the analytics revenue figure equals the sum of ledger rows, provably"),
    ],
    # ---- AB: Federation & multi-org (T455-T470, 16) ----
    "AB": [
        ("Parent org rolls up child-hive metrics", "a corporate parent aggregates KPIs across subsidiary hives it owns"),
        ("Cross-hive contractor with scoped access", "a contractor sees only the assets each client hive shared, nothing else"),
        ("Data-sharing agreement between two hives", "two independent hives share a defined slice under an agreement"),
        ("Org-level RBAC above hive roles", "an org admin role spans hives without becoming owner of each"),
        ("Subsidiary spins off into its own org", "a child hive is cleanly detached into an independent org with its data"),
        ("Shared marketplace seller across hives", "one seller identity operates from several hives without leaking between them"),
        ("Central template pushed to all child hives", "a parent publishes a PM template every subsidiary inherits"),
        ("Cross-org benchmarking, anonymized", "hives compare against an anonymized peer benchmark without exposing rows"),
        ("Merge two hives into one", "an acquisition merges two hives' assets and members without collision"),
        ("Federated single sign-on across orgs", "a user with an org SSO identity enters the right hives"),
        ("Delegated admin: parent acts for a child", "a parent admin performs an action in a child hive, audited as delegated"),
        ("Billing consolidated at the org level", "subsidiaries' usage rolls into one org invoice"),
        ("Cross-hive asset transfer", "an asset moves from one hive to another with its history intact"),
        ("Region-partitioned data residency", "an org keeps PH and non-PH hive data in the right residency"),
        ("Org-wide policy overrides a hive setting", "an org security policy forces a setting a hive cannot loosen"),
        ("Guest hive with an expiry date", "a temporary partner hive auto-expires and revokes access on the date"),
    ],
    # ---- AC: Platform-evolution & longitudinal (T471-T484, 14) ----
    "AC": [
        ("Deprecation-as-UX: a retired page's callers", "a user follows an old link to a retired page and is guided forward, not 404'd"),
        ("Version-skew client after a deploy", "a user on a stale tab hits new APIs; the app detects and reloads gracefully"),
        ("Breaking-change migration a live user is in", "a schema change lands while a user has a half-filled form open"),
        ("Multi-year asset history renders", "an asset with five years of records loads and charts without choking"),
        ("A feature flag flips mid-session", "a flag toggles while a user is mid-flow; the UI stays coherent"),
        ("Old cached service worker serves stale app", "a returning PWA user gets the new version, not a months-old cache"),
        ("Data written by a retired feature", "rows created by a since-removed feature still render safely"),
        ("Long-dormant account returns", "a user absent a year signs in to a changed platform and re-orients"),
        ("Renamed field across an API version", "a field renamed between versions maps for old and new clients"),
        ("Historical report reproducibility", "a report run today for last quarter matches what it said then"),
        ("Bulk re-embed after a model upgrade", "an embedding model change triggers a backfill without downtime"),
        ("Sunset an integration with active users", "a CMMS connector is retired while hives still use it; they're migrated"),
        ("Config/default change is backward-safe", "a changed default doesn't silently alter existing hives' behavior"),
        ("Terms/consent re-acceptance flow", "a policy update requires re-consent without locking users out of their data"),
    ],
    # ---- AD: Ops / observability surfaces (T485-T492, 8) — the never-walked pages ----
    "AD": [
        ("LLM observability dashboard reads true", "an operator reads llm-observability; every metric ties to a real trace"),
        ("Agentic-RAG observability traces a run", "an engineer follows one agentic-rag run end-to-end on the page"),
        ("PH-intelligence surface is grounded", "the ph-intelligence page's claims trace to real sources, not vibes"),
        ("Founder console shows honest platform state", "the founder-console reflects real tenancy/usage, not a demo mock"),
        ("Promo-poster generator produces a valid asset", "promo-poster renders a shareable asset with correct branding"),
        ("Symbol gallery is complete & accurate", "symbol-gallery lists every icon the app actually uses"),
        ("Analytics-report page reconciles to data", "analytics-report's figures equal the underlying rows"),
        ("Offline-fallback degrades gracefully", "offline-fallback gives a real, useful experience with no network"),
    ],
    # ---- AE: Compound systemic failures (T493-T500, 8) — multi-layer outages beyond T200 ----
    "AE": [
        ("DB failover mid-write storm", "the primary fails over while many hives are writing; no lost or dup rows"),
        ("Edge-function cold-start cascade under load", "a traffic spike cold-starts many functions at once; the queue holds"),
        ("Auth outage with cached sessions active", "the auth service is down but signed-in users must degrade safely"),
        ("Storage unavailable during an upload wave", "object storage blips while uploads are in flight; they retry, none corrupt"),
        ("Realtime + REST disagree during a partition", "a network partition splits realtime from REST; the UI reconciles on heal"),
        ("Third-party (GCash) outage mid-checkout", "the payment provider is down during checkouts; orders park, none half-pay"),
        ("Cron/scheduled-agents backlog after downtime", "scheduled jobs pile up during an outage and drain without double-firing"),
        ("Region-wide degradation, graceful global", "one region degrades; the platform stays coherent for everyone else"),
    ],
}


def bespoke_rows() -> list[dict]:
    order = [("W", 361), ("X", 385), ("Y", 403), ("Z", 421), ("AA", 439),
             ("AB", 455), ("AC", 471), ("AD", 485), ("AE", 493)]
    # a representative v2 cell per wave — grounds the bespoke arcs in the expansion diversity matrix
    WAVE_CELL = {
        "W": "wide-1920|adversary|api-direct|attack",
        "X": "narrow-320|assistive-tech|browser-ui|operate",
        "Y": "wide-1920|oversight|browser-ui|audit",
        "Z": "fixed-kiosk-print|machine-client|api-direct|operate",
        "AA": "wide-1920|oversight|api-direct|comply",
        "AB": "wide-1920|oversight|browser-ui|comply",
        "AC": "narrow-320|assistive-tech|browser-ui|operate",
        "AD": "wide-1920|oversight|browser-ui|audit",
        "AE": "fixed-kiosk-print|machine-client|webhook-inbound|operate",
    }
    rows: list[dict] = []
    for wave, start in order:
        for i, (title, story) in enumerate(BESPOKE[wave]):
            rows.append({
                "id": f"T{start + i}", "wave": wave, "status": "specced", "pct": 5,
                "basis": "", "title": title, "story": story,
                "pages": [], "cells": [WAVE_CELL[wave]],
            })
    return rows


def build_all() -> list[dict]:
    rows = mechanical_rows() + bespoke_rows()
    rows.sort(key=lambda r: int(r["id"][1:]))
    ids = [r["id"] for r in rows]
    assert ids == [f"T{n}" for n in range(201, 501)], \
        f"expansion rows must be exactly T201..T500 ({len(ids)} built, first {ids[:1]}, last {ids[-1:]})"
    return rows


def main() -> int:
    rows = build_all()
    from collections import Counter
    by_wave = Counter(r["wave"] for r in rows)
    if "--dry-run" in sys.argv:
        print(f"built {len(rows)} expansion rows · " + " · ".join(f"{k} {by_wave[k]}" for k in
              ["T", "U", "V", "W", "X", "Y", "Z", "AA", "AB", "AC", "AD", "AE"]))
        print("sample:", json.dumps(rows[0], ensure_ascii=False))
        print("sample:", json.dumps(rows[160], ensure_ascii=False))
        return 0
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    kept = [t for t in reg["trajectories"] if int(t["id"][1:]) <= 200]  # idempotent: drop any prior expansion
    reg["trajectories"] = kept + rows
    reg["count"] = len(reg["trajectories"])
    reg["updated"] = "2026-08-31"
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"registry now holds {reg['count']} trajectories (200 original + {len(rows)} expansion). "
          + " · ".join(f"{k} {by_wave[k]}" for k in
                       ["T", "U", "V", "W", "X", "Y", "Z", "AA", "AB", "AC", "AD", "AE"]))
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
