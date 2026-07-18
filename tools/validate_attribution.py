#!/usr/bin/env python3
# DEEPWALK-CELL: * D2
"""
validate_attribution.py  --  LOCK for the auth_uid attribution-drop bug class.

Bug class (found live 2026-07-06 on inventory_transactions, then audited platform-wide):
a CLIENT-side `db.from(T).insert/upsert(payload)` where T has an `auth_uid` column with
NO `DEFAULT auth.uid()`, and `payload` sets worker_name/hive_id but OMITS `auth_uid` ->
the row lands with NULL attribution. Only `ai_reply_feedback` has a DB default (exempt).

This gate fails any such write so the class can never regress. It statically resolves each
insert/upsert payload (inline object OR named variable's literal) and checks for `auth_uid`.

Usage:  python tools/validate_attribution.py [--check] [--json]
Exit 0 = clean, 1 = violations.
"""
import re, sys, pathlib, json

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Tables with an auth_uid column and NO `DEFAULT auth.uid()` -> client MUST set auth_uid.
# (ai_reply_feedback is intentionally excluded: it has DEFAULT auth.uid().)
INSCOPE = {
    "agent_episodic_memory", "agent_memory", "analytics_events", "asset_edges",
    "asset_nodes", "auth_session_events", "community_posts", "engineering_calcs",
    "gateway_audit_log", "hive_members", "inventory_items", "inventory_transactions",
    "logbook", "marketplace_sellers", "mfa_enrollments", "platform_feedback",
    "pm_assets", "pm_completions", "projects", "resume_documents", "resume_versions",
    "schedule_items", "skill_badges", "skill_exam_attempts", "skill_profiles",
    "voice_journal_entries", "worker_achievements", "worker_profiles",
}

def app_pages():
    skip = ("backup", "-test", "index-", "offline-fallback")
    for p in sorted(ROOT.glob("*.html")):
        if any(s in p.name for s in skip):
            continue
        yield p

def page_scripts():
    """Externalized page JS (e.g. engineering-design.js) — client db writes moved OUT of
    the HTML were invisible to the HTML-only scan, so an auth_uid drop in them (the exact
    P2/I-1 bug) was never caught. Scan root *.js too; skip minified vendor bundles + tools."""
    skip_sub = (".min.", "backup", "-test", "vendor")
    for p in sorted(ROOT.glob("*.js")):
        if any(s in p.name for s in skip_sub):
            continue
        yield p

# .from('T') ... .insert(  |  .upsert(   (chain may span a few lines / have .select() etc.)
FROM_RE = re.compile(r"\.from\(\s*['\"]([a-z_]+)['\"]\s*\)")
OP_RE   = re.compile(r"\.(insert|upsert)\s*\(")

def line_of(text, idx):
    return text.count("\n", 0, idx) + 1

def balanced(text, open_idx, opener="{", closer="}"):
    """Return substring of the balanced block starting at the opener at/after open_idx."""
    i = text.find(opener, open_idx)
    if i == -1:
        return ""
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == opener: depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return text[i:j+1]
        j += 1
    return text[i:]

def first_arg(text, paren_idx):
    """Given index of the '(' after insert/upsert, return (kind, token/objtext)."""
    # skip whitespace after '('
    k = paren_idx + 1
    while k < len(text) and text[k] in " \t\r\n":
        k += 1
    if k >= len(text):
        return ("none", "")
    if text[k] == "{":
        return ("obj", balanced(text, k))
    if text[k] == "[":
        # array of objects: check the first object literal inside
        return ("obj", balanced(text, k, "{", "}"))
    # identifier — either a plain payload variable or a function-call payload fn(...)
    m = re.match(r"[A-Za-z_$][\w$]*", text[k:])
    if not m:
        return ("none", "")
    after = text[k + m.end():]
    if re.match(r"\s*\(", after):
        return ("call", m.group(0))
    return ("ident", m.group(0))

def function_body(text, name):
    """Return the body text of `function name(` or `name = (..)=>{` / `name = function`."""
    pats = [
        rf"\bfunction\s+{re.escape(name)}\s*\(",
        rf"\b{re.escape(name)}\s*=\s*(?:async\s*)?function\b",
        rf"\b{re.escape(name)}\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*",
    ]
    for pat in pats:
        m = re.search(pat, text)
        if m:
            body = balanced(text, m.end())  # first {...} after the signature
            if body:
                return body
    return None

def resolve_ident_literal(text, name, before_idx, depth=0):
    """Resolve `name` to the object literal / body that defines its payload shape."""
    if depth > 4:
        return None
    # nearest definition before the call site (fallback: any definition)
    defs = list(re.finditer(rf"\b(?:const|let|var\s+)?{re.escape(name)}\s*=\s*", text))
    defs = [m for m in defs if m.end() <= before_idx + 5] or defs
    for m in defs[::-1]:
        # scope the RHS to THIS statement (up to the next ';')
        stmt_end = text.find(";", m.end())
        if stmt_end == -1:
            stmt_end = m.end() + 800
        rhs = text[m.end(): stmt_end]
        # 1. an object literal inside the statement (handles `= {...}` and `.map(r => ({...}))`)
        brace_rel = rhs.find("{")
        if brace_rel != -1:
            lit = balanced(text, m.end() + brace_rel)
            if lit:
                return lit
        # 2. .map(funcName)/.forEach(funcName) -> that function's row-shape body
        mapfn = re.search(r"\.(?:map|forEach|flatMap)\(\s*([A-Za-z_$][\w$]*)\s*\)", rhs)
        if mapfn:
            fb = function_body(text, mapfn.group(1))
            if fb:
                return fb
        # 3. indirection: SRC.slice/filter/concat(  OR  SRC[...]  -> resolve SRC
        ind = re.match(r"\s*([A-Za-z_$][\w$]*)\s*(?:\.(?:slice|filter|concat|sort|reverse)\(|\[)", rhs)
        if ind and ind.group(1) != name:
            r = resolve_ident_literal(text, ind.group(1), before_idx, depth+1)
            if r:
                return r
        # 4. function-call payload: name = fn(
        call = re.match(r"\s*([A-Za-z_$][\w$]*)\s*\(", rhs)
        if call:
            fb = function_body(text, call.group(1))
            if fb:
                return fb
    # last resort: name.push({...}) somewhere
    pm = re.search(rf"\b{re.escape(name)}\.push\(\s*\{{", text)
    if pm:
        return balanced(text, pm.end()-1)
    return None

def enclosing_scope(text, idx):
    """Text from the nearest preceding function declaration up to idx (payload-build window)."""
    starts = [m.end() for m in re.finditer(r"\b(?:async\s+)?function\s+\w+\s*\(|\b[\w$]+\s*[:=]\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>)", text) if m.end() < idx]
    start = max(starts) if starts else max(0, idx - 3000)
    return text[start:idx]

def _blank_block_comments(text):
    """Replace /* ... */ block comments with equal-length whitespace (newlines kept), so
    usage examples in a file's docstring (e.g. `await db.from('logbook').insert(payload)` in
    wh-capture-validate.js's header) are not matched as real writes — while byte offsets and
    line numbers stay identical for accurate reporting."""
    def repl(m):
        return "".join(ch if ch == "\n" else " " for ch in m.group(0))
    return re.sub(r"/\*.*?\*/", repl, text, flags=re.S)

def scan(path):
    raw  = path.read_text(encoding="utf-8", errors="ignore")
    text = _blank_block_comments(raw)   # structural matching ignores comment bodies
    viols = []
    for fm in FROM_RE.finditer(text):
        table = fm.group(1)
        if table not in INSCOPE:
            continue
        # find the next .insert(/.upsert( within a small window, with no ';' or new '.from(' between
        win = text[fm.end(): fm.end() + 300]
        om = OP_RE.search(win)
        if not om:
            continue
        between = win[:om.start()]
        if ";" in between or ".from(" in between:
            continue
        op = om.group(1)
        paren_idx = fm.end() + om.end() - 1  # index of '(' in full text
        kind, arg = first_arg(text, paren_idx)
        ln = line_of(text, fm.start())
        # explicit exemption marker (like empty-catch-allow) for verified cross-function flows.
        # Read from RAW (not comment-blanked) so a `/* attribution-allow */` marker is seen.
        line_start = raw.rfind("\n", 0, fm.start())
        ctx = raw[max(0, line_start - 200): paren_idx + 200]
        if "attribution-allow" in ctx:
            continue
        literal = None
        if kind == "obj":
            literal = arg
        elif kind == "ident":
            literal = resolve_ident_literal(text, arg, fm.start())
        elif kind == "call":
            literal = function_body(text, arg)
        # Per-PAYLOAD check only — NO enclosing-scope fallback (that hid the original
        # pm-scheduler bug where one function wrote pm_completions WITH auth_uid but the
        # logbook mirror WITHOUT it). Unresolvable payloads must carry an attribution-allow marker.
        ok = bool(literal and re.search(r"\bauth_uid\b", literal))
        if not ok:
            viols.append({
                "file": path.name, "line": ln, "table": table, "op": op,
                "payload": (arg[:40] if kind in ("ident", "call") else "inline-object"),
            })
    return viols

def main():
    as_json = "--json" in sys.argv
    all_viols = []
    targets = list(app_pages()) + list(page_scripts())
    for p in targets:
        all_viols.extend(scan(p))
    if as_json:
        print(json.dumps({"violations": all_viols, "count": len(all_viols)}, indent=2))
    else:
        print("attribution (auth_uid on every client write to auth_uid-no-default tables)")
        if not all_viols:
            print("  PASS: 0 attribution drops across", len(list(app_pages())), "pages +",
                  len(list(page_scripts())), "page scripts")
        else:
            print(f"  FAIL: {len(all_viols)} client insert/upsert(s) omit auth_uid:")
            for v in all_viols:
                print(f"    {v['file']}:{v['line']}  {v['op']}({v['payload']}) -> {v['table']}")
    return 1 if all_viols else 0

if __name__ == "__main__":
    sys.exit(main())
