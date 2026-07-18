#!/usr/bin/env python3
"""
D0 — Arc D Frontend-UFAI denominator miner.

Mines the *applicable* (page x UFAI sub-layer) cells for the user-facing pages,
credits F2 (Functionality-correctness) from Arc C's render_sweep.json, and stands
up frontend_ufai_results.json -- the live tracker that D1-D4 ratchet up.

Spine: COMPREHENSIVE_STUDY_FULLSTACK_GATE.md  §13.20 (Arc D).

Discipline (carried from Arc C, per CLAUDE.md Momentum + measured-% feedback):
  * The denominator is mined from EVIDENCE (real per-page HTML signals), not
    hardcoded guesses -- "a read-only dashboard has no F5 round-trip cell -> it
    DROPS from the denominator rather than scoring 0" (the anti-false-sense rule).
  * Every cell carries WHY it is applicable / N/A so the disposition is auditable.
  * F2 is CREDITED from Arc C (render==canonical 83/83) and not re-surveyed.

Run:
  python tools/mine_frontend_ufai_surfaces.py            # mine + write results + md
  python tools/mine_frontend_ufai_surfaces.py --check     # mine + verify denominator only (no write)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "frontend_ufai_results.json"
RESULTS_MD = ROOT / "frontend_ufai_results.md"
RENDER_SWEEP = ROOT / "render_sweep.json"
RENDER_SURFACES = ROOT / "render_surfaces.json"

# ---------------------------------------------------------------------------
# The 25 UFAI sub-layers (ground truth = the enumerated §13.20.1 table).
# NOTE: the §13.20.1 PROSE says "26 sub-layers" but the enumerated table lists
# 25 (U1-U7=7, F1-F6=6, A1-A6=6, I1-I6=6). The IDs are evidence; the prose count
# was vibes -> we mine from the 25 enumerated and reconcile the doc to 25.
# ---------------------------------------------------------------------------
SUBLAYERS = [
    ("U1", "U", "Recognizability & learnability"),
    ("U2", "U", "Operability (keyboard/touch)"),
    ("U3", "U", "System-status feedback"),
    ("U4", "U", "User-error protection"),
    ("U5", "U", "Inclusivity / accessibility"),
    ("U6", "U", "Consistency & minimalist aesthetic"),
    ("U7", "U", "Mobile / field usability"),
    ("F1", "F", "Completeness"),
    ("F2", "F", "Correctness (Arc A/B/C credit)"),
    ("F3", "F", "Appropriateness"),
    ("F4", "F", "Navigation & flow integrity"),
    ("F5", "F", "Data round-trip"),
    ("F6", "F", "Degraded states"),
    ("A1", "A", "Responsive/adaptive layout"),
    ("A2", "A", "Component reuse & design-system"),
    ("A3", "A", "Configurability (role/hive/prefs)"),
    ("A4", "A", "State-management discipline"),
    ("A5", "A", "Extensibility / scalability"),
    ("A6", "A", "Offline / PWA"),
    ("I1", "I", "Auth gating"),
    ("I2", "I", "Role/permission UI gating"),
    ("I3", "I", "Tenancy isolation at render"),
    ("I4", "I", "Client-side input validation"),
    ("I5", "I", "Auditability surfacing"),
    ("I6", "I", "Safe-by-default / no-bypass"),
]
SUBLAYER_TITLE = {sid: title for sid, _lens, title in SUBLAYERS}
SUBLAYER_LENS = {sid: lens for sid, lens, _t in SUBLAYERS}

# The 36 user-facing pages (the §13.20.4 table). Excludes *-test / *.backup /
# pure dev-docs (architecture / validator-catalog / symbol-gallery).
PAGES = [
    ("index.html", "0 Entry"),
    ("engineering-design.html", "1 Capture"),
    ("logbook.html", "1 Capture"),
    ("inventory.html", "1 Capture"),
    ("pm-scheduler.html", "1 Capture"),
    ("voice-journal.html", "1 Capture"),
    ("dayplanner.html", "1 Capture"),
    ("resume.html", "1 Capture"),
    ("asset-hub.html", "2 Dashboards"),
    ("alert-hub.html", "2 Dashboards"),
    ("analytics.html", "2 Dashboards"),
    ("analytics-report.html", "2 Dashboards"),
    ("shift-brain.html", "2 Dashboards"),
    ("ai-quality.html", "2 Dashboards"),
    ("ph-intelligence.html", "2 Dashboards"),
    ("project-manager.html", "3 Records"),
    ("project-report.html", "3 Records"),
    ("skillmatrix.html", "3 Records"),
    ("achievements.html", "3 Records"),
    ("audit-log.html", "3 Records"),
    ("assistant.html", "4 AI"),
    ("hive.html", "5 Connect/Commerce"),
    ("community.html", "5 Connect/Commerce"),
    ("public-feed.html", "5 Connect/Commerce"),
    ("marketplace.html", "5 Connect/Commerce"),
    ("marketplace-seller.html", "5 Connect/Commerce"),
    ("marketplace-seller-profile.html", "5 Connect/Commerce"),
    ("marketplace-admin.html", "5 Connect/Commerce"),
    ("integrations.html", "5 Connect/Commerce"),
    ("plant-connections.html", "5 Connect/Commerce"),
    ("report-sender.html", "5 Connect/Commerce"),
    ("status.html", "6 System/Admin"),
    ("founder-console.html", "6 System/Admin"),
    ("llm-observability.html", "6 System/Admin"),
    ("agentic-rag-observability.html", "6 System/Admin"),
]

# Page-class declarations (evidence-anchored, see memory + render artifacts).
PUBLIC_PAGES = {"index.html", "public-feed.html"}            # public entry, not auth-gated targets
SOLO_PAGES = {"resume.html"}                                  # public solo tool, no hive tenancy
CROSS_HIVE_ADMIN = {                                          # see cross-hive/platform data BY DESIGN
    "founder-console.html", "marketplace-admin.html",
    "llm-observability.html", "agentic-rag-observability.html", "status.html",
}


def load_f2_credit():
    """Pages whose F2 (correctness) is PROVEN by Arc C -> credited, not re-surveyed."""
    credit = {}
    sweep = json.loads(RENDER_SWEEP.read_text(encoding="utf-8"))
    for c in sweep.get("cells", []):
        if c.get("status") in ("PASS", "PANEL-PASS", "DETAIL-PASS"):
            credit.setdefault(c["page"], set()).add(c.get("tile_id", c.get("status")))
    surf = json.loads(RENDER_SURFACES.read_text(encoding="utf-8"))
    for page, basis in surf.get("non_tile_proven_pages", {}).items():
        credit.setdefault(page, set()).add("non-tile: " + str(basis)[:60])
    return credit


def scan_page(path):
    """Detect per-page structural signals from the real HTML (evidence for applicability)."""
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return None
    low = txt.lower()
    sig = {}
    # has_inputs: a form / editable control exists
    sig["has_inputs"] = bool(re.search(r"<form|<input|<textarea|<select|contenteditable", low))
    # has_text_input: a TEXT-ENTRY field (text/email/number/etc., textarea, or a
    # typeless <input> which defaults to text). A bare filter <select> / radio /
    # checkbox is NOT a text-entry field → it has nothing to validate or
    # error-protect (the U4/I4 applicability fix: a read-only dashboard's
    # time-window <select> must not pull U4 "user-error protection" into scope).
    sig["has_text_input"] = bool(
        re.search(r"<textarea|contenteditable", low)
        or re.search(r"<input[^>]*type\s*=\s*[\"'](text|email|number|search|tel|url|password|date|datetime-local|month|time|week)[\"']", low)
        or re.search(r"<input(?![^>]*\btype\s*=)", low)  # typeless input defaults to text
    )
    # has_mutation: a create/edit/delete write path exists
    sig["has_mutation"] = bool(
        re.search(r"\.(insert|update|upsert|delete)\s*\(", low)
        or re.search(r"\b(async\s+)?function\s+(save|create|add|edit|update|delete|remove)\w*", low)
        or "onsubmit" in low
        or "requestsubmit" in low
    )
    # has_role_gate: UI differentiates by role/permission
    sig["has_role_gate"] = bool(
        re.search(r"supervisor|issupervisor|canmanage|\brole\s*[=!]==|'manager'|\"manager\"|isadmin|is_admin", low)
    )
    # has_destructive: a REAL destructive/privileged USER ACTION — a confirm()
    # dialog, a destructive verb inside an onclick/onsubmit handler, or a
    # button LABELED delete/remove/approve/etc. NOT a bare `.remove(` (DOM API),
    # `removeEventListener`, the `delete` JS operator, or the word "archived" in
    # status text — those noisy keyword matches falsely pulled read-only obs
    # dashboards (founder-console/llm-obs/agentic-rag) into U4/I5/I6 scope.
    sig["has_destructive"] = bool(
        re.search(r"confirm\s*\(", low)
        or re.search(r"on(?:click|submit)\s*=\s*[\"'][^\"']*\b(?:delete|remove|approve|reject|archive|deactivate|revoke|discard)\b", low)
        or re.search(r"<button[^>]*>[^<]{0,48}\b(?:delete|remove|approve|reject|archive|deactivate|revoke)\b", low)
    )
    # renders_data: a data-backed page (canonical values to verify == F2 meaningful)
    sig["renders_data"] = bool(
        re.search(r"getdb\(|createclient|\.from\s*\(|\.rpc\s*\(|supabase", low)
    )
    return sig


def applicable(sid, page, sig, is_public, is_solo, is_xhive):
    """
    Return (applicable: bool, reason: str) for a sub-layer cell on a page.
    Grounded in §13.20.2 probe definitions; N/A only when the probe has no target.
    """
    lens = SUBLAYER_LENS[sid]
    # --- Universal UI sub-layers (every rendered page has these) ---
    if sid in ("U1", "U2", "U3", "U5", "U6", "U7", "F1", "F3", "F4", "F6",
               "A1", "A2", "A4", "A5", "A6"):
        return True, "universal (every rendered page)"
    # --- U4 user-error protection: needs a TEXT-ENTRY field or destructive action ---
    # (a filter <select>/radio can't be "invalid" and isn't destructive → nothing
    # to error-protect; was a false-applied fail on read-only obs dashboards).
    if sid == "U4":
        if sig["has_text_input"] or sig["has_destructive"]:
            return True, "has text-entry input/destructive action to protect"
        return False, "read-only display (filter-only): no error-prone input or destructive action"
    # --- F2 correctness: needs canonical data to verify (CREDIT handled by caller) ---
    if sid == "F2":
        if sig["renders_data"]:
            return True, "renders canonical data (correctness verifiable)"
        return False, "static page: no canonical value to verify"
    # --- F5 round-trip: needs a create/edit/delete write path ---
    if sid == "F5":
        if sig["has_mutation"]:
            return True, "has create/edit/delete write path"
        return False, "read-only dashboard: no write path to round-trip"
    # --- I1 auth gating: only authed-only pages (not public/solo entries) ---
    if sid == "I1":
        if is_public or is_solo:
            return False, "public/solo entry: not an auth-gated target"
        return True, "authed-only page: must bounce when logged out"
    # --- I2 role UI gating: only pages with role-differentiated actions ---
    if sid == "I2":
        if sig["has_role_gate"]:
            return True, "has role-differentiated actions in DOM"
        return False, "no role-gated action: nothing to mirror server-side"
    # --- I3 tenancy isolation: hive-scoped pages (not solo; not public-data feed) ---
    if sid == "I3":
        if is_solo:
            return False, "solo tool: no hive tenancy to isolate"
        if page == "public-feed.html":
            return False, "public feed: data is public by design"
        if is_xhive:
            return True, "cross-hive/admin BY DESIGN: must stay admin-gated, no unauthorized leak"
        return True, "hive-scoped: must render only this hive's data"
    # --- I4 client-side validation: needs a TEXT-ENTRY field to validate ---
    if sid == "I4":
        if sig["has_text_input"]:
            return True, "has text-entry input to validate client-side (UX)"
        return False, "no text-entry input (filter select/radio only): nothing to client-validate"
    # --- I5 auditability surfacing: control actions OR the audit surface itself ---
    if sid == "I5":
        if page == "audit-log.html":
            return True, "the audit surface itself"
        if sig["has_destructive"] or sig["has_role_gate"]:
            return True, "performs control actions that must write+surface audit"
        return False, "no control action that requires an audit row"
    # --- I6 safe-by-default / no-bypass: destructive/privileged/input pages ---
    if sid == "I6":
        if sig["has_destructive"] or sig["has_inputs"] or sig["has_role_gate"]:
            return True, "has privileged/destructive/input surface to harden"
        return False, "read-only display: no privileged action to bypass"
    # --- A3 configurability: role/hive/prefs vary the UI (not solo, not public feed) ---
    if sid == "A3":
        if is_solo:
            return False, "solo tool: no role/hive to configure against"
        if page == "public-feed.html":
            return False, "public feed: UI does not vary by role/hive"
        return True, "UI adapts to role/hive/prefs"
    return True, "default-applicable"


def main():
    check_only = "--check" in sys.argv
    f2_credit = load_f2_credit()

    pages_out = {}
    N = 0
    credited = 0
    na = 0
    lens_denom = {"U": 0, "F": 0, "A": 0, "I": 0}
    lens_credited = {"U": 0, "F": 0, "A": 0, "I": 0}
    missing = []

    for page, tier in PAGES:
        path = ROOT / page
        sig = scan_page(path)
        if sig is None:
            missing.append(page)
            continue
        is_public = page in PUBLIC_PAGES
        is_solo = page in SOLO_PAGES
        is_xhive = page in CROSS_HIVE_ADMIN
        cells = {}
        for sid, lens, _title in SUBLAYERS:
            app, reason = applicable(sid, page, sig, is_public, is_solo, is_xhive)
            cell = {
                "lens": lens,
                "title": SUBLAYER_TITLE[sid],
                "applicable": app,
                "reason": reason,
            }
            if not app:
                cell["status"] = "n/a"
                na += 1
            else:
                N += 1
                lens_denom[lens] += 1
                if sid == "F2" and page in f2_credit:
                    cell["status"] = "credited"
                    cell["source"] = "Arc C render_sweep.json (render==canonical)"
                    cell["evidence"] = sorted(f2_credit[page])[:4]
                    credited += 1
                    lens_credited[lens] += 1
                else:
                    cell["status"] = "pending"  # to be live-surveyed in D1-D4
            cells[sid] = cell
        pages_out[page] = {
            "tier": tier,
            "signals": sig,
            "class": ("public" if is_public else "solo" if is_solo
                      else "cross-hive-admin" if is_xhive else "hive-scoped"),
            "cells": cells,
            "applicable_count": sum(1 for c in cells.values() if c["applicable"]),
        }

    out = {
        "generated": "D0 — tools/mine_frontend_ufai_surfaces.py",
        "spine": "COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §13.20 (Arc D)",
        "sublayer_count": len(SUBLAYERS),
        "page_count": len(pages_out),
        "denominator_N": N,
        "na_cells": na,
        "covered": {
            "credited_F2": credited,
            "pending": N - credited,
            "covered_pct": round(100.0 * credited / N, 1) if N else 0.0,
        },
        "lens_denominator": lens_denom,
        "lens_credited": lens_credited,
        "lens_pct": {k: round(100.0 * lens_credited[k] / lens_denom[k], 1) if lens_denom[k] else 0.0
                     for k in lens_denom},
        "pages": pages_out,
    }
    if missing:
        out["MISSING_PAGES"] = missing

    print("=" * 72)
    print("ARC D — D0  Frontend-UFAI denominator (mined from evidence)")
    print("=" * 72)
    print(f"  pages mined        : {len(pages_out)}/{len(PAGES)}"
          + (f"  (MISSING: {missing})" if missing else ""))
    print(f"  sub-layers         : {len(SUBLAYERS)} (U7+F6+A6+I6)")
    print(f"  applicable cells N : {N}")
    print(f"  N/A cells (dropped): {na}")
    print(f"  F2 credited (Arc C): {credited}")
    print(f"  pending (D1-D4)    : {N - credited}")
    print(f"  baseline covered   : {out['covered']['covered_pct']}%  (credited/N)")
    print("  per-lens N (denominator):")
    for k in ("U", "F", "A", "I"):
        print(f"      {k}: {lens_denom[k]:3d}   credited {lens_credited[k]:2d}   ({out['lens_pct'][k]}%)")

    if check_only:
        print("\n--check: no files written.")
        return 0

    RESULTS.write_text(json.dumps(out, indent=2), encoding="utf-8")
    write_md(out)
    print(f"\n  -> wrote {RESULTS.name} ({N} applicable cells)")
    print(f"  -> wrote {RESULTS_MD.name}")
    return 0


def write_md(out):
    lines = []
    lines.append("# Arc D — Frontend-UFAI coverage tracker (D0 denominator)\n")
    lines.append(f"_Generated by `tools/mine_frontend_ufai_surfaces.py` · spine §13.20._\n")
    lines.append(f"- **Denominator N** = **{out['denominator_N']}** applicable (page × sub-layer) cells "
                 f"across **{out['page_count']}** pages × **{out['sublayer_count']}** sub-layers "
                 f"({out['na_cells']} N/A cells dropped — the anti-false-sense rule).")
    lines.append(f"- **F2 credited from Arc C**: {out['covered']['credited_F2']} · "
                 f"**pending live survey (D1–D4)**: {out['covered']['pending']} · "
                 f"**baseline covered**: {out['covered']['covered_pct']}%\n")
    lines.append("## Per-lens denominator (the weakest-axis-first order)\n")
    lines.append("| Lens | Applicable cells | Credited | Covered % | Phase |")
    lines.append("|---|--:|--:|--:|---|")
    phase = {"U": "D1 (weakest)", "F": "D4 (F2 credited)", "A": "D3", "I": "D2"}
    for k in ("U", "I", "A", "F"):
        lines.append(f"| {k} | {out['lens_denominator'][k]} | {out['lens_credited'][k]} | "
                     f"{out['lens_pct'][k]}% | {phase[k]} |")
    lines.append("\n## Per-page applicable cells\n")
    lines.append("| Tier | Page | Class | Applicable | F2 |")
    lines.append("|---|---|---|--:|:--:|")
    for page, tier in PAGES:
        p = out["pages"].get(page)
        if not p:
            continue
        f2 = p["cells"].get("F2", {})
        f2mark = "✅" if f2.get("status") == "credited" else ("—" if not f2.get("applicable") else "⏳")
        lines.append(f"| {tier} | {page} | {p['class']} | {p['applicable_count']} | {f2mark} |")
    RESULTS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
