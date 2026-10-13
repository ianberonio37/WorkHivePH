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


# ── AI6b · AI-DRAFTED, PERSON-SAVED ─────────────────────────────────────────────────────────────────────────────
# The section above covers rows a MODEL writes on its own. The second shape writes the same human-read tables through a
# person: an AI path fills a FORM, the person reviews and taps Save. The approval is theirs, so the row is NOT machine-
# authored and must not claim to be (fault_knowledge.source stays 'manual') - but its WORDS may be the model's, and
# before LM332 (marketplace) and LM422 (logbook, 2026-10-07) the saved row could not say which. The contract, per
# target: (1) SCHEMA - a migration gives the table `ai_assisted_fields`; (2) RECORD - every AI path that fills the form
# records what it filled; (3) SEND - every writer of the table puts `ai_assisted_fields` on the row it writes (and any
# helper the row passes through keeps it); (4) CARRY - a server writer that copies the row into the RAG corpus keeps
# the marks. Curated by evidence like DOMAIN_TABLES: add a target when a page gains an AI path that fills a form whose
# save writes a table a person later reads as fact.
PAGE_DRAFTS = (
    {"page": "marketplace.html", "table": "marketplace_listings", "recorder": r"_mktAiFilled\b",
     "ai_paths": {"listing assist": "handleAiAssist"},
     "writers": ("handlePostSubmit",), "via": ()},
    {"page": "logbook.html", "table": "logbook", "recorder": r"\blbNoteAiFill\s*\(",
     "ai_paths": {"Speak to fill (voice-logbook-entry)": "applySmartVoiceFill",
                  "Photo defect capture (visual-defect-capture)": "vdcApplyDraft",
                  "companion logbook.create prefill": "logbookCreateHandler"},
     "writers": ("addEntry", "saveEditFromForm"), "via": ()},
    {"page": "logbook.html", "table": "asset_nodes", "recorder": r"_lbAssetAiFilled\b",
     "ai_paths": {"Scan nameplate (equipment-label-ocr)": "wireAssetScan"},
     "writers": ("submitAsset",), "via": ("_assetToNode",)},
    # The page does not write fault_knowledge itself: it hands the marks to embed-entry, which upserts the row.
    {"page": "logbook.html", "table": "fault_knowledge", "recorder": None, "ai_paths": {},
     "writers": (), "via": ("embedFaultEntry",)},
)
# Server-side writers that copy a person-saved row into a domain table: (file, table, regex that must hold in code).
DRAFT_CARRIERS = (
    ("supabase/functions/embed-entry/index.ts", "fault_knowledge", r"\brow\.ai_assisted_fields\s*="),
    ("tools/drain_embedding_outbox.py", "fault_knowledge", r"[\"']ai_assisted_fields[\"']\s*:"),
)
_KEY = re.compile(r"\bai_assisted_fields\s*[:=]")


def _strip_js(src: str) -> str:
    """Blank JS comments (keeping newlines) while respecting strings, template literals (with nested ${...}) and
    regex literals. The edge-fn stripper above is regex-based, which is fine for .ts files but not for a page: a
    string like 'image/*' opens a phantom block comment that swallows the code after it
    (feedback_accept_image_star_broke_comment_stripping)."""
    out, i, n = [], 0, len(src)
    stack = []            # template-literal nesting: each entry is the brace depth inside its ${...}
    prev = ""             # last significant code char, to tell a regex literal from a division
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = src.find("\n", i); j = n if j < 0 else j
            out.append(" " * (j - i)); i = j; continue
        if c == "/" and nxt == "*":
            j = src.find("*/", i + 2); j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", src[i:j])); i = j; continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1]); i = j + 1; prev = "a"; continue
        if c == "`" or (c == "}" and stack and stack[-1] == 0):
            if c == "}":
                stack.pop()
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2; continue
                if src[j] == "`":
                    break
                if src[j] == "$" and j + 1 < n and src[j + 1] == "{":
                    break
                j += 1
            if j < n and src[j] == "$":
                stack.append(0); out.append(src[i:j + 2]); i = j + 2; prev = "{"; continue
            out.append(src[i:j + 1]); i = j + 1; prev = "a"; continue
        if c == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^"):
            j, in_cls = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2; continue
                if src[j] == "[":
                    in_cls = True
                elif src[j] == "]":
                    in_cls = False
                elif src[j] == "/" and not in_cls:
                    break
                j += 1
            out.append(src[i:j + 1]); i = j + 1; prev = "a"; continue
        if stack:
            if c == "{":
                stack[-1] += 1
            elif c == "}":
                stack[-1] -= 1
        out.append(c)
        if not c.isspace():
            prev = c if not (c.isalnum() or c in "_$") else "a"
        i += 1
    return "".join(out)


def _page_js(html: str) -> str:
    """Inline <script> bodies only (src= scripts are other files), comment-stripped."""
    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, flags=re.S | re.I)
    return "\n".join(_strip_js(b) for b in blocks)


def _fn_body(js: str, name: str) -> str | None:
    """Body of `function NAME(...) {...}` by brace-walking the comment-stripped code. None when absent - a renamed
    function must surface as a finding, never as a silently-skipped check."""
    m = re.search(r"\bfunction\s+" + re.escape(name) + r"\s*\(", js)
    if not m:
        return None
    depth, i = 0, m.end() - 1
    while i < len(js):                      # skip the parameter list
        if js[i] == "(":
            depth += 1
        elif js[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    start = js.find("{", i)
    if start < 0:
        return None
    depth, j = 0, start
    while j < len(js):
        if js[j] == "{":
            depth += 1
        elif js[j] == "}":
            depth -= 1
            if depth == 0:
                return js[start:j + 1]
        j += 1
    return js[start:]


def _first_arg(src: str, open_paren: int) -> str:
    """First argument of the call whose '(' is at open_paren, counting (), [] and {} - _arg_text above counts only
    parentheses, so `insert([{ a, b }])` came back as `[{ a` (it cut at the first comma) and a correct payload read as
    a gap on its first run against marketplace.html."""
    depth, i, n = 0, open_paren, len(src)
    while i < n:
        c = src[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return src[open_paren + 1:i]
        elif c == "," and depth == 1:
            return src[open_paren + 1:i]
        i += 1
    return src[open_paren + 1:open_paren + 4000]


def _ident_carries(body: str, name: str, depth: int) -> bool:
    """`name` carries the marks if they are stamped on it (`name.ai_assisted_fields = ...`) or the literal that
    builds it holds the key (`const name = { ..., ai_assisted_fields: ... }`, or a spread of something that does)."""
    if re.search(r"\b" + re.escape(name) + r"\s*\.\s*ai_assisted_fields\s*=(?!=)", body):
        return True
    # only a literal assigned DIRECTLY (`name = {` / `name = [{`): a call on the right-hand side is not resolved here,
    # because "the next brace after the =" would be some other object and could pass the check for the wrong reason
    return any(_carries(body, _payload_after(body, m.end()), depth + 1)
               for m in re.finditer(r"\b" + re.escape(name) + r"\s*=(?!=)\s*(?=[\[{])", body))


def _carries(body: str, expr: str, depth: int = 0) -> bool:
    """Does the expression passed to insert/upsert/update put ai_assisted_fields on the row? Follows a literal (and
    its spreads), an identifier back to its stamp or literal, and a helper call into its argument (the helper itself is
    checked separately, as a `via`)."""
    expr = expr.strip()
    if depth > 4 or not expr:
        return False
    if expr.startswith("["):
        expr = expr[1:].strip()
    if expr.startswith("{"):
        lit = _payload_after(expr, 0)
        if _KEY.search(lit):
            return True
        return any(_ident_carries(body, s, depth) for s in re.findall(r"\.\.\.\s*([A-Za-z_$][\w$]*)\b(?!\s*[.(\[])", lit))
    m = re.match(r"([A-Za-z_$][\w$.]*)\s*\(", expr)
    if m:
        return _carries(body, _first_arg(expr, m.end() - 1), depth + 1)
    if re.fullmatch(r"[A-Za-z_$][\w$]*", expr):
        return _ident_carries(body, expr, depth)
    return False


def _migrations_text() -> str:
    parts = []
    for f in sorted((ROOT / "supabase" / "migrations").glob("*.sql")):
        sql = f.read_text(encoding="utf-8", errors="replace")
        parts.append(re.sub(r"(?m)--.*$", " ", sql))
    return "\n".join(parts)


def _schema_has(mig: str, table: str) -> bool:
    return bool(re.search(r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?(?:public\.)?" + re.escape(table)
                          + r"\b[^;]*?\badd\s+column\s+(?:if\s+not\s+exists\s+)?ai_assisted_fields\b", mig, re.I))


def measure_drafts(pages: dict | None = None, mig: str | None = None, carriers: dict | None = None) -> dict:
    """Each argument can be injected (the selftest mutates real files in memory); None = read the repo."""
    mig = _migrations_text() if mig is None else mig
    js_cache: dict[str, str] = {}

    def js_of(page: str) -> str:
        if page not in js_cache:
            html = pages[page] if pages and page in pages else (ROOT / page).read_text(encoding="utf-8-sig",
                                                                                        errors="replace")
            js_cache[page] = _page_js(html)
        return js_cache[page]

    rows = []
    for t in PAGE_DRAFTS:
        js, problems = js_of(t["page"]), []
        if not _schema_has(mig, t["table"]):
            problems.append(f"no migration adds {t['table']}.ai_assisted_fields")
        for label, fn in t["ai_paths"].items():
            body = _fn_body(js, fn)
            if body is None:
                problems.append(f"AI path '{label}': function {fn}() not found")
            elif not re.search(t["recorder"], body):
                problems.append(f"AI path '{label}' ({fn}) does not record what it filled")
        for fn in t["writers"]:
            body = _fn_body(js, fn)
            if body is None:
                problems.append(f"writer {fn}() not found")
                continue
            calls = list(re.finditer(r"\.from\(\s*['\"]" + re.escape(t["table"])
                                     + r"['\"]\s*\)\s*\.\s*(insert|upsert|update)\s*\(", body))
            if not calls:
                problems.append(f"writer {fn}() no longer writes {t['table']} (re-curate this target)")
            for c in calls:
                # The ROW this call writes must carry the marks - a mention elsewhere in the function (a log line,
                # the embed hand-off) is not the row. v1 of this check matched anywhere in the body and passed with
                # addEntry's payload stamp deleted, because embedFaultEntry({... ai_assisted_fields ...}) sat
                # twenty lines below the insert.
                if not _carries(body, _first_arg(body, c.end() - 1)):
                    problems.append(f"writer {fn}() {c.group(1)}s {t['table']} without ai_assisted_fields on the row")
        for fn in t["via"]:
            body = _fn_body(js, fn)
            if body is None:
                problems.append(f"helper {fn}() not found")
            elif not _KEY.search(body):
                problems.append(f"helper {fn}() drops ai_assisted_fields on the way to {t['table']}")
        rows.append({"page": t["page"], "table": t["table"], "ok": not problems, "problems": problems})
    for path, table, rx in DRAFT_CARRIERS:
        if carriers and path in carriers:
            raw = carriers[path]
        else:
            fp = ROOT / path
            raw = fp.read_text(encoding="utf-8", errors="replace") if fp.exists() else ""
        code = _strip_comments(raw) if path.endswith(".ts") else re.sub(r"(?m)^\s*#.*$", " ", raw)
        problems = [] if re.search(rx, code) else [f"{path} writes {table} without carrying ai_assisted_fields"]
        if not _schema_has(mig, table):
            problems.append(f"no migration adds {table}.ai_assisted_fields")
        rows.append({"page": path, "table": table, "ok": not problems, "problems": problems})
    return {"total": len(rows), "ok": sum(r["ok"] for r in rows), "rows": rows}


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

    # ── AI6b teeth ─────────────────────────────────────────────────────────────────────────────────────────────
    # (1) the JS stripper: a comment must never satisfy a check, and a string must never start a comment.
    js = _strip_js("const a = 'image/*'; x.ai_assisted_fields = 1; // ai_assisted_fields: y\n"
                   "/* lbNoteAiFill( */ const r = /['\"]/g; const t = `${`n`}//`; z();")
    if "x.ai_assisted_fields = 1" not in js or "z();" not in js or len(_KEY.findall(js)) != 1 \
            or "lbNoteAiFill" in js:
        print(f"{R}selftest FAIL: _strip_js kept a comment or ate code: {js!r}{X}"); ok = False

    # (2) the SHIPPED files pass, and each mutation of them FAILS - teeth measured on the real code, not a toy.
    clean = measure_drafts()
    if clean["ok"] != clean["total"]:
        print(f"{R}selftest FAIL: AI6b is not green on the shipped files: "
              f"{[p for r in clean['rows'] for p in r['problems']]}{X}"); ok = False
    texts = {p: (ROOT / p).read_text(encoding="utf-8-sig", errors="replace")
             for p in {t["page"] for t in PAGE_DRAFTS}}

    def _mutate_fn(html: str, fn: str, old: str, new: str) -> str:
        m2 = re.search(r"\bfunction\s+" + re.escape(fn) + r"\s*\(", html)
        start = html.find("{", m2.end())
        depth, j = 0, start
        while j < len(html):
            depth += html[j] == "{"; depth -= html[j] == "}"
            if depth == 0:
                break
            j += 1
        return html[:start] + re.sub(old, new, html[start:j + 1]) + html[j + 1:]

    cases = []
    for t in PAGE_DRAFTS:
        for fn in t["writers"] + t["via"]:
            cases.append((f"{t['page']}: {fn}() stops sending ai_assisted_fields", t["page"], t["table"],
                          {t["page"]: _mutate_fn(texts[t["page"]], fn, r"ai_assisted_fields", "ai_assisted_fieldz")}))
        for label, fn in t["ai_paths"].items():
            cases.append((f"{t['page']}: AI path '{label}' stops recording", t["page"], t["table"],
                          {t["page"]: _mutate_fn(texts[t["page"]], fn, t["recorder"], "noRecord(")}))
    # The hole v1 had: addEntry's ROW loses its stamp while the embed hand-off in the same function still names the
    # key. Must FAIL - a mention elsewhere in the writer is not the row. Same for the stamp surviving only as a comment.
    lb = texts["logbook.html"]
    cases.append(("logbook.html: addEntry row unstamped, embed hand-off still names the key", "logbook.html", "logbook",
                  {"logbook.html": _mutate_fn(lb, "addEntry", r"payload\.ai_assisted_fields\s*=", "payload.other =")}))
    cases.append(("logbook.html: addEntry stamp commented out", "logbook.html", "logbook",
                  {"logbook.html": _mutate_fn(lb, "addEntry", r"\n(\s*)payload\.ai_assisted_fields\s*=",
                                              r"\n\1// payload.ai_assisted_fields =")}))
    cases.append(("logbook.html: submitAsset passes the asset without its stamp", "logbook.html", "asset_nodes",
                  {"logbook.html": _mutate_fn(lb, "submitAsset", r"asset\.ai_assisted_fields\s*=", "asset.other =")}))
    for label, page, table, pages in cases:
        res = measure_drafts(pages=pages)
        row = next(r for r in res["rows"] if r["page"] == page and r["table"] == table)
        if row["ok"]:
            print(f"{R}selftest FAIL: mutation not caught - {label}{X}"); ok = False
    # the schema half: drop the migrations and every target must fail
    res = measure_drafts(mig="")
    if any(r["ok"] for r in res["rows"]):
        print(f"{R}selftest FAIL: a target passed with no migration defining ai_assisted_fields{X}"); ok = False
    # the carriers: embed-entry and the outbox drain must each be caught dropping the marks
    for path, table, rx in DRAFT_CARRIERS:
        raw = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        res = measure_drafts(carriers={path: raw.replace("ai_assisted_fields", "ai_assisted_fieldz")})
        if next(r for r in res["rows"] if r["page"] == path)["ok"]:
            print(f"{R}selftest FAIL: carrier {path} dropping the marks was not caught{X}"); ok = False
    print(f"  AI6b teeth: {len(cases)} page mutations + schema + {len(DRAFT_CARRIERS)} carriers, each must FAIL")
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
    m["drafts"] = d = measure_drafts()
    REPORT.write_text(json.dumps(m, indent=2), encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(m, indent=2)); return 0
    print(f"{B}AI6 · agentic write accountability — AI fns writing DOMAIN tables{X}")
    for r in m["rows"]:
        mark = f"{G}OK  {X}" if r["accountable"] else f"{R}GAP {X}"
        print(f"  {mark} {r['fn']:30s} -> {r['table']}.{r['op']}")
    status = f"{G}OK{X}" if m["pct"] >= floor else f"{R}REGRESSED{X}"
    print(f"\n  {status}  AI6: {m['ok']}/{m['total']} = {m['pct']}% (baseline {floor}%)")
    print(f"\n{B}AI6b · AI-drafted, person-saved - the row names which fields the AI wrote (ai_assisted_fields){X}")
    for r in d["rows"]:
        mark = f"{G}OK  {X}" if r["ok"] else f"{R}GAP {X}"
        print(f"  {mark} {r['page']:42s} -> {r['table']}")
        for p in r["problems"]:
            print(f"         {R}{p}{X}")
    print(f"\n  AI6b: {d['ok']}/{d['total']} (every target must hold - no baseline)")
    if m["pct"] < floor:
        print(f"{R}{B}FAIL{X} - an AI write lost its provenance marker: {', '.join(m['gaps'])}")
        return 1
    if d["ok"] < d["total"]:
        print(f"{R}{B}FAIL{X} - an AI-drafted, person-saved write no longer says which fields the AI wrote.")
        return 1
    print(f"{G}{B}PASS{X} - every AI write into a human-read domain table declares machine authorship, and every "
          f"AI-drafted form a person saves records which fields the AI wrote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
