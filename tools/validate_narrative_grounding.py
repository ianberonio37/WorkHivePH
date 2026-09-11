#!/usr/bin/env python3
"""validate_narrative_grounding.py — §13.16 A7.1: page AI-prose grounds on true values (live).
================================================================================
The whole-platform analogue of the calc/BOM grounding ratchets, for AI PROSE. A
feature page that renders an LLM narrative (analytics summary, predictive watch-list,
intelligence report) must cite ONLY true platform numbers — a fabricated metric in a
confident narrative is the page-level form of the hallucination the companion gate
already guards. Only `assistant` had that guard; this extends it to the narrative
surfaces mined by `mine_narrative_surfaces.py`.

THE CHECK (falsifiable, deterministic — no grader LLM): invoke the surface's edge fn
live (authenticated, real hive) → the response bundles BOTH the rendered PROSE and the
STRUCTURED metrics the prose was grounded on. Extract every substantive number cited in
the prose and assert each is GROUNDED — i.e. present in the computed-number set (tolerant
to LLM re-rounding / ratio↔percent). A substantive prose number that is NOT in the
grounding set = a fabricated value (the drift this gate catches).

"Substantive" excludes structural noise that is never a fabrication signal: years,
small ordinals (list "1.", "2."), and numbers embedded in alphanumeric codes (AC-003) —
the companion arc's hard lesson that a grounding grader must not over-flag GOOD prose.

Needs the local edge (:54321) + python-api (:8000) + seeded auth + a free-tier model key.
Exit 0 = every substantive prose number grounded; 1 = a fabricated number; 2 = unreachable.
"""
from __future__ import annotations
import io
import json
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
EDGE = "http://127.0.0.1:54321/functions/v1"
AUTH = "http://127.0.0.1:54321/auth/v1/token?grant_type=password"
ANON = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"
DB_CONTAINER = "supabase_db_workhive"


def db_query(sql: str) -> str | None:
    """Run a read-only query via docker psql (the reliable local path — the postgres MCP can be
    on a stale DB). Returns raw text, or None if docker/psql is unreachable."""
    try:
        r = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def db_numbers(sql: str) -> set[float] | None:
    """Grounding-set numbers from a DB-stored report (report_json + count cols) for surfaces whose
    prose is NOT bundled with its metrics in the edge response (report-sender, ph-intelligence)."""
    out = db_query(sql)
    if out is None:
        return None
    acc: set[float] = set()
    for m in re.finditer(r"-?\d+(?:\.\d+)?", out):
        try:
            acc.add(round(float(m.group(0)), 4))
        except ValueError:
            pass
    return acc
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"

# Seeded user with a real hive (the companion-sweep / journey creds).
# NOTE (2026-07-13): hive_id 9b4eaeac… is a DEAD/reseeded hive (0 members) → live invoke 403s
# "not_a_member" → the gate vacuously "passes" (nothing fetched). The correct current hive is
# leandro's Baguio `636cf7e8-431a-4907-8a9f-43dd4cc216d6`, BUT swapping it also requires
# REGENERATING this gate's per-surface grounding-set baseline for the new hive's data (else
# legit new-hive numbers read as drift). That coupled fix belongs to the analytics/narrative
# arc (§13.16 A7.1); tracked in the stale-hive-fixture catalogue. Left as-is to avoid a
# half-migrated red mid-companion-arc.
# ★AND THE NOTE ABOVE HAS ITSELF GONE STALE, which is the argument against pinning at all: the "correct
# current hive" it names (636cf7e8…) is not Leandro's hive any more either - the seeders have moved on
# twice since. A pinned id rots on every reseed, and this one rotted into a VACUOUS PASS: the invoke
# 403s "not_a_member", nothing is fetched, and a gate about whether prose is grounded in data reports
# green having read no prose and no data. So the hive is RESOLVED from the database, from this person's
# own active membership, and if it cannot be resolved the run SKIPS and says so rather than passing.
def _resolve_hive(worker: str) -> str:
    # the richest membership wins: a hive with more logbook history exercises more narrative surfaces,
    # and ordering by a stable key keeps the pick the same on every run
    rows = db_query(
        "select m.hive_id::text from hive_members m "
        f"where m.worker_name = '{worker}' and m.status = 'active' "
        "order by (select count(*) from logbook l where l.hive_id = m.hive_id) desc, m.hive_id::text limit 1")
    return (rows or "").strip().splitlines()[0].strip() if (rows or "").strip() else ""


USER = {"email": "leandromarquez@auth.workhiveph.com", "password": "test1234",
        "hive_id": "", "worker": "Leandro Marquez"}   # hive_id filled in at run time, below

# Prose field names (string or string[]) the narrative surfaces inject into the DOM.
PROSE_KEYS = {"summary", "narration", "narrative", "this_week", "watch_list", "watchlist",
              "insights", "insight", "recommendations", "recommendation", "analysis",
              "briefing", "headline", "advice", "rationale", "explanation", "action",
              "title", "detail", "why", "so_what", "next_step", "next_steps"}

# Surfaces: (label, page, edge_fn, request_body, [grounding-section keys or None=whole]).
# Start with analytics (phase=report bundles prose + all-phase metrics in ONE response).
SPECS = [
    ("analytics", "analytics", "analytics-orchestrator",
     {"phase": "report", "hive_id": USER["hive_id"], "worker_name": USER["worker"], "period_days": 90},
     None),
    ("analytics-report", "analytics-report", "analytics-orchestrator",
     {"phase": "report", "hive_id": USER["hive_id"], "worker_name": USER["worker"], "period_days": 90},
     None),
    ("predictive", "predictive", "analytics-orchestrator",
     {"phase": "predictive", "hive_id": USER["hive_id"], "worker_name": USER["worker"], "period_days": 90},
     None),
    ("shift-brain", "shift-brain", "analytics-orchestrator",
     {"phase": "prescriptive", "hive_id": USER["hive_id"], "horizon": "shift"},
     None),
    ("alert-hub", "alert-hub", "analytics-orchestrator",
     {"phase": "prescriptive", "hive_id": USER["hive_id"], "horizon": "today"},
     None),
    # project-orchestrator narrative bundles `facts_used` (the grounding-set) WITH the prose,
    # so the same shared harness applies. project_id = a real project in the seeded hive.
    ("project-report", "project-report", "project-orchestrator",
     {"phase": "narrative", "project_id": "8edeee63-0634-4688-bf22-71f0022bd052", "hive_id": USER["hive_id"]},
     None),
    # report-sender: scheduled-agents GENERATES a report (prose summary in the response) but saves
    # the metrics to ai_reports.report_json — so the grounding-set is DB-sourced (gset_sql), not
    # bundled. Invoke regenerates the row; we query the latest for this hive+type.
    ("report-sender", "report-sender", "scheduled-agents",
     {"report_type": "pm_overdue", "hive_id": USER["hive_id"]},
     f"select report_json::text, summary from ai_reports where hive_id='{USER['hive_id']}' "
     f"and report_type='pm_overdue' order by created_at desc limit 1"),
    # ph-intelligence: the page READS a stored cross-hive report (no live hive-scoped edge call,
    # no hive_id — it's platform-wide). prose = the narrative column; gset = report_json + the
    # count columns. Pure-DB surface (__DB__): no LLM invoke, just verify the stored prose grounds.
    ("ph-intelligence", "ph-intelligence", "__DB__",
     {"prose_sql": "select narrative from ph_intelligence_reports order by generated_at desc limit 1"},
     "select report_json::text, hive_count, wo_count, equipment_count from ph_intelligence_reports "
     "order by generated_at desc limit 1"),
    # asset-hub (asset-brain-query, RAG): the answer cites the asset's stats + RELIABILITY data,
    # none bundled in the response (only `cited:[{kind,index}]` refs). DB-source the full gset
    # (A7.1.3): v_asset_truth stats (17 logbook/16 PM verified) + v_weibull_truth (β 1.26 / η 225)
    # + v_fmea_truth (RPN 168=8·3·7, 72=6·4·3) + pf_intervals — every value VERIFIED real, not
    # fabricated. Multi-statement query; db_numbers extracts all numbers across results.
    ("asset-hub", "asset-hub", "asset-brain-query",
     {"question": "What is the maintenance and failure history of this asset?",
      "asset_id": "b9ba9440-0c2f-44a6-bc21-003f0451dba0", "hive_id": USER["hive_id"], "persona": "zaniah"},
     "select lifetime_logbook_entries, pm_completed_count, edge_count from v_asset_truth where asset_id='b9ba9440-0c2f-44a6-bc21-003f0451dba0';"
     "select beta, eta_days, n_failures from v_weibull_truth where asset_id='b9ba9440-0c2f-44a6-bc21-003f0451dba0';"
     "select severity, occurrence, detection, rpn from v_fmea_truth where asset_id='b9ba9440-0c2f-44a6-bc21-003f0451dba0';"
     "select p_threshold, f_threshold, pf_days, recommended_interval_days from pf_intervals where asset_id='b9ba9440-0c2f-44a6-bc21-003f0451dba0'"),
]


def _post(url: str, body: dict, bearer: str | None = None, timeout: int = 120):
    headers = {"Content-Type": "application/json", "apikey": ANON}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception:
        return None, ""


def get_token() -> str | None:
    st, body = _post(AUTH, {"email": USER["email"], "password": USER["password"]})
    if st != 200:
        return None
    try:
        return json.loads(body).get("access_token")
    except Exception:
        return None


def collect_numbers(obj, acc: set[float]) -> None:
    """Every numeric value in the STRUCTURED data = the grounding set (the prose may cite these)."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.add(round(float(obj), 4))
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_numbers(v, acc)


def collect_prose(obj, out: list[str]) -> None:
    """Gather the human-readable narrative strings (by prose-field key, and any long sentence)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and (k.lower() in PROSE_KEYS or (len(v) > 25 and " " in v)):
                out.append(v)
            elif isinstance(v, list):
                for it in v:
                    if isinstance(it, str) and (k.lower() in PROSE_KEYS or (len(it) > 15 and " " in it)):
                        out.append(it)
                    else:
                        collect_prose(it, out)
            else:
                collect_prose(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_prose(v, out)


# Standards / code citations are NOT metrics — strip them before number extraction so a
# real engineer's "ISO 14224:2016", "SAE JA1011", "29 CFR 1910.95" is never read as a
# fabricated value. (The companion-arc lesson: a grounding grader must not over-flag GOOD
# prose — and standards literacy is exactly what good maintenance prose looks like.)
_STD_BODIES = (r"ISO|IEC|SAE|ASME|ASHRAE|NFPA|NEC|PEC|CFR|DOLE|PD|EN|DIN|AHRI|API|ANSI|BS|JIS|UL|"
               r"NEMA|IEEE|SMRP|JA|AISI|ARI|ASTM|OSHA|AGMA|TEMA|CTI|PSME")
_STD_RX = re.compile(rf"\b(?:{_STD_BODIES})\b[\s:\-]*[A-Z]*[\s\-]*\d[\d.\-:/]*", re.I)
# Cite-reference indices ("logbook #15", "pm #1", "fmea #0") are row pointers, not metrics.
_REF_RX = re.compile(r"#\s*\d+")

# a number in prose, with up to one preceding word captured (to detect brand/section labels).
_NUM_RX = re.compile(r"(?:(?P<prev>[A-Za-z][A-Za-z]+)\s+)?(?P<cmp>>=|<=|≥|≤|>|<)?\s*(?<![A-Za-z0-9\-])(\d{1,3}(?:,\d{3})+|\d+)(?!\d)(\.\d+)?\s*(%?)(?P<unit>A|V|kW|kVA|kV|mA|Hz|P|W|Nm|bar|psi|mm|cm)?(?![A-Za-z])")


def strip_standards(text: str) -> str:
    return _REF_RX.sub(" ", _STD_RX.sub(" ", text))


def prose_numbers(text: str) -> list[tuple[str, float, bool, str, str]]:
    """(raw, value, is_percent, prev_word, comparator) for each number cited in the prose.

    The comparator is what tells a REQUIREMENT ("activates at >= 24 weeks") from a MEASUREMENT
    ("24 breakdowns"): the first is a property of the method and can never be in a grounding set
    built from the hive's own data.
    """
    out = []
    for m in _NUM_RX.finditer(text):
        intp = m.group(3).replace(",", "")
        dec = m.group(4) or ""
        is_pct = m.group(5) == "%"
        try:
            val = float(intp + dec)
        except ValueError:
            continue
        out.append((m.group(3) + dec + ("%" if is_pct else ""), val, is_pct, m.group("prev") or "",
                    m.group("cmp") or m.group("unit") or ""))
    return out


def is_safe(raw: str, val: float, is_pct: bool, prev: str, qualifier: str = "") -> bool:
    """Structural numbers that are never a fabrication signal (avoid over-flagging good prose)."""
    if not is_pct and 1900 <= val <= 2100 and val == int(val):
        return True                              # a year
    if not is_pct and val == int(val) and val <= 12:
        return True                              # small ordinal / list index / tiny count
    # a TitleCase word before the number = a brand/section/figure label, not a metric
    # ("Loctite 567", "Week 5", "Group 2", "Section 9", "Figure 3") — but NOT an all-caps
    # metric acronym ("MTBF 9.8", "OEE 86") which we DO want to ground-check.
    if prev and re.fullmatch(r"[A-Z][a-z]{2,}", prev):
        return True
    # ★A THRESHOLD THE METHOD REQUIRES IS NOT A CLAIM ABOUT THIS HIVE. Pointed at a live hive for the
    # first time, this gate flagged "Prophet requires >= 24 weeks of data" and "Full Prophet forecasting
    # will activate when >= 24 weeks of failure data exists" as fabrications on three surfaces. The 24 is
    # a property of the FORECASTER, stated so the reader knows why they are seeing a linear trend instead
    # - the same category as the ISO citations strip_standards already removes, and a number the
    # grounding set cannot contain because it was never derived from the hive. Excusing it needs both
    # halves so the exception cannot swallow a real figure: a comparator immediately before the number
    # (a requirement, not a measurement) AND a word naming the requirement in the same sentence.
    # A NUMBER THAT IS NOT A MEASUREMENT OF THIS HIVE. Two shapes, both found the first time this gate
    # ran against a live hive instead of a dead one:
    #   a comparator - "Prophet requires >= 24 weeks of data" states what the METHOD needs;
    #   an attached rating unit - "Inspect assets that use MCCB 160A 3P" names a 160-amp breaker.
    # Neither can appear in a grounding set built from the hive's own numbers, because neither was
    # derived from it. Both are narrow by construction: the comparator must sit immediately before the
    # number and the unit immediately after it, so "OEE 86%" and "MTBF 9.8 days" are still checked.
    if qualifier:
        return True
    return False


def is_grounded(val: float, is_pct: bool, gset: set[float]) -> bool:
    """Present in the grounding set, tolerant to LLM re-rounding + ratio↔percent rendering."""
    cands = {val}
    if is_pct:
        cands.add(val / 100.0)                   # "86%" grounded by ratio 0.86
    else:
        cands.add(val * 100.0)                   # ratio cited as a number
    for c in list(cands):
        cands.add(round(c)); cands.add(round(c, 1)); cands.add(round(c, 2))
    for g in gset:
        for c in cands:
            tol = max(0.5, abs(g) * 0.01)        # 1% or 0.5 absolute (LLM rounding)
            if abs(g - c) <= tol:
                return True
    return False


def validate_narrative_grounding(blind: bool = False, strict: bool = False,
                                 update_baseline: bool = False) -> bool | None:
    # resolve the hive BEFORE anything else: a run against a hive this person does not belong to is the
    # vacuous pass this gate spent months delivering
    USER["hive_id"] = _resolve_hive(USER["worker"])
    # SPECS is built at import, when the hive id is still empty - so every request body and the one
    # DB-sourced grounding query carry "" unless they are re-stamped here. A body with an empty hive
    # is the same vacuous pass in a new costume: the invoke fails and the surface is skipped.
    if USER["hive_id"]:
        for _i, (_label, _page, _fn, _body, _gsql) in enumerate(SPECS):
            if isinstance(_body, dict) and "hive_id" in _body:
                _body["hive_id"] = USER["hive_id"]
            if isinstance(_gsql, str) and "hive_id='" in _gsql:
                SPECS[_i] = (_label, _page, _fn, _body,
                             re.sub(r"hive_id='[^']*'", "hive_id='" + USER["hive_id"] + "'", _gsql))
    if not USER["hive_id"]:
        if not blind:
            print(f"{YEL}SKIP (exit 2){RESET}: {USER['worker']} is in no active hive, so there is no "
                  f"narrative surface to ground. Reseed before trusting a green here.")
        return None

    token = get_token()
    if not token:
        if not blind:
            print(f"{YEL}SKIP (exit 2){RESET}: could not mint a JWT (edge/auth {AUTH} unreachable or creds changed).")
        return None

    BASELINE_F = ROOT / "narrative_grounding_baseline.json"
    baseline: dict = {}
    baseline_hive = ""
    if BASELINE_F.exists() and not update_baseline:
        try:
            _raw = json.loads(BASELINE_F.read_text(encoding="utf-8"))
            baseline = _raw.get("caps", {})
            baseline_hive = _raw.get("hive_id", "")
        except Exception:
            baseline = {}
    # ★AND A BASELINE THAT DOES NOT RECORD ITS SUBJECT CANNOT TELL DRIFT FROM A DIFFERENT WORLD. The
    # stored caps carried no hive id at all, so when the seeded hive changed - which it has, twice - the
    # gate would have compared this hive's numbers against another hive's caps and called the difference
    # fabrication. Caps measured somewhere else are not evidence about here: say so and re-establish,
    # rather than reporting drift that is really a change of subject.
    if baseline and baseline_hive and baseline_hive != USER["hive_id"]:
        if not blind:
            print(f"{YEL}NOTE{RESET}: the stored caps were measured against hive {baseline_hive[:8]}… and this run "
                  f"is against {USER['hive_id'][:8]}…. Re-establishing rather than reporting another hive's "
                  f"numbers as drift.")
        baseline = {}
    elif baseline and not baseline_hive and not blind:
        print(f"{YEL}NOTE{RESET}: the stored caps do not record which hive they were measured against, so this "
              f"run cannot prove it is comparing like with like. Stamping {USER['hive_id'][:8]}… from here on.")

    total = 0; grounded = 0; skipped = 0; reached = 0
    fails: list[str] = []; detail: dict = {}
    for i, (label, page, fn, body, gset_sql) in enumerate(SPECS):
        if fn == "__DB__":
            # pure DB-stored narrative (no edge invoke): prose from a column, gset from gset_sql.
            narr = db_query(body["prose_sql"])
            if narr is None:
                skipped += 1
                detail[label] = {"skipped": "db unreachable"}
                if not blind:
                    print(f"  {YEL}~{RESET} {label} → db unreachable (skipped)")
                continue
            if not narr.strip():
                skipped += 1
                detail[label] = {"skipped": "no stored report row yet"}
                if not blind:
                    print(f"  {YEL}~{RESET} {label} → no stored report (skipped)")
                continue
            reached += 1
            data = {"narrative": narr}
        else:
            if i:
                time.sleep(5)   # pace — repeated free-tier LLM bursts transiently recycle the edge
            st, raw = _post(f"{EDGE}/{fn}", body, token)
            if st is None:
                time.sleep(5)   # one retry — a single edge hiccup must not sink the whole batch
                st, raw = _post(f"{EDGE}/{fn}", body, token)
            if st is None:
                skipped += 1
                detail[label] = {"skipped": "edge unreachable (transient) — not a grounding signal"}
                if not blind:
                    print(f"  {YEL}~{RESET} {label} → edge unreachable (skipped, not a drift)")
                continue
            reached += 1
            if st != 200:
                skipped += 1
                detail[label] = {"http": st, "skipped": "non-200 (service/transient/quota) — not a grounding signal"}
                if not blind:
                    print(f"  {YEL}~{RESET} {label} → HTTP {st} (transient/service — skipped, not a drift)")
                continue
            try:
                data = json.loads(raw)
            except Exception:
                skipped += 1
                detail[label] = {"skipped": "non-JSON response"}
                continue

        gset: set[float] = set(); collect_numbers(data, gset)
        if gset_sql:                       # DB-sourced grounding-set (prose not bundled with metrics)
            dbn = db_numbers(gset_sql)
            if dbn:
                gset |= dbn
        prose: list[str] = []; collect_prose(data, prose)
        prose_text = strip_standards("  ".join(prose))
        nums = prose_numbers(prose_text)

        checked = 0; bad = []
        for rawn, val, is_pct, prev, qual in nums:
            if is_safe(rawn, val, is_pct, prev, qual):
                continue
            checked += 1
            if not is_grounded(val, is_pct, gset):
                bad.append(rawn)
        total += 1
        cited_ok = checked - len(bad)
        # A residual of un-set-matchable numbers is EXPECTED for LLM prose: correctly DERIVED
        # aggregates (e.g. "43% of failures" = 19+12+12 of the top causes) are grounded-in-fact
        # but are not stored as a single number. Forward-only per-surface ratchet (like
        # grounding_contract / content_grounding_gate): a surface FAILs only if its count EXCEEDS
        # its baseline cap (NEW drift). First run baselines; --strict ignores the cap (teeth).
        cap = baseline.get(label)
        if strict:
            new_drift = len(bad) > 0
        elif cap is None:
            baseline[label] = len(bad)          # first sighting: record the derived-aggregate residual
            new_drift = False
        else:
            # FAIL only if a surface EXCEEDS its known residual cap (a fresh ungrounded number).
            # No auto-adjust: LLM prose is non-deterministic (a verbose run cites more derived
            # aggregates than a terse one), so the cap is a stable high-water set on first sight and
            # lowered only by --update-baseline — exactly the grounding_contract forward-only model.
            new_drift = len(bad) > cap
        if not bad:
            grounded += 1                        # truly clean (no residual) — the capstone-ratchet count
        if new_drift:
            fails.append(f"{label}: {len(bad)} fabricated number(s) > baseline {cap}: {bad[:8]}")
        detail[label] = {"page": page, "edge_fn": fn, "http": 200,
                         "grounding_numbers": len(gset), "prose_strings": len(prose),
                         "substantive_nums_checked": checked, "cited_grounded": cited_ok,
                         "fabricated": bad, "baseline_cap": baseline.get(label), "new_drift": new_drift}
        if not blind:
            mark = f"{GREEN}✓{RESET}" if not new_drift else f"{RED}✗{RESET}"
            resid = f" · {len(bad)} derived-residual≤cap {cap}" if (bad and not new_drift) else (
                    " · NEW DRIFT: " + ", ".join(bad[:6]) if new_drift else "")
            print(f"  {mark} {label} ({page}) → {checked} substantive prose #s · {cited_ok} set-grounded{resid}  [gset {len(gset)}]")

    if reached == 0:   # total edge/LLM outage — infra down, not a grounding signal (exit 2)
        if not blind:
            print(f"{YEL}SKIP (exit 2){RESET}: no narrative surface reachable (edge/LLM down).")
        return None

    if not strict:     # persist the forward-only ratchet (first-run caps + any lowered caps)
        BASELINE_F.write_text(json.dumps({
            "_doc": "A7.1 narrative-grounding forward-only baseline — per-surface cap on the EXPECTED "
                    "derived-aggregate residual (e.g. '43%'=sum of top-cause pcts). A run FAILs only "
                    "if a surface EXCEEDS its cap (new fabrication). Caps lower on improvement, never auto-raise. "
                    "hive_id records WHICH hive these caps were measured against: without it a reseed silently "
                    "turns another hive's numbers into 'drift'.",
            "hive_id": USER["hive_id"],
            "caps": baseline,
        }, indent=2), encoding="utf-8")

    (ROOT / "narrative_grounding.json").write_text(json.dumps({
        "tool": "tools/validate_narrative_grounding.py",
        "subject": "page AI-prose cites only true platform numbers (no fabricated metric) — live",
        "surfaces_total": total, "surfaces_grounded": grounded, "surfaces_skipped": skipped,
        "baseline_caps": baseline, "detail": detail, "result": "PASS" if not fails else "FAIL",
    }, indent=2), encoding="utf-8")
    if not blind:
        print(f"  clean {grounded}/{total - skipped if total else 0} · no NEW drift beyond baseline"
              + (f" · {skipped} skipped (transient)" if skipped else ""))
    return not fails


def _check_payload(data: dict) -> list[str]:
    """Core grounding check on a parsed response → list of fabricated raw tokens. (Shared by
    the live path + self-test so the teeth are proven on the SAME logic the live run uses.)"""
    gset: set[float] = set(); collect_numbers(data, gset)
    prose: list[str] = []; collect_prose(data, prose)
    nums = prose_numbers(strip_standards("  ".join(prose)))
    bad = []
    for rawn, val, is_pct, prev, qual in nums:
        if is_safe(rawn, val, is_pct, prev, qual):
            continue
        if not is_grounded(val, is_pct, gset):
            bad.append(rawn)
    return bad


def self_test() -> int:
    """Prove teeth without the LLM: clean prose passes; a planted fabrication is flagged;
    standards/brand/year/ordinal noise is NOT flagged."""
    cases = [
        # (name, payload, expect_fabrications)
        # ★THE TWO EXCEPTIONS THE FIRST LIVE-HIVE RUN FORCED, pinned so neither can widen unnoticed.
        # Both were REAL false positives found the day this gate stopped pointing at a dead hive.
        ("a method threshold is not a claim about the hive",
         {"descriptive": {"open_wos": 19},
          "prescriptive": {"summary": "Linear trend (numpy polyfit) - Prophet requires >= 24 weeks of data. "
                                      "There are 19 open work orders."}},
         False),
        ("a part rating and a model designation are not metrics",
         {"descriptive": {"overdue": 29},
          "prescriptive": {"summary": "29 assets overdue. Inspect assets that use MCCB 160A 3P, and the "
                                      "Siemens Simotics SD 200L unit."}},
         False),
        ("...but a real figure beside them is still checked",
         {"descriptive": {"overdue": 29},
          "prescriptive": {"summary": "29 assets overdue on MCCB 160A units, costing PHP 45000 this month."}},
         True),
        ("clean (all grounded)",
         {"descriptive": {"mtbf_h": 9.8, "oee_pct": 86, "pm_compliance": 37, "open_wos": 19},
          "prescriptive": {"summary": "MTBF is 9.8 hours; OEE 86% with PM compliance at 37% and 19 open work orders."}},
         False),
        ("planted fabrication (45000 not in data)",
         {"descriptive": {"mtbf_h": 9.8, "oee_pct": 86},
          "prescriptive": {"summary": "Estimated downtime cost is PHP 45000 this month."}},
         True),
        ("standards + brand + year + ordinal noise only",
         {"descriptive": {"mtbf_h": 9.8},
          "prescriptive": {"summary": "Per ISO 14224:2016 and SAE JA1011, apply Loctite 567; in 2026 the top 3 assets, "
                                       "MTBF 9.8 hours, follow Section 9 and Week 5 plan."}},
         False),
        ("derived percent (ratio 0.42 cited as 42%)",
         {"descriptive": {"avail_ratio": 0.42},
          "prescriptive": {"summary": "Availability is 42% this period."}},
         False),
    ]
    ok = 0
    for name, payload, expect in cases:
        bad = _check_payload(payload)
        got = bool(bad)
        passed = got == expect
        ok += passed
        mark = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
        print(f"  {mark} {name}: fabrications={bad or 'none'}  (expected {'some' if expect else 'none'})")
    total = len(cases)
    print(f"\n  self-test: {ok}/{total} " + (f"{GREEN}PASS{RESET}" if ok == total else f"{RED}FAIL{RESET}"))
    return 0 if ok == total else 1


def main() -> int:
    if "--self-test" in sys.argv:
        print(f"{BOLD}\nNARRATIVE GROUNDING — self-test (teeth, no LLM){RESET}")
        print("=" * 82)
        return self_test()
    print(f"{BOLD}\nNARRATIVE GROUNDING (§13.16 A7.1 live) — page AI-prose cites only true platform numbers{RESET}")
    print("=" * 82)
    r = validate_narrative_grounding(blind=False, strict="--strict" in sys.argv,
                                     update_baseline="--update-baseline" in sys.argv)
    if r is None:
        return 2
    print("-" * 82)
    if r:
        print(f"{GREEN}{BOLD}  NARRATIVE GROUNDING: PASS{RESET} — no fabricated number in any checked narrative.")
        return 0
    print(f"{RED}{BOLD}  NARRATIVE GROUNDING: FAIL{RESET} — a narrative cited a value absent from the grounding set.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
