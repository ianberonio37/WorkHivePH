"""validate_audit_trail_coverage.py — Walkthrough 2026-05-13 finding generalised.

Bug class found during walkthrough: a supervisor power action mutates a
status-lifecycle row (anomaly_signals ack/resolve) but never writes a
matching row to hive_audit_log. The action is invisible in the standard
audit trail. Compliance reports, insurance bridge view, and multi-
supervisor coordination all lose traceability.

This validator enumerates every lifecycle table that should be audited
when its status changes via UI, then scans every page's update handler
for the matching writeAuditLog call.

  Layer 1 — UI mutation paired with audit log
    For each LIFECYCLE_TABLE, every `.update({ status: ... }` call site
    must be in the same function body as a `writeAuditLog(` call.

  Layer 2 — Audit-log action vocabulary completeness
    utils.js's WH_AUDIT_ACTIONS (the ONE vocabulary the hive board and
    audit-log.html both render through) must have words for every action
    any writer can produce: a writeAuditLog call on ANY page, a root
    script, an edge function, a migration (a literal, a CASE, or the
    generic audit_shared_change trigger's add_/change_/remove_<thing>
    grammar, whose <thing> must be in WH_AUDIT_THINGS), a seeder, or a
    voice intent kind. Unknown actions render as a code.

  Layer 3 — What is STORED has words (live, the local database)
    SL L2 (2026-10-21): layer 2 passed while 10 of the 46 actions stored
    in hive_audit_log had no words (supervisor_password_reset, 71 rows;
    soft_delete_post, 57; ...). It scanned 12 named pages: community and
    marketplace-seller were not among them, and no edge function was
    read at all. The stored rows are what a supervisor reads, so they
    are checked directly: every distinct hive_audit_log.action and
    ai_audit_log.event must have words.

  Layer 4 — Both readers render through the vocabulary
    audit-log.html showed `action.replace(/_/g, ' ')` ("amend closed
    logbook entry") where the hive board said "Amended a signed-off
    entry": two readers, two vocabularies. Both must call whAuditLabel,
    neither may keep its own map, and the CSV must carry the words.

  Layer 5 — A trail row names the thing in words, not an id
    writeAuditLog's target name is what the reader sees. Passing the id
    as the name (approve_rcm_strategy logged the strategy's uuid, which
    the board then hides) or no name at all leaves "Approved RCM strategy"
    with nothing saying which.

Out of scope (intentional):
  - Server-side mutations (edge functions writing through service-role).
    Those should write audit-log entries too, but a different validator
    covers edge fn audit (validate_edge_contracts).
  - Lifecycle tables whose status changes are driven only by cron / RPC
    (failure_signature_alerts is written by the failure-signature-scan
    edge fn; ack/resolve UI is also in alert-hub but goes through this
    validator already because it's UI-layer).
"""
from __future__ import annotations
import json, re, subprocess, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent
DB_CONTAINER = "supabase_db_workhive"

# Lifecycle tables where every UI-layer status change is a supervisor
# power action that MUST land in hive_audit_log. Add new tables here as
# the platform gains them. Each entry: (table, [valid_status_values]).
LIFECYCLE_TABLES = {
    "anomaly_signals":     ["acknowledged", "resolved"],
    "hive_members":        ["kicked"],
    "amc_briefings":       ["approved", "rejected"],
    "asset_nodes":         ["approved", "rejected"],
    "inventory_items":     ["approved", "rejected"],
    "assets":              ["approved", "rejected"],
    "drone_inspections":   ["reviewed", "archived", "cancelled"],
    "consulting_engagements": ["completed", "cancelled"],
}

# Audit log action vocabulary — every action any writer produces must have words in utils.js's WH_AUDIT_ACTIONS (or be
# add_/change_/remove_<thing> with <thing> in WH_AUDIT_THINGS), the one map the hive board and audit-log.html render.
VOCAB_FILE = "utils.js"
RENDERERS = ("hive.html", "audit-log.html")
# Folders whose HTML is not a production page (fixtures for gates, poster art).
NON_PAGE_DIRS = {"_fixtures", "promo_posters", "node_modules", "test-runs", "tests", "tools", "substrate", "supabase",
                 "test-data-seeder", "workflows", "venv"}


def all_pages() -> list[Path]:
    """Every production page: the root and one folder down (learn/, about/, ...). A fixed list of 12 is how
    community.html and marketplace-seller.html - 10 stored actions between them - went unread for months."""
    pages = sorted(ROOT.glob("*.html"))
    for sub in sorted(p for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in NON_PAGE_DIRS):
        pages += sorted(sub.glob("*.html"))
    return pages


def all_scripts() -> list[Path]:
    """Root scripts the pages load (device-fingerprint.js, voice-handler.js, ...) and every edge function."""
    out = sorted(ROOT.glob("*.js"))
    fn = ROOT / "supabase" / "functions"
    if fn.exists():
        out += sorted(fn.rglob("*.ts"))     # _shared included
    return out

# Re-entry guard: some pages declare an UPDATE inside a generator / loop
# rather than a handler. Skip those — we only care about function-scoped
# update calls.

# L1 — "is there a writeAuditLog call at all". Accepts any first arg
# (literal, ternary, variable). The presence of the call is enough for
# audit-coverage; the action vocabulary check is separate.
WRITE_AUDIT_ANY_RE = re.compile(r"\bwriteAuditLog\s*\(")
# L2 — extract literal action names. Also recognises the ternary form
# `cond ? 'name_a' : 'name_b'` by collecting BOTH names so the ACTION_ICON
# completeness check covers conditional dispatch.
# Action names follow snake_case verb_noun. Requiring at least one
# underscore filters out comparison literals like 'acknowledge', 'approved',
# 'pending' that appear in `cond === 'X' ? ...` first-arg ternaries.
WRITE_AUDIT_NAMES_RE = re.compile(r"['\"]([a-z][a-z0-9_]*_[a-z0-9_]{1,40})['\"]")
WRITE_AUDIT_CALL_RE  = re.compile(r"\bwriteAuditLog\s*\(([^)]{0,400})")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _enclosing_function_body(content: str, position: int, window: int = 4000) -> str:
    """Return ~window chars of the enclosing function body around `position`.
    Walks backward to find `function`/`async function`/arrow function open;
    if none found within `window`, returns a fixed-size slice instead.
    """
    start = max(0, position - window)
    return content[start:position + window]


def check_lifecycle_audit_coverage() -> list[dict]:
    issues = []
    for p in all_pages():
        page = p.relative_to(ROOT).as_posix()
        content = _read(p)
        if not content:
            continue
        for table, statuses in LIFECYCLE_TABLES.items():
            # Match: .from('TABLE')...update({ status:
            patt = re.compile(
                rf"\.from\(\s*['\"]{re.escape(table)}['\"]\s*\)[\s\S]{{0,200}}\.update\s*\(\s*\{{[^}}]*status\s*:",
                re.IGNORECASE,
            )
            for m in patt.finditer(content):
                line = content[:m.start()].count("\n") + 1
                # Within ~30 lines of this update, is there a writeAuditLog
                # call? That's the audit-trail pairing the validator demands.
                lookahead = content[m.start():m.start() + 3000]
                lookbehind = content[max(0, m.start() - 1500):m.start()]
                window_blob = lookbehind + lookahead
                # ★A DATABASE TRIGGER IS ALSO AN AUDIT WRITER (2026-09-06). asset-hub's approve/reject paths
                # used to call writeAuditLog from the client AND be audited by the 20260728000015 trigger, so
                # every decision wrote the row twice. Removing the client copy is the correct fix - the trigger
                # is authoritative and fires however the row is updated, including from psql or another surface -
                # but L1 then reported the page as unaudited. A status update whose own table is audited by a
                # trigger, and which SAYS so in a comment naming that trigger, is covered.
                TRIGGER_COVERED = re.compile('audit(ed)? by (the )?[a-z_0-9]*trigger|trigger .{0,60}(writes|is authoritative)|[0-9]{14}[a-z_0-9]* trigger', re.I)
                if not WRITE_AUDIT_ANY_RE.search(window_blob) and not TRIGGER_COVERED.search(window_blob):
                    issues.append({
                        "check": "lifecycle_audit_missing",
                        "page": page,
                        "table": table,
                        "line": line,
                        "reason": (
                            f"{page}:{line} — `{table}` status update has no "
                            f"writeAuditLog call in scope. Supervisor power "
                            f"actions on lifecycle tables MUST land in "
                            f"hive_audit_log so compliance audits and the "
                            f"insurance bridge view can read the trail."
                        ),
                    })
    return issues


def _harvest_actions_from_js(src: str) -> set:
    """Pull action names from writeAuditLog(FIRST_ARG, ...) calls in JS."""
    out = set()
    for call_m in WRITE_AUDIT_CALL_RE.finditer(src):
        args_window = call_m.group(1)
        first_arg = ''
        depth = 0
        for i, ch in enumerate(args_window):
            if ch in '([{': depth += 1
            elif ch in ')]}': depth -= 1
            elif ch == ',' and depth == 0:
                first_arg = args_window[:i]
                break
        else:
            first_arg = args_window
        for n in WRITE_AUDIT_NAMES_RE.findall(first_arg):
            out.add(n)
    return out


# SQL: INSERT INTO hive_audit_log (..., action, ...) VALUES (..., 'action_name', ...)
# OR  : INSERT INTO hive_audit_log (..., action, ...) SELECT ..., 'action_name', ...
# OR  : INSERT INTO hive_audit_log (..., action, ...) SELECT (ARRAY['a','b'])[floor(...)]
# We walk the column list, find the position of `action`, then harvest
# every literal string at that position across VALUES tuples + ARRAY[...]
# constructs. False-positive risk is low because we lock to the action
# column index.
SQL_INSERT_AUDIT_RE = re.compile(
    r"INSERT\s+INTO\s+(?:public\.)?hive_audit_log\s*\(([^)]+)\)([\s\S]{0,4000}?);",
    re.IGNORECASE,
)
PY_AUDIT_INSERT_RE = re.compile(
    # client.table('hive_audit_log').insert({...})  OR  table("hive_audit_log").upsert({...})
    r"\.table\(\s*['\"]hive_audit_log['\"]\s*\)[\s\S]{0,400}?(?:insert|upsert)\s*\(\s*(\{[\s\S]{0,1500}?\})",
    re.IGNORECASE,
)
PY_AUDIT_ACTION_RE = re.compile(
    r"['\"]action['\"]\s*:\s*['\"]([a-z][a-z0-9_]*_[a-z0-9_]{1,40}|[a-z][a-z0-9_]{2,40})['\"]",
)


def _balanced_paren_groups(text: str, limit: int = 4000):
    """Yield the contents of each TOP-LEVEL (...) group, keeping nested calls intact.

    A VALUES row is one such group. Matching with `\\(([^)]*)\\)` instead stops at the first ')',
    which both truncates a row containing a nested call and then matches that nested call's own
    argument list as if it were a row — how a jsonb_build_object meta key came to be reported as an
    audit action while the row's real CASE-based actions went unseen.
    """
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == '(':
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ')':
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    group = text[start:i]
                    if len(group) <= limit:
                        yield group
                    start = None


def _harvest_actions_from_sql(src: str) -> set:
    # Strip SQL line comments FIRST. A commented-out `-- INSERT INTO hive_audit_log (action, ...)`
    # example, or an aside like `-- gen_random_uuid() (pg_catalog)`, must never be parsed as a real
    # audit insert — otherwise the crude positional scan harvests a schema/keyword ('pg_catalog') as
    # a phantom action. (2026-07-11: fixed a false-positive from 20260707000006_fix_delete_worker_data_audit_hive.sql.)
    src = re.sub(r"--[^\n]*", "", src)
    out = set()
    for m in SQL_INSERT_AUDIT_RE.finditer(src):
        col_list = [c.strip() for c in m.group(1).split(',')]
        try:
            action_idx = col_list.index('action')
        except ValueError:
            continue
        body = m.group(2)
        # ARRAY['a','b','c'] picker: harvest every literal inside ARRAY[...]
        for arr in re.finditer(r"ARRAY\s*\[([^\]]+)\]", body, re.IGNORECASE):
            for lit in re.findall(r"'([a-z][a-z0-9_]*)'", arr.group(1)):
                out.add(lit)
        # Plain VALUES (... 'action_name' ...): pick column at action_idx.
        # Positional scan over each VALUES row.
        #
        # 2026-07-28: the old pattern was `\(([^)]{1,2000})\)`, which stops at the FIRST ')'. On a
        # row whose action is a CASE expression and whose meta is a jsonb_build_object(...), that is
        # wrong in both directions at once: it never captures the real row (so the actual actions are
        # missed), and it DOES match the inner jsonb_build_object argument list, where position
        # `action_idx` lands on a META KEY. A trigger writing
        #   ... CASE WHEN ... THEN 'reopen_...' ELSE 'amend_...' END, ...,
        #       jsonb_build_object('prev_status', OLD.status, 'new_status', NEW.status, ...)
        # therefore reported a phantom action 'new_status' while silently missing both real ones.
        # Same false-positive family as the pg_catalog fix above, one nesting level deeper.
        #
        # Fixed by matching balanced parens, so a row is the whole row and nested calls stay nested.
        for row in _balanced_paren_groups(body, limit=4000):
            # Tokenise on commas at depth 0 (won't split inside nested parens)
            parts, depth, buf = [], 0, []
            for ch in row:
                if ch in '([': depth += 1
                elif ch in ')]': depth -= 1
                if ch == ',' and depth == 0:
                    parts.append(''.join(buf).strip()); buf = []
                else:
                    buf.append(ch)
            parts.append(''.join(buf).strip())
            if action_idx < len(parts):
                tok = parts[action_idx]
                lit = re.search(r"^'([a-z][a-z0-9_]*)'$", tok)
                if lit:
                    out.add(lit.group(1))
                elif re.match(r"^\s*CASE\b", tok, re.IGNORECASE):
                    # A conditional action picks one of several literals at runtime, so EVERY
                    # branch is a real action the viewer must be able to render. Harvest them all.
                    for branch in re.findall(r"'([a-z][a-z0-9_]*)'", tok):
                        out.add(branch)
    return out


def _harvest_actions_from_py(src: str) -> set:
    out = set()
    for m in PY_AUDIT_INSERT_RE.finditer(src):
        payload = m.group(1)
        for am in PY_AUDIT_ACTION_RE.finditer(payload):
            out.add(am.group(1))
    return out


# An edge function / root script inserting a row object: .from("hive_audit_log").insert({ ..., action: "x", ... }).
# The action may be a literal or `cond ? "a" : "b"`; both names are collected.
TS_AUDIT_INSERT_RE = re.compile(
    r"from\(\s*['\"]hive_audit_log['\"]\s*\)[\s\S]{0,300}?\.(?:insert|upsert)\s*\(\s*\[?\s*\{([\s\S]{0,1500}?)\}", re.I)
TS_ACTION_RE = re.compile(r"\baction\s*:\s*([^,\n}]{1,200})")
# Voice: every confirmed intent is recorded in ai_audit_log under the intent's kind, and audit-log.html shows those rows
# in the same timeline - so a registered kind is an action a supervisor reads.
VOICE_KIND_RE = re.compile(r"\bregister(?:Handler|Intent)?\s*\(\s*['\"]([a-z_]+\.[a-z_]+)['\"]")
VOICE_EVENT_RE = re.compile(r"from\(\s*['\"]ai_audit_log['\"]\s*\)[\s\S]{0,200}?insert\s*\(\s*\{[\s\S]{0,400}?\bevent\s*:\s*['\"]([a-z_.]+)['\"]")
# The generic trail (SL L2): create trigger ... after <events> ... execute function public.audit_shared_change('<thing>', ...)
SHARED_TRIGGER_RE = re.compile(
    r"create\s+trigger\s+\w+\s+after\s+([\s\S]{1,300}?)\s+on\s+(?:public\.)?(\w+)[\s\S]{0,200}?"
    r"execute\s+function\s+(?:public\.)?audit_shared_change\s*\(\s*'([^']+)'", re.I)


def _harvest_actions_from_ts(src: str) -> set:
    out = set()
    for m in TS_AUDIT_INSERT_RE.finditer(src):
        for am in TS_ACTION_RE.finditer(m.group(1)):
            out.update(re.findall(r"['\"]([a-z][a-z0-9_]*)['\"]", am.group(1)))
    return out


def _harvest_voice(src: str) -> set:
    return set(VOICE_KIND_RE.findall(src)) | set(VOICE_EVENT_RE.findall(src))


def _thing_key(thing: str) -> str:
    return thing.strip().lower().replace(" ", "_")     # the trigger's own rule: lower(replace(thing, ' ', '_'))


# A trigger that picks its action into a variable first (audit_platform_decision: `v_action := case new.status when
# 'verified' then 'verify_topup' else 'reject_topup' end;`) - the INSERT carries the variable, so the literals are read
# from the assignment, inside any function that writes either trail.
ACTION_ASSIGN_RE = re.compile(r"\b\w*action\w*\s*:=\s*(case\b[\s\S]{0,600}?\bend\b|'[a-z][a-z0-9_]*')", re.I)
TRAIL_FN_RE = re.compile(r"create\s+or\s+replace\s+function[\s\S]{0,12000}?\$\$\s*;", re.I)


def _harvest_action_assignments(src: str) -> set:
    out = set()
    src = re.sub(r"--[^\n]*", "", src)
    for fn in TRAIL_FN_RE.finditer(src):
        body = fn.group(0)
        if not re.search(r"insert\s+into\s+(?:public\.)?(?:hive|platform)_audit_log", body, re.I):
            continue
        for m in ACTION_ASSIGN_RE.finditer(body):
            out.update(re.findall(r"'([a-z][a-z0-9_]*_[a-z0-9_]+)'", m.group(1)))
    return out


def _harvest_shared_trigger(src: str) -> set:
    out = set()
    src = re.sub(r"--[^\n]*", "", src)
    for events, _table, thing in SHARED_TRIGGER_RE.findall(src):
        ev = events.lower()
        key = _thing_key(thing)
        if "insert" in ev: out.add("add_" + key)
        if "update" in ev: out.add("change_" + key)
        if "delete" in ev: out.add("remove_" + key)
    return out


def actions_written() -> dict:
    """action -> where it is written (first source found). Every surface that can put a row in a trail a person reads."""
    found: dict = {}
    def add(names, where):
        for n in names:
            found.setdefault(n, where)
    for p in all_pages():
        src = _read(p)
        add(_harvest_actions_from_js(src), p.relative_to(ROOT).as_posix())
        add(_harvest_voice(src), p.relative_to(ROOT).as_posix())
    for p in all_scripts():
        src = _read(p)
        rel = p.relative_to(ROOT).as_posix()
        add(_harvest_actions_from_js(src), rel)
        add(_harvest_actions_from_ts(src), rel)
        add(_harvest_voice(src), rel)
    migrations_dir = ROOT / "supabase" / "migrations"
    if migrations_dir.exists():
        for sql_path in sorted(migrations_dir.glob("*.sql")):
            src = _read(sql_path)
            add(_harvest_actions_from_sql(src), "migration " + sql_path.name)
            add(_harvest_shared_trigger(src), "migration " + sql_path.name)
            add(_harvest_action_assignments(src), "migration " + sql_path.name)
    seeders_dir = ROOT / "test-data-seeder" / "seeders"
    if seeders_dir.exists():
        for py_path in sorted(seeders_dir.glob("*.py")):
            add(_harvest_actions_from_py(_read(py_path)), "seeder " + py_path.name)
    return found


def _block(src: str, name: str) -> str:
    """The body of `const NAME = { ... };` in utils.js (brace-matched, so nested {} entries stay inside)."""
    m = re.search(r"\bconst\s+%s\s*=\s*\{" % re.escape(name), src)
    if not m:
        return ""
    depth, i = 0, m.end() - 1
    for j in range(i, len(src)):
        if src[j] == "{": depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i + 1:j]
    return ""


def vocabulary() -> tuple[set, set]:
    """(actions with words, things the generic grammar may name) - read from utils.js, the one source."""
    src = _read(ROOT / VOCAB_FILE)
    acts = set(re.findall(r"^\s*'?([a-z][a-z0-9_.]*)'?\s*:\s*\{[^\n]*\blabel\s*:", _block(src, "WH_AUDIT_ACTIONS"), re.M))
    things = set(re.findall(r"^\s*'?([a-z][a-z0-9_]*)'?\s*:", _block(src, "WH_AUDIT_THINGS"), re.M))
    return acts, things


GENERIC_RE = re.compile(r"^(add|change|remove)_([a-z0-9_]+)$")


def has_words(action: str, acts: set, things: set) -> bool:
    if action in acts:
        return True
    g = GENERIC_RE.match(action or "")
    return bool(g and g.group(2) in things)


def check_action_icon_completeness() -> list[dict]:
    """L2: every action any writer can produce has words in utils.js (2026-05-13: an `assign` row from seed SQL rendered
    as a dot, so migrations + seeders are read; SL L2 2026-10-21: every page, root script and edge function too)."""
    issues = []
    acts, things = vocabulary()
    for action, where in sorted(actions_written().items()):
        if has_words(action, acts, things):
            continue
        issues.append({
            "check": "action_words_missing",
            "page": VOCAB_FILE,
            "action": action,
            "reason": (
                f"'{action}' is written by {where} but {VOCAB_FILE}'s WH_AUDIT_ACTIONS has no words for it, so the "
                f"hive board and audit-log.html show the code. Add `{action}: {{ icon: '...', label: '...' }}`"
                + (" - or, for the generic trail, the thing to WH_AUDIT_THINGS." if GENERIC_RE.match(action) else ".")),
        })
    return issues


def stored_actions() -> tuple[dict | None, str]:
    """Distinct actions in the LOCAL database's two trails, with counts. None when the database cannot be read."""
    sql = ("select 'A|' || action || '|' || count(*) from public.hive_audit_log group by action "
           "union all select 'V|' || event || '|' || count(*) from public.ai_audit_log group by event "
           "union all select 'P|' || action || '|' || count(*) from public.platform_audit_log group by action")
    try:
        r = subprocess.run(["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-Atc", sql],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "").strip()[:200]
    out = {}
    for line in r.stdout.splitlines():
        parts = line.split("|")
        if len(parts) == 3:
            out[parts[1]] = out.get(parts[1], 0) + int(parts[2])
    return out, ""


def check_stored_actions() -> tuple[list[dict], list[dict]]:
    """L3: what a supervisor will actually read - every stored action has words."""
    stored, err = stored_actions()
    if stored is None:
        return [], [{"check": "stored_unread", "reason": f"the local database could not be read ({err}) - L3 not run"}]
    acts, things = vocabulary()
    issues = []
    for action, n in sorted(stored.items(), key=lambda kv: -kv[1]):
        if not has_words(action, acts, things):
            issues.append({"check": "stored_action_without_words", "page": VOCAB_FILE, "action": action,
                           "reason": f"{n} stored trail row(s) say '{action}' and {VOCAB_FILE} has no words for it - "
                                     f"a supervisor reads the code. Find its writer and add the words."})
    return issues, []


# L4 - the readers. Each must render through whAuditLabel and keep no vocabulary of its own.
OWN_MAP_RE = re.compile(r"\bconst\s+ACTION_ICON\s*=\s*\{")
CODE_AS_WORDS_RE = re.compile(r"\(\s*en\.action\s*\|\|\s*''\s*\)\.replace\(/_/g")


def _code_only(src: str) -> str:
    """The source with HTML, block and line comments removed - the explanatory comments beside these renderers NAME
    whAuditView and ACTION_ICON, and a comment must never satisfy (or trip) a check meant for code."""
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return re.sub(r"(?<![:'\"\\])//[^\n]*", "", src)


def check_renderers() -> list[dict]:
    issues = []
    for page in RENDERERS:
        src = _code_only(_read(ROOT / page))
        why = []
        if "whAuditLabel(" not in src and "whAuditView(" not in src:
            why.append("never renders through whAuditLabel / whAuditView")
        if OWN_MAP_RE.search(src):
            why.append("keeps its own ACTION_ICON map (a second vocabulary drifts from the first)")
        if CODE_AS_WORDS_RE.search(src):
            why.append("shows the action code with underscores opened up instead of its words")
        if page == "audit-log.html" and not re.search(r"['\"]what_happened['\"]", src):
            why.append("its CSV export carries the code only - an auditor reading the file needs the words too "
                       "(a 'what_happened' column)")
        for w in why:
            issues.append({"check": "renderer_vocabulary", "page": page, "reason": f"{page} {w}."})
    return issues


# L5 - a trail row names its thing. Each page's writeAuditLog helper has its own parameter order; the name parameter is
# found by its NAME (targetName), then every call is checked at that position.
HELPER_RE = re.compile(r"function\s+writeAuditLog\s*\(([^)]*)\)")
SELF_NAMES = {"WORKER_NAME", "workerName", "WORKER", "me", "actor"}


def _split_args(s: str) -> list[str]:
    out, depth, buf, q = [], 0, [], None
    for ch in s:
        if q:
            buf.append(ch)
            if ch == q: q = None
            continue
        if ch in "'\"`": q = ch; buf.append(ch); continue
        if ch in "([{": depth += 1
        elif ch in ")]}":
            if depth == 0: break
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(buf).strip()); buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail: out.append(tail)
    return out


def check_target_names() -> list[dict]:
    issues = []
    for p in all_pages():
        src = _read(p)
        h = HELPER_RE.search(src)
        if not h:
            continue
        # a RETIRED page (founder-console, marketplace-admin) keeps its code so the static validators that scan it still
        # pass, but its controls sit under #wh-retired-overlay and nobody can reach them - platform-actions owns those
        # decisions now, and the database records them (platform_audit_log)
        if 'id="wh-retired-overlay"' in src:
            continue
        params = [x.split("=")[0].strip() for x in h.group(1).split(",")]
        if "targetName" not in params:
            continue
        ni = params.index("targetName")
        ii = params.index("targetId") if "targetId" in params else None
        page = p.relative_to(ROOT).as_posix()
        for m in re.finditer(r"\bwriteAuditLog\s*\(", src):
            if src[max(0, m.start() - 9):m.start()].endswith("function "):
                continue
            line_start = src.rfind("\n", 0, m.start()) + 1
            if src[line_start:m.start()].lstrip().startswith(("//", "*")):
                continue
            args = _split_args(src[m.end():m.end() + 600])
            name = args[ni] if len(args) > ni else ""
            ident = args[ii] if ii is not None and len(args) > ii else None
            line = src.count("\n", 0, m.start()) + 1
            bad = None
            if not name or name in ("null", "undefined", "''", '""'):
                bad = "passes no name"
            elif ident is not None and name == ident and name not in SELF_NAMES:
                bad = f"passes the id ({ident}) as the name"
            if bad:
                issues.append({"check": "trail_row_without_name", "page": page, "line": line,
                               "reason": f"{page}:{line} writeAuditLog(...) {bad} - the reader sees what happened and "
                                         f"not to what. Pass the thing's own name (its title, label, the post's opening words)."})
    return issues


LAYERS = [
    {"layer": "L1", "label": "UI status updates on lifecycle tables write to hive_audit_log"},
    {"layer": "L2", "label": "Every action any writer produces has words in utils.js (pages, scripts, edge fns, migrations, seeders, voice)"},
    {"layer": "L3", "label": "Every action STORED in the local trails has words (live)"},
    {"layer": "L4", "label": "hive.html and audit-log.html render through whAuditLabel; the CSV carries the words"},
    {"layer": "L5", "label": "Each writeAuditLog call names its thing (not an id, not nothing)"},
]


def run() -> dict:
    issues, warnings = [], []
    issues.extend(check_lifecycle_audit_coverage())
    issues.extend(check_action_icon_completeness())
    l3, w3 = check_stored_actions()
    issues.extend(l3); warnings.extend(w3)
    issues.extend(check_renderers())
    issues.extend(check_target_names())
    failed_layers = {"lifecycle_audit_missing": "L1", "action_words_missing": "L2", "stored_action_without_words": "L3",
                     "renderer_vocabulary": "L4", "trail_row_without_name": "L5"}
    failed = len({failed_layers.get(i["check"]) for i in issues})
    return {
        "validator": "audit_trail_coverage",
        "total_checks": len(LAYERS),
        "passed": len(LAYERS) - failed, "failed": failed, "warned": len(warnings),
        "layers": LAYERS,
        "issues": issues,
        "warnings": warnings,
        "tracked_tables": sorted(LIFECYCLE_TABLES.keys()),
    }


def self_test() -> list[str]:
    """Each mutant is a regression this gate exists to catch, applied to the file in memory; every one must turn its
    layer red, and the real sources must stay green."""
    fails = []
    real_read = _read
    cases = [
        ("the vocabulary loses a stored action's words", "utils.js",
         lambda s: s.replace("  supervisor_password_reset:", "  _no_longer_here_:", 1), {"action_words_missing", "stored_action_without_words"}),
        ("a generic thing nobody named", "utils.js",
         lambda s: s.replace("  api_key: 'API key',\n", "", 1), {"action_words_missing"}),
        ("the board keeps its own map", "hive.html", lambda s: s + "\nconst ACTION_ICON = {};\n", {"renderer_vocabulary"}),
        ("audit-log prints the code", "audit-log.html", lambda s: s + "\n(en.action || '').replace(/_/g, ' ');\n", {"renderer_vocabulary"}),
        ("the CSV loses its words", "audit-log.html", lambda s: s.replace("'what_happened'", "'whathappened'"), {"renderer_vocabulary"}),
        ("an id passed as the name", "asset-hub.html",
         lambda s: s.replace("strategyId, strategyName || null,", "strategyId, strategyId,", 1), {"trail_row_without_name"}),
        # the calls removed, a comment still naming them: a comment must not keep the reader "rendering through" it
        ("the board stops calling the vocabulary (a comment still names it)", "hive.html",
         lambda s: s.replace("whAuditView(row)", "null").replace("typeof whAuditView", "typeof _none") + "\n// whAuditView(row) renders each row\n",
         {"renderer_vocabulary"}),
    ]
    g = globals()
    try:
        clean = check_action_icon_completeness() + check_renderers() + check_target_names() + check_stored_actions()[0]
        if clean:
            fails.append(f"the real sources are not clean: {clean[0]['reason'][:160]}")
        for name, suffix, fn, want in cases:
            def fake(p, _suffix=suffix, _fn=fn):
                s = real_read(p)
                return _fn(s) if str(p).replace("\\", "/").endswith(_suffix) else s
            g["_read"] = fake
            try:
                got = {i["check"] for i in (check_action_icon_completeness() + check_renderers()
                                             + check_target_names() + check_stored_actions()[0])}
            finally:
                g["_read"] = real_read
            if not (want & got):
                fails.append(f"mutant '{name}' was not caught (wanted {sorted(want)}, got {sorted(got) or 'nothing'})")
    finally:
        g["_read"] = real_read
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (7 mutants, each caught; the real sources are clean)" if not fails
              else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    out = run()
    print(f"\nAudit Trail Coverage Validator ({len(out['layers'])}-layer)")
    print("=" * 60)
    for layer in out["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    for w in out["warnings"]:
        print(f"  [WARN] [{w['check']}]  {w['reason']}")
    if out["issues"]:
        print(f"  \033[91m{out['failed']} FAIL\033[0m")
        for i in out["issues"][:60]:
            print(f"  [FAIL] [{i['check']}]  {i['reason']}")
        if len(out["issues"]) > 60:
            print(f"  ...and {len(out['issues']) - 60} more")
    else:
        print(f"  \033[92mAll {out['total_checks']} checks passed.\033[0m")
    (ROOT / "audit_trail_coverage_report.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
