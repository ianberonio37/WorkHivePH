"""
score_ia_streamlining.py  —  Phase 2 (rubric) of the IA-streamlining surveyor.
================================================================================
Reads ia_inventory_corpus.json (Phase 1's grounded map — NO re-parse of HTML) and
scores every redundancy with a DETERMINISTIC rubric, then writes the audit plan +
a queue of critic candidates. Phase 1 surfaced WHAT repeats; Phase 2 says WHAT TO
DO about each — keep / consolidate / move / remove — with the ONE canonical home,
the UX-law citation, and a severity. It still DISPOSES NOTHING: every row is a
PROPOSAL a human signs off (doctrine: engine proposes, you dispose — never an
auto-collapse of UI).

THE RUBRIC (rule-based, grounded — not vibes). Four outcomes, because "the same
thing on N pages" is really FOUR different situations and conflating them is how
you delete something you needed:

  1. KEEP (consistent pattern)  — a design-SYSTEM convention replicated on many
     pages, where each instance shows THAT page's own data through a shared shell
     (e.g. the `:detail_panel` breakdown on 15 pages, the 3-tile `.simple-card`
     header). NOT a redundancy defect → Jakob's Law (consistency) + Nielsen #4.
     The copy-paste cost is a SEPARATE jscpd/Architect component-extraction job;
     it does NOT change the IA. Not queued (no decision needed).

  2. CONSOLIDATE  — the SAME VALUE/KPI surfaced on N pages → pick ONE canonical
     home (single source of truth), deep-link the rest (or render all from the
     same v_*_truth). Tesler's Law (complexity is conserved — duplicated state
     drifts) + the field lesson: redundancy CAUSES what-bugs (a KPI computed two
     ways let a stale value survive). Drift-capable KPI = Major, else Minor.
     VERIFY-FIRST caveat carried on every row (confirm it's the same derivation).

  3. RELABEL / keep-distinct  — SAME LABEL, DIFFERENT SUBJECT. "Pending approval"
     on asset-hub (assets) and inventory (parts) is NOT one unit — same-NAMED ≠
     same-derivation (the analytics RC-001 lesson applied to IA). Don't collapse;
     DISAMBIGUATE the labels (Nielsen #2, match real world). Major-confusion.

  4. DIFFERENTIATE / merge (REVIEW)  — a theme cluster: different labels serving
     ONE job-to-be-done from N pages (overdue/due/risk families). Hick's Law (many
     entry points to one job slow the user) — but possibly legitimate role/context
     views, so it's a REVIEW candidate a human adjudicates, never an auto-merge.

Affordance overlap: hub links (index/hive/community/assistant/marketplace) =
KEEP (expected, Jakob); a DEEP page reached from ≥2 extra bodies = REVIEW (Hick).

OUTPUTS:
  - streamlining_plan.md            — the full audit table (unit · pages ·
                                      recommendation · canonical-home · UX-law ·
                                      severity · verify-note), grouped by verb.
  - ia_streamlining_candidates.json — {candidates:[…]} in the sweep_critiques
                                      schema. Route into the queue with:
                                        python ufai_ingest.py ia_streamlining_candidates.json
                                      (idempotent dedupe; KEEP-consistent rows are
                                       NOT queued — only real decisions are).

USAGE:  python tools/score_ia_streamlining.py [--keep-threshold 10] [--ingest]
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import re
import sys
from pathlib import Path

# Windows cp1252 console can't encode ≥/—/→ — wrap stdout (same guard as
# ufai_ingest.py). The .md/.json files are written UTF-8 regardless.
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "ia_inventory_corpus.json"

# ── grounded maps ────────────────────────────────────────────────────────────
# Canonical owner per data DOMAIN (the page whose JOB owns that fact → the single
# source of truth a CONSOLIDATE should deep-link to). Grounded in nav sections +
# each page's purpose.
DOMAIN_OWNER = [
    (r"overdue|due|\bpm\b|pms|compliance|schedul", "pm-scheduler"),
    (r"risk|hot asset|forecast|heatmap|mtbf|anomaly|predict", "predictive"),
    (r"alert|severity|signal|amc", "alert-hub"),
    (r"stock|reorder|inventory|parts", "inventory"),
    (r"asset|critical asset|rcm", "asset-hub"),
    (r"skill|badge|quiz|target", "skillmatrix"),
    (r"shift|carry", "shift-brain"),
    (r"xp|level|achievement|composite|domain", "achievements"),
    (r"project|end date|on hold", "project-manager"),
    (r"listing|seller|marketplace", "marketplace"),
    (r"plant|network|failure cause", "ph-intelligence"),
    (r"oee|quality", "analytics"),
]

# What each page is fundamentally ABOUT — used to detect "same label, different
# subject" (the RELABEL case): "Pending approval" on asset-hub=ASSETS vs
# inventory=PARTS is two different units wearing one label.
PAGE_SUBJECT = {
    "asset-hub": "assets", "inventory": "parts", "pm-scheduler": "PM tasks",
    "dayplanner": "personal tasks", "predictive": "asset risk", "shift-brain": "the shift",
    "alert-hub": "alerts", "skillmatrix": "skills", "achievements": "achievements",
    "project-manager": "projects", "marketplace": "listings", "ph-intelligence": "the PH network",
    "analytics": "analytics", "hive": "the hive", "integrations": "integrations",
    "report-sender": "reports",
}

# A unit whose value is COMPUTED and can disagree page-to-page (drift-capable →
# a consolidation here is Major: this is the class that causes what-bugs).
DRIFT_CAPABLE_RE = re.compile(
    r"overdue|due|compliance|risk|mtbf|oee|score|anomaly|\bpm\b|pms|count|critical|forecast", re.I)

# Hubs every page links to BY DESIGN — an in-body link to one is expected, not a
# redundancy finding (Jakob).
HUB_PAGES = {"index", "hive", "community", "assistant", "marketplace", "alert-hub"}

KEEP_KEYS = {"detail panel", "detail_panel", "results panel", "detail breakdown panel"}


def slug(p: str) -> str:
    return p.replace(".html", "")


def owner_of(text: str) -> str | None:
    t = text.lower()
    for pat, page in DOMAIN_OWNER:
        if re.search(pat, t):
            return page
    return None


def subjects_of(pages: list[str]) -> set[str]:
    return {PAGE_SUBJECT.get(slug(p), slug(p)) for p in pages}


# ── scoring ──────────────────────────────────────────────────────────────────
def score(corpus: dict, keep_threshold: int) -> dict:
    g = corpus["groups"]
    rows = []          # full plan rows
    candidates = []    # queued (sweep_critiques schema)

    def add_candidate(key, page, title, severity, should_be, pillar="IA"):
        candidates.append({
            "key": key, "page": page, "wave": 0, "title": title,
            "pillar": pillar, "severity": severity, "effort": "M",
            "flag": "TASTE", "should_be": should_be,
        })

    # ── 1+2+3: exact-label and same-key info redundancy (HIGH confidence) ──────
    # Label-grouping and key-grouping are two VIEWS of the same redundancy: the
    # label pass normalizes "Pending approval"→"pending approval" and the key pass
    # normalizes "pending_approval"→"pending approval" — the SAME unit. Dedupe on
    # the bare normalized key so a unit gets ONE verdict, label pass first (it
    # carries the richer per-page labels that expose a different-subject RELABEL).
    seen_units = set()
    for kind, groups in (("label", g["info_redundancy_by_label"]),
                         ("key", g["info_redundancy_by_key"])):
        for grp in groups:
            key = grp["key"]
            pages = grp["pages"]
            labels = grp.get("labels") or [key]
            disp = labels[0] if labels else key
            if key in seen_units:
                continue
            seen_units.add(key)

            # KEEP — a structural convention on many pages (it's the same SHELL,
            # not the same VALUE; each panel shows its own page's data).
            if key in KEEP_KEYS or grp["pageCount"] >= keep_threshold:
                # the labels vary per page in a key-grouped family ("Asset detail",
                # "Hive detail", …) → name the row by the family key, not an
                # arbitrary first label, so it reads as the pattern it is.
                fam = f"{key.replace(' ', '_')} (family ×{grp['pageCount']})" if kind == "key" else disp
                rows.append({
                    "unit": fam, "kind": f"info:{kind}", "pages": pages,
                    "rec": "KEEP (consistent pattern)", "home": "— (each page owns its own)",
                    "law": "Jakob + Nielsen #4 (consistency)", "sev": "Polish",
                    "note": f"Design-system pattern on {grp['pageCount']} pages — each instance "
                            "renders THAT page's data. Not an IA defect. The copy-paste cost is a "
                            "separate jscpd/Architect component-extraction job (see clone-debt).",
                })
                continue

            subs = subjects_of(pages)
            home = (owner_of(disp) or owner_of(key))
            # RELABEL — same label/key, ≥2 distinct page-subjects → not one unit
            # (same-NAMED ≠ same-derivation). Checked in BOTH passes.
            if len(subs) >= 2:
                note = (f"Same LABEL \"{disp}\" but different SUBJECTS ({', '.join(sorted(subs))}) — "
                        "same-named ≠ same-derivation. Do NOT consolidate; DISAMBIGUATE the labels "
                        f"(e.g. \"{disp}\" → per-page \"{disp} ({list(sorted(subs))[0]})\").")
                rows.append({
                    "unit": disp, "kind": f"info:{kind}", "pages": pages,
                    "rec": "RELABEL / keep-distinct", "home": "n/a (distinct units)",
                    "law": "Nielsen #2 (match real world) + Jakob", "sev": "Major", "note": note,
                })
                add_candidate(
                    f"sweep:ia:relabel:{re.sub(r'[^a-z0-9]+','-',key)}",
                    pages[0], f'"{disp}" means different things on {", ".join(slug(p) for p in pages)}',
                    "Minor",
                    note + " Surfaced by the IA streamlining survey (Phase 2).")
                continue

            # CONSOLIDATE — the same value/KPI on N pages → one canonical home.
            drift = bool(DRIFT_CAPABLE_RE.search(disp + " " + key))
            sev = "Major" if drift else "Minor"
            home_disp = home if home else "— (human picks the owner)"
            note = (f"Same unit on {grp['pageCount']} pages. Canonical home → "
                    f"{home_disp}; deep-link the rest (or render all from one v_*_truth). "
                    + ("DRIFT-CAPABLE KPI: a computed value shown two ways can disagree and hide a "
                       "what-bug — reconcile to one source. " if drift else "")
                    + "VERIFY-FIRST: confirm every instance is the SAME derivation before collapsing.")
            rows.append({
                "unit": disp, "kind": f"info:{kind}", "pages": pages,
                "rec": "CONSOLIDATE", "home": home_disp,
                "law": "Tesler (complexity conserved) + Jakob", "sev": sev, "note": note,
            })
            add_candidate(
                f"sweep:ia:consolidate:{re.sub(r'[^a-z0-9]+','-',key)}",
                home if home else pages[0],
                f'"{disp}" surfaced on {grp["pageCount"]} pages ({", ".join(slug(p) for p in pages)})',
                sev, note + " (IA streamlining survey, Phase 2.)")

    # ── 4: theme clusters (CANDIDATES — different labels, same job) ────────────
    for grp in g["info_theme_clusters"]:
        theme = grp["key"]
        pages = grp["pages"]
        if theme in ("detail breakdown panel", "pending approval"):
            continue  # already covered by the high-confidence passes above
        members = "; ".join(f"{u['label']} ({slug(u['page'])})" for u in grp["units"] if u.get("label"))
        home = owner_of(theme) or "— (human picks)"
        note = (f"{grp['pageCount']} pages answer the \"{theme}\" job a different way: {members}. "
                f"Hick's Law — multiple entry points to one job slow the user. Likely canonical home → "
                f"{home}, others deep-link. REVIEW: confirm one job (merge) vs legitimately distinct "
                "role/context views (e.g. PM-overdue ≠ project-overdue) before acting.")
        rows.append({
            "unit": f"theme: {theme}", "kind": "info:theme", "pages": pages,
            "rec": "DIFFERENTIATE / merge (review)", "home": home,
            "law": "Hick + Miller (chunking)", "sev": "Minor", "note": note,
        })
        add_candidate(
            f"sweep:ia:theme:{re.sub(r'[^a-z0-9]+','-',theme)}",
            pages[0], f'"{theme}" job served {grp["pageCount"]} ways across pages',
            "Minor", note)

    # ── affordance overlap ─────────────────────────────────────────────────────
    for grp in g["affordance_overlap_destinations"]:
        dest = slug(grp["dest"])
        pages = grp["pages"]
        if dest in HUB_PAGES:
            rows.append({
                "unit": f"link → {dest}", "kind": "affordance", "pages": pages,
                "rec": "KEEP (hub link)", "home": dest,
                "law": "Jakob (expected hub)", "sev": "Polish",
                "note": f"{dest} is a hub every page reaches by design; body links to it are expected.",
            })
            continue
        note = (f"Deep page \"{dest}\" reached from {grp['pageCount']} page bodies BEYOND the global "
                f"nav ({', '.join(slug(p) for p in pages)}). Hick's Law — confirm each extra path "
                "earns its place; otherwise rely on the nav + one contextual link.")
        rows.append({
            "unit": f"link → {dest}", "kind": "affordance", "pages": pages,
            "rec": "REVIEW (extra path)", "home": dest,
            "law": "Hick's Law", "sev": "Minor", "note": note,
        })
        add_candidate(
            f"sweep:ia:affordance:{re.sub(r'[^a-z0-9]+','-',dest)}",
            pages[0], f'"{dest}" linked from {grp["pageCount"]} page bodies beyond the nav',
            "Minor", note)

    return {"rows": rows, "candidates": candidates}


# ── markdown plan ────────────────────────────────────────────────────────────
REC_ORDER = ["CONSOLIDATE", "RELABEL / keep-distinct", "DIFFERENTIATE / merge (review)",
             "REVIEW (extra path)", "KEEP (consistent pattern)", "KEEP (hub link)"]


def render_plan(corpus: dict, scored: dict, keep_threshold: int) -> str:
    rows = scored["rows"]
    n_q = len(scored["candidates"])
    L = []
    L.append("# Streamlining Plan — Phase 2 (rubric)\n")
    L.append("> **Proposals, not actions.** Every row is scored by a deterministic rubric and"
             " awaits your sign-off. The engine PROPOSES; you DISPOSE (via"
             " `promotion_dispositions.json`). **No UI is collapsed automatically.**\n")
    L.append("> Built from `ia_inventory_corpus.json` (Phase 1). Method = NN/g content audit"
             " verbs (keep / consolidate / move / remove) + lawsofux severity. The"
             " keep/consolidate/relabel/review split exists because *\"the same thing on N pages\"*"
             " is four different situations — and conflating them is how you delete what you needed.\n")
    counts = {}
    for r in rows:
        verb = r["rec"].split(" (")[0] if r["rec"].startswith("KEEP") else r["rec"]
        counts[r["rec"]] = counts.get(r["rec"], 0) + 1
    L.append("**Tally:** " + " · ".join(f"{v}× {k}" for k, v in sorted(counts.items(), key=lambda x: -x[1])))
    L.append(f"  ·  **{n_q}** rows queued for disposition (KEEP rows are documented here but not"
             " queued — no decision needed).\n")

    by_rec: dict[str, list] = {}
    for r in rows:
        by_rec.setdefault(r["rec"], []).append(r)

    def section(title, recs, blurb):
        present = [(rec, by_rec[rec]) for rec in recs if rec in by_rec]
        if not present:
            return
        L.append(f"## {title}\n")
        L.append(blurb + "\n")
        L.append("| Unit | On pages | Canonical home | UX-law | Severity | Why / verify |")
        L.append("|---|---|---|---|---|---|")
        for rec, rs in present:
            for r in rs:
                pages = ", ".join(slug(p) for p in r["pages"])
                L.append(f"| **{r['unit']}** — _{rec}_ | {pages} | {r['home']} | {r['law']} "
                         f"| {r['sev']} | {r['note']} |")
        L.append("")

    section("1. Consolidate — same value, many pages → one source of truth",
            ["CONSOLIDATE"],
            "_The dangerous kind: a value/KPI duplicated across pages can DRIFT and hide a what-bug._"
            " Pick the canonical home, deep-link the rest (or render all from one `v_*_truth`)."
            " **Verify the derivation is identical before collapsing.**")
    section("2. Relabel — same label, different subject (do NOT collapse)",
            ["RELABEL / keep-distinct"],
            "_same-NAMED ≠ same-derivation, applied to IA._ These are distinct units wearing one"
            " label — disambiguate the wording; collapsing them would lose real information.")
    section("3. Differentiate / merge — one job served many ways (review)",
            ["DIFFERENTIATE / merge (review)"],
            "_Theme candidates (lower confidence)._ A human confirms whether these are one"
            " job-to-be-done (merge to a canonical home + deep-links) or legitimately distinct"
            " role/context views.")
    section("4. Affordance paths — review extra routes",
            ["REVIEW (extra path)"],
            "_Body links to a deep page beyond the global nav (Hick's Law)._ Confirm each extra"
            " path earns its place.")
    section("5. Keep — consistent patterns (documented, no action)",
            ["KEEP (consistent pattern)", "KEEP (hub link)"],
            "_Replicated BY DESIGN — each instance shows its own page's data, or is an expected hub"
            " link (Jakob's Law)._ Not IA defects. Any copy-paste cost is a separate jscpd /"
            " Architect component-extraction refactor that does **not** change the IA.")

    L.append("---")
    L.append("### How to act on this")
    L.append("1. **Queue the decisions:** `python ufai_ingest.py ia_streamlining_candidates.json`"
             f" → merges the {n_q} non-KEEP rows into `sweep_critiques.json` (idempotent), where they"
             " flow through `flywheel_orchestrator` → `promotion_queue.md`.")
    L.append("2. **Dispose** each via `promotion_dispositions.json` (accept / defer / reject) — same"
             " mechanism as every other sweep finding.")
    L.append("3. **For accepted CONSOLIDATE rows**, the implementation is an Architect/Frontend job"
             " (shared component or canonical-source read + deep-link); the **0-math-drift** invariant"
             " (`validate_user_facing_kpi_canonical.py`) must stay green.")
    L.append("\n_Phase 3 (optional): a UXAgent novice×role persona walkthrough to confirm a new user"
             " isn't confused by what survives._")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 2 rubric for the IA streamlining survey.")
    ap.add_argument("--keep-threshold", type=int, default=10,
                    help="info-unit on ≥N pages = a design-system pattern → KEEP (default 10)")
    ap.add_argument("--ingest", action="store_true",
                    help="after writing, also merge candidates into sweep_critiques.json via ufai_ingest.py")
    args = ap.parse_args()

    if not CORPUS.exists():
        print(f"ERROR: {CORPUS.name} not found — run tools/survey_ia_redundancy.py (Phase 1) first.")
        return 1
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    scored = score(corpus, args.keep_threshold)

    plan = ROOT / "streamlining_plan.md"
    plan.write_text(render_plan(corpus, scored, args.keep_threshold), encoding="utf-8")

    cand_file = ROOT / "ia_streamlining_candidates.json"
    cand_file.write_text(json.dumps({
        "_doc": "Phase 2 IA-streamlining critic candidates (sweep_critiques schema). Route via: "
                "python ufai_ingest.py ia_streamlining_candidates.json. Engine proposes, you dispose.",
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "candidates": scored["candidates"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # summary
    recs: dict[str, int] = {}
    for r in scored["rows"]:
        recs[r["rec"]] = recs.get(r["rec"], 0) + 1
    print(f"IA streamlining rubric -- {len(scored['rows'])} rows scored, "
          f"{len(scored['candidates'])} queued for disposition")
    for k in REC_ORDER:
        if k in recs:
            print(f"  {recs[k]:2d}x  {k}")
    print(f"  -> {plan.name} + {cand_file.name}")

    if args.ingest:
        import subprocess
        print("\n--ingest: routing candidates through ufai_ingest.py ...")
        subprocess.run([sys.executable, str(ROOT / "ufai_ingest.py"), str(cand_file)], check=False)
    else:
        print("  (run `python ufai_ingest.py ia_streamlining_candidates.json` to queue them)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
