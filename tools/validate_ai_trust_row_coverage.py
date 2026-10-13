#!/usr/bin/env python3
"""validate_ai_trust_row_coverage.py - every AI answer a person READS carries the shared "was this right?" row.

THE CLASS (LM-E walk, 2026-10-08): pages showed AI-written reading text with no way to say it was wrong. The browser
gate `ai-trust` (tools/prove_ai_trust.mjs) said "10/10 AI surfaces" - but its roster was the ten pages one wave had
named, not the platform's AI surfaces. analytics-report's action plan, alert-hub's AMC + live action brief,
project-report's narrative, project-manager's lessons draft, ph-intelligence's three narrative cards, resume's cover
letter, hive's Reliability Coach, report-sender's agent summaries, the logbook photo diagnosis and voice notes, and
engineering-design's AI-drafted summary all rendered model prose with no "was this right?" - and the gate was green,
because none of them was on its list. A roster that is typed by hand describes where someone looked.

THE RULE: the surface list is DERIVED from the code. Every call to an edge function (functions.invoke('x'),
invokeWithTimeout('x'), or a fetch of /functions/v1/x - only names that exist under supabase/functions/) in every
production page and script is discovered, and every one must be classified here:
  NOT_READING   the function returns nothing a person reads as the model's words (no model, an embedding, speech,
                a transcript of the person's own words, a retrieval of existing rows) - one reason per function
  SURFACES      per file: what the AI output IS on screen, and
    reading     -> the file must call whAiTrustRow({ db, agent, source, page, question, answer, groundedOn }) with the
                   entry's literal agent + page (+ source when named), every key present, groundedOn not empty
    prefill     -> skipped WITH a reason: the person reviews and edits the output field by field, so their edit is
                   the correction (voice fill, photo/listing/wizard pre-fill, an editable checklist)
    approval    -> skipped WITH a reason: the output is a pending record a person approves or rejects
    own-row     -> the surface carries its own feedback control; its marker must be present (assistant chat, companion)
A discovered (file, function) pair with no classification FAILS ("a new AI surface - classify it"), and a SURFACES
entry whose function is no longer called FAILS (stale), so the list cannot drift from the code in either direction.
Page-specific scripts (a local .js loaded by exactly one page, e.g. engineering-design.js) are read as part of that page.

    python tools/validate_ai_trust_row_coverage.py               # PASS / FAIL + the survey table
    python tools/validate_ai_trust_row_coverage.py --selftest    # teeth: every reading surface fails with its row removed
    python tools/validate_ai_trust_row_coverage.py --rev HEAD    # the same check over the sources at a git revision
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FN_DIR = ROOT / "supabase" / "functions"

# functions whose response is never model-written text a person reads - one reason each
NOT_READING = {
    "embed-entry": "an embedding of the person's own entry; nothing is shown",
    "tts-speak": "speech for text that is already on screen",
    "voice-transcribe": "the person's own words, transcribed into an input they review",
    "voice-health": "a liveness ping",
    "health": "a liveness ping",
    "semantic-search": "a retrieval of existing records, not generated text",
    "voice-semantic-rag": "a retrieval of existing records, not generated text",
    "platform-scraper": "no model call",
    "batch-risk-scoring": "no model call (a computed score)",
    "benchmark-compute": "no model call (computed benchmarks)",
    "pf-calculator": "no model call (a P-F interval computation)",
    "weibull-fitter": "no model call (a statistical fit)",
    "intelligence-api": "no model call (the data API; its URLs on ph-intelligence are documentation)",
    "project-progress": "no model call",
    "export-hive-data": "no model call",
    "login": "no model call",
    "supervisor-reset-password": "no model call",
    "cmms-sync": "no model call",
    "cmms-webhook-receiver": "no model call",
    "cmms-push-completion": "no model call",
    "send-report-email": "no model call (it mails the summaries scheduled-agents wrote)",
}

REQUIRED_KEYS = ("db", "agent", "source", "page", "question", "answer", "groundedOn")

# file -> surfaces. fns = the functions whose output this surface shows; fn None = AI text read from a table, proven
# present by `evidence`. A reading surface names the row it must carry (agent / page / optional source literal).
SURFACES: dict[str, list[dict]] = {
    "analytics.html": [
        dict(fns=["analytics-orchestrator"], surface="four-phase analysis + action plan (#results-panel)", kind="reading",
             agent="analytics-orchestrator", page="analytics"),
    ],
    "analytics-report.html": [
        dict(fns=["analytics-orchestrator"], surface="report section 4.1, the AI action plan (#ar-ai-synthesis)", kind="reading",
             agent="analytics-orchestrator", page="analytics-report", source="report-action-plan"),
    ],
    "alert-hub.html": [
        dict(fns=None, evidence=r"amc_briefings", surface="stored AMC daily brief headline + summary (#amc-summary)",
             kind="reading", agent="amc-orchestrator", page="alert-hub", source="amc-brief"),
        dict(fns=["analytics-orchestrator"], surface="live Action Brief that replaces it (#amc-summary)", kind="reading",
             agent="analytics-orchestrator", page="alert-hub", source="action-brief"),
    ],
    "shift-brain.html": [
        dict(fns=["shift-planner-orchestrator"], surface="stored shift briefing (#brief-text)", kind="reading",
             agent="shift-planner-orchestrator", page="shift-brain", source="briefing"),
        dict(fns=["analytics-orchestrator"], surface="live Action Brief that replaces it (#brief-text)", kind="reading",
             agent="analytics-orchestrator", page="shift-brain", source="action-brief"),
    ],
    "asset-hub.html": [
        dict(fns=["ai-gateway", "asset-brain-query"], surface="Asset Brain answer", kind="reading",
             agent="asset-brain", page="asset-hub"),
        dict(fns=["fmea-populator"], surface="AI failure-mode suggestions", kind="approval",
             reason="inserted as PENDING FMEA rows a supervisor approves or rejects one by one; approval is the correction"),
    ],
    "hive.html": [
        dict(fns=["ai-gateway", "ai-orchestrator"], surface="Reliability Coach ranked actions (#coach-result)", kind="reading",
             agent="coach", page="hive", source="coach"),
    ],
    "voice-journal.html": [
        dict(fns=["ai-gateway"], surface="journal reply (#current-reply)", kind="reading", agent="voice-journal", page="voice-journal"),
    ],
    "assistant.html": [
        dict(fns=["ai-gateway"], surface="assistant chat reply", kind="own-row",
             marker=r"function _attachChatFeedback\(|data-rate", reason="its own 44px thumbs (_attachChatFeedback) under every reply"),
    ],
    "project-report.html": [
        dict(fns=["project-orchestrator"], surface="AI hero finding + executive summary + lessons synthesis (#exec-summary)",
             kind="reading", agent="project-orchestrator", page="project-report", source="narrative"),
    ],
    "project-manager.html": [
        dict(fns=["project-orchestrator"], surface="AI-drafted lessons learned (lessons box)", kind="reading",
             agent="project-orchestrator", page="project-manager", source="lessons"),
        dict(fns=["project-orchestrator"], surface="'Parse with AI' intent -> new-project wizard", kind="prefill",
             reason="fills the wizard's type, template, name, dates, priority and description; the person reviews each "
                    "field and presses Create, and the project records which AI values were kept"),
    ],
    "ph-intelligence.html": [
        dict(fns=["intelligence-report"], surface="executive summary, seasonal insight and recommendation cards",
             kind="reading", agent="intelligence-report", page="ph-intelligence"),
    ],
    "resume.html": [
        dict(fns=["resume-polish"], surface="polish / tailor / summary suggestions in the review sheet (#review-body)",
             kind="reading", agent="resume-polish", page="resume", source="review"),
        dict(fns=["resume-polish"], surface="cover letter draft (#cover-letter-panel)", kind="reading",
             agent="resume-polish", page="resume", source="cover-letter"),
        dict(fns=["resume-extract"], surface="upload -> extracted items checklist", kind="prefill",
             reason="the person's OWN document read into an editable checklist, each item ticked and editable, its chip "
                    "naming the file it came from"),
    ],
    "report-sender.html": [
        dict(fns=["scheduled-agents"], surface="each report's agent-written summary sentence (#results-list)", kind="reading",
             agent="scheduled-agents", page="report-sender", source="report-summary"),
        dict(fns=["voice-report-intent"], surface="spoken request -> report chips + recipient", kind="prefill",
             reason="selects report chips and a recipient hint the person reviews before pressing Send"),
    ],
    "logbook.html": [
        dict(fns=["visual-defect-capture"], surface="photo diagnosis: failure mode, severity, confidence (#vdc-result)",
             kind="reading", agent="visual-defect-capture", page="logbook", source="photo-diagnosis"),
        dict(fns=["voice-logbook-entry"], surface="voice fill's LOTO / parts / supervisor notes (#vf-result)", kind="reading",
             agent="voice-logbook-entry", page="logbook", source="voice-notes"),
        dict(fns=["equipment-label-ocr"], surface="nameplate scan -> Register Asset form", kind="prefill",
             reason="fills asset form fields the person reviews before saving; ai_assisted_fields records what was kept"),
    ],
    "marketplace.html": [
        dict(fns=["marketplace-listing-assist"], surface="AI listing assist -> category + description", kind="prefill",
             reason="fills the category select and an EMPTY description the seller edits before posting; "
                    "marketplace_listings.ai_assisted_fields records what was kept"),
        dict(fns=["ai-gateway"], surface="service triage -> urgency + category", kind="prefill",
             reason="sets the urgency select and the catalog picker the client reviews before hailing; the one-line "
                    "'AI suggests' note only names the fields it set"),
    ],
    "engineering-design.html": [
        dict(fns=["engineering-calc-agent"], surface="AI-drafted objective / assumptions / recommendations (#ed-ai-note)",
             kind="reading", agent="engineering-calc-agent", page="engineering-design", source="calc-narrative"),
        dict(fns=["engineering-bom-sow"], surface="BOM + SOW checklist", kind="prefill",
             reason="an editable checklist: every item ticked or unticked, every field editable, before export"),
    ],
    # shared scripts (loaded by many pages)
    "companion-launcher.js": [
        dict(fns=["ai-gateway"], surface="floating companion reply", kind="own-row",
             marker=r"function _attachFeedback\(", reason="its own thumbs (_attachFeedback, .wh-msg-rate) under every reply"),
    ],
    "voice-handler.js": [
        dict(fns=["ai-gateway", "agentic-rag-loop"], surface="voice companion reply", kind="own-row",
             marker=r"data-rate=\"-1\"", reason="its own Helpful / Unhelpful buttons under every reply"),
    ],
    "utils.js": [
        dict(fns=["gcash-receipt-ocr"], surface="GCash receipt scan -> payment fields", kind="prefill",
             reason="fills reference / amount fields the payer checks before submitting"),
    ],
}

CALL = re.compile(r"""(?:\b[\w$.]*[Ii]nvoke[\w$]*\(\s*['"`]([\w-]+)['"`])|(?:functions/v1/([\w-]+))""")
ROW_CALL = re.compile(r"\bwhAiTrustRow\(")
SCRIPT_SRC = re.compile(r"""<script\b[^>]*\bsrc=["']([^"':]+?\.js)(?:\?[^"']*)?["']""", re.I)


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)   # accept="image/*" is not a comment opener
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def call_args(src: str, start: int) -> str:
    """The argument text of the call whose '(' is at src[start-1] - balanced parens, strings skipped."""
    depth, i, n = 1, start, len(src)
    while i < n and depth:
        c = src[i]
        if c in "'\"`":
            q = c
            i += 1
            while i < n and src[i] != q:
                i += 2 if src[i] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    return src[start:i - 1]


def lit(args: str, key: str) -> str | None:
    m = re.search(r"\b" + key + r"\s*:\s*(['\"])([^'\"]*)\1", args)
    return m.group(2) if m else None


def has_key(args: str, key: str) -> bool:
    return bool(re.search(r"(?:^|[{,\s])" + key + r"\s*(?::|,|\}|$)", args))


def row_calls(src: str) -> list[dict]:
    out = []
    for m in ROW_CALL.finditer(src):
        a = call_args(src, m.end())
        g = re.search(r"\bgroundedOn\s*:\s*(.{0,4})", a, flags=re.S)
        out.append(dict(agent=lit(a, "agent"), page=lit(a, "page"), source=lit(a, "source"),
                        missing=[k for k in REQUIRED_KEYS if not has_key(a, k)],
                        empty_ground=bool(g and re.match(r"\s*(?:''|\"\")", g.group(1)))))
    return out


# ── sources ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _skip(name: str) -> bool:
    return name.startswith(("test", "_", "survey_")) or name.endswith((".test.js", ".spec.js", "_battery.js"))


def load_sources(rev: str | None) -> dict[str, str]:
    """file key -> comment-stripped source. A page's key carries its page-specific scripts appended."""
    def read(rel: str) -> str:
        if rev:
            r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT, capture_output=True)
            return r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else ""
        p = ROOT / rel
        return io.open(p, encoding="utf-8", errors="replace").read() if p.exists() else ""

    pages = sorted(p.name for p in ROOT.glob("*.html") if not _skip(p.name))
    scripts = sorted(p.name for p in ROOT.glob("*.js") if not _skip(p.name))
    raw = {n: read(n) for n in pages + scripts}
    loaded_by: dict[str, list[str]] = {}
    for pg in pages:
        for s in set(SCRIPT_SRC.findall(raw[pg])):
            s = s.lstrip("./")
            if s in raw and s not in pages:
                loaded_by.setdefault(s, []).append(pg)
    own = {s: pgs[0] for s, pgs in loaded_by.items() if len(pgs) == 1}
    out: dict[str, str] = {}
    for pg in pages:
        out[pg] = strip_comments(raw[pg] + "\n" + "\n".join(raw[s] for s, owner in own.items() if owner == pg))
    for s in scripts:
        if s not in own:
            out[s] = strip_comments(raw[s])
    return out


def edge_functions() -> set[str]:
    return {p.name for p in FN_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")} if FN_DIR.exists() else set()


def discover(sources: dict[str, str], fns: set[str]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for key, src in sources.items():
        for m in CALL.finditer(src):
            fn = m.group(1) or m.group(2)
            if fn in fns:
                found.setdefault(key, set()).add(fn)
    return found


# ── the check ────────────────────────────────────────────────────────────────────────────────────────────────────
def check(sources: dict[str, str], fns: set[str], surfaces=None) -> tuple[list[str], list[tuple]]:
    surfaces = SURFACES if surfaces is None else surfaces
    fails, table = [], []
    found = discover(sources, fns)
    # 1. every discovered model call is classified
    for key in sorted(found):
        classified = {f for s in surfaces.get(key, []) for f in (s.get("fns") or [])}
        for fn in sorted(found[key]):
            if fn in NOT_READING or fn in classified:
                continue
            fails.append(f"{key}: calls '{fn}' and no surface classifies it - a new AI surface: say what it shows "
                         f"(reading / prefill / approval / own-row) in SURFACES, or why it is not reading text in NOT_READING")
    # 2. every surface still matches the code, and every reading surface carries the row
    for key in sorted(surfaces):
        src = sources.get(key)
        if src is None:
            fails.append(f"{key}: listed in SURFACES but no such production file")
            continue
        calls = row_calls(src)
        for s in surfaces[key]:
            live = s.get("fns")
            if live:
                gone = [f for f in live if f not in found.get(key, set())]
                if len(gone) == len(live):
                    fails.append(f"{key}: SURFACES lists '{s['surface']}' on {'/'.join(live)}, which this file no longer calls (stale)")
                    continue
            elif s.get("evidence") and not re.search(s["evidence"], src):
                fails.append(f"{key}: SURFACES lists '{s['surface']}' but its evidence /{s['evidence']}/ is gone (stale)")
                continue
            kind = s["kind"]
            if kind in ("prefill", "approval"):
                ok = bool(s.get("reason"))
                if not ok:
                    fails.append(f"{key}: '{s['surface']}' is skipped as {kind} with no reason")
                table.append((key, s, "skip", s.get("reason", "")))
                continue
            if kind == "own-row":
                ok = bool(re.search(s["marker"], src))
                if not ok:
                    fails.append(f"{key}: '{s['surface']}' claims its own feedback control, but /{s['marker']}/ is gone")
                table.append((key, s, "own" if ok else "MISSING", s.get("reason", "")))
                continue
            match = [c for c in calls if c["agent"] == s["agent"] and c["page"] == s["page"]
                     and (s.get("source") is None or c["source"] == s["source"])]
            if not match:
                fails.append(f"{key}: '{s['surface']}' shows AI reading text with no whAiTrustRow(agent '{s['agent']}', "
                             f"page '{s['page']}'{', source ' + repr(s['source']) if s.get('source') else ''}) - "
                             f"a person who catches a wrong answer cannot say so")
                table.append((key, s, "MISSING", ""))
                continue
            bad = [c for c in match if c["missing"] or c["empty_ground"]]
            if bad:
                c = bad[0]
                why = ("missing " + ", ".join(c["missing"])) if c["missing"] else "an empty groundedOn"
                fails.append(f"{key}: '{s['surface']}' row has {why} - the row must carry the question, the answer it rated "
                             f"and what the answer rested on")
                table.append((key, s, "INCOMPLETE", why))
                continue
            table.append((key, s, "row", ""))
    return fails, table


def print_table(table: list[tuple]) -> None:
    print(f"  {'file':<24} {'kind':<9} {'row':<10} surface")
    for key, s, state, why in table:
        print(f"  {key:<24} {s['kind']:<9} {state:<10} {s['surface']}" + (f"  [{why[:90]}]" if why and state == "skip" else ""))


# ── teeth ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _drop_row(src: str, s: dict) -> str:
    """the same source with this surface's whAiTrustRow call(s) renamed away - what a page looks like without its row"""
    out, last = [], 0
    for m in ROW_CALL.finditer(src):
        a = call_args(src, m.end())
        if lit(a, "agent") == s["agent"] and lit(a, "page") == s["page"] and (s.get("source") is None or lit(a, "source") == s["source"]):
            out.append(src[last:m.start()] + "whAiTrustRowREMOVED(")
            last = m.end()
    return "".join(out) + src[last:]


def selftest() -> int:
    fns = edge_functions()
    sources = load_sources(None)
    problems = []
    base, _ = check(sources, fns)
    if base:
        problems.append(f"the live tree is not clean ({len(base)} failure(s)) - fix those first")
    n = 0
    for key, entries in SURFACES.items():
        for s in entries:
            if s["kind"] != "reading" or key not in sources:
                continue
            n += 1
            mutated = dict(sources)
            mutated[key] = _drop_row(sources[key], s)
            f, _ = check(mutated, fns)
            if not any(s["surface"] in x for x in f):
                problems.append(f"removing the row from {key} '{s['surface']}' was NOT caught")
    # a new AI call nobody classified
    mutated = dict(sources)
    mutated["hive.html"] = sources.get("hive.html", "") + "\nawait db.functions.invoke('resume-extract', { body: {} });\n"
    f, _ = check(mutated, fns)
    if not any("resume-extract" in x and "no surface classifies it" in x for x in f):
        problems.append("an unclassified model call on hive.html was NOT caught")
    # a row with no groundedOn
    mutated = dict(sources)
    mutated["hive.html"] = re.sub(r"groundedOn\s*:", "groundedOnX:", sources.get("hive.html", ""))
    f, _ = check(mutated, fns)
    if not any("missing groundedOn" in x for x in f):
        problems.append("a row with no groundedOn was NOT caught")
    # a stale entry: the function is no longer called
    mutated = dict(sources)
    mutated["ph-intelligence.html"] = sources.get("ph-intelligence.html", "").replace("intelligence-report", "intelligence-rep0rt")
    f, _ = check(mutated, fns)
    if not any("stale" in x and "ph-intelligence" in x for x in f):
        problems.append("a stale SURFACES entry was NOT caught")
    for p in problems:
        print("  SELFTEST FAIL", p)
    if problems:
        print("selftest FAILED")
        return 1
    print(f"selftest: {n} reading surfaces each FAIL with their row removed; an unclassified call, a row with no "
          f"groundedOn and a stale entry are each caught")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    rev = None
    if "--rev" in sys.argv:
        i = sys.argv.index("--rev")
        rev = sys.argv[i + 1] if i + 1 < len(sys.argv) else "HEAD"
    fns = edge_functions()
    sources = load_sources(rev)
    fails, table = check(sources, fns)
    reading = [t for t in table if t[1]["kind"] == "reading"]
    with_row = [t for t in reading if t[2] == "row"]
    if "--table" in sys.argv or fails:
        print_table(table)
    where = f" at {rev}" if rev else ""
    if fails:
        print(f"FAIL ai-trust-row-coverage{where} - {len(fails)} problem(s); {len(with_row)}/{len(reading)} reading AI surfaces carry the row:")
        for f in fails:
            print("  " + f)
        return 1
    skipped = sum(1 for t in table if t[2] == "skip")
    own = sum(1 for t in table if t[2] == "own")
    print(f"PASS ai-trust-row-coverage{where} - {len(with_row)}/{len(reading)} reading AI surfaces carry the shared "
          f"\"was this right?\" row; {own} carry their own; {skipped} pre-fill/approval surfaces skipped with a reason; "
          f"every model call in {len(sources)} production files is classified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
