"""
ux_persona_walkthrough.py  —  Phase 3 of the IA-streamlining surveyor.
================================================================================
Phase 1 found WHAT repeats; Phase 2 said WHAT TO DO; Phase 3 asks the question
that actually decides priority: **does this redundancy hurt a REAL user trying to
get a job done?** A redundancy on a novice's core task path is urgent; the same
redundancy off the beaten path is noise. This is the deterministic, grounded core
of a "UXAgent-style novice×role walkthrough" (reference-holistic-critic-tooling
#4) — it simulates personas attempting jobs-to-be-done and flags the confusion
their path crosses, using REAL inputs:
  - the role model parsed from nav-hub.js (field/supervisor/engineer · hidden ·
    role-gating) → what each persona can actually SEE and REACH;
  - the redundancy map from ia_inventory_corpus.json (Phase 1) → where a job's
    answer is surfaced more than once.

THE CONFUSION RUBRIC (deterministic, each finding cites WHY):
  - AMBIGUITY OF SOURCE — the job's answer appears on ≥2 pages the persona can see
    in their nav. "Which number is right?" Worse for a NOVICE; worst when the value
    is drift-capable (the field lesson: the overdue KPI is derived two ways —
    v_pm_compliance_truth per-asset vs v_pm_scope_items_truth per-scope-item — and
    that drift is what let a stale 'closed' value survive). Jakob + Nielsen #4.
  - CANONICAL UNREACHABLE — the authoritative page for the job is hidden from the
    persona's nav (or role-gated away), so they land on a SECONDARY surface and
    take it as truth. (e.g. predictive.html — the risk source of truth — is
    hidden:true; a supervisor hunting "top risk" never sees it in nav.) Nielsen #6.
  - RELABEL COLLISION — the persona meets the SAME label meaning two different
    things ("Pending approval" = assets on asset-hub, parts on inventory). Nielsen
    #2 (match the real world).
  - CLEAN — exactly one role-visible surface + reachable canonical = the positive
    control (proves the rubric isn't just crying wolf — low_stock comes back CLEAR).

It also computes per-role nav choice-load (Hick's Law): a novice facing a long
tool list decides slower.

DOCTRINE: still SURFACE-only. Phase 3 PRIORITIZES Phase 2's proposals (it cites
the matching sweep:ia:* candidate key) — it never changes UI. The heavier LIVE
tier (drive the actual pages as the persona via Playwright MCP + an LLM reading
the screen) is documented at the foot of the report; this deterministic pass is
the build-first spine that says WHERE to point the live agent.

OUTPUT:  ux_persona_walkthrough.md
USAGE:   python tools/ux_persona_walkthrough.py
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "ia_inventory_corpus.json"
NAVJS = ROOT / "nav-hub.js"

ROLES = ["field", "supervisor", "engineer"]
EXPERIENCES = ["novice", "experienced"]

# What each page is fundamentally ABOUT — so the ambiguity rule applies the same
# same-NAMED ≠ same-derivation discipline as Phase 2: two surfaces about different
# subjects ("PMs on track" vs "workers on target") share a WORD, not a drifting
# number → that's a weak signal, not a "which is right?" confusion.
PAGE_SUBJECT = {
    "asset-hub": "assets", "inventory": "parts", "pm-scheduler": "PM tasks",
    "dayplanner": "personal tasks", "predictive": "asset risk", "shift-brain": "the shift",
    "alert-hub": "alerts", "skillmatrix": "skills", "achievements": "achievements",
    "project-manager": "projects", "marketplace": "listings", "ph-intelligence": "the PH network",
    "analytics": "analytics", "hive": "the hive",
}


# ── parse the role model from nav-hub.js ─────────────────────────────────────
def load_nav() -> dict[str, dict]:
    txt = NAVJS.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"const TOOLS = \[(.*?)\n\s*\];", txt, re.S)
    body = m.group(1) if m else ""
    nav = {}
    for chunk in re.split(r"\{\s*label:", body)[1:]:
        head = chunk.split("icon:")[0]
        href = re.search(r"href:\s*'([^']+\.html)'", head)
        if not href:
            continue
        page = href.group(1)
        label = re.match(r"\s*'([^']+)'", chunk)
        roles_m = re.search(r"roles:\s*\[([^\]]*)\]", head)
        roles = (set(re.findall(r"'([^']+)'", roles_m.group(1))) if roles_m else set(ROLES))
        nav[page] = {
            "label": label.group(1) if label else page,
            "roles": roles,                      # which modes show it
            "universal": roles_m is None,        # visible in every mode
            "hidden": "hidden: true" in head or "hidden:true" in head,
            "section": (re.search(r"section:\s*'([^']+)'", head) or [None, None])[1]
            if re.search(r"section:\s*'([^']+)'", head) else None,
        }
    return nav


def role_can_see_in_nav(nav: dict, page: str, role: str) -> bool:
    """Visible in this role's PRIMARY nav = role allowed AND not hidden."""
    e = nav.get(page)
    if not e:
        return False
    return (not e["hidden"]) and (e["universal"] or role in e["roles"])


def role_allowed(nav: dict, page: str, role: str) -> bool:
    e = nav.get(page)
    if not e:
        return False
    return e["universal"] or role in e["roles"]


# ── tasks (jobs-to-be-done), grounded in the survey themes + the role model ──
# theme → the corpus cluster whose pages are the job's redundant surfaces.
TASKS = [
    {"id": "due_overdue", "name": "Find what maintenance is due or overdue",
     "roles": {"field", "supervisor"}, "canonical": "pm-scheduler.html",
     "themes": ["late / overdue", "due soon / upcoming"], "drift": True,
     "candidates": ["sweep:ia:theme:late-overdue", "sweep:ia:theme:due-soon-upcoming"],
     "drift_note": "the overdue count is derived two ways (per-asset v_pm_compliance_truth vs "
                   "per-scope-item v_pm_scope_items_truth) → the surfaces CAN disagree."},
    {"id": "top_risk", "name": "Find the highest-risk asset right now",
     "roles": {"supervisor", "engineer"}, "canonical": "predictive.html",
     "themes": ["risk / hot / critical"], "drift": True,
     "candidates": ["sweep:ia:theme:risk-hot-critical"],
     "drift_note": "risk is shown as alerts (alert-hub), critical assets (asset-hub), and the "
                   "risk ranking (predictive) — three lenses, one underlying question."},
    {"id": "approvals", "name": "See what is waiting for my approval",
     "roles": {"supervisor"}, "canonical": None,
     "themes": [], "relabel": "Pending approval", "relabel_pages": ["asset-hub.html", "inventory.html"],
     "candidates": ["sweep:ia:relabel:pending-approval"],
     "drift": False},
    {"id": "low_stock", "name": "Check which parts are low or out of stock",
     "roles": {"field", "supervisor"}, "canonical": "inventory.html",
     "themes": [], "drift": False, "candidates": []},   # positive control — single source
    {"id": "team_health", "name": "Check the team's skills / readiness",
     "roles": {"supervisor"}, "canonical": "skillmatrix.html",
     "themes": ["healthy / on-track"], "drift": False,
     "candidates": ["sweep:ia:theme:healthy-on-track"]},
]


def theme_pages(corpus: dict, theme_keys: list[str]) -> list[str]:
    out = set()
    for grp in corpus["groups"]["info_theme_clusters"]:
        if grp["key"] in theme_keys:
            out.update(grp["pages"])
    return sorted(out)


def slug(p: str) -> str:
    return p.replace(".html", "")


# ── the walkthrough ──────────────────────────────────────────────────────────
def walk(corpus: dict, nav: dict) -> dict:
    findings = []   # one per persona×task
    for task in TASKS:
        surfaces = set(theme_pages(corpus, task.get("themes", [])))
        if task.get("relabel_pages"):
            surfaces.update(task["relabel_pages"])
        if task["canonical"]:
            surfaces.add(task["canonical"])
        for role in sorted(task["roles"]):
            visible = sorted(p for p in surfaces if role_can_see_in_nav(nav, p, role))
            for exp in EXPERIENCES:
                issues = []
                # AMBIGUITY OF SOURCE
                if len(visible) >= 2:
                    subjects = {PAGE_SUBJECT.get(slug(p), slug(p)) for p in visible}
                    note = (f"{len(visible)} pages in this {role}'s nav answer the same job "
                            f"({', '.join(slug(p) for p in visible)}).")
                    if task.get("drift"):
                        # a genuinely drift-capable KPI (same number, two derivations) = the
                        # dangerous ambiguity regardless of page subject.
                        sev = "High"
                        note += " " + task.get("drift_note", "")
                        issues.append(("Ambiguity of source", sev, "Jakob + Nielsen #4", note))
                    elif len(subjects) >= 2:
                        # cross-subject: shares a word, not a number → weak (same discipline
                        # as Phase 2's RELABEL — don't cry "which is right?" over distinct jobs).
                        issues.append(("Ambiguity (weak / cross-subject)", "Low", "Jakob",
                                       note + f" BUT these surface different subjects "
                                       f"({', '.join(sorted(subjects))}) → likely distinct jobs sharing "
                                       "a word, not one drifting number."))
                    else:
                        issues.append(("Ambiguity of source", "High" if exp == "novice" else "Med",
                                       "Jakob + Nielsen #4", note))
                # CANONICAL UNREACHABLE
                can = task["canonical"]
                if can and not role_can_see_in_nav(nav, can, role):
                    why = ("hidden from primary nav" if nav.get(can, {}).get("hidden")
                           else "not in this role's mode")
                    if role_allowed(nav, can, role) or nav.get(can, {}).get("hidden"):
                        sev = "High" if exp == "novice" else "Med"
                        issues.append(("Canonical unreachable", sev, "Nielsen #6 (recognition)",
                                       f"The source of truth ({slug(can)}) is {why} → this {role} "
                                       f"lands on a secondary surface and takes it as authoritative."))
                # RELABEL COLLISION
                if task.get("relabel"):
                    seen = [p for p in task["relabel_pages"] if role_can_see_in_nav(nav, p, role)]
                    if len(seen) >= 2:
                        sev = "High" if exp == "novice" else "Med"
                        issues.append(("Relabel collision", sev, "Nielsen #2 (real world)",
                                       f'"{task["relabel"]}" appears on {", ".join(slug(p) for p in seen)} '
                                       "meaning different subjects (assets vs parts) under one label."))
                # verdict
                hi = any(i[1] == "High" for i in issues)
                med = any(i[1] == "Med" for i in issues)
                verdict = "CONFUSING" if hi else ("MILD" if med else "CLEAR")
                findings.append({
                    "task": task["id"], "task_name": task["name"], "role": role, "exp": exp,
                    "canonical": slug(can) if can else "— (ambiguous)",
                    "canonical_reachable": bool(can and role_can_see_in_nav(nav, can, role)),
                    "visible_surfaces": [slug(p) for p in visible],
                    "issues": issues, "verdict": verdict,
                    "candidates": task.get("candidates", []),
                })

    # Hick: per-role primary-nav load
    nav_load = {}
    for role in ROLES:
        items = [p for p, e in nav.items() if (not e["hidden"]) and (e["universal"] or role in e["roles"])]
        nav_load[role] = len(items)

    return {"findings": findings, "nav_load": nav_load}


# ── report ───────────────────────────────────────────────────────────────────
SEV_RANK = {"High": 0, "Med": 1, "Low": 2}


def render(corpus: dict, nav: dict, res: dict) -> str:
    f = res["findings"]
    L = []
    L.append("# UX Persona Walkthrough — Phase 3 (does the redundancy confuse a real user?)\n")
    L.append("> **Simulated, deterministic, SURFACE-only.** Personas (role × experience) attempt"
             " real jobs-to-be-done; the rubric flags the confusion their path crosses, grounded in"
             " the nav-hub.js role model + the Phase-1 redundancy map. It PRIORITIZES Phase 2's"
             " proposals (each finding cites the matching `sweep:ia:*` key); it changes nothing.\n")

    # Hick nav load
    L.append("## Nav choice-load per role (Hick's Law)\n")
    L.append("_Primary-nav items a role sees (hidden tools excluded). More choices = slower"
             " decisions, worst for a novice._\n")
    L.append("| Role | Primary-nav tools |")
    L.append("|---|---|")
    for role in ROLES:
        L.append(f"| {role} | {res['nav_load'][role]} |")
    L.append("")

    # headline verdict matrix (novice)
    L.append("## Novice verdict matrix\n")
    L.append("_The novice is where confusion bites. CLEAR = single obvious source; MILD = a"
             " secondary-source risk; CONFUSING = multiple authoritative-looking answers or an"
             " unreachable source of truth._\n")
    L.append("| Job-to-be-done | Role | Canonical home | Reachable? | Surfaces in nav | Verdict |")
    L.append("|---|---|---|---|---|---|")
    for fi in [x for x in f if x["exp"] == "novice"]:
        reach = "yes" if fi["canonical_reachable"] else "**NO**"
        surf = ", ".join(fi["visible_surfaces"]) or "—"
        L.append(f"| {fi['task_name']} | {fi['role']} | {fi['canonical']} | {reach} | {surf} "
                 f"| {'**'+fi['verdict']+'**' if fi['verdict']!='CLEAR' else fi['verdict']} |")
    L.append("")

    # ranked confusions (novice, High/Med)
    L.append("## Confusion findings, ranked (novice first)\n")
    flat = []
    for fi in f:
        for (kind, sev, law, note) in fi["issues"]:
            flat.append((fi, kind, sev, law, note))
    flat.sort(key=lambda x: (0 if x[0]["exp"] == "novice" else 1, SEV_RANK.get(x[2], 3), x[0]["task"]))
    if not flat:
        L.append("_No confusion findings — every job has a single clear source for every persona._")
    else:
        L.append("| # | Persona | Job | Confusion | Sev | UX-law | Why | Prioritizes |")
        L.append("|---|---|---|---|---|---|---|---|")
        for i, (fi, kind, sev, law, note) in enumerate(flat, 1):
            cand = ", ".join(f"`{c}`" for c in fi["candidates"]) or "—"
            L.append(f"| {i} | {fi['role']}/{fi['exp']} | {fi['task_name']} | **{kind}** | {sev} "
                     f"| {law} | {note} | {cand} |")
    L.append("")

    # what's CLEAR (the positive control)
    clean = [fi for fi in f if fi["exp"] == "novice" and fi["verdict"] == "CLEAR"]
    if clean:
        L.append("### Positive control (came back CLEAR — proves the rubric isn't crying wolf)\n")
        for fi in clean:
            L.append(f"- **{fi['task_name']}** ({fi['role']} novice): single source "
                     f"`{fi['canonical']}`, reachable — no ambiguity.")
        L.append("")

    # how Phase 3 feeds Phase 2
    confusing = sorted({c for fi in f if fi["verdict"] == "CONFUSING" for c in fi["candidates"]})
    L.append("## How this re-prioritizes Phase 2\n")
    if confusing:
        L.append("These Phase-2 candidates sit on a **CONFUSING novice path** → treat as the"
                 " highest-priority dispositions (not just Minor TASTE):\n")
        for c in confusing:
            L.append(f"- `{c}`")
    else:
        L.append("_No queued candidate falls on a CONFUSING path._")
    L.append("")
    L.append("---")
    L.append("### Phase 3 — the heavier LIVE tier (optional)")
    L.append("This deterministic pass says WHERE a new user gets confused. To CONFIRM it with a"
             " real agent: drive each CONFUSING row live in Playwright MCP as the persona —"
             " sign in, set the role mode, attempt the job, and have the model report (a) could it"
             " find the answer, (b) did two surfaces show different numbers, (c) did it trust the"
             " wrong one. Feed disagreements back as evidence on the cited `sweep:ia:*` candidate."
             " The seam already exists: `__UFAI.inventory()` (Layer A) dumps the per-page units the"
             " agent reads. **Still SURFACE-only — the human disposes.**")
    return "\n".join(L) + "\n"


def main() -> int:
    if not CORPUS.exists():
        print(f"ERROR: {CORPUS.name} not found — run Phase 1 (survey_ia_redundancy.py) first.")
        return 1
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    nav = load_nav()
    res = walk(corpus, nav)

    out = ROOT / "ux_persona_walkthrough.md"
    out.write_text(render(corpus, nav, res), encoding="utf-8")

    nov = [x for x in res["findings"] if x["exp"] == "novice"]
    confusing = [x for x in nov if x["verdict"] == "CONFUSING"]
    mild = [x for x in nov if x["verdict"] == "MILD"]
    clear = [x for x in nov if x["verdict"] == "CLEAR"]
    print(f"UX persona walkthrough -- {len(res['findings'])} persona x task runs "
          f"({len(nav)} nav tools parsed)")
    print(f"  novice verdicts: {len(confusing)} CONFUSING / {len(mild)} MILD / {len(clear)} CLEAR")
    for x in confusing:
        kinds = ", ".join(i[0] for i in x["issues"])
        print(f"   CONFUSING: {x['role']} novice -- {x['task_name']}  [{kinds}]")
    print(f"  nav load (Hick): " + " / ".join(f"{r}={res['nav_load'][r]}" for r in ROLES))
    print(f"  -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
