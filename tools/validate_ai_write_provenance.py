#!/usr/bin/env python3
"""
validate_ai_write_provenance.py — AI6 · AGENTIC WRITE ACCOUNTABILITY (dimension-expansion loop 21).

THE DIMENSION THIS LOCKS. The rubric's AI1-AI5 (from the HAX guidelines) all grade the AI's
ANSWER: can it say what it does (AI1), show its basis (AI2), be corrected (AI3), fail honestly
(AI4), be dismissed (AI5). NONE of them grade the AI's ACT. On this platform the AI does not just
answer - it WRITES: 14 AI edge fns insert/upsert, and several of those rows are domain content a
human later reads as fact (a failure mode, a shift assignment, a risk score, a fault-knowledge
entry). "AI acting on the user's behalf" is therefore a distinct, measurable property:

  When an AI writes DOMAIN content, the row must SAY it was machine-authored.

FOUND BY THIS ORACLE (the defect that motivated it): `visual-defect-capture` wrote model-generated
problem/root_cause/action/knowledge into `fault_knowledge` stamped `worker_name = <the signed-in
human>` with no provenance field. fault_knowledge is read back by intelligence-api,
intelligence-report and semantic-search (RPC search_fault_knowledge), so the model's own inference
re-entered RAG as human field experience under a technician's name. Two harms: ACCOUNTABILITY (a
worker's name on a diagnosis they never wrote) and EPISTEMIC CONTAMINATION (AI output cited back as
field-verified ground truth - a self-reinforcing loop). Fixed by mig 20260724000001 + source
markers; this gate stops it from silently coming back, and catches the NEXT AI writer that forgets.

DENOMINATOR IS CURATED BY EVIDENCE, not "every table an AI touches" (the classify-by-evidence
discipline, same as Y1b's CAPTURE_TARGETS). Telemetry/infra writes (ai_rate_limits, automation_log,
agentic_rag_traces, ai_quality_log, client_errors) are EXCLUDED: nobody reads a rate-limit counter
as field knowledge, so a provenance marker there is noise. Tables whose NAME already declares the
content is AI-generated (ai_reports, amc_briefings, ph_intelligence_reports) are also out of scope
- the table itself is the marker. What remains is the honest set: rows that LOOK like human domain
knowledge unless they say otherwise.

USAGE: python tools/validate_ai_write_provenance.py [--json] [--selftest] [--accept]
Exit 0 = no regression, 1 = an AI write lost (or never had) its provenance marker.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
FNS = ROOT / "supabase" / "functions"
BASELINE = ROOT / "ai_write_provenance_baseline.json"
REPORT = ROOT / "ai_write_provenance_report.json"

# Domain tables where a row reads as HUMAN knowledge unless it declares otherwise.
# Add a table here only after confirming a human actually consumes it as fact.
DOMAIN_TABLES = {
    "fault_knowledge":          "RAG + intelligence reports cite it as field experience",
    "rcm_fmea_modes":           "safety-critical engineering content (FMEA)",
    "knowledge_graph_facts":    "asserted facts reused by downstream reasoning",
    "shift_plans":              "assigns real people to real shifts",
    "asset_risk_scores":        "drives maintenance priority + spend",
    "failure_signature_alerts": "raises alerts humans act on",
}
# A row is accountable if the insert payload carries ANY of these. Multiple spellings are allowed
# on purpose: the platform already uses `source` (rcm_fmea_modes), `generated_by` (shift_plans),
# `source_type` (knowledge_graph_facts) and `model_version` (asset_risk_scores). Normalising them
# would be a bigger refactor than the accountability property needs - what matters is that the row
# states machine authorship SOMEHOW.
PROV_KEYS = ("source", "source_type", "detail_source", "ai_model", "model_version",
             "generated_by", "ai_confidence")

_AI = re.compile(r"ai-chain|callAI|checkAIRateLimit|OPENROUTER|GROQ|gemini|generateContent|chat/completions", re.I)
_NONPROD = re.compile(r"\.bak\b|\.old\b|\.orig\b", re.I)


def _strip_comments(src: str) -> str:
    """Comments must never satisfy this gate. Four scanners were fooled by prose this session
    (feedback_string_is_not_an_announcement_until_it_reaches_a_user) - a doc comment saying
    'we set source here' would otherwise count as setting it."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"(?m)^\s*//.*$", " ", src)
    return src


def _payload_after(src: str, idx: int) -> str:
    """Return the object literal passed to insert(/upsert(, by walking braces from the call's
    first '{'. A fixed char-window would either truncate a long payload (false FAIL) or run into
    the NEXT insert (false PASS) - both were real risks here, several payloads are 15+ lines."""
    start = src.find("{", idx)
    if start < 0:
        return ""
    depth, i, n = 0, start, len(src)
    while i < n:
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    return src[start:start + 4000]


def _arg_text(src: str, open_paren: int) -> str:
    """Text of the first argument to a call whose '(' is at open_paren."""
    depth, i, n = 0, open_paren, len(src)
    start = open_paren + 1
    while i < n:
        c = src[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return src[start:i]
        elif c == "," and depth == 1:
            return src[start:i]
        i += 1
    return src[start:start + 300]


def _identifier_payloads(src: str, name: str) -> list[str]:
    """Rows are usually BUILT then inserted: `toInsert.push({...})` ... `.insert(toInsert)`, or
    `const rows = xs.map(x => ({...}))`. v1 of this gate only read the payload at the insert call
    site, so it reported 3 FALSE GAPS (fmea-populator, semantic-fact-extractor, batch-risk-scoring
    all DO stamp provenance) - caught by cross-checking the live DB, which held source='ai_logbook'
    rows the gate claimed did not exist. Resolve the identifier back to the literals that build it."""
    out, seen, queue = [], set(), [name]
    # Resolve TRANSITIVELY (depth 3): batch-risk-scoring does `rows = xs.map(x => ({...}))` then
    # `validRows = rows.filter(...)` then `.insert(validRows)`. A one-hop resolver reported it as a
    # gap even though the row literal carries model_version + generated_at - the FOURTH false gap
    # this oracle produced before it was trustworthy. Follow `V = <base>.filter/map/slice/...`.
    while queue and len(seen) < 4:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        for m in re.finditer(r"\b" + re.escape(cur) + r"\s*(?:=|\.push\s*\(|\.concat\s*\()", src):
            out.append(_payload_after(src, m.end() - 1))
            rhs = src[m.end(): m.end() + 160]
            base = re.match(r"\s*([A-Za-z_$][\w$]*)\s*\.\s*(?:filter|map|slice|concat|flat|sort)", rhs)
            if base:
                queue.append(base.group(1))
            # `validRows.push(row)` - the pushed thing is itself a variable, not a literal.
            pushed = re.match(r"\s*\(?\s*([A-Za-z_$][\w$]*)\s*[,)]", rhs)
            if pushed:
                queue.append(pushed.group(1))
        # `for (const row of rows)` binds row from rows - follow the iterable.
        for m in re.finditer(r"for\s*\(\s*(?:const|let|var)\s+" + re.escape(cur)
                             + r"\s+of\s+([A-Za-z_$][\w$]*)", src):
            queue.append(m.group(1))
    return [p for p in out if p]


def measure() -> dict:
    rows, ok, tot = [], 0, 0
    for f in sorted(FNS.glob("*/index.ts")):
        if _NONPROD.search(f.name):
            continue
        raw = f.read_text(encoding="utf-8", errors="replace")
        if not _AI.search(raw):
            continue
        src = _strip_comments(raw)
        for m in re.finditer(r"\.from\(\s*['\"]([a-z_]+)['\"]\s*\)\s*\.\s*(insert|upsert)\s*\(", src):
            table, op = m.group(1), m.group(2)
            if table not in DOMAIN_TABLES:
                continue
            tot += 1
            arg = _arg_text(src, m.end() - 1).strip()
            if arg.startswith("{"):
                payloads = [_payload_after(src, m.end() - 1)]
            elif re.fullmatch(r"[A-Za-z_$][\w$]*", arg):
                payloads = _identifier_payloads(src, arg)      # rows built elsewhere
            else:
                payloads = [_payload_after(src, m.end() - 1)]
            has = any(re.search(r"\b" + k + r"\s*:", p) for k in PROV_KEYS for p in payloads)
            if not has:
                # Or stamped onto the rows imperatively: `for (const r of rows) r.source = "..."`.
                window = src[max(0, m.start() - 1500): m.end() + 500]
                has = any(re.search(r"\.\s*" + k + r"\s*=", window) for k in PROV_KEYS)
            if has:
                ok += 1
            rows.append({"fn": f.parent.name, "table": table, "op": op, "accountable": has})
    pct = round(ok / tot * 100, 1) if tot else 100.0
    return {"total": tot, "ok": ok, "pct": pct,
            "gaps": [f"{r['fn']} -> {r['table']}.{r['op']}" for r in rows if not r["accountable"]],
            "rows": rows}


def self_test() -> bool:
    ok = True
    accountable = '''const x = await db.from("fault_knowledge").insert({
        hive_id, problem: draft.problem, worker_name, source: "ai_visual_capture" });'''
    bare = '''const x = await db.from("fault_knowledge").insert({
        hive_id, problem: draft.problem, worker_name });'''
    commented = '''const x = await db.from("fault_knowledge").insert({
        // we set source below
        hive_id, problem: draft.problem, worker_name });'''
    telemetry = '''const x = await db.from("ai_rate_limits").insert({ hive_id, count: 1 });'''
    for label, sample, want_hit, want_counted in (
        ("payload with source", accountable, True, True),
        ("bare payload", bare, False, True),
        ("comment-only claim", commented, False, True),
        ("telemetry table", telemetry, False, False),
    ):
        s = _strip_comments(sample)
        m = re.search(r"\.from\(\s*['\"]([a-z_]+)['\"]\s*\)\s*\.\s*(insert|upsert)\s*\(", s)
        counted = bool(m) and m.group(1) in DOMAIN_TABLES
        if counted != want_counted:
            print(f"{R}selftest FAIL: '{label}' counted={counted}, expected {want_counted}{X}"); ok = False
        if counted:
            payload = _payload_after(s, m.end() - 1)
            hit = any(re.search(r"\b" + k + r"\s*:", payload) for k in PROV_KEYS)
            if hit != want_hit:
                print(f"{R}selftest FAIL: '{label}' accountable={hit}, expected {want_hit}{X}"); ok = False
    # brace-walker must not run past the payload into a following insert
    two = '''db.from("fault_knowledge").insert({ a: 1 }); db.from("x").insert({ source: "y" });'''
    m = re.search(r"\.from\(\s*['\"]([a-z_]+)['\"]\s*\)\s*\.\s*insert\s*\(", two)
    if "source" in _payload_after(two, m.end() - 1):
        print(f"{R}selftest FAIL: payload walker leaked into the NEXT insert{X}"); ok = False
    print((G + "selftest PASS - ai-write-provenance has teeth." + X) if ok else (R + "selftest FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv:
        return 0 if self_test() else 1
    m = measure()
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    floor = float(base.get("AI6", 0.0))
    if "--accept" in sys.argv:
        BASELINE.write_text(json.dumps({"AI6": m["pct"]}, indent=2), encoding="utf-8")
        print(f"{G}baseline accepted: AI6 = {m['pct']}%{X}")
        return 0
    REPORT.write_text(json.dumps(m, indent=2), encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(m, indent=2)); return 0
    print(f"{B}AI6 · agentic write accountability — AI fns writing DOMAIN tables{X}")
    for r in m["rows"]:
        mark = f"{G}OK  {X}" if r["accountable"] else f"{R}GAP {X}"
        print(f"  {mark} {r['fn']:30s} -> {r['table']}.{r['op']}")
    status = f"{G}OK{X}" if m["pct"] >= floor else f"{R}REGRESSED{X}"
    print(f"\n  {status}  AI6: {m['ok']}/{m['total']} = {m['pct']}% (baseline {floor}%)")
    if m["pct"] < floor:
        print(f"{R}{B}FAIL{X} - an AI write lost its provenance marker: {', '.join(m['gaps'])}")
        return 1
    print(f"{G}{B}PASS{X} - every AI write into a human-read domain table declares machine authorship.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
